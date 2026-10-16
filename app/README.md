# Ứng dụng Robo Dev

Ứng dụng Windows (Python + PySide6) để nạp, cấu hình, kiểm tra và tùy biến firmware robot ESP32-S3. Thiết kế: [../document.md](../document.md).

## Chạy từ mã nguồn

```powershell
cd app
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt pytest
.\.venv\Scripts\python.exe -m robodev            # mở ứng dụng
.\.venv\Scripts\python.exe -m robodev --demo     # chọn sẵn mạch mô phỏng, không cần mạch thật
```

Tùy chọn khác: `--theme dark`, `--open đường/dẫn.robodev.json`, `--shot THƯ_MỤC` (chụp ảnh từng trang rồi thoát).

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Gói firmware

Mỗi gói là một thư mục trong `firmware/` có `manifest.json` (tên, phiên bản, `variant` usb/uart, tên các file `.bin`). Chỉ `manifest.json` được commit; file `.bin` tạo bằng cách build firmware (`../firmware/build.ps1`) rồi chạy `package_firmware.py` (xem README ở gốc repo).

## Đóng gói `.exe`

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe build_exe.py     # ra ../releases/Robo-Dev/
```
