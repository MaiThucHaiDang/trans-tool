"""Khởi động ứng dụng: biểu tượng khay hệ thống, phím tắt, chỉ chạy một bản."""

import ctypes
import ctypes.wintypes
import getpass
import sys
from pathlib import Path

from PySide6.QtCore import QAbstractNativeEventFilter, QTimer
from PySide6.QtGui import QGuiApplication, QIcon, QImage
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from . import settings as cfg
from . import tasks, theme
from .capture import CaptureOverlay, grab_screen, screen_under_cursor
from .main_window import MainWindow

SERVER_NAME = f"Dich-{getpass.getuser()}"
CAPTURE_ARG = "--chup"  # mở thẳng chế độ chọn vùng

# Phím tắt toàn cục Ctrl+Alt+Q để chọn vùng (dành cho ai quen bàn phím).
HOTKEY_ID = 0xD1C
MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x1, 0x2, 0x4000
WM_HOTKEY = 0x0312
HIDE_DELAY_MS = 250  # chờ cửa sổ ẩn hẳn rồi mới chụp màn hình


def asset_path(name: str) -> str:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return str(base / "assets" / name)


class _HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def nativeEventFilter(self, event_type, message):
        if event_type == b"windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                QTimer.singleShot(0, self.callback)
                return True, 0
        return False, 0


