"""Dịch văn bản qua endpoint miễn phí của Google Translate (không cần API key).

Đây là endpoint mà các tiện ích trình duyệt của Google dùng, không phải
Cloud Translation API chính thức, nên không tốn phí nhưng cũng không được
cam kết ổn định. Nếu một ngày nó đổi định dạng, chỉ cần sửa file này.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

# Các cặp (địa chỉ, client) cùng trả về một định dạng. Google thỉnh thoảng
# chặn tạm một cặp (lỗi 429), khi đó thử cặp kế tiếp.
ENDPOINTS = [
    ("https://translate.googleapis.com/translate_a/single", "dict-chrome-ex"),
    ("https://clients5.google.com/translate_a/single", "dict-chrome-ex"),
    ("https://translate.googleapis.com/translate_a/single", "gtx"),
]
TIMEOUT = 10  # giây
_preferred = 0  # cặp chạy được gần nhất, lần sau thử trước

# Tên tiếng Việt của các ngôn ngữ hay gặp; mã lạ thì hiện nguyên mã.
LANGUAGE_NAMES = {
    "vi": "Tiếng Việt", "en": "Tiếng Anh", "fr": "Tiếng Pháp",
    "de": "Tiếng Đức", "es": "Tiếng Tây Ban Nha", "it": "Tiếng Ý",
    "pt": "Tiếng Bồ Đào Nha", "ru": "Tiếng Nga", "ja": "Tiếng Nhật",
    "ko": "Tiếng Hàn", "zh-CN": "Tiếng Trung", "zh-TW": "Tiếng Trung (phồn thể)",
    "th": "Tiếng Thái", "lo": "Tiếng Lào", "km": "Tiếng Khmer",
    "id": "Tiếng Indonesia", "ms": "Tiếng Mã Lai", "nl": "Tiếng Hà Lan",
    "la": "Tiếng Latinh",
}

# Tên tiếng Việt của từ loại trong phần từ điển.
POS_NAMES = {
    "noun": "Danh từ", "verb": "Động từ", "adjective": "Tính từ",
    "adverb": "Trạng từ", "pronoun": "Đại từ", "preposition": "Giới từ",
    "conjunction": "Liên từ", "interjection": "Thán từ",
    "abbreviation": "Viết tắt", "phrase": "Cụm từ", "prefix": "Tiền tố",
    "suffix": "Hậu tố", "article": "Mạo từ", "particle": "Tiểu từ",
}


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code, code)


class TranslateError(Exception):
    """Lỗi có thông báo thân thiện, hiển thị thẳng cho người dùng."""


@dataclass
class DictEntry:
    pos: str            # từ loại, đã dịch sang tiếng Việt
    terms: list[str]    # các nghĩa


@dataclass
class Translation:
    source_text: str
    text: str
    source_lang: str
    target_lang: str
    dictionary: list[DictEntry] = field(default_factory=list)


def _request_once(endpoint: str, client: str, text: str, source: str, target: str) -> list:
    params = [("client", client), ("sl", source), ("tl", target),
              ("dt", "t"), ("dt", "bd")]
    url = endpoint + "?" + urllib.parse.urlencode(params)
    # Gửi văn bản trong body (POST) để không bị giới hạn độ dài URL.
    body = urllib.parse.urlencode({"q": text}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _request(text: str, source: str, target: str) -> list:
    global _preferred
    order = ENDPOINTS[_preferred:] + ENDPOINTS[:_preferred]
    last_error = None
    for endpoint, client in order:
        try:
            data = _request_once(endpoint, client, text, source, target)
            _preferred = ENDPOINTS.index((endpoint, client))
            return data
        except urllib.error.HTTPError as e:
            last_error = e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise TranslateError("Không kết nối được máy chủ dịch. "
                                 "Vui lòng kiểm tra kết nối mạng.") from e
        except ValueError as e:
            last_error = e
    if isinstance(last_error, urllib.error.HTTPError) and last_error.code == 429:
        raise TranslateError("Máy chủ dịch đang bận (dịch quá nhiều trong thời gian ngắn). "
                             "Vui lòng đợi vài phút rồi thử lại.") from last_error
    raise TranslateError("Máy chủ dịch đang gặp lỗi, vui lòng thử lại sau.") from last_error


def _parse(data: list, text: str, target: str) -> Translation:
    sentences = data[0] or []
    translated = "".join(s[0] for s in sentences if s and s[0])
    source_lang = data[2] if len(data) > 2 and isinstance(data[2], str) else "auto"

    dictionary = []
    if len(data) > 1 and data[1]:
        for entry in data[1]:
            try:
                pos, terms = entry[0], entry[1]
            except (IndexError, TypeError):
                continue
            if terms:
                dictionary.append(DictEntry(POS_NAMES.get(pos, pos), list(terms[:6])))
    return Translation(text, translated, source_lang, target, dictionary)


def translate(text: str, target: str = "vi", fallback: str = "en") -> Translation:
    """Dịch `text` sang `target`, tự nhận diện ngôn ngữ nguồn.

    Nếu văn bản vốn đã là ngôn ngữ đích (ví dụ gõ tiếng Việt) thì dịch
    sang `fallback` thay vì trả lại y nguyên.
    """
    text = text.strip()
    if not text:
        return Translation("", "", "", target)
    result = _parse(_request(text, "auto", target), text, target)
    if result.source_lang == target and fallback and fallback != target:
        result = _parse(_request(text, target, fallback), text, fallback)
        result.source_lang = target
    return result
