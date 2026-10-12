"""Nhận diện chữ trong ảnh bằng Windows OCR (Windows.Media.Ocr).

Có sẵn trên Windows 10/11, chạy offline, miễn phí. Ngôn ngữ đọc được phụ
thuộc gói ngôn ngữ đã cài trên máy; chữ Latin (tiếng Anh) thì gói en-US hoặc
vi-VN đều đọc được.
"""

import asyncio

from winrt.windows.globalization import Language
from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.storage.streams import DataWriter

# Thứ tự ưu tiên chọn bộ nhận diện; văn bản cần dịch chủ yếu là tiếng Anh.
PREFERRED_LANGUAGES = ["en-US", "en-GB", "en"]

# Kết thúc dòng bằng các dấu này thì coi như hết câu, không nối với dòng sau.
SENTENCE_END = tuple(".!?:;。")


class OcrError(Exception):
    """Lỗi có thông báo thân thiện, hiển thị thẳng cho người dùng."""


_engine = None


def _get_engine() -> OcrEngine:
    global _engine
    if _engine is not None:
        return _engine
    available = [l.language_tag for l in OcrEngine.available_recognizer_languages]
    for tag in PREFERRED_LANGUAGES:
        for avail in available:
            if avail.lower().startswith(tag.lower()):
                _engine = OcrEngine.try_create_from_language(Language(avail))
                if _engine:
                    return _engine
    _engine = OcrEngine.try_create_from_user_profile_languages()
    if _engine is None and available:
        _engine = OcrEngine.try_create_from_language(Language(available[0]))
    if _engine is None:
        raise OcrError("Máy này chưa có bộ nhận diện chữ của Windows.\n"
                       "Vào Settings → Time & Language → Language, thêm "
                       "English (United States) rồi thử lại.")
    return _engine


def max_image_dimension() -> int:
    return OcrEngine.max_image_dimension


def _line_box(line):
    words = list(line.words)
    if not words:
        return 0.0, 0.0, 0.0
    top = min(w.bounding_rect.y for w in words)
    bottom = max(w.bounding_rect.y + w.bounding_rect.height for w in words)
    left = min(w.bounding_rect.x for w in words)
    return top, bottom, left


def _join_lines(lines) -> str:
    """Ghép các dòng OCR thành đoạn văn.

    Văn bản hành chính hay bị xuống dòng giữa câu; nếu để nguyên, mỗi dòng
    sẽ bị dịch rời rạc. Vì vậy dòng nào chưa kết thúc câu và nằm sát dòng
    trước thì nối vào bằng dấu cách; khoảng trống lớn thì tách đoạn mới.
    """
    paragraphs: list[str] = []
    prev_bottom = None
    for line in lines:
        text = line.text.strip()
        if not text:
            continue
        top, bottom, _ = _line_box(line)
        height = max(bottom - top, 1.0)
        gap = None if prev_bottom is None else top - prev_bottom
        if (paragraphs and not paragraphs[-1].endswith(SENTENCE_END)
                and gap is not None and gap < height * 0.9):
            paragraphs[-1] += " " + text
        else:
            paragraphs.append(text)
        prev_bottom = bottom
    return "\n".join(paragraphs)


async def _recognize_async(bgra: bytes, width: int, height: int) -> str:
    writer = DataWriter()
    writer.write_bytes(bgra)
    bitmap = SoftwareBitmap.create_copy_from_buffer(
        writer.detach_buffer(), BitmapPixelFormat.BGRA8, width, height)
    result = await _get_engine().recognize_async(bitmap)
    return _join_lines(result.lines)


def recognize(bgra: bytes, width: int, height: int) -> str:
    """Nhận diện chữ từ ảnh BGRA 8-bit (4 byte/điểm ảnh, không padding).

    Hàm chạy đồng bộ, nên gọi từ luồng phụ để không đứng giao diện.
    """
    try:
        return asyncio.run(_recognize_async(bgra, width, height))
    except OcrError:
        raise
    except Exception as e:  # lỗi COM/WinRT không có kiểu cụ thể
        raise OcrError(f"Không nhận diện được chữ: {e}") from e
