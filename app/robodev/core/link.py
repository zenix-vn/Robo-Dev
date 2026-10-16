"""Giao tiếp với mạch: liệt kê cổng COM, nạp firmware bằng esptool, phiên lệnh RD_* qua cổng log.

Firmware Robo Dev trả lời các lệnh tiền tố RD_. Lệnh RD_INFO báo danh sách khả năng (`caps`) để chương trình
biết bản firmware trên mạch hỗ trợ những gì (ví dụ "hw" = đổi chân lúc chạy, "commands" = lệnh tùy chỉnh).
"""
import hashlib
import json
import os
import re
import sys
import tempfile
import time

import serial
import serial.tools.list_ports

BAUD = 460800
MONITOR_BAUD = 115200
ESPRESSIF_VID = 0x303A
USB_UART_VIDS = {0x1A86, 0x10C4, 0x0403}  # CH343/CH340, CP210x, FTDI
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

OFFSET_PARTITION_TABLE = 0x8000
OFFSET_OTADATA = 0xD000
OFFSET_APP = 0x20000
OFFSET_ASSETS = 0x800000
PARTITION_TABLE_SIZE = 0xC00

DEMO_PORT = "DEMO"

ACTIVATION_STEPS = [
    ("cmd", "Mạch nhận thông tin Wi-Fi"),
    ("wifi", "Kết nối Wi-Fi"),
    ("server", "Kết nối máy chủ xiaozhi.me"),
    ("code", "Nhận mã kích hoạt"),
    ("done", "Kích hoạt hoàn tất"),
]


class PortInfo:
    def __init__(self, device, description, kind):
        self.device = device
        self.description = description
        self.kind = kind     # "native" (USB của ESP32-S3) | "uart" (chip USB-COM) | "other" | "demo"

    @property
    def label(self):
        if self.kind == "demo":
            return "DEMO (mô phỏng)"
        hint = {"native": "USB native", "uart": "cổng COM"}.get(self.kind, "")
        return f"{self.device} · {hint}" if hint else f"{self.device} · {self.description}"


def list_ports(include_demo=True):
    """Các cổng, cổng giống ESP32 lên đầu, cuối cùng là mạch mô phỏng."""
    out = []
    for p in serial.tools.list_ports.comports():
        kind = "native" if p.vid == ESPRESSIF_VID else "uart" if p.vid in USB_UART_VIDS else "other"
        out.append(PortInfo(p.device, p.description or p.device, kind))
    out.sort(key=lambda x: (x.kind == "other", x.device))
    if include_demo:
        out.append(PortInfo(DEMO_PORT, "Mạch mô phỏng", "demo"))
    return out


def find_native_port(exclude=None):
    for p in serial.tools.list_ports.comports():
        if p.vid == ESPRESSIF_VID and p.device != exclude:
            return p.device
    return None


def port_kind(port):
    for p in serial.tools.list_ports.comports():
        if p.device == port:
            return "native" if p.vid == ESPRESSIF_VID else "uart" if p.vid in USB_UART_VIDS else "other"
    return "other"


# ----------------------------------------------------------------------------------------
# esptool
# ----------------------------------------------------------------------------------------
class _Capture:
    """Hứng chữ esptool in ra, tách phần trăm tiến độ."""

    def __init__(self, on_text, on_progress):
        self.on_text = on_text
        self.on_progress = on_progress
        self.buf = ""
        self.encoding = "utf-8"
        self.lines = []

    def write(self, s):
        if not s:
            return 0
        self.buf += s
        parts = re.split(r"[\r\n]", self.buf)
        self.buf = parts.pop()
        for line in parts:
            line = ANSI.sub("", line).strip()
            if not line:
                continue
            m = re.search(r"(\d+(?:\.\d+)?)\s*%", line)
            if m and ("Writing" in line or "Erasing" in line or "Reading" in line):
                self.on_progress(float(m.group(1)))
                continue
            self.lines.append(line)
            self.on_text(line)
        return len(s)

    def flush(self):
        pass

    def isatty(self):
        return False

    def fileno(self):
        raise OSError("no fileno")


