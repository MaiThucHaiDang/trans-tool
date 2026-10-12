"""Màu sắc tương phản cao, tự đổi sáng/tối theo cài đặt của Windows."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette

LIGHT = {
    "bg": "#FFFFFF",
    "surface": "#F0F0F0",
    "text": "#000000",
    "muted": "#2B2B2B",
    "border": "#5A5A5A",
    "accent": "#0040A8",       # nút chính
    "accent_text": "#FFFFFF",
    "accent_hover": "#00307D",
    "highlight": "#0040A8",    # tiêu đề, khung chọn
    "error": "#B00020",
    "selection": "#FFD500",
    "selection_text": "#000000",
}

DARK = {
    "bg": "#121212",
    "surface": "#242424",
    "text": "#FFFFFF",
    "muted": "#E6E6E6",
    "border": "#B0B0B0",
    "accent": "#FFD500",
    "accent_text": "#000000",
    "accent_hover": "#FFE45C",
    "highlight": "#FFD500",
    "error": "#FF7A7A",
    "selection": "#FFD500",
    "selection_text": "#000000",
}


def is_dark() -> bool:
    hints = QGuiApplication.styleHints()
    return hints.colorScheme() == Qt.ColorScheme.Dark


def colors() -> dict:
    return DARK if is_dark() else LIGHT


def palette(c: dict) -> QPalette:
    p = QPalette()
    for role, key in [
        (QPalette.ColorRole.Window, "bg"), (QPalette.ColorRole.Base, "bg"),
        (QPalette.ColorRole.AlternateBase, "surface"),
        (QPalette.ColorRole.Button, "surface"),
        (QPalette.ColorRole.WindowText, "text"), (QPalette.ColorRole.Text, "text"),
        (QPalette.ColorRole.ButtonText, "text"), (QPalette.ColorRole.ToolTipBase, "bg"),
        (QPalette.ColorRole.ToolTipText, "text"),
        (QPalette.ColorRole.Highlight, "selection"),
        (QPalette.ColorRole.HighlightedText, "selection_text"),
        (QPalette.ColorRole.PlaceholderText, "muted"),
    ]:
        p.setColor(role, QColor(c[key]))
    return p


def stylesheet(c: dict, font_pt: int) -> str:
    return f"""
    QWidget {{
        font-family: "Segoe UI", Arial, sans-serif;
        font-size: {font_pt}pt;
        color: {c['text']};
    }}
    QWidget#Root, QFrame#ResultPanel, QDialog, QMenu {{
        background: {c['bg']};
    }}
    QFrame#ResultPanel {{
        border: 3px solid {c['highlight']};
        border-radius: 10px;
    }}
    QFrame#Bar {{
        background: {c['bg']};
        border: 2px solid {c['border']};
        border-radius: 8px;
    }}
    QLabel#Heading {{
        font-weight: bold;
        color: {c['highlight']};
    }}
    QLabel#Status {{ color: {c['muted']}; font-size: {max(font_pt - 3, 10)}pt; }}
    QLabel#Status[error="true"] {{ color: {c['error']}; font-weight: bold; }}
    QPlainTextEdit, QTextBrowser, QListWidget {{
        background: {c['bg']};
        border: 2px solid {c['border']};
        border-radius: 6px;
        padding: 6px;
        selection-background-color: {c['selection']};
        selection-color: {c['selection_text']};
    }}
    QPlainTextEdit:focus {{ border-color: {c['highlight']}; }}
    QListWidget::item {{ padding: 6px; border-bottom: 1px solid {c['surface']}; }}
    QListWidget::item:selected {{ background: {c['selection']}; color: {c['selection_text']}; }}
    QPushButton, QToolButton {{
        background: {c['surface']};
        border: 2px solid {c['border']};
        border-radius: 6px;
        padding: 6px 12px;
    }}
    QPushButton:hover, QToolButton:hover {{ border-color: {c['highlight']}; }}
    QPushButton:pressed, QToolButton:pressed {{ background: {c['border']}; }}
    QPushButton#Primary {{
        background: {c['accent']};
        color: {c['accent_text']};
        border-color: {c['accent']};
        font-weight: bold;
        padding: 10px 16px;
    }}
    QPushButton#Primary:hover {{ background: {c['accent_hover']}; }}
    QToolButton::menu-indicator {{ image: none; width: 0; }}
    QMenu {{ border: 2px solid {c['border']}; padding: 4px; }}
    QMenu::item {{ padding: 8px 24px; }}
    QMenu::item:selected {{ background: {c['selection']}; color: {c['selection_text']}; }}
    QToolTip {{ background: {c['bg']}; color: {c['text']}; border: 1px solid {c['border']}; }}
    QScrollBar:vertical {{ width: 16px; background: {c['surface']}; }}
    QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 6px; min-height: 30px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    """
