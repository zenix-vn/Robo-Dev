"""Các việc chạy nền (không phụ thuộc giao diện).

Mỗi việc nhận `emit(kind, *args)` để báo tiến độ và `stop` (threading.Event) để dừng giữa chừng.
Sự kiện: log(text), progress(percent), step(key, state, text), code(code), check(result),
firmware(version), caps(list), test(module, step, ok, text), done(ok, message).
"""
import queue
import re
import time

from robodev.core import link, pins, profile, simulator

FLASH_STEPS = [
    ("board", "Kiểm tra mạch"),
    ("flash", "Nạp firmware"),
    ("config", "Gửi cấu hình"),
]

MAX_LINE = 3900


def _step(emit, key, state, text=""):
    emit("step", key, state, text)


def open_session(port, emit):
    on_line = lambda line: emit("log", line)  # noqa: E731
    if port == link.DEMO_PORT:
        return simulator.DemoSession(port, on_line)
    return link.Session(port, on_line)


def _chip(port, emit, stop):
    text = lambda t: emit("log", t)  # noqa: E731
    progress = lambda p: emit("progress", p)  # noqa: E731
    if port == link.DEMO_PORT:
        return simulator.check_chip(text, progress)
    return link.check_chip(port, text, progress)


def _boot(session, emit, stop, label="Đợi mạch khởi động"):
    emit("log", f"[Robo Dev] {label}...")
    version = session.ping(timeout=30, stop=stop)
    if version:
        emit("firmware", version)
    return version


# ----------------------------------------------------------------------------------------
# Kiểm tra mạch
# ----------------------------------------------------------------------------------------
def job_check(port, emit, stop):
    result = {"chip": None, "firmware": None, "info": None}
    ok, message = _chip(port, emit, stop)
    result["chip"] = (ok, message)
    if not ok:
        emit("check", result)
        emit("done", False, message)
        return
    with open_session(port, emit) as session:
        session.reset()
        version = _boot(session, emit, stop)
        if not version:
            result["firmware"] = (False, "Chưa có firmware Robo Dev (mạch trống hoặc firmware khác)")
            emit("check", result)
            emit("done", True, "Mạch đúng loại nhưng chưa có firmware Robo Dev. Hãy nạp ở bước Nạp & kết nối.")
            return
        result["firmware"] = (True, version)
        result["info"] = session.info()
        if result["info"] is not None:
            emit("caps", result["info"].get("caps", []))
    emit("check", result)
    emit("done", True, "Đã kiểm tra xong mạch.")


# ----------------------------------------------------------------------------------------
# Áp dụng hồ sơ
# ----------------------------------------------------------------------------------------
def _apply(session, project, emit, stop):
    """Gửi hw (nếu firmware hỗ trợ) và cfg, rồi đọc lại để xác nhận. Trả về True nếu mạch dùng đúng hồ sơ."""
    _step(emit, "config", "run", "Đang gửi...")
    info = session.info() or {}
    caps = set(info.get("caps", []))
    emit("caps", sorted(caps))

    if "hw" in caps:
        errors = [i for i in pins.validate(project["hw"]) if i.level == "error"]
        if errors:
            _step(emit, "config", "fail", errors[0].text)
            return False
        payload = profile.compact(profile.hw_payload(project))
        current = session.get_hw()
        if current != profile.hw_payload(project):
            ok, message = session.send_hw(payload)
            if not ok:
                _step(emit, "config", "fail", "Cấu hình chân: " + message)
                return False
            emit("log", "[Robo Dev] Đã gửi cấu hình chân. " + message)
            if not _boot(session, emit, stop, "Mạch khởi động lại"):
                _step(emit, "config", "fail", "Mạch không khởi động lại sau khi đổi chân")
                return False

    cfg = profile.cfg_payload(project, caps)
    command = profile.compact(cfg)
    if cfg == {"version": 1}:
        if info.get("cfg_saved"):
            emit("log", "[Robo Dev] Hồ sơ là mặc định: xóa cấu hình cũ trong mạch.")
            session.clear("CFG")
            if not _boot(session, emit, stop, "Mạch khởi động lại"):
                _step(emit, "config", "fail", "Mạch không khởi động lại")
                return False
    else:
        if len(command.encode("utf-8")) > MAX_LINE:
            _step(emit, "config", "fail", f"Cấu hình quá dài ({len(command.encode('utf-8'))} byte, tối đa {MAX_LINE}).")
            return False
        ok, message = session.send_cfg(command)
        if not ok:
            _step(emit, "config", "fail", message)
            return False
        emit("log", "[Robo Dev] " + message)
        if not _boot(session, emit, stop, "Mạch khởi động lại"):
            _step(emit, "config", "fail", "Mạch không khởi động lại")
            return False

    actual = session.get_cfg()
    if actual is None:
        _step(emit, "config", "fail", "Không đọc lại được cấu hình từ mạch")
        return False
    diffs = profile.differences(profile.expected_cfg(project, caps), actual)
    if diffs:
        _step(emit, "config", "fail", "Mạch báo khác hồ sơ: " + "; ".join(diffs[:3]))
        return False
    note = "" if "hw" in caps else " (bản firmware này giữ chân cố định)"
    _step(emit, "config", "ok", "Mạch đang dùng đúng hồ sơ" + note)
    return True