def run_esptool(port, args, on_text, on_progress):
    """Chạy esptool. Trả về (thành công, lý do, các dòng in ra)."""
    import esptool  # nạp chậm, chỉ cần khi dùng

    capture = _Capture(on_text, on_progress)
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = capture
    try:
        base = ["--chip", "esp32s3", "--port", port, "--baud", str(BAUD),
                "--before", "default-reset", "--after", "hard-reset"]
        esptool.main(base + args)
        return True, "", capture.lines
    except SystemExit as e:
        if e.code in (0, None):
            return True, "", capture.lines
        return False, f"esptool dừng với mã {e.code}: " + " | ".join(capture.lines[-3:]), capture.lines
    except Exception as e:  # noqa: BLE001 - hiển thị mọi lỗi cho người dùng
        return False, str(e), capture.lines
    finally:
        sys.stdout, sys.stderr = old_out, old_err


def check_chip(port, on_text, on_progress):
    """Đọc chip và dung lượng flash. Trả về (ok, thông báo)."""
    ok, reason, lines = run_esptool(port, ["flash-id"], on_text, on_progress)
    text = "\n".join(lines)
    if not ok:
        if "not ESP32-S3" in text or "Wrong --chip" in text:
            return False, "Đây không phải chip ESP32-S3. Robo Dev v1 chỉ hỗ trợ ESP32-S3."
        return False, "Không kết nối được với chip: " + reason
    m = re.search(r"Detected flash size:\s*(\d+)\s*MB", text)
    size = int(m.group(1)) if m else 0
    if size != 16:
        return False, f"Flash của mạch là {size or 'không rõ'} MB. Robo Dev v1 chỉ hỗ trợ 16 MB."
    return True, "ESP32-S3 · flash 16 MB"


def _md5(path, size=None):
    with open(path, "rb") as f:
        data = f.read()
    if size is not None:
        data = data[:size].ljust(size, b"\xff")
    return hashlib.md5(data).hexdigest()


def partition_table_matches(port, package, on_text, on_progress):
    table = package.path("partition_table")
    if not table or not os.path.isfile(table):
        return False
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
    tmp.close()
    try:
        ok, _, _ = run_esptool(port, ["read-flash", hex(OFFSET_PARTITION_TABLE), hex(PARTITION_TABLE_SIZE), tmp.name],
                               on_text, on_progress)
        return ok and _md5(tmp.name, PARTITION_TABLE_SIZE) == _md5(table, PARTITION_TABLE_SIZE)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


_WRITE = ["write-flash", "--flash-mode", "dio", "--flash-freq", "80m", "--flash-size", "16MB"]


def flash_full(port, package, on_text, on_progress):
    return run_esptool(port, _WRITE + ["0x0", package.path("full")], on_text, on_progress)[:2]


def flash_fast(port, package, include_assets, on_text, on_progress):
    """Chỉ ghi ứng dụng + otadata (+ assets), giữ nguyên vùng NVS chứa Wi-Fi và cấu hình."""
    args = _WRITE + [hex(OFFSET_APP), package.path("app"), hex(OFFSET_OTADATA), package.path("otadata")]
    if include_assets and package.has("assets"):
        args += [hex(OFFSET_ASSETS), package.path("assets")]
    return run_esptool(port, args, on_text, on_progress)[:2]


