"""Chép firmware vừa build (../firmware/xiaozhi-esp32/build) thành một gói trong firmware/ để nạp bằng Robo Dev.

    .\\.venv\\Scripts\\python.exe package_firmware.py --name "Robo Dev thử nghiệm" --version "1.0.1"

Gói tạo ra: firmware/<thư mục>/ gồm các file .bin và manifest.json.
"""
import argparse
import json
import os
import re
import shutil
import sys
import unicodedata

ROOT = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(os.path.dirname(ROOT), "firmware", "xiaozhi-esp32", "build")
FILES = {  # vai trò -> (file trong build/, tên file trong gói)
    "full": ("merged-binary.bin", "merged-binary.bin"),
    "app": ("xiaozhi.bin", "xiaozhi.bin"),
    "otadata": ("ota_data_initial.bin", "ota_data_initial.bin"),
    "partition_table": (os.path.join("partition_table", "partition-table.bin"), "partition-table.bin"),
    "assets": ("generated_assets.bin", "generated_assets.bin"),
    "bootloader": (os.path.join("bootloader", "bootloader.bin"), "bootloader.bin"),
}


def slug(text):
    """Tên thư mục không dấu: "Robo Dev thử nghiệm-1.0.1" -> "robo-dev-thu-nghiem-1.0.1"."""
    text = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9.]+", "-", text.lower()).strip("-")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", required=True, help="tên hiển thị trong Robo Dev")
    parser.add_argument("--version", required=True, help="phiên bản, ví dụ 1.0.1")
    parser.add_argument("--variant", default="usb", choices=["usb", "uart"], help="cổng đọc log của firmware")
    parser.add_argument("--notes", default="", help="ghi chú hiện trong Robo Dev")
    args = parser.parse_args()

    if not os.path.isfile(os.path.join(BUILD, "xiaozhi.bin")):
        sys.exit(f"Chưa có bản build trong {BUILD}. Hãy build firmware trước (firmware/build.ps1).")
    folder = os.path.join(ROOT, "firmware", slug(f"{args.name}-{args.version}"))
    os.makedirs(folder, exist_ok=True)
    files = {}
    for role, (src, dst) in FILES.items():
        path = os.path.join(BUILD, src)
        if os.path.isfile(path):
            shutil.copyfile(path, os.path.join(folder, dst))
            files[role] = dst
    manifest = {"name": args.name, "version": args.version, "variant": args.variant, "chip": "esp32s3",
                "flash_mb": 16, "notes": args.notes, "files": files}
    with open(os.path.join(folder, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("Đã tạo gói:", folder)
    print("Có:", ", ".join(files))
    if "full" not in files:
        print("Chú ý: thiếu merged-binary.bin nên gói này chỉ nạp nhanh được.")


if __name__ == "__main__":
    main()
