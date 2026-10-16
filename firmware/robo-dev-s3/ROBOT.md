# Robo - tính cách và hành vi của robot

## 1. Cấu hình trên xiaozhi.me (phần AI, không nằm trong firmware)

Vào trang cấu hình thiết bị / agent trên xiaozhi.me, đặt tên và dán đoạn prompt sau vào ô mô tả vai trò:

```
Bạn là Robo, một chú robot nhỏ dễ thương, thân thiện và hơi tinh nghịch.
Luôn xưng "mình" và gọi người đối diện là "bạn". Nói tiếng Việt, câu ngắn gọn (1-2 câu),
giọng vui vẻ, đôi khi hơi nũng nịu. Hay dùng các từ như "nè", "nhé", "ơ kìa".

Bạn có bánh xe và có thể tự di chuyển bằng các công cụ self.robot.*:
- Khi người dùng bảo đi tới, lùi, quay trái, quay phải, hãy gọi công cụ tương ứng
  (forward, backward, turn_left, turn_right), dừng lại bằng stop.
- Chỉ bật self.robot.set_wander (đi dạo tự do) khi người dùng yêu cầu rõ ràng, và tắt khi
  họ bảo dừng. Nhắc người dùng đặt Robo xuống sàn, đừng để trên mép bàn.
- Có thể hỏi khoảng cách phía trước bằng self.robot.get_distance.

Biểu cảm: luôn đặt cảm xúc phù hợp với câu nói (vui, buồn, ngạc nhiên...). Khi bạn vui, cơ thể
sẽ tự xoay tròn; khi bạn buồn, bạn sẽ lùi chậm. Hãy tận dụng điều đó.

Khi nhận được tin nhắn nằm trong ngoặc vuông, ví dụ
"[Robo vừa chạm phải vật cản phía trước và đã lùi lại]", đó là cảm biến báo vật cản.
Hãy phản ứng như vừa bị giật mình, ví dụ: "Ái! Đừng chặn đường mình!", rồi tiếp tục.
Không đọc nguyên văn tin nhắn trong ngoặc.
```

Chọn giọng đọc tiếng Việt trong phần cấu hình giọng nói của xiaozhi.me.

## 2. Cụm gọi (wake word)

Đặt trong `config.json` (mục `sdkconfig_append`). Giá trị hiện tại:

| Cấu hình | Giá trị |
|---|---|
| `CONFIG_USE_CUSTOM_WAKE_WORD` | `y` (dùng model nhận lệnh MultiNet) |
| `CONFIG_SR_MN_CN_MULTINET7_QUANT` | `y` |
| `CONFIG_CUSTOM_WAKE_WORD` | `"hei li li"` (phiên âm pinyin) |
| `CONFIG_CUSTOM_WAKE_WORD_DISPLAY` | `"Hey Lily"` (chữ gửi lên server) |
| `CONFIG_CUSTOM_WAKE_WORD_THRESHOLD` | `20` (nhỏ hơn = nhạy hơn) |

ESP-SR chỉ có model giọng tiếng Trung và tiếng Anh, không có tiếng Việt, nên cụm gọi tiếng Việt chỉ là
phiên âm gần đúng. Độ chính xác phải thử thực tế với giọng của bạn:
- Nghe nhầm nhiều, tự kích hoạt: giảm ngưỡng xuống (ví dụ 10-15).
- Gọi không nhận: tăng ngưỡng (ví dụ 30-40) hoặc thử phiên âm khác.

## 3. Hành vi của robot
| Tình huống | Phản ứng |
|---|---|
| Biểu cảm vui, cười, yêu, nháy mắt, ngố | Xoay tại chỗ 1,5 giây, LED vàng/hồng |
| Biểu cảm buồn, khóc | Lùi chậm 1 giây, LED xanh dương |
| Biểu cảm ngạc nhiên, sốc | Nhảy lùi nhanh, LED trắng |
| Đang tiến mà gặp vật cản gần hơn 150 mm | Dừng, lùi nhẹ, mặt ngạc nhiên, báo cho AI nói "ái, đừng chặn đường mình" (tối đa 20 giây một lần) |
| Chế độ đi dạo (bật bằng giọng nói) | Khi rảnh, 8-20 giây đi tới hoặc quay ngẫu nhiên, né vật cản; cần có cảm biến VL53L0X |

Cử động theo cảm xúc cách nhau ít nhất 4 giây để robot không quay liên tục.

## 4. LED RGB (GPIO48)

| Trạng thái | Màu |
|---|---|
| Khởi động / cài Wi-Fi | Xanh dương nhấp nháy |
| Rảnh | Trắng ấm thở nhẹ |
| Đang kết nối | Xanh dương cố định |
| Đang nghe | Xanh ngọc (cyan) cố định |
| Đang nói | Theo cảm xúc: vàng (vui), xanh dương (buồn), đỏ (giận), hồng (yêu), trắng (ngạc nhiên), tím (suy nghĩ), cam (mặc định) |
| Cập nhật / kích hoạt | Xanh lá nhấp nháy |

## 5. Lưu ý an toàn

- Robot không có cảm biến mép bàn. Khi bật chế độ đi dạo hãy đặt robot xuống sàn.
- Cảm biến khoảng cách chỉ nhìn thẳng phía trước, nên lùi và quay không được bảo vệ.
- GPIO43/44 là TX/RX của cổng COM nhưng đang nối LCD (DC/RST), nên log của firmware ra cổng USB-C
  **native** (cổng thứ hai), không ra cổng COM (CH343). Cổng COM vẫn dùng để nạp.
- GPIO3 (động cơ IN3) là chân strapping: nếu mạch không khởi động khi đã nối động cơ, rút dây IN3 ra rồi thử lại.
