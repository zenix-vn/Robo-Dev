# Robo Dev S3 (ESP32-S3-N16R8 devkit 2 cổng USB-C)

Board của robot Robo Dev: ESP32-S3-N16R8 (16 MB flash, 8 MB PSRAM, không có cổng camera). Ngôn ngữ mặc định: tiếng Việt (vi-VN). Ảnh mạch và sơ đồ: `docs/hardware/` ở gốc repo.

Chân GPIO (theo `config.h`):

| Thiết bị | Chân thiết bị | GPIO |
|---|---|---|
| Mic INMP441 | WS / SCK / SD | 4 / 5 / 6 (L/R nối 3V3) |
| Loa MAX98357A | LRC / BCLK / DIN | 16 / 15 / 7 |
| LCD ST7789 240x240 | SDA / SCL / DC / RST | 1 / 2 / 43 / 44 (CS nối GND, BL nối 3V3) |
| Cảm biến VL53L0X / VL6180X (I2C) | SDA / SCL | 12 / 13 |
| Mạch động cơ | IN1 / IN2 / IN3 / IN4 | 17 / 18 / 3 / 14 |
| LED RGB onboard | DIN | 48 |
| Nút BOOT | | 0 |

GPIO43/44 (TX/RX của cổng COM) dùng cho LCD, nên log và lệnh `RD_*` đi qua cổng USB native (USB-Serial/JTAG, GPIO19/20). Cổng COM vẫn dùng để nạp.

Lệnh cho AI (MCP): `self.robot.forward|backward|turn_left|turn_right|stop|set_wander|get_distance`, `self.screen.*`. Lệnh qua cổng log: xem đầu file `serial_setup.h`. Tính cách mẫu cho AI: `ROBOT.md`.

Build: chạy `..uild.ps1` (gắn thư mục này vào `xiaozhi-esp32/main/boards/` rồi build). Xem `../README.md`.
