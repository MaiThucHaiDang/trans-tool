"""Hộp chính: gõ/dán chữ để dịch, nút chọn vùng màn hình, lịch sử, cài đặt."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QGuiApplication, QImage, QImageReader
from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QMenu, QMessageBox,
                               QPushButton, QToolButton, QVBoxLayout, QWidget)

from . import settings as cfg
from .translator import Translation
from .widgets import TranslatePanel

IMAGE_FILTER = "Ảnh (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff)"

HELP_TEXT = """<h3>Cách dùng Dịch</h3>
<p><b>1. Gõ hoặc dán chữ:</b> gõ chữ tiếng Anh vào ô trên, bản dịch tự hiện ở ô dưới.
Đã chép chữ ở đâu đó thì bấm <b>📋 Dán</b>.</p>
<p><b>2. Dịch chữ trên màn hình:</b> bấm <b>✂ Chọn vùng cần dịch</b>. Màn hình đứng yên lại,
giữ chuột trái kéo một khung quanh chữ, chỉnh khung bằng các ô vuông nhỏ, rồi bấm <b>✔ Dịch</b>.
Lăn chuột để phóng to nếu chữ nhỏ. Đọc xong bấm <b>✖ Đóng</b>.</p>
<p><b>3. Dịch giấy tờ:</b> chụp ảnh tờ giấy bằng điện thoại, gửi qua Zalo sang máy tính.
Trên máy tính, chuột phải vào ảnh → <i>Sao chép</i>, rồi bấm <b>📋 Dán</b> trong Dịch.
Hoặc bấm <b>🖼 Mở ảnh</b> để chọn file ảnh.</p>
<p><b>Mẹo:</b> gõ tiếng Việt thì Dịch tự dịch sang tiếng Anh.
Bấm <b>A+</b> / <b>A−</b> để chữ to/nhỏ. Đóng cửa sổ thì Dịch vẫn chạy ở góc phải
màn hình (cạnh đồng hồ), bấm vào biểu tượng đó để mở lại.</p>"""


class HistoryDialog(QDialog):
    picked = Signal(dict)

    def __init__(self, history: cfg.History, parent=None):
        super().__init__(parent)
        self.history = history
        self.setWindowTitle("Lịch sử tra cứu")
        self.resize(parent.width() if parent else 600, parent.height() if parent else 600)
        self.list = QListWidget()
        self.list.setWordWrap(True)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.itemClicked.connect(self._pick)
        for item in history.items:
            src = item["source"].replace("\n", " ")
            dst = item["translated"].replace("\n", " ")
            w = QListWidgetItem(f"{_short(src)}\n→ {_short(dst)}")
            w.setData(Qt.ItemDataRole.UserRole, item)
            self.list.addItem(w)
        if not history.items:
            self.list.addItem("(Chưa có lượt tra nào)")

        clear = QPushButton("🗑 Xóa lịch sử")
        clear.clicked.connect(self._clear)
        close = QPushButton("Đóng", objectName="Primary")
        close.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addWidget(clear)
        buttons.addStretch(1)
        buttons.addWidget(close)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Bấm vào một dòng để xem lại:", objectName="Heading"))
        layout.addWidget(self.list)
        layout.addLayout(buttons)

    def _pick(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.picked.emit(data)
            self.accept()

    def _clear(self):
        box = QMessageBox(QMessageBox.Icon.Question, "Xóa lịch sử",
                          "Xóa toàn bộ lịch sử tra cứu?", parent=self)
        yes = box.addButton("Xóa", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Không", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is yes:
            self.history.clear()
            self.list.clear()
            self.list.addItem("(Chưa có lượt tra nào)")


def _short(text: str, limit: int = 120) -> str:
    return text if len(text) <= limit else text[:limit - 1] + "…"


class MainWindow(QWidget):
    capture_requested = Signal()
    image_requested = Signal(QImage)
    font_size_changed = Signal(int)
    quit_requested = Signal()
    hidden_to_tray = Signal()

    def __init__(self, settings: cfg.Settings, history: cfg.History):
        super().__init__(objectName="Root")
        self.settings = settings
        self.history = history
        self.setWindowTitle(cfg.APP_NAME)
        self.setAcceptDrops(True)

        capture = QPushButton("✂ Chọn vùng cần dịch", objectName="Primary")
        capture.setToolTip("Khoanh một vùng trên màn hình để dịch chữ trong đó")
        capture.clicked.connect(self.capture_requested)
        paste = QPushButton("📋 Dán")
        paste.setToolTip("Dán chữ hoặc ảnh vừa sao chép")
        paste.clicked.connect(self.paste)
        open_image = QPushButton("🖼 Mở ảnh")
        open_image.setToolTip("Chọn một file ảnh (ví dụ ảnh chụp giấy tờ) để dịch")
        open_image.clicked.connect(self.open_image)

        history = QPushButton("🕘 Lịch sử")
        history.setToolTip("Xem lại các lượt tra trước")
        history.clicked.connect(self.show_history)
        smaller = QPushButton("A−")
        smaller.setToolTip("Chữ nhỏ lại")
        smaller.clicked.connect(lambda: self._change_font(-1))
        bigger = QPushButton("A+")
        bigger.setToolTip("Chữ to lên")
        bigger.clicked.connect(lambda: self._change_font(+1))
        menu_button = QToolButton(text="☰")
        menu_button.setToolTip("Cài đặt và hướng dẫn")
        menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu_button.setMenu(self._build_menu())

        row1 = QHBoxLayout()
        row1.addWidget(capture, 1)
        row1.addWidget(paste)
        row1.addWidget(open_image)
        row2 = QHBoxLayout()
        row2.addWidget(history)
        row2.addStretch(1)
        row2.addWidget(smaller)
        row2.addWidget(bigger)
        row2.addWidget(menu_button)

        self.panel = TranslatePanel("Gõ hoặc dán chữ cần dịch:",
                                    "Ví dụ: Two-factor authentication", stretch=(1, 2))
        self.panel.translated.connect(self._remember)
        clear = QPushButton("✖ Xóa chữ")
        clear.clicked.connect(self.clear)
        self.panel.buttons.addWidget(clear)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addLayout(row1)
        layout.addLayout(row2)
        layout.addWidget(self.panel, 1)

    def _build_menu(self) -> QMenu:
        menu = QMenu(self)
        self.autostart_action = QAction("Tự chạy khi bật máy", menu, checkable=True)
        self.autostart_action.toggled.connect(cfg.set_autostart)
        menu.aboutToShow.connect(
            lambda: self.autostart_action.setChecked(cfg.autostart_enabled()))
        menu.addAction(self.autostart_action)
        if cfg.is_frozen():
            menu.addAction("Tạo lại biểu tượng ngoài Desktop", self._make_shortcuts)
        menu.addAction("Hướng dẫn sử dụng", self.show_help)
        menu.addSeparator()
        menu.addAction("Thoát hẳn chương trình", self.quit_requested)
        return menu

    # --- Hành động ----------------------------------------------------------

    def bring_to_front(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.panel.source.setFocus()

    def clear(self):
        self.panel.set_source("")
        self.panel.source.setFocus()

    def paste(self):
        mime = QGuiApplication.clipboard().mimeData()
        if not self._accept_mime(mime):
            self.panel.set_status("Chưa có gì để dán. Hãy sao chép chữ hoặc ảnh trước.",
                                  error=True)

    def open_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn ảnh cần dịch",
                                              str(Path.home() / "Downloads"), IMAGE_FILTER)
        if path:
            self._load_image_file(path)

    def show_history(self):
        dialog = HistoryDialog(self.history, self)
        dialog.picked.connect(lambda item: self.panel.show_result(Translation(
            item["source"], item["translated"], item.get("source_lang", "auto"),
            item.get("target_lang", "vi"))))
        dialog.exec()

    def show_help(self):
        QMessageBox.information(self, "Hướng dẫn sử dụng", HELP_TEXT)

    def show_translation(self, tr_or_text):
        """Đưa kết quả từ màn hình chụp về hộp chính."""
        if isinstance(tr_or_text, Translation):
            self.panel.show_result(tr_or_text)
        elif tr_or_text:
            self.panel.set_source(tr_or_text)

    def _make_shortcuts(self):
        if cfg.create_shortcuts():
            QMessageBox.information(self, cfg.APP_NAME,
                                    "Đã tạo biểu tượng “Dịch” ngoài Desktop.\n\n"
                                    "Muốn ghim lên thanh taskbar: chuột phải vào biểu tượng "
                                    "→ “Pin to taskbar” (Ghim vào thanh tác vụ).")

    def _change_font(self, delta: int):
        size = max(cfg.FONT_MIN, min(cfg.FONT_MAX, self.settings.font_size + delta))
        self.settings.set("font_size", size)
        self.font_size_changed.emit(size)

    def _remember(self, tr: Translation):
        self.history.add(tr.source_text, tr.text)

    # --- Dán / kéo thả ------------------------------------------------------

    def _accept_mime(self, mime) -> bool:
        if mime is None:
            return False
        if mime.hasImage():
            image = QImage(mime.imageData())
            if not image.isNull():
                self.image_requested.emit(image)
                return True
        if mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile() and self._load_image_file(url.toLocalFile()):
                    return True
        if mime.hasText() and mime.text().strip():
            self.panel.set_source(mime.text())
            return True
        return False

    def _load_image_file(self, path: str) -> bool:
        reader = QImageReader(path)
        reader.setAutoTransform(True)  # ảnh điện thoại thường bị xoay
        image = reader.read()
        if image.isNull():
            self.panel.set_status("Không mở được file này. Hãy chọn file ảnh (JPG, PNG…).",
                                  error=True)
            return False
        self.image_requested.emit(image)
        return True

    def dragEnterEvent(self, e):
        mime = e.mimeData()
        if mime.hasImage() or mime.hasUrls() or mime.hasText():
            e.acceptProposedAction()

    def dropEvent(self, e):
        if self._accept_mime(e.mimeData()):
            e.acceptProposedAction()

    def closeEvent(self, e):
        # Nút X chỉ ẩn cửa sổ; chương trình vẫn chạy ở khay hệ thống.
        e.ignore()
        self.hide()
        self.hidden_to_tray.emit()
