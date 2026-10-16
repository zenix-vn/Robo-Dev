# Robo Dev

Phần mềm giúp người mới làm quen firmware ESP32: nạp và cập nhật firmware, cài Wi-Fi, kết nối xiaozhi.me, xem log, kiểm tra từng module, tùy chỉnh nối chân và lệnh điều khiển cho robot ESP32-S3 (mic INMP441, loa MAX98357A, LCD ST7789, cảm biến VL53L0X/VL6180X, động cơ, LED WS2812).

| Thư mục | Nội dung |
| --- | --- |
| `app/` | Phần mềm Robo Dev (Python) |
| `firmware/` | Mã nguồn firmware chạy trên mạch (ESP-IDF, dựa trên xiaozhi-esp32) |
| `docs/` | Sơ đồ nối dây, ảnh mạch, bảng chân GPIO, đề xuất v2 |
| `document.md` | Tài liệu thiết kế |

---

## 0. Lấy mã nguồn

Cần [Git](https://git-scm.com/download/win). Mở PowerShell ở thư mục bạn muốn đặt dự án rồi chạy:

```powershell
git clone --recurse-submodules https://github.com/zenix-vn/Robo-Dev.git
cd Robo-Dev
```

`--recurse-submodules` tải kèm thư viện xiaozhi-esp32 cho phần firmware.

**Mọi lệnh bên dưới đều tính từ thư mục `Robo-Dev` vừa clone.** Cách mở PowerShell đúng thư mục này:
- mở thư mục `Robo-Dev` bằng VS Code rồi chọn **Terminal → New Terminal**; hoặc
- mở thư mục `Robo-Dev` trong File Explorer, gõ `powershell` vào thanh địa chỉ rồi Enter.

---

## 1. Chạy phần mềm Robo Dev

Mọi lệnh gõ trong **PowerShell**. Cần Python 3.11 trở lên ([python.org](https://www.python.org/downloads/), khi cài nhớ tick "Add python.exe to PATH").

### Lần đầu: cài đặt (chỉ làm một lần)

Từ thư mục `Robo-Dev`:

```powershell
cd app
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Mở phần mềm

Từ thư mục `Robo-Dev\app` (nếu đang ở `Robo-Dev` thì `cd app` trước):

```powershell
.\.venv\Scripts\python.exe run.py
```

Chưa có mạch? Dùng mạch mô phỏng để làm quen:

```powershell
.\.venv\Scripts\python.exe run.py --demo
```

### Tạo file Robo-Dev.exe (gửi cho người khác, không cần cài Python)

Từ thư mục `Robo-Dev\app`:

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe build_exe.py
```

Kết quả nằm ở `Robo-Dev\releases\Robo-Dev\` (gửi cả thư mục, gồm `Robo-Dev.exe` và `firmware\`).

### Lỗi thường gặp

| Lỗi | Cách sửa |
| --- | --- |
| `No module named 'PySide6'` | Bạn đang chạy bằng `py` hoặc `python` chung của máy. Dùng `.\.venv\Scripts\python.exe` như trên, hoặc làm lại bước cài đặt. |
| `.venv\Scripts\python.exe` không tồn tại | Chưa làm bước "Lần đầu: cài đặt". |
| Không thấy cổng COM của mạch | Đổi cáp USB khác (nhiều cáp chỉ để sạc). Cài driver CH343 nếu cổng COM không hiện trong Device Manager. |

---

## 2. Phát triển firmware

Phần này dành cho người muốn sửa code chạy trên mạch (thêm tính năng, đổi chân, thêm lệnh cho AI). Nếu chỉ muốn đổi tốc độ, màu đèn, bật/tắt tính năng thì **không cần** sửa firmware: dùng phần mềm Robo Dev ở trên.

### 2.1. Chuẩn bị (chỉ làm một lần)

1. Cài **ESP-IDF v6.1** bằng [ESP-IDF Installation Manager](https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/get-started/windows-setup.html).
2. `firmware\idf-env.ps1` tự tìm ESP-IDF ở các chỗ cài thường gặp (`C:\Espressif`, `D:\Espressif`, `%USERPROFILE%\esp`, `%USERPROFILE%\.espressif`) hoặc theo biến môi trường `IDF_PATH`. Nếu cài ở chỗ khác, đặt đường dẫn một lần (thay bằng đường dẫn của bạn):
   ```powershell
   setx IDF_PATH "E:\duong-dan\esp-idf"
   ```
   rồi mở cửa sổ PowerShell mới.
3. Cắm mạch bằng **hai** cáp USB-C:
   - cổng **COM** (chip CH343) để nạp, ví dụ `COM3`;
   - cổng **USB** (USB native của ESP32-S3) để xem log, ví dụ `COM4`.

   Xem số cổng trong Device Manager → Ports (COM & LPT).

### 2.2. Mở môi trường ESP-IDF (mỗi lần mở cửa sổ PowerShell mới)

Từ thư mục `Robo-Dev`:

```powershell
cd firmware
. .\idf-env.ps1
```

Có dấu chấm và dấu cách ở đầu lệnh thứ hai. Thấy dòng xanh `Đã mở môi trường ESP-IDF: ESP-IDF v6.1` là được.

Nếu PowerShell báo "running scripts is disabled", chạy một lần lệnh sau rồi thử lại:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 2.3. Build, nạp, xem log

Từ thư mục `Robo-Dev\firmware` (sau bước 2.2):

```powershell
.\build.ps1                                     # build (lần đầu 10-20 phút, các lần sau nhanh hơn)
idf.py -C xiaozhi-esp32 -p COM3 flash           # nạp qua cổng COM, giữ nguyên Wi-Fi đã cài
idf.py -C xiaozhi-esp32 -p COM4 monitor         # xem log, thoát bằng Ctrl + ]
```

Lần đầu, `build.ps1` tự tải thư viện xiaozhi-esp32 nếu chưa có (cần mạng).

Thay `COM3`, `COM4` bằng cổng của bạn. Khi đang xem log trong phần mềm Robo Dev, hãy bấm **Dừng log** trước, vì một cổng chỉ một chương trình mở được.

Nếu nạp báo không kết nối được chip: giữ nút **BOOT**, nhấn **RST**, thả **BOOT**, rồi nạp lại.

### 2.4. Nạp bằng phần mềm Robo Dev (không cần gõ lệnh nạp)

Sau khi build xong, đóng gói bản build cho Robo Dev. Từ thư mục `Robo-Dev\firmware`:

```powershell
cd ..\app
.\.venv\Scripts\python.exe package_firmware.py --name "Robo Dev thử nghiệm" --version "1.0.1"
```

Mở Robo Dev → **5. Nạp & kết nối** → chọn gói vừa tạo → **Nạp nhanh**.

Gói nằm ở `app\firmware\<tên>-<phiên bản>\`, ví dụ `app\firmware\robo-dev-1.0.1\`. Muốn nạp bằng công cụ khác (ESP Flash Download Tool, trang web nạp ESP...), dùng file cùng tên gói, ví dụ `robo-dev-1.0.1.bin`, ghi từ địa chỉ `0x0`. Cách này xóa Wi-Fi đã lưu. Các file còn lại trong thư mục là từng phần của cùng bản build, dùng cho nạp nhanh.

### 2.5. Sửa ở đâu

Thư mục `firmware\` tách riêng code của mình và thư viện của người khác (chi tiết: [firmware/README.md](firmware/README.md)):

| Thư mục | Của ai | Sửa không? |
| --- | --- | --- |
| `firmware\robo-dev-s3\` | Code của robot Robo Dev | **Sửa ở đây** |
| `firmware\patches\` | Những chỗ buộc phải sửa trong thư viện | Hiếm khi |
| `firmware\xiaozhi-esp32\` | Thư viện [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) (git submodule) | **Không sửa trực tiếp** |

Các file trong `firmware\robo-dev-s3\`:

| Muốn làm | Sửa file |
| --- | --- |
| Đổi chân GPIO, kích thước màn hình | `config.h` |
| Đổi cụm gọi (wake word), ngôn ngữ, cấu hình build | `config.json` |
| Thêm lệnh cho AI, khởi tạo phần cứng | `robo_dev_s3.cc` |
| Thêm lệnh gõ qua cổng log (`RD_...`) | `serial_setup.h` |
| Cấu hình đọc từ NVS (tốc độ, màu, bật/tắt) | `robot_config.h` |
| Hành vi theo cảm xúc, đi dạo | `robot_behavior.h` |
| Điều khiển động cơ | `robot_motor_controller.h` |
| Màu đèn LED | `robot_led.h` |
| Đọc cảm biến khoảng cách | `vl53l0x.h`, `vl6180x.h` |

### 2.6. Ví dụ: thêm một lệnh cho AI

AI trên xiaozhi.me điều khiển robot bằng **công cụ MCP**. Thêm một công cụ trong `robo_dev_s3.cc`, cạnh các dòng `McpServer::GetInstance().AddTool(...)` đã có:

```cpp
McpServer::GetInstance().AddTool("self.robot.blink",
    "Nháy đèn LED của robot vài lần. Gọi khi người dùng bảo robot nháy đèn.",  // AI đọc mô tả này để biết khi nào gọi
    PropertyList({Property("times", kPropertyTypeInteger, 3, 1, 10)}),          // tham số: mặc định 3, từ 1 đến 10
    [this](const PropertyList& properties) -> ReturnValue {
        int times = properties["times"].value<int>();
        // ... code nháy đèn ở đây ...
        return true;
    });
```

Build và nạp lại, rồi nói với robot "nháy đèn 5 lần". Mô tả nên viết rõ "lệnh làm gì" và "khi nào gọi"; tên lệnh bắt đầu bằng `self.`.

### 2.7. Quy tắc nhỏ

- Mỗi lần sửa, build và thử trên mạch thật trước khi sửa tiếp. Xem log (`idf.py monitor`) khi có lỗi: dòng bắt đầu bằng `E (` là lỗi, `W (` là cảnh báo.
- Đổi chân GPIO thì sửa cả `config.h` lẫn `docs/hardware.md`, và tránh các chân bị cấm (GPIO 26-37, cổng log); xem `document.md` mục 5.
- Không sửa thẳng vào `firmware\xiaozhi-esp32\`: lần cập nhật thư viện sau sẽ mất. Nếu buộc phải sửa thư viện, lưu thành patch (xem [firmware/README.md](firmware/README.md)).
- Quy tắc kiến trúc của thư viện: `firmware\xiaozhi-esp32\AGENTS.md`. Cách cập nhật thư viện lên bản mới: [firmware/README.md](firmware/README.md).
- Lưu lại công việc bằng git (chạy ở bất kỳ thư mục con nào trong `Robo-Dev`):

```powershell
git add -A
git commit -m "Mô tả ngắn điều đã sửa"
git push
```
