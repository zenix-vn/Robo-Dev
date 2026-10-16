# CLAUDE.md

Hướng dẫn cho Claude Code khi làm việc trong repo này.

## Dự án

Robo Dev: phần mềm Python (Windows) giúp người mới học ESP32 nạp, cấu hình, kiểm tra và tùy biến một **firmware base Robo Dev** dựa trên xiaozhi-esp32 cho mạch ESP32-S3. Chân GPIO, tính năng và lệnh điều khiển được cấu hình lúc chạy (NVS) qua cổng COM, không cần biên dịch lại.

- Tài liệu thiết kế: [document.md](document.md). Đọc trước khi làm bất kỳ phần nào; cập nhật khi quyết định thay đổi.
- Repo: https://github.com/zenix-vn/Robo-Dev, nhánh `main`.
- Ngôn ngữ trao đổi và giao diện: tiếng Việt. Comment trong code và commit message có thể dùng tiếng Anh.

## Cấu trúc (dự kiến, xem document.md mục 10)

- `firmware/`: dự án ESP-IDF copy từ xiaozhi-esp32; board mới `main/boards/robo-dev-s3/`.
- `app/robodev/`: ứng dụng Python (PySide6, esptool, pyserial), đóng gói PyInstaller. `core/` không phụ thuộc giao diện; `ui/` là PySide6 (theme/màu chỉ lấy từ `ui/theme.py`).
- `docs/`: phần cứng, sơ đồ nối dây ([docs/hardware.md](docs/hardware.md)).

## Phần cứng v1

ESP32-S3-N16R8, mic INMP441, MAX98357A + loa, LCD ST7789 240x240, VL53L0X hoặc VL6180X, 2 động cơ qua cầu H, LED WS2812 onboard, nút BOOT. Luật chân ở document.md mục 5. Không đổi chân mặc định khi người dùng chưa xác nhận dây nối thực tế.

## Mã nguồn tham khảo

Robo Dev phải tự chứa: code cần dùng được **copy vào** `Robo-Dev/`, không import hay trỏ ra thư mục khác. Thư mục cha `D:\Code\xiaozhi-firmware` chứa bản tham khảo, chỉ đọc:

- `../xiaozhi-esp32/`: firmware đã chạy trên mạch, board `main/boards/ai-box-robot-s3cam/`. Quy tắc kiến trúc trong `AGENTS.md` ở đó cũng áp dụng cho `firmware/`.
- `../Voi-Studio/`: ứng dụng nạp/cấu hình tiền thân (`studio/link.py`, `jobs.py`...), thiết kế trong `docs.md`, `document-v2.md`.
- `../Voi-Flasher-src/`: tool nạp đơn giản đời đầu.

## Build

- App: `cd app; .\.venv\Scripts\python.exe -m robodev --demo` (mạch mô phỏng, không cần phần cứng); test: `.\.venv\Scripts\python.exe -m pytest`; lint: `-m pyflakes robodev tests`.
- Kiểm tra giao diện bằng mắt: `-m robodev --demo --shot <thư mục>` chụp ảnh 6 trang rồi đọc ảnh.
- Firmware: ESP-IDF v6.x, target `esp32s3`. ESP-IDF không chạy trong Git Bash/MSYS; dùng PowerShell với `export.ps1`.
- Không commit `build/`, `managed_components/`, `sdkconfig`, `releases/`, `*.bin`.

## Quy tắc làm việc

- Giữ patch gọn, đúng phạm vi yêu cầu.
- Lệnh COM mới dùng tiền tố `RD_`; khóa NVS là API lâu dài, đổi cấu trúc phải tăng `schema` và viết chuyển đổi.
- Không push, force-push hay đổi lịch sử khi người dùng chưa yêu cầu.
