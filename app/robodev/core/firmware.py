"""Gói firmware: mỗi gói là một thư mục trong firmware/ có manifest.json mô tả các file nạp."""
import json
import os
from dataclasses import dataclass

from robodev import paths

FULL_FILES = ("full",)
FAST_FILES = ("app", "otadata", "partition_table")


@dataclass
class Package:
    folder: str
    name: str
    version: str
    variant: str       # "usb" | "uart": cổng đọc log của firmware
    notes: str
    files: dict

    def path(self, role):
        name = self.files.get(role)
        return os.path.join(self.folder, name) if name else None

    def has(self, role):
        path = self.path(role)
        return bool(path) and os.path.isfile(path)

    def missing(self, roles):
        return [self.files.get(r, r) for r in roles if not self.has(r)]

    @property
    def label(self):
        return f"{self.name}"


def _read(folder):
    with open(os.path.join(folder, "manifest.json"), encoding="utf-8") as f:
        raw = json.load(f)
    return Package(folder=folder, name=raw.get("name", os.path.basename(folder)), version=raw.get("version", "?"),
                   variant=raw.get("variant", "usb"),
                   notes=raw.get("notes", ""), files=raw.get("files", {}))


def discover(root=None):
    """Các gói firmware tìm thấy, theo tên."""
    root = root or paths.FIRMWARE_DIR
    out = []
    if os.path.isdir(root):
        for name in sorted(os.listdir(root)):
            folder = os.path.join(root, name)
            if os.path.isfile(os.path.join(folder, "manifest.json")):
                try:
                    out.append(_read(folder))
                except (OSError, ValueError):
                    continue
    out.sort(key=lambda p: p.name)
    return out


def single_file(path):
    """Gói tạm từ một file .bin người dùng chọn (nạp đầy đủ từ địa chỉ 0x0)."""
    return Package(folder=os.path.dirname(path), name=os.path.basename(path), version="?",
                   variant="usb", notes="File chọn từ máy tính", files={"full": os.path.basename(path)})
