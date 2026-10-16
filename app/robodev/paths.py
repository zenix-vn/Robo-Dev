"""Đường dẫn tới dữ liệu đi kèm chương trình, chạy được cả từ mã nguồn lẫn bản đóng gói PyInstaller."""
import os
import sys

FROZEN = getattr(sys, "frozen", False)

if FROZEN:
    PACKAGE_DIR = os.path.join(sys._MEIPASS, "robodev")  # noqa: SLF001
    APP_DIR = os.path.dirname(sys.executable)
else:
    PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_DIR = os.path.dirname(PACKAGE_DIR)

DATA_DIR = os.path.join(PACKAGE_DIR, "data")
PHOTO_DIR = os.path.join(DATA_DIR, "photos")
FIRMWARE_DIR = os.path.join(APP_DIR, "firmware")


def data_file(name):
    return os.path.join(DATA_DIR, name)


def photo(name):
    return os.path.join(PHOTO_DIR, name) if name else None


def user_dir():
    """Thư mục lưu hồ sơ của người dùng (Tài liệu/Robo Dev)."""
    base = os.path.join(os.path.expanduser("~"), "Documents", "Robo Dev")
    os.makedirs(base, exist_ok=True)
    return base
