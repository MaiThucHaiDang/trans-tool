"""Chạy việc nặng (OCR, gọi mạng) ở luồng phụ để giao diện không bị đứng."""

from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QColor, QImage, QPainter

from . import ocr, translator

_pool = ThreadPoolExecutor(max_workers=3)


class _Bridge(QObject):
    """Chuyển kết quả từ luồng phụ về luồng giao diện qua signal của Qt."""

    finished = Signal(object, object, object)

    def __init__(self):
        super().__init__()
        self.finished.connect(self._dispatch, Qt.ConnectionType.QueuedConnection)

    @Slot(object, object, object)
    def _dispatch(self, callbacks, result, error):
        on_done, on_error = callbacks
        try:
            if error is None:
                on_done(result)
            elif on_error is not None:
                on_error(str(error))
        except RuntimeError:
            pass  # cửa sổ nhận kết quả đã bị đóng trong lúc chờ


_bridge = None


def init() -> None:
    """Gọi một lần từ luồng giao diện, sau khi tạo QApplication."""
    global _bridge
    _bridge = _Bridge()


def run(fn, *args, on_done, on_error=None) -> None:
    def job():
        try:
            result, error = fn(*args), None
        except Exception as e:
            result, error = None, e
        _bridge.finished.emit((on_done, on_error), result, error)
    _pool.submit(job)


# --- Các việc cụ thể ---------------------------------------------------------

def translate(text: str) -> translator.Translation:
    return translator.translate(text)


def _prepare_for_ocr(image: QImage) -> QImage:
    """Phóng to vùng nhỏ và thêm viền để OCR đọc chính xác hơn."""
    image = image.convertToFormat(QImage.Format.Format_ARGB32)
    limit = ocr.max_image_dimension() - 40
    longest = max(image.width(), image.height())
    if image.height() < 80:
        factor = 3.0
    elif image.height() < 400 or image.width() < 600:
        factor = 2.0
    else:
        factor = 1.0
    factor = min(factor, limit / longest)
    if abs(factor - 1.0) > 0.01:
        image = image.scaled(round(image.width() * factor), round(image.height() * factor),
                             Qt.AspectRatioMode.IgnoreAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)

    pad = 16
    padded = QImage(image.width() + 2 * pad, image.height() + 2 * pad,
                    QImage.Format.Format_ARGB32)
    padded.fill(QColor(image.pixel(0, 0)))
    painter = QPainter(padded)
    painter.drawImage(pad, pad, image)
    painter.end()
    return padded


def recognize(image: QImage) -> str:
    img = _prepare_for_ocr(image)
    # Định dạng ARGB32 trên máy little-endian nằm trong bộ nhớ là BGRA.
    data = bytes(img.constBits())[: img.bytesPerLine() * img.height()]
    text = ocr.recognize(data, img.width(), img.height())
    if not text.strip():
        raise ocr.OcrError("Không tìm thấy chữ trong vùng đã chọn.\n"
                           "Hãy thử khoanh rộng hơn hoặc phóng to rồi chọn lại.")
    return text
