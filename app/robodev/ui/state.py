"""Trạng thái chung của ứng dụng và bộ chạy việc nền."""
import copy
import os
import queue
import threading

from PySide6.QtCore import QObject, QSettings, Signal

from robodev.core import firmware, jobs, link, profile


class AppState(QObject):
    """Hồ sơ đang mở, cổng đang chọn, thông tin mạch. Các trang lắng nghe tín hiệu để cập nhật."""
    project_changed = Signal()          # thay hồ sơ (mới/mở) hoặc đổi từ trang khác
    dirty_changed = Signal(bool)
    port_changed = Signal(str)
    device_changed = Signal()           # firmware/info thay đổi
    mode_changed = Signal(bool)         # True = chế độ nâng cao
    busy_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self.settings = QSettings("RoboDev", "RoboDev")
        self.project = profile.new_project()
        self.path = None
        self.applied = copy.deepcopy(self.project)   # bản đã gửi xuống mạch lần cuối
        self.saved = copy.deepcopy(self.project)
        self.port = None
        self.version = None      # phiên bản firmware Robo Dev trên mạch (None = chưa biết)
        self.caps = None         # khả năng firmware báo qua RD_INFO (None = chưa biết)
        self.info = None
        self.chip_ok = None
        self.activated = None
        self.advanced = self.settings.value("advanced", False, type=bool)
        self.packages = firmware.discover()
        self.runner = JobRunner(self)

    # Hồ sơ ------------------------------------------------------------------------------
    def touch(self):
        """Gọi sau mỗi lần sửa hồ sơ."""
        self.dirty_changed.emit(self.unapplied)

    @property
    def unapplied(self):
        return self.project != self.applied

    @property
    def unsaved(self):
        return self.project != self.saved

    def changes(self):
        """Số khối khác so với lần áp dụng cuối (để hiện trên thanh Áp dụng)."""
        count = 0
        for key in ("hw", "cfg", "commands"):
            if self.project.get(key) != self.applied.get(key):
                count += 1
        return count

    def mark_applied(self):
        self.applied = copy.deepcopy(self.project)
        self.dirty_changed.emit(False)

    def revert(self):
        self.project = copy.deepcopy(self.applied)
        self.project_changed.emit()
        self.dirty_changed.emit(False)

    def new(self, name="Robo"):
        self.project = profile.new_project(name)
        self.path = None
        self.saved = copy.deepcopy(self.project)
        self.project_changed.emit()
        self.touch()

    def open(self, path):
        self.project = profile.load(path)
        self.path = path
        self.saved = copy.deepcopy(self.project)
        self.settings.setValue("last_project", path)
        self.project_changed.emit()
        self.touch()

    def save(self, path=None):
        path = path or self.path
        profile.save(self.project, path)
        self.path = path
        self.saved = copy.deepcopy(self.project)
        self.settings.setValue("last_project", path)
        self.touch()

    @property
    def title(self):
        if self.path:
            return os.path.basename(self.path).replace(profile.EXTENSION, "")
        return self.project.get("name", "Robo")

    # Thiết bị ---------------------------------------------------------------------------
    def set_port(self, port):
        if port != self.port:
            self.port = port
            self.version = self.caps = self.info = self.chip_ok = self.activated = None
            if port:
                self.settings.setValue("last_port", port)
            self.port_changed.emit(port or "")
            self.device_changed.emit()

    def set_firmware(self, version):
        if version != self.version:
            self.version = version
            self.device_changed.emit()

    def set_caps(self, caps):
        caps = set(caps)
        if caps != self.caps:
            self.caps = caps
            self.device_changed.emit()

    def set_advanced(self, on):
        self.advanced = on
        self.settings.setValue("advanced", on)
        self.mode_changed.emit(on)

    @property
    def is_demo(self):
        return self.port == link.DEMO_PORT

    def supports(self, cap):
        """Firmware trên mạch có khả năng `cap` không (chưa biết thì coi như có)."""
        return self.caps is None or cap in self.caps

    @property
    def firmware_label(self):
        return f"Robo Dev {self.version}" if self.version else "Chưa kiểm tra"


class JobRunner(QObject):
    """Chạy một việc nền tại một thời điểm (riêng phiên xem log chạy song song nhưng bị dừng khi có việc khác)."""
    event = Signal(str, tuple)       # (job id, sự kiện)
    started = Signal(str)
    finished = Signal(str, bool, str)

    def __init__(self, state):
        super().__init__()
        self.state = state
        self.job_id = None
        self.stop_event = None
        self.thread = None
        self.monitor_thread = None
        self.monitor_stop = None
        self.monitor_queue = None

    @property
    def busy(self):
        return self.thread is not None and self.thread.is_alive()

    @property
    def monitoring(self):
        return self.monitor_thread is not None and self.monitor_thread.is_alive()

    def _emit_for(self, job_id):
        def emit(kind, *args):
            # Tín hiệu Qt tự chuyển sự kiện từ luồng nền sang luồng giao diện
            self.event.emit(job_id, (kind, *args))
            if kind == "done":
                self.finished.emit(job_id, bool(args[0]), str(args[1]) if len(args) > 1 else "")
        return emit

    def start(self, job_id, func, *args):
        if self.busy:
            return False
        self.stop_monitor()
        self.job_id = job_id
        self.stop_event = threading.Event()
        emit = self._emit_for(job_id)

        def run():
            try:
                func(*args, emit, self.stop_event)
            except Exception as e:  # noqa: BLE001 - mọi lỗi phải hiện cho người dùng
                emit("log", f"[Robo Dev] Lỗi: {e!r}")
                emit("done", False, f"Có lỗi không mong muốn: {e}")

        self.thread = threading.Thread(target=run, daemon=True, name=job_id)
        self.thread.start()
        self.started.emit(job_id)
        self.state.busy_changed.emit(True)
        return True

    def stop(self):
        if self.stop_event:
            self.stop_event.set()

    # Phiên xem log --------------------------------------------------------------------
    def start_monitor(self, port):
        if self.monitoring or self.busy or not port:
            return False
        self.monitor_queue = queue.Queue()
        self.monitor_stop = threading.Event()
        emit = self._emit_for("monitor")
        self.monitor_thread = threading.Thread(target=jobs.job_monitor,
                                               args=(port, self.monitor_queue, emit, self.monitor_stop),
                                               daemon=True, name="monitor")
        self.monitor_thread.start()
        self.started.emit("monitor")
        return True

    def stop_monitor(self, wait=True):
        if self.monitoring:
            self.monitor_stop.set()
            if wait:
                self.monitor_thread.join(3.0)

    def send(self, item):
        if self.monitoring:
            self.monitor_queue.put(item)
            return True
        return False
