# Phần cứng

Board ESP32-S3-N16R8 (flash 16 MB, PSRAM 8 MB). Sơ đồ nối dây trong thư mục [hardware/](hardware/):

- `so-do-noi-day.png` / `.svg`: sơ đồ nối dây robot (vẽ theo bảng chân **cũ**, chưa cập nhật theo `config.h`).
- `photos/`: ảnh mạch thật.
- `so-do-mach-thuc-te.svg`: sơ đồ theo mạch thực tế.
- `so-do-test-mic-loa.png` / `.svg`: sơ đồ test mic và loa.

## Bảng chân GPIO

> Bảng dưới lấy từ `config.h` của board `robo-dev-s3` (firmware đang chạy trên mạch). Sơ đồ `so-do-noi-day` vẽ theo một bảng chân cũ hơn (mic 1/2/42, LCD 19/20/21/47...), cần vẽ lại.

| Thiết bị | Chân thiết bị | GPIO |
| --- | --- | --- |
| Mic INMP441 | WS / SCK / SD | 4 / 5 / 6 |
| Khuếch đại MAX98357A | LRC / BCLK / DIN | 16 / 15 / 7 |
| LCD ST7789 240x240 | SCL / SDA / DC / RST | 2 / 1 / 43 / 44 (CS nối GND, BL nối 3V3) |
| VL53L0X | SDA / SCL | 12 / 13 |
| Động cơ | IN1 / IN2 / IN3 / IN4 | 17 / 18 / 3 / 14 |
| LED RGB WS2812 onboard | DIN | 48 |
| Nút BOOT | - | 0 |

Thông số LCD đang dùng: SPI mode 3, 10 MHz, đảo màu, thứ tự RGB.
