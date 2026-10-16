"""Mạch mô phỏng: trả lời giống firmware Robo Dev để thử chương trình khi chưa cắm mạch (cổng "DEMO")."""
import json
import random
import threading
import time

from robodev.core import link, profile


class DemoDevice:
    """Trạng thái lưu trong "flash" của mạch mô phỏng, giữ qua các phiên."""

    def __init__(self):
        self.lock = threading.Lock()
        self.flashed = True
        self.version = "1.0.0-demo"
        self.hw = None
        self.cfg = None
        self.wifi = None
        self.linked = False


DEVICE = DemoDevice()
# Mạch mô phỏng đóng vai bản firmware Robo Dev đầy đủ (kể cả các khả năng firmware thật chưa có)
CAPS = ("cfg", "wifi", "test", "hw", "commands")


def check_chip(on_text, on_progress):
    for line in ("esptool v5 (mô phỏng)", "Connecting....", "Chip type: ESP32-S3 (QFN56) (revision v0.2)",
                 "Features: Wi-Fi, BT 5 (LE), Dual Core + LP Core, 240MHz, Embedded PSRAM 8MB",
                 "Detected flash size: 16MB"):
        on_text(line)
        time.sleep(0.12)
    return True, "ESP32-S3 · flash 16 MB"


def flash(on_text, on_progress, stop=None, seconds=4.0, wipe=False):
    on_text("Connecting....")
    on_text("Stub flasher running.")
    steps = 50
    for i in range(steps + 1):
        if stop is not None and stop.is_set():
            return False, "Đã dừng."
        on_progress(100.0 * i / steps)
        time.sleep(seconds / steps)
    on_text("Hash of data verified.")
    on_text("Hard resetting via RTS pin...")
    with DEVICE.lock:
        DEVICE.flashed = True
        if wipe:
            DEVICE.hw = DEVICE.cfg = DEVICE.wifi = None
            DEVICE.linked = False
    return True, ""


