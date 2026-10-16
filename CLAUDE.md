# CLAUDE.md

Hướng dẫn cho Claude Code khi làm việc trong repo này.

## Dự án

Zin-ESP32-Smart: firmware cho mạch ESP32-S3 (robot "Voi" / thiết bị Zin). Repo mới bắt đầu từ trống, chưa có code firmware.

- Repo: https://github.com/zenix-vn/Zin-ESP32-Smart (nhánh `main`)
- Ngôn ngữ trao đổi: tiếng Việt. Comment trong code và commit message có thể dùng tiếng Anh.

## Phần cứng mục tiêu

- Board: ESP32-S3-N16R8 (flash 16 MB, PSRAM 8 MB octal).
- Ngoại vi: mic I2S INMP441, khuếch đại I2S MAX98357A + loa, LCD ST7789 240x240 1,54" (SPI, không có CS), cảm biến khoảng cách VL53L0X (I2C), mạch động cơ 2 bánh (4 chân IN), LED RGB WS2812 onboard GPIO48, nút BOOT GPIO0.
- Nạp và đọc log qua cổng COM (chip USB-UART CH343).
- Chi tiết chân GPIO và sơ đồ nối dây: [docs/hardware.md](docs/hardware.md), ảnh trong `docs/hardware/`.

Ràng buộc cần nhớ:

- GPIO26-37 bị flash/PSRAM octal chiếm, không dùng.
- GPIO0, 3, 45, 46 là chân strapping, cẩn thận khi nối ngoại vi.
- Không đổi chân GPIO khi chưa có xác nhận của người dùng về dây nối thực tế.

## Dự án tham khảo trong workspace

Thư mục cha `D:\Code\xiaozhi-firmware` chứa các dự án thử nghiệm trước đó (chỉ đọc để tham khảo, không sửa từ repo này):

- `../xiaozhi-esp32/`: bản xiaozhi-esp32 (upstream 78/xiaozhi-esp32) đã chạy được trên mạch này, board `main/boards/ai-box-robot-s3cam/`. Xem `AGENTS.md` ở đó cho quy tắc kiến trúc.
- `../Voi-Studio/`: công cụ Windows chỉnh cấu hình và nạp firmware; `docs.md` mô tả giao thức `VOI_CFG` / `VOI_WIFI` / `VOI_PING` qua COM.
- `../Voi-Flasher-src/`: tool nạp firmware đơn giản (Python).

## Môi trường build

- ESP-IDF v6.x (xiaozhi-esp32 yêu cầu tối thiểu v6.0.1). Target: `esp32s3`.
- Khi đã có code: `idf.py set-target esp32s3`, `idf.py build`, `idf.py -p COMx flash monitor`.
- Không commit `build/`, `managed_components/`, `sdkconfig` sinh tự động (xem `.gitignore`).

## Quy tắc làm việc

- Giữ patch gọn, đúng phạm vi yêu cầu.
- Không push lên GitHub, không force-push, không đổi lịch sử khi người dùng chưa yêu cầu.
- Cập nhật file này khi kiến trúc hoặc lệnh build thay đổi.