class DichApp:
    def __init__(self, app: QApplication):
        self.app = app
        self.settings = cfg.Settings()
        self.history = cfg.History()
        self.overlay: CaptureOverlay | None = None
        self._tray_tip_shown = False

        app.setQuitOnLastWindowClosed(False)
        app.setStyle("Fusion")  # giao diện giống nhau trên Windows 10 và 11
        app.setWindowIcon(QIcon(asset_path("icon.ico")))
        tasks.init()

        self.window = MainWindow(self.settings, self.history)
        self.window.capture_requested.connect(self.start_capture)
        self.window.image_requested.connect(self.open_image)
        self.window.font_size_changed.connect(lambda _: self.apply_theme())
        self.window.quit_requested.connect(self.quit)
        self.window.hidden_to_tray.connect(self._on_hidden)

        self._build_tray()
        self.apply_theme()
        QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _: self.apply_theme())
        self._register_hotkey()

    # --- Giao diện chung ----------------------------------------------------

    def apply_theme(self):
        colors = theme.colors()
        size = self.settings.font_size
        self.app.setPalette(theme.palette(colors))
        self.app.setStyleSheet(theme.stylesheet(colors, size))
        self.window.panel.refresh()
        self.window.resize(max(self.window.width(), 34 * size), max(self.window.height(), 40 * size))
        if self.overlay:
            self.overlay.panel.refresh()

    def _build_tray(self):
        self.tray = QSystemTrayIcon(QIcon(asset_path("icon.ico")), self.app)
        self.tray.setToolTip("Dịch – bấm để mở")
        menu = QMenu()
        menu.addAction("Mở Dịch", self.show_window)
        menu.addAction("✂ Chọn vùng cần dịch", self.start_capture)
        menu.addSeparator()
        menu.addAction("Thoát hẳn", self.quit)
        self.tray.setContextMenu(menu)
        self._tray_menu = menu
        self.tray.activated.connect(self._on_tray)
        self.tray.show()

    def _on_tray(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            if self.window.isVisible() and self.window.isActiveWindow():
                self.window.hide()
            else:
                self.show_window()

    def _on_hidden(self):
        if not self._tray_tip_shown:
            self._tray_tip_shown = True
            self.tray.showMessage("Dịch vẫn đang chạy",
                                  "Bấm vào biểu tượng Dịch ở góc phải màn hình để mở lại.",
                                  QSystemTrayIcon.MessageIcon.Information, 4000)

    def show_window(self):
        if self.overlay:
            self.overlay.raise_()
            self.overlay.activateWindow()
            return
        self.window.bring_to_front()

    def quit(self):
        self._unregister_hotkey()
        self.tray.hide()
        self.app.quit()

    # --- Chọn vùng ----------------------------------------------------------

    def start_capture(self):
        if self.overlay:
            self.overlay.raise_()
            self.overlay.activateWindow()
            return
        self._restore_window = self.window.isVisible()
        self.window.hide()
        QTimer.singleShot(HIDE_DELAY_MS, self._grab_and_show)

    def _grab_and_show(self):
        screen = screen_under_cursor()
        self._show_overlay(grab_screen(screen), screen, from_screen=True)

    def open_image(self, image: QImage):
        if self.overlay:
            return
        self._restore_window = self.window.isVisible()
        image.setDevicePixelRatio(1.0)
        screen = self.window.screen() or screen_under_cursor()
        self.window.hide()
        self._show_overlay(image, screen, from_screen=False)

    def _show_overlay(self, image, screen, from_screen):
        overlay = CaptureOverlay(image, screen, from_screen)
        overlay.translated.connect(lambda tr: self.history.add(tr.source_text, tr.text))
        overlay.open_in_main.connect(self._open_in_main)
        overlay.finished.connect(self._on_overlay_finished)
        self.overlay = overlay
        overlay.show()
        overlay.raise_()
        overlay.activateWindow()
        overlay.setFocus()

    def _open_in_main(self, tr_or_text):
        self._restore_window = True
        self.window.show_translation(tr_or_text)

    def _on_overlay_finished(self, last_result):
        self.overlay = None
        if last_result is not None and not self.window.panel.source_text().strip():
            self.window.show_translation(last_result)
        if self._restore_window:
            self.window.bring_to_front()

    # --- Phím tắt -----------------------------------------------------------

    def _register_hotkey(self):
        self._hotkey_filter = _HotkeyFilter(self.start_capture)
        self.app.installNativeEventFilter(self._hotkey_filter)
        ctypes.windll.user32.RegisterHotKey(None, HOTKEY_ID,
                                            MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ord("Q"))

    def _unregister_hotkey(self):
        ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)

    # --- Lần chạy đầu -------------------------------------------------------

    def first_run(self):
        if self.settings.get("first_run_done"):
            return
        self.settings.set("first_run_done", True)
        cfg.set_autostart(True)
        if cfg.is_frozen():
            cfg.create_shortcuts()
        QMessageBox.information(
            self.window, "Chào mừng đến với Dịch",
            "Dịch đã sẵn sàng và sẽ tự chạy mỗi khi bật máy.\n\n"
            "• Biểu tượng Dịch nằm ở góc phải màn hình, cạnh đồng hồ.\n"
            "• Muốn ghim lên thanh taskbar: chuột phải vào nút Dịch ở thanh taskbar "
            "→ “Pin to taskbar” (Ghim vào thanh tác vụ).\n"
            "• Bấm ☰ → Hướng dẫn sử dụng để xem cách dùng.")

    # --- Chỉ chạy một bản ---------------------------------------------------

    def listen(self):
        QLocalServer.removeServer(SERVER_NAME)
        self.server = QLocalServer(self.app)
        self.server.newConnection.connect(self._on_connection)
        self.server.listen(SERVER_NAME)

    def _on_connection(self):
        sock = self.server.nextPendingConnection()
        if sock is None:
            return
        def read():
            command = bytes(sock.readAll()).decode(errors="ignore").strip()
            sock.disconnectFromServer()
            if command == "capture":
                self.start_capture()
            else:
                self.show_window()
        if sock.bytesAvailable():
            read()
        else:
            sock.readyRead.connect(read)


def _send_to_running(command: str) -> bool:
    """Nếu Dịch đang chạy thì nhờ bản đó mở cửa sổ, trả về True."""
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if not sock.waitForConnected(500):
        return False
    ctypes.windll.user32.AllowSetForegroundWindow(-1)  # cho bản kia được lên trước
    sock.write(command.encode())
    sock.flush()
    sock.waitForBytesWritten(500)
    sock.disconnectFromServer()
    return True


def main() -> int:
    args = sys.argv[1:]
    app = QApplication(sys.argv)
    app.setApplicationName(cfg.APP_ID)
    app.setApplicationDisplayName(cfg.APP_NAME)

    command = "capture" if CAPTURE_ARG in args else "show"
    if _send_to_running(command):
        return 0

    dich = DichApp(app)
    dich.listen()
    if CAPTURE_ARG in args:
        QTimer.singleShot(300, dich.start_capture)
    elif cfg.HIDDEN_ARG not in args:
        dich.window.resize(34 * dich.settings.font_size, 40 * dich.settings.font_size)
        dich.window.bring_to_front()
        QTimer.singleShot(300, dich.first_run)
    return app.exec()
