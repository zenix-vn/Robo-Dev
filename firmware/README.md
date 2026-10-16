# Firmware Robo Dev

Firmware chạy trên mạch ESP32-S3 của robot, xây trên thư viện [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32).

## Cấu trúc: tách code của mình và thư viện của người khác

```
firmware/
  xiaozhi-esp32/   THƯ VIỆN (của người khác) - git submodule, KHÔNG sửa trực tiếp
  robo-dev-s3/     CODE CỦA MÌNH - board của robot (chân GPIO, động cơ, cảm biến, LED, lệnh RD_*...)
  patches/         CODE CỦA MÌNH - những chỗ buộc phải sửa trong thư viện, mỗi chủ đề một file
  build.ps1        ghép 3 phần trên rồi build
  idf-env.ps1      mở môi trường ESP-IDF
```

- `xiaozhi-esp32/` là **git submodule**: repo Robo Dev chỉ lưu địa chỉ `https://github.com/78/xiaozhi-esp32` và mã commit đang dùng (`e076ac4`), không lưu code của thư viện. Khi clone repo Robo Dev, git tải thư viện về đúng commit đó.
- `build.ps1` áp các patch vào thư viện và gắn `robo-dev-s3/` vào `xiaozhi-esp32/main/boards/` bằng junction (một "lối tắt" thư mục: sửa file trong `robo-dev-s3/` là bản build thấy ngay).
- Kết quả build nằm ở `xiaozhi-esp32/build/`. Thư viện tải thêm (`managed_components/`) và `sdkconfig` cũng nằm trong `xiaozhi-esp32/` và không được commit.

| Patch | Sửa gì trong thư viện | Vì sao |
| --- | --- | --- |
| `01-board-robo-dev-s3.patch` | `main/CMakeLists.txt`, `main/Kconfig.projbuild` | Đăng ký board `robo-dev-s3` |
| `02-project-version.patch` | `CMakeLists.txt` | Số phiên bản firmware Robo Dev (`1.0.0`) |
| `03-audio-play-pcm.patch` | `main/audio/audio_service.*` | Thêm `PlayPcm()` để phát âm thanh thử và chuông |
| `04-mic-input-shift.patch` | `main/audio/codecs/no_audio_codec.*` | Chỉnh độ lớn mic INMP441 (lệnh `RD_SHIFT`) |
| `05-vi-vn-strings.patch` | `main/assets/locales/vi-VN/language.json` | Chuỗi tiếng Việt hiển thị trên màn hình |

## Lấy code về (máy mới)

```powershell
git clone --recurse-submodules https://github.com/zenix-vn/Robo-Dev.git
```

Đã clone mà quên `--recurse-submodules` cũng không sao: `build.ps1` tự tải thư viện ở lần chạy đầu.

## Build và nạp

```powershell
cd Robo-Dev\firmware
. .\idf-env.ps1                              # mở môi trường ESP-IDF (mỗi cửa sổ PowerShell mới)
.\build.ps1                                  # áp patch, gắn board, build
idf.py -C xiaozhi-esp32 -p COM3 flash        # nạp qua cổng COM, giữ nguyên Wi-Fi
idf.py -C xiaozhi-esp32 -p COM4 monitor      # xem log, thoát bằng Ctrl + ]
```

## Sửa code

> **Quy tắc:** `xiaozhi-esp32/` là repo của người khác: **không sửa**, và không bao giờ commit vào đó. Nếu buộc phải sửa, phần sửa phải được lưu thành patch trong `patches/` (thuộc repo Robo Dev) thì mới commit được. Sửa mà chưa lưu thì sẽ mất khi `-Reset` hoặc khi cập nhật thư viện.

- **Sửa board của robot** (gần như mọi việc): sửa trong `robo-dev-s3/`, chạy lại `.\build.ps1`.
- **Buộc phải sửa thư viện** (hiếm):
  1. Sửa file trong `xiaozhi-esp32/` như bình thường.
  2. Lưu phần sửa vào patch:
     ```powershell
     .\build.ps1 -SavePatches                     # file đã có trong patch cũ: cập nhật patch đó
     .\build.ps1 -SavePatches -NewName ten-ngan   # có file mới sửa: tạo thêm patch NN-ten-ngan.patch
     ```
  3. Ghi patch mới (nếu có) vào bảng ở trên, rồi commit thư mục `patches/`.

  Mỗi lần chạy, `build.ps1` tự kiểm tra và **cảnh báo** nếu trong `xiaozhi-esp32/` còn chỗ sửa chưa lưu vào patch. `-Reset` cũng từ chối chạy khi còn chỗ chưa lưu.
- Muốn trả thư viện về nguyên gốc: `.\build.ps1 -Reset`.

## Cập nhật thư viện xiaozhi-esp32 lên bản mới

```powershell
.\build.ps1 -Reset
git -C xiaozhi-esp32 fetch --depth 1 origin <mã-commit-mới>
git -C xiaozhi-esp32 checkout <mã-commit-mới>
.\build.ps1
```

Nếu một patch không áp được, `build.ps1` báo tên patch: mở patch đó, sửa lại cho khớp code mới. Build và thử trên mạch thật, rồi commit (repo Robo Dev sẽ ghi nhận mã commit mới của submodule).