# ----------------------------------------------------------------------------------------
# Phiên lệnh qua cổng log
# ----------------------------------------------------------------------------------------
class Session:
    """Mở cổng log, khởi động lại mạch, đọc từng dòng và gửi lệnh."""

    def __init__(self, port, on_line=None, prefer_native=True):
        self.on_line = on_line or (lambda line: None)
        self.flash_port = port
        self.port = port
        if prefer_native and port_kind(port) != "native":
            native = find_native_port(port)
            if native:
                self.on_line(f"[Robo Dev] Đọc log qua cổng USB native {native} (cổng {port} dùng để nạp).")
                self.port = native
        self.ser = serial.Serial(self.port, MONITOR_BAUD, timeout=0.2)
        self.buf = b""

    def close(self):
        try:
            self.ser.close()
        except Exception:  # noqa: BLE001
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def reset(self):
        self.ser.dtr = False
        self.ser.rts = True
        time.sleep(0.1)
        self.ser.rts = False

    def send(self, line):
        self.ser.write((line + "\n").encode("utf-8"))

    @staticmethod
    def cmd(name):
        return f"RD_{name}"

    def read_lines(self):
        chunk = self.ser.read(8192)
        if not chunk:
            return []
        self.buf += chunk
        *lines, self.buf = re.split(rb"\r\n|\n|\r", self.buf)
        out = []
        for raw in lines:
            line = ANSI.sub("", raw.decode("utf-8", "replace")).strip()
            if line:
                out.append(line)
                self.on_line(line)
        return out

    def wait_for(self, needles, timeout, resend=None, resend_every=1.5, stop=None, start_after=0.0):
        """Đợi dòng chứa một trong `needles`. `resend`: lệnh (hoặc danh sách lệnh luân phiên) gửi lại định kỳ."""
        if isinstance(needles, str):
            needles = (needles,)
        if isinstance(resend, str):
            resend = [resend]
        t0 = time.time()
        last = 0.0
        turn = 0
        while time.time() - t0 < timeout:
            if stop is not None and stop.is_set():
                return None
            for line in self.read_lines():
                if any(n in line for n in needles):
                    return line
            now = time.time()
            if resend and now - t0 >= start_after and now - last >= resend_every:
                last = now
                self.send(resend[turn % len(resend)])
                turn += 1
        return None

    def ping(self, timeout=25, stop=None):
        """Đợi mạch khởi động xong và trả lời PONG. Trả về chuỗi phiên bản hoặc None."""
        needles, probes = ("RD_PONG",), ["RD_PING"]
        first = timeout if self.port == self.flash_port else timeout * 0.6
        line = self.wait_for(needles, first, resend=probes, resend_every=1.0, start_after=2.0, stop=stop)
        if not line and self.port != self.flash_port and not (stop and stop.is_set()):
            # Firmware ghi log qua cổng COM (biến thể uart): thử lại trên cổng gốc
            self.on_line(f"[Robo Dev] Cổng {self.port} không trả lời, thử cổng {self.flash_port}.")
            self.ser.close()
            self.port = self.flash_port
            self.ser = serial.Serial(self.port, MONITOR_BAUD, timeout=0.2)
            self.buf = b""
            self.reset()
            line = self.wait_for(needles, timeout - first, resend=probes, resend_every=1.0, start_after=2.0, stop=stop)
        if not line:
            return None
        return line.split("RD_PONG", 1)[1].strip()

    def _json_reply(self, command, marker, timeout=8):
        line = self.wait_for(marker, timeout, resend=self.cmd(command), resend_every=2.0)
        if not line:
            return None
        try:
            return json.loads(line.split(marker, 1)[1].strip())
        except ValueError:
            return None

    def info(self, timeout=8):
        return self._json_reply("INFO", self.cmd("INFO") + " ", timeout)

    def get_cfg(self, timeout=8):
        return self._json_reply("CFG_GET", self.cmd("CFG_JSON") + " ", timeout)

    def get_hw(self, timeout=8):
        return self._json_reply("HW_GET", self.cmd("HW_JSON") + " ", timeout)

    def _store(self, kind, payload, timeout=10):
        """Gửi CFG hoặc HW. Trả về (ok, thông báo)."""
        ok_tag, err_tag = self.cmd(kind + "_OK"), self.cmd(kind + "_ERR")
        self.send(self.cmd(kind) + " " + payload)
        t0 = time.time()
        while time.time() - t0 < timeout:
            for line in self.read_lines():
                if ok_tag in line:
                    return True, "Mạch đã lưu và đang khởi động lại"
                if err_tag in line:
                    return False, line.split(err_tag, 1)[1].strip() or "Mạch từ chối cấu hình"
                if self.cmd("ERR") in line:
                    return False, line.split(self.cmd("ERR"), 1)[1].strip()
        return False, "Mạch không trả lời lệnh cấu hình."

    def send_cfg(self, payload, timeout=10):
        return self._store("CFG", payload, timeout)

    def send_hw(self, payload, timeout=10):
        return self._store("HW", payload, timeout)

    def clear(self, kind, timeout=8):
        self.send(self.cmd(kind + "_CLEAR"))
        return bool(self.wait_for(self.cmd(kind + "_OK"), timeout))

    def send_wifi(self, ssid, password, timeout=10):
        self.send(self.cmd("WIFI") + " " + json.dumps({"s": ssid, "p": password}, ensure_ascii=False))
        line = self.wait_for((self.cmd("WIFI_OK"), self.cmd("WIFI_ERR")), timeout)
        return bool(line) and "WIFI_OK" in line

    def request(self, command, ok_marker, timeout=8):
        """Gửi một lệnh và đợi dòng trả lời chứa `ok_marker` (hoặc _ERR). Trả về dòng hoặc None."""
        self.send(command)
        return self.wait_for((ok_marker, self.cmd("TEST_ERR"), self.cmd("ERR")), timeout)


