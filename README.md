# Dịch

Công cụ nhỏ trên Windows để dịch nhanh tiếng Anh (và nhiều ngôn ngữ khác) sang tiếng Việt.
Làm cho người không rành công nghệ: dùng hoàn toàn bằng chuột, chữ to, màu tương phản cao.

- **Gõ hoặc dán chữ:** bản dịch hiện ngay khi ngừng gõ. Với từ đơn, Dịch hiện thêm các nghĩa khác theo từ loại.
- **Chọn vùng trên màn hình** (giống Snipping Tool): màn hình đứng yên lại, kéo khung quanh chữ,
  chỉnh khung, phóng to bằng con lăn chuột, rồi bấm **✔ Dịch**. Bản dịch hiện ngay cạnh khung.
- **Dịch giấy tờ:** dán ảnh chụp (ví dụ ảnh gửi qua Zalo) hoặc mở file ảnh, rồi khoanh vùng như trên.
- Tự nhận diện ngôn ngữ. Nếu gõ tiếng Việt thì Dịch tự dịch sang tiếng Anh.
- Lịch sử 50 lượt tra gần nhất, nút chép bản dịch, chỉnh cỡ chữ A+/A−.
- Giao diện sáng/tối tự đổi theo Windows.
- Chạy ngầm ở khay hệ thống (cạnh đồng hồ), tự chạy khi bật máy. Phím tắt `Ctrl+Alt+Q` để chọn vùng nhanh.

**Miễn phí hoàn toàn:** nhận diện chữ dùng OCR có sẵn của Windows (chạy offline), còn phần dịch
dùng endpoint miễn phí của Google Dịch (không cần API key).

## Cài lên máy (Windows 10/11)

1. Vào [Releases](https://github.com/MaiThucHaiDang/trans-tool/releases/latest) và tải **`Dich-Setup.exe`**.
2. Chạy file vừa tải. Nếu Windows hiện *"Windows protected your PC"*, bấm **More info → Run anyway**.
   Cảnh báo này xuất hiện vì file chưa được ký số, không phải do virus.
3. Bấm Next cho tới hết. Bộ cài **không cần quyền quản trị**. Nó tạo biểu tượng ngoài Desktop
   và trong Start Menu, đồng thời bật tự chạy khi mở máy.
4. **Ghim lên taskbar:** mở Dịch, chuột phải vào nút Dịch ở thanh taskbar → **Pin to taskbar**.

Không cài được (ví dụ máy trường chặn)? Tải **`Dich-portable.zip`**, giải nén vào một thư mục
cố định (như `Documents\Dich`) rồi chạy `Dich.exe`. Lần chạy đầu, Dịch tự tạo biểu tượng ngoài Desktop.

Gỡ cài đặt: Settings → Apps → Dịch → Uninstall.

## Cách dùng

| Muốn làm gì | Thao tác |
|---|---|
| Mở Dịch | Bấm biểu tượng Dịch trên taskbar, hoặc biểu tượng ở góc phải cạnh đồng hồ |
| Dịch chữ gõ vào | Gõ vào ô trên, bản dịch hiện ở ô dưới |
| Dịch chữ đã sao chép | Bấm **📋 Dán** |
| Dịch chữ trên màn hình | Bấm **✂ Chọn vùng cần dịch** → kéo khung → **✔ Dịch** → đọc xong bấm **✖ Đóng** |
| Chữ nhỏ quá | Trong lúc chọn vùng: lăn chuột để phóng to, giữ chuột phải kéo để di chuyển ảnh |
| OCR đọc sai chữ | Sửa ngay trong ô "Chữ nhận diện được", bản dịch tự cập nhật |
| Dịch giấy tờ | Chụp ảnh bằng điện thoại → gửi Zalo sang máy tính → chuột phải vào ảnh → *Sao chép* → bấm **📋 Dán** trong Dịch |
| Chép bản dịch | Bấm **📋 Chép bản dịch**, rồi dán vào nơi cần dùng |
| Chữ to/nhỏ | Bấm **A+** / **A−** |
| Thoát hẳn | ☰ → *Thoát hẳn chương trình* (nút ✖ của cửa sổ chỉ thu Dịch xuống khay hệ thống) |

Cần tra ngay trên giấy mà không có máy tính: ứng dụng **Google Dịch** trên điện thoại
có chế độ camera dịch trực tiếp, miễn phí.

## Khi gặp sự cố

- **"Không kết nối được máy chủ dịch"**: kiểm tra mạng.
- **"Máy chủ dịch đang bận"**: đợi vài phút rồi thử lại. Dịch đã tự đổi qua lại giữa 3 địa chỉ dự phòng
  trước khi báo lỗi này.
- **"Máy này chưa có bộ nhận diện chữ"**: vào Settings → Time & Language → Language, thêm
  *English (United States)*.
- **Tự kiểm tra:** mở Command Prompt rồi chạy `"%LOCALAPPDATA%\Programs\Dich\Dich.exe" --kiem-tra`.
  Kết quả được ghi vào `%APPDATA%\Dich\selftest.txt`, dòng cuối là `OK` nếu mọi thứ chạy tốt.

## Dành cho người phát triển

Yêu cầu: Windows 10/11, Python 3.12 trở lên.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python -m dich            # chạy thử
```

Tham số dòng lệnh: `--an` (chạy ngầm, dùng khi khởi động cùng Windows), `--chup` (mở thẳng chế độ
chọn vùng), `--kiem-tra` (tự kiểm tra OCR và dịch).

### Cấu trúc

```
dich/
  app.py          khởi động, khay hệ thống, chỉ chạy 1 bản, phím tắt, tự kiểm tra
  main_window.py  hộp chính: gõ/dán, mở ảnh, lịch sử, cài đặt
  capture.py      màn hình đóng băng để chọn vùng: zoom, kính lúp, bong bóng kết quả
  widgets.py      khung dịch dùng chung (ô chữ gốc + bản dịch + nút chép)
  translator.py   gọi Google Dịch miễn phí, có địa chỉ dự phòng khi bị giới hạn
  ocr.py          Windows OCR + ghép các dòng bị xuống hàng thành đoạn văn
  tasks.py        chạy OCR/gọi mạng ở luồng phụ để giao diện không bị đứng
  theme.py        màu tương phản cao, sáng/tối theo Windows
  settings.py     cài đặt, lịch sử (%APPDATA%\Dich), tự chạy, shortcut
tools/make_icon.py  vẽ lại biểu tượng
dich.spec           cấu hình đóng gói PyInstaller
installer.iss       bộ cài Inno Setup
```

### Đóng gói và phát hành

```powershell
pyinstaller dich.spec --noconfirm       # ra dist\Dich\Dich.exe
iscc installer.iss                      # (tùy chọn) ra Output\Dich-Setup.exe, cần Inno Setup 6
```

Cách phát hành bản mới lên GitHub: đẩy một tag, GitHub Actions sẽ tự build và tạo Release.

```powershell
git tag v1.0.1
git push origin v1.0.1
```

### Lưu ý

Endpoint dịch là endpoint không chính thức mà tiện ích trình duyệt của Google dùng. Nó miễn phí
nhưng không được cam kết ổn định. Nếu một ngày Google thay đổi, chỉ cần sửa `dich/translator.py`,
ví dụ chuyển sang Google Cloud Translation API chính thức (miễn phí 500.000 ký tự/tháng,
nhưng phải gắn thẻ thanh toán).
