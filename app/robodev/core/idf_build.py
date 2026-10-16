"""Chế độ nâng cao: build lại firmware ngay trên máy (dùng khi đổi cụm gọi hoặc sửa code).

Gọi firmware/build.ps1 (áp patch vào thư viện xiaozhi-esp32, gắn board robo-dev-s3, build).
Chưa gắn vào giao diện; xem document.md mục 8 (wake word) và mục 11 (lộ trình).
"""
import json
import os
import subprocess

from robodev import paths

BOARD = "robo-dev-s3"


def find_firmware():
    """Thư mục firmware/ của Robo Dev (có build.ps1 và robo-dev-s3/), hoặc None."""
    candidate = os.path.join(os.path.dirname(paths.APP_DIR), "firmware")
    for path in (os.environ.get("ROBODEV_FIRMWARE", ""), candidate):
        if path and os.path.isfile(os.path.join(path, "build.ps1")) and os.path.isdir(os.path.join(path, BOARD)):
            return path
    return None


def build_dir(firmware):
    return os.path.join(firmware, "xiaozhi-esp32", "build")


def set_wake_word(firmware, phrase, display, threshold):
    """Ghi cụm gọi vào sdkconfig_append trong robo-dev-s3/config.json (cần build lại assets)."""
    path = os.path.join(firmware, BOARD, "config.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    lines = data["builds"][0]["sdkconfig_append"]
    wanted = {
        "CONFIG_CUSTOM_WAKE_WORD=": f'CONFIG_CUSTOM_WAKE_WORD="{phrase}"',
        "CONFIG_CUSTOM_WAKE_WORD_DISPLAY=": f'CONFIG_CUSTOM_WAKE_WORD_DISPLAY="{display}"',
        "CONFIG_CUSTOM_WAKE_WORD_THRESHOLD=": f"CONFIG_CUSTOM_WAKE_WORD_THRESHOLD={int(threshold)}",
    }
    for prefix, value in wanted.items():
        for i, line in enumerate(lines):
            if line.startswith(prefix):
                lines[i] = value
                break
        else:
            lines.append(value)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        f.write("\n")


def run_build(firmware, emit, stop):
    """Chạy firmware/build.ps1. Trả về mã thoát (0 = thành công)."""
    # ESP-IDF từ chối chạy khi thấy biến môi trường của Git Bash / MSYS
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith(("MSYSTEM", "MINGW", "MSYS", "ORIGINAL_PATH"))}
    proc = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                             os.path.join(firmware, "build.ps1")],
                            cwd=firmware, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                            env=env)
    try:
        for line in proc.stdout:
            if line.strip():
                emit("log", line.rstrip())
            if stop.is_set():
                proc.terminate()
                return -1
    finally:
        proc.wait()
    return proc.returncode