def job_apply(port, project, emit, stop):
    with open_session(port, emit) as session:
        session.reset()
        if not _boot(session, emit, stop):
            emit("done", False, "Mạch không trả lời. Kiểm tra cáp, cổng COM và firmware.")
            return
        if _apply(session, project, emit, stop):
            emit("done", True, "Đã áp dụng hồ sơ. Mạch đã khởi động lại với cấu hình mới.")
        else:
            emit("done", False, "Chưa áp dụng được hồ sơ. Xem bước báo lỗi.")


# ----------------------------------------------------------------------------------------
# Nạp firmware
# ----------------------------------------------------------------------------------------
def job_flash(port, package, mode, include_assets, project, ssid, password, emit, stop):
    """Kiểm tra mạch, nạp, gửi hồ sơ, cài Wi-Fi và theo dõi kích hoạt. mode: "fast" | "full"."""
    log = lambda t: emit("log", t)  # noqa: E731
    progress = lambda p: emit("progress", p)  # noqa: E731
    demo = port == link.DEMO_PORT

    if not demo:
        missing = package.missing(["full"] if mode == "full" else ["app", "otadata", "partition_table"])
        if missing:
            emit("done", False, "Gói firmware thiếu file: " + ", ".join(missing))
            return

    _step(emit, "board", "run", "Đang đọc chip...")
    ok, message = _chip(port, emit, stop)
    if not ok:
        _step(emit, "board", "fail", message)
        emit("done", False, message)
        return
    _step(emit, "board", "ok", message)
    if stop.is_set():
        emit("done", False, "Đã dừng.")
        return

    _step(emit, "flash", "run", "Đang nạp, đừng rút cáp...")
    if mode == "fast" and not demo:
        log("[Robo Dev] Kiểm tra bảng phân vùng để nạp nhanh...")
        if not link.partition_table_matches(port, package, log, progress):
            log("[Robo Dev] Bảng phân vùng trong mạch khác gói firmware: chuyển sang nạp đầy đủ.")
            if not package.has("full"):
                _step(emit, "flash", "fail", "Cần nạp đầy đủ nhưng gói không có file nạp đầy đủ")
                emit("done", False, "Gói firmware thiếu file nạp đầy đủ.")
                return
            mode = "full"
    if demo:
        ok, reason = simulator.flash(log, progress, stop, seconds=6.0 if mode == "full" else 3.0, wipe=mode == "full")
    elif mode == "fast":
        ok, reason = link.flash_fast(port, package, include_assets, log, progress)
    else:
        ok, reason = link.flash_full(port, package, log, progress)
    if not ok:
        _step(emit, "flash", "fail", reason)
        emit("done", False, "Nạp thất bại. Giữ nút BOOT, nhấn RST, thả BOOT rồi thử lại.\n" + reason)
        return
    _step(emit, "flash", "ok", "Nạp nhanh, giữ Wi-Fi" if mode == "fast" else "Nạp đầy đủ (Wi-Fi cũ đã xóa)")

    with open_session(port, emit) as session:
        session.reset()
        if not _boot(session, emit, stop):
            _step(emit, "config", "fail", "Mạch không trả lời sau khi nạp")
            emit("done", False, "Mạch không phản hồi sau khi nạp. Kiểm tra cáp rồi thử lại.")
            return
        if not _apply(session, project, emit, stop):
            emit("done", False, "Đã nạp nhưng chưa áp dụng được hồ sơ. Xem bước báo lỗi.")
            return
        _wifi_and_activation(session, ssid, password, emit, stop, wifi_was_wiped=mode == "full")


