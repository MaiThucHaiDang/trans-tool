"""Khung dịch dùng chung cho hộp chính và bong bóng kết quả khi chụp vùng."""

import html

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
                               QTextBrowser, QVBoxLayout, QWidget)

from . import tasks, theme
from .translator import Translation, language_name

TYPING_DELAY_MS = 600  # dịch sau khi ngừng gõ chừng này mili-giây


def translation_html(tr: Translation) -> str:
    c = theme.colors()
    body = "<br>".join(html.escape(line) for line in tr.text.split("\n"))
    parts = [f"<div style='font-size:115%'>{body}</div>"]
    if tr.dictionary:
        parts.append(f"<p style='margin-top:14px; color:{c['highlight']}; "
                     f"font-weight:bold'>Các nghĩa khác:</p>")
        for entry in tr.dictionary:
            terms = ", ".join(html.escape(t) for t in entry.terms)
            parts.append(f"<p style='margin:4px 0'><b>{html.escape(entry.pos)}:</b> {terms}</p>")
    return "".join(parts)


class TranslatePanel(QWidget):
    """Ô chữ gốc (sửa được) + ô bản dịch + dòng trạng thái + nút chép."""

    translated = Signal(object)  # Translation

    def __init__(self, source_title: str, placeholder: str = "",
                 stretch: tuple[int, int] = (2, 3), parent=None):
        super().__init__(parent)
        self._request_id = 0
        self._last_text = None
        self._result: Translation | None = None

        self.source_title = QLabel(source_title, objectName="Heading")
        self.source = QPlainTextEdit()
        self.source.setPlaceholderText(placeholder)
        self.source.textChanged.connect(self._on_text_changed)

        self.result_title = QLabel("Bản dịch:", objectName="Heading")
        self.status = QLabel("", objectName="Status")
        self.status.setWordWrap(True)
        self.result = QTextBrowser()
        self.result.setOpenLinks(False)

        self.copy_button = QPushButton("📋 Chép bản dịch")
        self.copy_button.setToolTip("Chép bản dịch để dán vào chỗ khác")
        self.copy_button.clicked.connect(self.copy_result)
        self.copy_button.setEnabled(False)

        self.buttons = QHBoxLayout()
        self.buttons.addWidget(self.copy_button)
        self.buttons.addStretch(1)

        title_row = QHBoxLayout()
        title_row.addWidget(self.result_title)
        title_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.source_title)
        layout.addWidget(self.source, stretch[0])
        layout.addLayout(title_row)
        layout.addWidget(self.result, stretch[1])
        layout.addWidget(self.status)
        layout.addLayout(self.buttons)

        self._timer = QTimer(self, singleShot=True, interval=TYPING_DELAY_MS)
        self._timer.timeout.connect(self.translate_now)

    # --- Trạng thái ---------------------------------------------------------

    def set_status(self, text: str, error: bool = False) -> None:
        self.status.setText(text)
        self.status.setProperty("error", error)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def set_source(self, text: str) -> None:
        """Đặt chữ gốc và dịch ngay, không chờ."""
        self.source.blockSignals(True)
        self.source.setPlainText(text)
        self.source.blockSignals(False)
        self.translate_now()

    def source_text(self) -> str:
        return self.source.toPlainText()

    def result_text(self) -> str:
        return self._result.text if self._result else ""

    def show_result(self, tr: Translation) -> None:
        """Hiện một bản dịch có sẵn (ví dụ lấy từ lịch sử) mà không gọi mạng."""
        self._request_id += 1
        self.source.blockSignals(True)
        self.source.setPlainText(tr.source_text)
        self.source.blockSignals(False)
        self._last_text = tr.source_text.strip()
        self._apply(tr)

    def refresh(self) -> None:
        """Vẽ lại bản dịch (khi đổi giao diện sáng/tối)."""
        if self._result:
            self.result.setHtml(translation_html(self._result))

    # --- Dịch ---------------------------------------------------------------

    def _on_text_changed(self) -> None:
        self._timer.start()

    def translate_now(self) -> None:
        self._timer.stop()
        text = self.source_text().strip()
        if text == self._last_text:
            return
        self._last_text = text
        self._request_id += 1
        if not text:
            self._result = None
            self.result.clear()
            self.copy_button.setEnabled(False)
            self.result_title.setText("Bản dịch:")
            self.set_status("")
            return
        request_id = self._request_id
        self.set_status("⏳ Đang dịch…")
        tasks.run(tasks.translate, text,
                  on_done=lambda tr: self._on_done(request_id, tr),
                  on_error=lambda msg: self._on_error(request_id, msg))

    def _on_done(self, request_id: int, tr: Translation) -> None:
        if request_id != self._request_id:
            return  # đã có yêu cầu mới hơn
        self._apply(tr)
        self.translated.emit(tr)

    def _apply(self, tr: Translation) -> None:
        self._result = tr
        self.result_title.setText(
            f"Bản dịch ({language_name(tr.source_lang)} → {language_name(tr.target_lang)}):")
        self.result.setHtml(translation_html(tr))
        self.copy_button.setEnabled(bool(tr.text))
        self.set_status("")

    def _on_error(self, request_id: int, message: str) -> None:
        if request_id != self._request_id:
            return
        self._last_text = None  # cho phép thử lại với cùng nội dung
        self.set_status("⚠ " + message, error=True)

    def copy_result(self) -> None:
        if self._result and self._result.text:
            QGuiApplication.clipboard().setText(self._result.text)
            self.set_status("✔ Đã chép bản dịch. Chuột phải → Dán (Paste) ở nơi cần dùng.")