class DemoSession(link.Session):
    """Cùng giao diện với link.Session nhưng không mở cổng thật."""

    def __init__(self, port=link.DEMO_PORT, on_line=None, prefer_native=True):  # noqa: D401 - giữ chữ ký
        self.on_line = on_line or (lambda line: None)
        self.flash_port = self.port = link.DEMO_PORT
        self.buf = b""
        self._queue = []          # [(thời điểm, dòng)]
        self._t = time.time()
        self._booted = False
        self.boot = link.BootLog()

    def close(self):
        pass

    # Thời gian và hàng đợi dòng trả lời -------------------------------------------------
    def _later(self, delay, line):
        self._t = max(self._t, time.time()) + delay
        self._queue.append((self._t, line))

    def _reply(self, delay, line):
        """Trả lời lệnh: tính từ bây giờ, không xếp sau chuỗi log khởi động."""
        self._queue.append((time.time() + delay, line))

    def read_lines(self):
        time.sleep(0.05)
        now = time.time()
        due = [line for t, line in self._queue if t <= now]
        self._queue = [(t, line) for t, line in self._queue if t > now]
        for line in due:
            self.boot.feed(line)
            self.on_line(line)
        return due

    # Khởi động ----------------------------------------------------------------------------
    def reset(self):
        self._queue.clear()
        self._t = time.time()
        self._boot()

    def _boot(self):
        ms = random.randint(300, 400)
        boot = ["ESP-ROM:esp32s3-20210327", "rst:0x1 (POWERON),boot:0x8 (SPI_FAST_FLASH_BOOT)",
                f"I ({ms}) app_init: Project name:     xiaozhi",
                f"I ({ms + 2}) app_init: App version:      {DEVICE.version}",
                f"I ({ms + 40}) RoboDev: hw: {'đã lưu' if DEVICE.hw else 'mặc định'}, cfg: {'đã lưu' if DEVICE.cfg else 'mặc định'}",
                f"I ({ms + 120}) RoboDev: Sensor VL6180X found at 0x29",
                f"I ({ms + 180}) Display: ST7789 240x240 ready",
                f"W ({ms + 190}) RoboDev: GPIO3 is a strapping pin (motor IN3)",
                f"I ({ms + 260}) Application: STATE: starting"]
        for line in boot:
            self._later(0.08, line)
        if DEVICE.wifi:
            self._wifi_flow()
        else:
            self._later(0.3, f"I ({ms + 900}) WifiBoard: No saved Wi-Fi, entering setup mode")
        self._booted = True

    def _wifi_flow(self):
        ssid = DEVICE.wifi["s"]
        if DEVICE.wifi.get("p") == "sai":
            self._later(1.2, "I (1500) WifiStation: Connecting to " + ssid)
            self._later(3.0, "W (6500) WifiStation: WiFi connection timeout")
            return
        self._later(1.0, "I (1500) WifiStation: Connecting to " + ssid)
        self._later(1.0, "I (2600) WifiStation: Got IP: 192.168.1.42")
        self._later(0.2, "I (2610) WifiStation: Connected to WiFi: " + ssid)
        self._later(0.8, "I (3400) Ota: Current version: " + DEVICE.version)
        if not DEVICE.linked:
            self._later(0.6, "I (4000) Application: Alert [link]: Kích hoạt thiết bị")
            self._later(0.2, "482916")
            self._later(4.0, "I (8500) Activation done")
            DEVICE.linked = True
        else:
            self._later(0.5, "I (4000) Activation done")
        self._later(0.4, "I (4500) Application: STATE: idle")

    def _restart(self):
        # Mạch thật khởi động lại thì mọi log đang chạy dở bị bỏ; chỉ giữ câu trả lời vừa gửi
        now = time.time()
        self._queue = [(t, line) for t, line in self._queue if t <= now + 0.2]
        self._t = now + 0.2
        self._later(0.2, "I (0) RoboDev: restarting...")
        self._booted = False
        self._t += 0.6
        self._boot()

    # Lệnh -------------------------------------------------------------------------------
    def send(self, line):
        self.on_line("> " + line)
        if not self._booted:
            return
        if not line.startswith("RD_"):
            return          # firmware Robo Dev chỉ hiểu lệnh RD_
        p = "RD"
        name, _, arg = line[len(p) + 1:].partition(" ")
        r = lambda text, d=0.05: self._reply(d, f"{p}_{text}")  # noqa: E731
        if name == "PING":
            r(f"PONG {DEVICE.version}")
        elif name == "INFO":
            r("INFO " + json.dumps({"board": "robo-dev-s3", "version": DEVICE.version, "variant": "usb",
                                    "chip": "esp32s3", "flash_mb": 16, "psram_mb": 8, "sensor": "vl6180x",
                                    "wifi": bool(DEVICE.wifi), "activated": DEVICE.linked,
                                    "hw_saved": bool(DEVICE.hw), "cfg_saved": bool(DEVICE.cfg), "module_errors": [],
                                    "caps": list(CAPS),
                                    "tests": ["speaker", "mic", "sensor", "lcd", "motors", "led", "button"],
                                    "state": "idle" if DEVICE.linked else "wifi_configuring" if not DEVICE.wifi else "activating",
                                    "wifi_saved": bool(DEVICE.wifi)}))
        elif name == "CFG_GET":
            cfg = profile.firmware_defaults()
            if DEVICE.cfg:
                stored = dict(DEVICE.cfg)
                stored.pop("commands", None)
                profile.merge_into(cfg, stored)
            r("CFG_JSON " + json.dumps(cfg, ensure_ascii=False))
        elif name == "HW_GET":
            r("HW_JSON " + json.dumps(DEVICE.hw or profile.hw_payload(profile.new_project()), ensure_ascii=False))
        elif name in ("CFG", "HW"):
            try:
                data = json.loads(arg)
            except ValueError:
                r(f"{name}_ERR JSON không hợp lệ")
                return
            if name == "HW":
                from robodev.core import pins  # tránh vòng import khi nạp module
                errors = [i for i in pins.validate(data) if i.level == "error"]
                if errors:
                    r("HW_ERR " + errors[0].text)
                    return
                DEVICE.hw = data
            else:
                DEVICE.cfg = data
            r(f"{name}_OK")
            self._restart()
        elif name in ("CFG_CLEAR", "HW_CLEAR"):
            if name == "CFG_CLEAR":
                DEVICE.cfg = None
            else:
                DEVICE.hw = None
            r(name.split("_")[0] + "_OK")
            self._restart()
        elif name == "WIFI":
            try:
                DEVICE.wifi = json.loads(arg)
            except ValueError:
                r("WIFI_ERR")
                return
            r("WIFI_OK")
            self._restart()
        elif name == "WIFI_CLEAR":
            DEVICE.wifi = None
            r("WIFI_OK")
            self._restart()
        elif name == "VOL":
            r("VOL_OK " + (arg or "70"))
        elif name == "TEST":
            self._test(arg, r)
        elif name == "RUN":
            r("RUN_OK " + arg, 1.5)
        else:
            r("ERR lệnh không hỗ trợ")

    def _test(self, arg, r):
        module, _, step = arg.partition(" ")
        if module == "mic":
            r(f"TEST_OK mic avg_abs={random.randint(180, 2400)} peak={random.randint(4000, 20000)}", 1.0)
        elif module == "sensor":
            r(f"TEST_OK sensor type=vl6180x mm={random.randint(40, 190)}", 0.2)
        elif module == "button":
            r("TEST_OK button pressed", 2.0)
        elif module in ("speaker", "lcd", "motors", "led"):
            r(f"TEST_OK {module}", 0.6)
        else:
            r(f"TEST_ERR {module} unsupported")