# ----------------------------------------------------------------------------------------
# Theo dõi Wi-Fi + kích hoạt từ log
# ----------------------------------------------------------------------------------------
class Tracker:
    """Đọc từng dòng log của mạch, cập nhật các bước Wi-Fi và kích hoạt."""

    def __init__(self, emit):
        self.emit = emit
        self.code = None
        self.wait_code = False
        self.finished = False
        self.failed = False
        self.states = {k: "wait" for k, _ in ACTIVATION_STEPS}

    def step(self, key, state, text=""):
        self.states[key] = state
        self.emit("step", key, state, text)

    def feed(self, line):
        if "WIFI_ERR" in line:
            self.step("cmd", "fail", "Tên Wi-Fi không hợp lệ")
            self.failed = True
            return
        m = re.search(r"Connected to WiFi: (.+)$", line)
        if m:
            if self.states["cmd"] != "ok":
                self.step("cmd", "ok")
            self.step("wifi", "ok", "Đã kết nối " + m.group(1).strip())
            self.step("server", "run", "Đang liên hệ máy chủ...")
            return
        m = re.search(r"Got IP: (\S+)", line)
        if m:
            self.step("wifi", "ok", "Địa chỉ IP " + m.group(1))
            if self.states["server"] == "wait":
                self.step("server", "run", "Đang liên hệ máy chủ...")
            return
        if "WiFi connection timeout" in line:
            self.step("wifi", "fail", "Không kết nối được. Kiểm tra tên, mật khẩu Wi-Fi hoặc sóng yếu.")
            self.failed = True
            return
        if "Established new connection to" in line or "Ota: Current version" in line:
            if self.states["wifi"] != "ok":
                self.step("wifi", "ok", "Đã có mạng")
            self.step("server", "ok", "Đã liên hệ máy chủ")
            return
        if "Alert [link]" in line:
            self.step("server", "ok", "Đã liên hệ máy chủ")
            self.step("code", "run", "Đang chờ mã...")
            self.wait_code = True
            return
        if self.wait_code:
            m = re.fullmatch(r"\s*(\d{4,8})\s*", line)
            if m:
                self.code = m.group(1)
                self.wait_code = False
                self.step("code", "ok", "Mã " + self.code)
                self.step("done", "run", "Nhập mã vào xiaozhi.me → Thêm thiết bị")
                self.emit("code", self.code)
                return
        if "Activation done" in line:
            if self.states["code"] != "ok":
                self.step("code", "skip", "Không có mã: thiết bị đã liên kết sẵn với một tài khoản")
            self.step("done", "ok", "Robot đã kết nối xiaozhi.me")
            self.finished = True


NO_CODE_MESSAGE = (
    "Robot đã kết nối xiaozhi.me, nhưng máy chủ không cấp mã mới vì thiết bị đã được liên kết với một tài khoản "
    "từ trước. Muốn lấy mã mới: vào xiaozhi.me, hủy liên kết thiết bị khỏi agent rồi xóa thiết bị, sau đó cài "
    "Wi-Fi lại.")


def track_activation(session, emit, stop, timeout=180, wifi_started=True):
    """Đọc log tới khi kích hoạt xong, báo lỗi hoặc hết giờ. Trả về (ok, thông báo, mã)."""
    tracker = Tracker(emit)
    if wifi_started:
        tracker.step("cmd", "ok", "Đã lưu, mạch đang khởi động lại")
        tracker.step("wifi", "run", "Đang kết nối...")
    t0 = time.time()
    while time.time() - t0 < timeout:
        if stop.is_set():
            return False, "Đã dừng.", tracker.code
        for line in session.read_lines():
            tracker.feed(line)
            if tracker.finished:
                ok_text = "Robot đã kết nối xiaozhi.me thành công!"
                return True, ok_text if tracker.code else NO_CODE_MESSAGE, tracker.code
            if tracker.failed:
                return False, "Chưa hoàn tất. Xem bước báo lỗi.", tracker.code
    for key, state in tracker.states.items():
        if state == "run":
            tracker.step(key, "fail", "Hết thời gian chờ")
    return False, "Hết thời gian chờ. Xem các bước để biết dừng ở đâu.", tracker.code
