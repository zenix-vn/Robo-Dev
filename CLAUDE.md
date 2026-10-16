# CLAUDE.md

Hướng dẫn cho Claude Code khi làm việc trong repo này.

## Dự án

Robo Dev: phần mềm Python (Windows) giúp người mới học ESP32 nạp, cấu hình, kiểm tra và tùy biến một **firmware base Robo Dev** dựa trên xiaozhi-esp32 cho mạch ESP32-S3. Chân GPIO, tính năng và lệnh điều khiển được cấu hình lúc chạy (NVS) qua cổng COM, không cần biên dịch lại.

- Tài liệu thiết kế: [document.md](document.md). Đọc trước khi làm bất kỳ phần nào; cập nhật khi quyết định thay đổi.
- Repo: https://github.com/zenix-vn/Robo-Dev, nhánh `main`.
- Ngôn ngữ trao đổi và giao diện: tiếng Việt. Comment trong code và commit message có thể dùng tiếng Anh.

## Cấu trúc (xem document.md mục 10)

- `firmware/`: tách code của mình và thư viện (chi tiết `firmware/README.md`):
  - `firmware/xiaozhi-esp32/`: git submodule 78/xiaozhi-esp32 @ `e076ac4`. **Không sửa trực tiếp.**
  - `firmware/robo-dev-s3/`: code board của robot (sửa ở đây). `build.ps1` gắn vào thư viện bằng junction.
  - `firmware/patches/*.patch`: sửa bắt buộc trong thư viện, mỗi chủ đề một file; `build.ps1` tự áp.
- `app/robodev/`: ứng dụng Python (PySide6, esptool, pyserial), đóng gói PyInstaller. `core/` không phụ thuộc giao diện; `ui/` là PySide6 (theme/màu chỉ lấy từ `ui/theme.py`).
- `docs/`: phần cứng, sơ đồ nối dây ([docs/hardware.md](docs/hardware.md)).

## Phần cứng v1

ESP32-S3-N16R8, mic INMP441, MAX98357A + loa, LCD ST7789 240x240, VL53L0X hoặc VL6180X, 2 động cơ qua cầu H, LED WS2812 onboard, nút BOOT. Luật chân ở document.md mục 5. Không đổi chân mặc định khi người dùng chưa xác nhận dây nối thực tế.

## Mã nguồn tham khảo

Từ 16/10/2026 mọi thứ nằm trong `Robo-Dev/`. Các thư mục thử nghiệm cũ trong `D:\Code\xiaozhi-firmware` đã được chép vào đây rồi xóa; không import hay trỏ ra ngoài repo.

- Quy tắc kiến trúc của thư viện: `firmware/xiaozhi-esp32/AGENTS.md` (áp dụng cả cho `robo-dev-s3/`). Cách thêm patch, cập nhật thư viện: `firmware/README.md`.
- `app/firmware/<gói>/`: gói firmware đã build (chỉ `manifest.json` được commit; `.bin` tạo lại bằng `app/package_firmware.py`).
- `docs/de-xuat-v2.md`: đề xuất cho phiên bản 2 (danh mục module, tự phân bổ chân, sơ đồ đấu dây).

## Build

- App: `cd app; .\.venv\Scripts\python.exe -m robodev --demo` (mạch mô phỏng, không cần phần cứng); test: `.\.venv\Scripts\python.exe -m pytest`; lint: `-m pyflakes robodev tests`.
- Kiểm tra giao diện bằng mắt: `-m robodev --demo --shot <thư mục>` chụp ảnh 6 trang rồi đọc ảnh.
- Firmware: ESP-IDF v6.1 ở `D:\Espressif\esp-idf` (tools `D:\Espressif\tools`), target `esp32s3`. ESP-IDF không chạy trong Git Bash/MSYS: dùng PowerShell. Build: `powershell -File firmware/build.ps1` (tự mở ESP-IDF qua `idf-env.ps1`, áp patch, gắn board, build; ra `firmware/xiaozhi-esp32/build/`). Submodule đặt `core.autocrlf=false` để patch (LF) áp được; PowerShell 5.1 coi stderr của lệnh native là lỗi khi `$ErrorActionPreference = "Stop"`.
- Không commit `build/`, `managed_components/`, `sdkconfig`, `releases/`, `*.bin`.

## Quy tắc làm việc

- Giữ patch gọn, đúng phạm vi yêu cầu.
- Tên dự án và robot thống nhất là Robo Dev / Robo; không dùng tên của các dự án thử nghiệm trước đây. Lệnh COM dùng tiền tố `RD_`; khóa NVS là API lâu dài, đổi cấu trúc phải tăng `schema` và viết chuyển đổi.
- Không push, force-push hay đổi lịch sử khi người dùng chưa yêu cầu.