def _wifi_and_activation(session, ssid, password, emit, stop, wifi_was_wiped):
    if ssid:
        _step(emit, "cmd", "run", "Đang gửi...")
        if not session.send_wifi(ssid, password):
            _step(emit, "cmd", "fail", "Mạch không nhận Wi-Fi")
            emit("done", False, "Mạch không nhận thông tin Wi-Fi.")
            return
        ok, message, _ = link.track_activation(session, emit, stop, wifi_started=True)
        emit("done", ok, message)
        return
    if wifi_was_wiped:
        for key, _ in link.ACTIVATION_STEPS:
            _step(emit, key, "skip", "Chưa nhập Wi-Fi")
        emit("done", True, "Đã nạp xong. Wi-Fi cũ đã bị xóa: nhập Wi-Fi rồi bấm \"Chỉ cài Wi-Fi\".")
        return
    _step(emit, "cmd", "ok", "Dùng Wi-Fi đã lưu trong mạch")
    _step(emit, "wifi", "run", "Đang kết nối...")
    session.reset()
    ok, message, _ = link.track_activation(session, emit, stop, wifi_started=False)
    emit("done", ok, message)


def job_wifi(port, ssid, password, emit, stop):
    with open_session(port, emit) as session:
        session.reset()
        if not _boot(session, emit, stop):
            _step(emit, "cmd", "fail", "Mạch không trả lời")
            emit("done", False, "Mạch không phản hồi. Hãy nạp firmware trước.")
            return
        _wifi_and_activation(session, ssid, password, emit, stop, wifi_was_wiped=False)


# ----------------------------------------------------------------------------------------
# Xem log + kiểm tra module
# ----------------------------------------------------------------------------------------
TEST_TIMEOUT = {"button": 20.0, "mic": 8.0}

def job_monitor(port, commands, emit, stop):
    """Mở cổng log liên tục. `commands` là queue.Queue gồm chuỗi lệnh thô hoặc tuple:
    ("reset",), ("test", module, step), ("run", tên lệnh)."""
    try:
        session = open_session(port, emit)
    except Exception as e:  # noqa: BLE001
        emit("done", False, f"Không mở được {port}: {e}")
        return
    pending = {}     # module -> (step, các chuỗi cần thấy, hạn chót)
    try:
        emit("log", f"[Robo Dev] Đang xem log trên {session.port}")
        if port == link.DEMO_PORT:
            session.reset()
        session.send("RD_PING")
        while not stop.is_set():
            try:
                while True:
                    item = commands.get_nowait()
                    if isinstance(item, str):
                        session.send(item)
                    elif item[0] == "reset":
                        session.reset()
                    elif item[0] == "run":
                        session.send(f"RD_RUN {item[1]}")
                    elif item[0] == "test":
                        module, step = item[1], item[2]
                        deadline = time.time() + TEST_TIMEOUT.get(module, 6.0)
                        session.send(f"RD_TEST {module} {step}")
                        pending[module] = (step, (f"RD_TEST_OK {module}", f"RD_TEST_ERR {module}"), deadline)
            except queue.Empty:
                pass
            for line in session.read_lines():
                m = re.search(r"RD_PONG\s*(.*)$", line)
                if m:
                    emit("firmware", m.group(1).strip())
                for module, (step, needles, _) in list(pending.items()):
                    hit = next((n for n in needles if n in line), None)
                    if not hit:
                        continue
                    del pending[module]
                    ok = hit.startswith("RD_TEST_OK")
                    text = line.split(hit, 1)[1].strip()
                    emit("test", module, step, ok, text)
            now = time.time()
            for module, (step, _, deadline) in list(pending.items()):
                if now > deadline:
                    del pending[module]
                    emit("test", module, step, False, "Mạch không trả lời bài kiểm tra")
        emit("done", True, "Đã dừng xem log.")
    finally:
        session.close()


def job_run_command(port, name, emit, stop):
    """Chạy thử một lệnh tùy chỉnh đã lưu trên mạch (RD_RUN), không qua AI."""
    with open_session(port, emit) as session:
        session.reset()
        if not _boot(session, emit, stop):
            emit("done", False, "Mạch không trả lời.")
            return
        if "commands" not in (session.info() or {}).get("caps", []):
            emit("done", False, "Bản firmware trên mạch chưa hỗ trợ lệnh tùy chỉnh.")
            return
        line = session.request(f"RD_RUN {name}", "RD_RUN_OK", timeout=profile.MAX_RUN_MS / 1000 + 5)
        if line and "RD_RUN_OK" in line:
            emit("done", True, f"Robot đã chạy xong lệnh {name}.")
        else:
            emit("done", False, (line or "Mạch không trả lời lệnh RD_RUN.").split("_ERR", 1)[-1].strip())
