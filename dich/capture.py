"""Màn hình "đóng băng" để khoanh vùng chữ cần dịch (giống Snipping Tool).

Ảnh nền là ảnh chụp màn hình (hoặc ảnh người dùng dán/mở). Người dùng
kéo chuột vẽ khung, chỉnh khung bằng các ô vuông ở góc/cạnh, lăn chuột để
phóng to/thu nhỏ, kéo chuột phải để di chuyển ảnh. Bấm "Dịch" thì chữ trong
khung được nhận diện và dịch, kết quả hiện ngay cạnh khung.

Toạ độ: khung chọn lưu theo điểm ảnh của ảnh gốc; hiển thị qua phép biến
đổi view = ảnh * scale + offset (đơn vị điểm logic của Qt).
"""

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (QColor, QCursor, QGuiApplication, QImage, QPainter,
                           QPainterPath, QPen, QPixmap)
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout, QWidget)

from . import tasks
from .widgets import TranslatePanel

ZOOM_STEP = 1.25
HANDLE = 12             # cạnh ô vuông chỉnh khung (điểm logic)
HANDLE_HIT = 10         # vùng bắt chuột quanh ô vuông
DRAG_THRESHOLD = 4      # phải kéo quá chừng này mới tính là kéo
MIN_SELECTION = 6       # khung nhỏ hơn (điểm ảnh) thì bỏ qua
MAGNIFIER = 170         # kích thước kính lúp
MAGNIFY = 4             # độ phóng của kính lúp
FRAME_COLOR = QColor("#FFD500")
DIM_COLOR = QColor(0, 0, 0, 120)

# (dx, dy): -1 = cạnh trái/trên, 1 = cạnh phải/dưới, 0 = không đổi
HANDLES = [(-1, -1), (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0)]

HINT_IDLE = "Giữ chuột trái và kéo để khoanh vùng chữ cần dịch"
HINT_SELECTED = "Kéo ô vuông ở góc để chỉnh khung • kéo bên trong để di chuyển • rồi bấm ✔ Dịch"
HINT_RESULT = "Đọc xong bấm ✖ Đóng để quay lại làm việc"
HINT_ZOOM = "Lăn chuột: phóng to/thu nhỏ • Giữ chuột phải kéo: di chuyển ảnh"


class _Mode:
    NONE, NEW, MOVE, RESIZE, PAN = range(5)


class CaptureOverlay(QWidget):
    translated = Signal(object)      # mỗi lần có bản dịch mới (để lưu lịch sử)
    open_in_main = Signal(object)    # người dùng muốn tra tiếp trong hộp chính
    finished = Signal(object)        # đóng overlay, kèm bản dịch cuối (hoặc None)

    def __init__(self, image: QImage, screen, from_screen: bool):
        super().__init__(None, Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.image = image
        self.pixmap = QPixmap.fromImage(image)
        self.from_screen = from_screen
        self.sel: QRectF | None = None
        self.last_result = None
        self._done = False

        self._mode = _Mode.NONE
        self._press_view = QPointF()
        self._press_image = QPointF()
        self._press_sel = QRectF()
        self._press_offset = QPointF()
        self._handle = (0, 0)
        self._dragging = False
        self._hover = None  # vị trí chuột để vẽ kính lúp

        self.setScreen(screen)
        self.setGeometry(screen.geometry())

        self._build_top_bar()
        self._build_action_bar()
        self._build_result_panel()

        self._reset_view()
        if not from_screen:
            # Ảnh dán/mở: chọn sẵn cả ảnh, người dùng có thể bấm Dịch luôn.
            self.sel = QRectF(0, 0, image.width(), image.height())
        self._update_ui()

    # --- Dựng giao diện -----------------------------------------------------

    def _button(self, text, slot, primary=False, tip=None):
        b = QPushButton(text)
        if primary:
            b.setObjectName("Primary")
        if tip:
            b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(slot)
        return b

    def _build_top_bar(self):
        bar = QFrame(self, objectName="Bar")
        self.hint = QLabel(HINT_IDLE)
        self.hint.setWordWrap(False)
        zoom_hint = QLabel(HINT_ZOOM, objectName="Status")
        text = QVBoxLayout()
        text.setSpacing(0)
        text.addWidget(self.hint)
        text.addWidget(zoom_hint)
        row = QHBoxLayout(bar)
        row.setContentsMargins(12, 8, 8, 8)
        row.addLayout(text)
        row.addSpacing(12)
        row.addWidget(self._button("🔍+", lambda: self._zoom_center(ZOOM_STEP), tip="Phóng to"))
        row.addWidget(self._button("🔍−", lambda: self._zoom_center(1 / ZOOM_STEP), tip="Thu nhỏ"))
        row.addWidget(self._button("⤢ Vừa màn hình", self._fit_view,
                                   tip="Trở về kích thước ban đầu"))
        row.addWidget(self._button("✖ Thoát", self.close, tip="Thoát (phím Esc)"))
        self.top_bar = bar

    def _build_action_bar(self):
        bar = QFrame(self, objectName="Bar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(6, 6, 6, 6)
        row.addWidget(self._button("✔ Dịch", self.translate_selection, primary=True,
                                   tip="Nhận diện và dịch chữ trong khung (phím Enter)"))
        row.addWidget(self._button("✖ Bỏ chọn", self._clear_selection))
        self.action_bar = bar

    def _build_result_panel(self):
        frame = QFrame(self, objectName="ResultPanel")
        self.panel = TranslatePanel("Chữ nhận diện được (sửa lại nếu sai):")
        self.panel.translated.connect(self._on_translated)
        open_main = self._button("↗ Mở trong hộp chính", self._open_in_main,
                                 tip="Mở bản dịch trong cửa sổ chính để tra tiếp")
        self.panel.buttons.insertWidget(1, open_main)
        row2 = QHBoxLayout()
        row2.addWidget(self._button("✂ Chọn vùng khác", self._clear_selection))
        row2.addStretch(1)
        row2.addWidget(self._button("✖ Đóng", self.close, primary=True,
                                    tip="Đóng và quay lại làm việc (phím Esc)"))
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.addWidget(self.panel)
        layout.addLayout(row2)
        self.result_frame = frame
        frame.hide()

    # --- Chuyển đổi toạ độ --------------------------------------------------

    def to_view(self, p: QPointF) -> QPointF:
        return p * self.scale + self.offset

    def to_image(self, p: QPointF) -> QPointF:
        return (p - self.offset) / self.scale

    def view_rect(self, r: QRectF) -> QRectF:
        return QRectF(self.to_view(r.topLeft()), self.to_view(r.bottomRight()))

    def _image_bounds(self) -> QRectF:
        return QRectF(0, 0, self.image.width(), self.image.height())

    def _clamp_point(self, p: QPointF) -> QPointF:
        return QPointF(min(max(p.x(), 0), self.image.width()),
                       min(max(p.y(), 0), self.image.height()))

    # --- Phóng to / di chuyển ảnh -------------------------------------------

    def _reset_view(self):
        w, h = self.width(), self.height()
        iw, ih = self.image.width(), self.image.height()
        if self.from_screen:
            self.base_scale = w / iw
        else:
            # Chừa chỗ trên/dưới cho thanh công cụ, không phóng ảnh nhỏ quá 100%.
            self.base_scale = min((w - 80) / iw, (h - 200) / ih, 1.0)
        self.min_scale = self.base_scale * (1.0 if self.from_screen else 0.5)
        self.max_scale = max(self.base_scale * 8, 4.0)
        self.scale = self.base_scale
        self.offset = QPointF(0, 0)
        self._clamp_offset()

    def _clamp_offset(self):
        def axis(off, content, view):
            if content <= view:
                return (view - content) / 2
            return min(0.0, max(view - content, off))
        self.offset = QPointF(
            axis(self.offset.x(), self.image.width() * self.scale, self.width()),
            axis(self.offset.y(), self.image.height() * self.scale, self.height()))

    def _zoom_at(self, view_pt: QPointF, factor: float):
        new_scale = min(self.max_scale, max(self.min_scale, self.scale * factor))
        if abs(new_scale - self.scale) < 1e-9:
            return
        ip = self.to_image(view_pt)
        self.scale = new_scale
        self.offset = view_pt - ip * new_scale
        self._clamp_offset()
        self._update_ui()

    def _zoom_center(self, factor: float):
        center = self.view_rect(self.sel).center() if self.sel else QPointF(self.rect().center())
        self._zoom_at(center, factor)

    def _fit_view(self):
        self._reset_view()
        self._update_ui()

    # --- Khung chọn ---------------------------------------------------------

    def _handle_rects(self) -> list[tuple[tuple[int, int], QRectF]]:
        if not self.sel:
            return []
        r = self.view_rect(self.sel)
        out = []
        for dx, dy in HANDLES:
            x = {-1: r.left(), 0: r.center().x(), 1: r.right()}[dx]
            y = {-1: r.top(), 0: r.center().y(), 1: r.bottom()}[dy]
            out.append(((dx, dy), QRectF(x - HANDLE / 2, y - HANDLE / 2, HANDLE, HANDLE)))
        return out

    def _hit_handle(self, p: QPointF):
        for hid, rect in self._handle_rects():
            if rect.adjusted(-HANDLE_HIT, -HANDLE_HIT, HANDLE_HIT, HANDLE_HIT).contains(p):
                return hid
        return None

    def _clear_selection(self):
        self.sel = None
        self.result_frame.hide()
        self._update_ui()
        self.setFocus()

    def _cursor_for(self, p: QPointF):
        hid = self._hit_handle(p)
        if hid:
            return {(-1, -1): Qt.CursorShape.SizeFDiagCursor, (1, 1): Qt.CursorShape.SizeFDiagCursor,
                    (1, -1): Qt.CursorShape.SizeBDiagCursor, (-1, 1): Qt.CursorShape.SizeBDiagCursor,
                    (0, -1): Qt.CursorShape.SizeVerCursor, (0, 1): Qt.CursorShape.SizeVerCursor,
                    }.get(hid, Qt.CursorShape.SizeHorCursor)
        if self.sel and self.view_rect(self.sel).contains(p):
            return Qt.CursorShape.SizeAllCursor
        return Qt.CursorShape.CrossCursor

    # --- Chuột và bàn phím --------------------------------------------------

    def mousePressEvent(self, e):
        p = e.position()
        self._press_view = p
        self._press_image = self.to_image(p)
        self._press_offset = QPointF(self.offset)
        self._press_sel = QRectF(self.sel) if self.sel else QRectF()
        self._dragging = False
        if e.button() in (Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
            self._mode = _Mode.PAN
        elif e.button() == Qt.MouseButton.LeftButton:
            hid = self._hit_handle(p)
            if hid:
                self._mode, self._handle = _Mode.RESIZE, hid
            elif self.sel and self.view_rect(self.sel).contains(p):
                self._mode = _Mode.MOVE
            else:
                self._mode = _Mode.NEW

    def mouseMoveEvent(self, e):
        p = e.position()
        self._hover = p
        if self._mode == _Mode.NONE:
            self.setCursor(self._cursor_for(p))
            self.update()
            return
        if not self._dragging:
            if (p - self._press_view).manhattanLength() < DRAG_THRESHOLD:
                return
            self._dragging = True
            if self._mode != _Mode.PAN:
                self.result_frame.hide()  # khung đổi thì kết quả cũ không còn đúng

        ip = self.to_image(p)
        bounds = self._image_bounds()
        if self._mode == _Mode.PAN:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.offset = self._press_offset + (p - self._press_view)
            self._clamp_offset()
        elif self._mode == _Mode.NEW:
            self.sel = QRectF(self._clamp_point(self._press_image),
                              self._clamp_point(ip)).normalized()
        elif self._mode == _Mode.MOVE:
            r = self._press_sel.translated(ip - self._press_image)
            r.moveLeft(min(max(r.left(), 0), bounds.width() - r.width()))
            r.moveTop(min(max(r.top(), 0), bounds.height() - r.height()))
            self.sel = r
        elif self._mode == _Mode.RESIZE:
            r = QRectF(self._press_sel)
            ip = self._clamp_point(ip)
            dx, dy = self._handle
            if dx == -1:
                r.setLeft(ip.x())
            elif dx == 1:
                r.setRight(ip.x())
            if dy == -1:
                r.setTop(ip.y())
            elif dy == 1:
                r.setBottom(ip.y())
            self.sel = r.normalized()
        self._update_ui()

    def mouseReleaseEvent(self, e):
        mode, dragged = self._mode, self._dragging
        self._mode = _Mode.NONE
        self._dragging = False
        if mode == _Mode.PAN and not dragged and e.button() == Qt.MouseButton.RightButton:
            # Bấm chuột phải (không kéo) = bỏ khung đang chọn.
            if self.sel:
                self._clear_selection()
        if self.sel and (self.sel.width() < MIN_SELECTION or self.sel.height() < MIN_SELECTION):
            self.sel = None
        self.setCursor(self._cursor_for(e.position()))
        self._update_ui()

    def mouseDoubleClickEvent(self, e):
        if (e.button() == Qt.MouseButton.LeftButton and self.sel
                and self.view_rect(self.sel).contains(e.position())):
            self.translate_selection()

    def wheelEvent(self, e):
        steps = e.angleDelta().y() / 120
        if steps:
            self._zoom_at(e.position(), ZOOM_STEP ** steps)

    def leaveEvent(self, e):
        self._hover = None
        self.update()

    def keyPressEvent(self, e):
        key = e.key()
        if key == Qt.Key.Key_Escape:
            self.close()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.sel:
            self.translate_selection()
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self._zoom_center(ZOOM_STEP)
        elif key == Qt.Key.Key_Minus:
            self._zoom_center(1 / ZOOM_STEP)
        else:
            super().keyPressEvent(e)

    # --- Dịch ---------------------------------------------------------------

    def translate_selection(self):
        if not self.sel:
            return
        crop = self.image.copy(self.sel.toAlignedRect().intersected(self.image.rect()))
        if crop.isNull():
            return
        self.panel.set_source("")
        self.panel.set_status("⏳ Đang nhận diện chữ…")
        self._position_result_panel()
        self.result_frame.show()
        self._update_ui()
        self._ocr_id = getattr(self, "_ocr_id", 0) + 1
        ocr_id = self._ocr_id
        tasks.run(tasks.recognize, crop,
                  on_done=lambda text: self._on_ocr(ocr_id, text),
                  on_error=lambda msg: self._on_ocr_error(ocr_id, msg))

    def _on_ocr(self, ocr_id, text):
        if ocr_id == self._ocr_id and self.result_frame.isVisible():
            self.panel.set_source(text)

    def _on_ocr_error(self, ocr_id, message):
        if ocr_id == self._ocr_id:
            self.panel.set_status("⚠ " + message, error=True)

    def _on_translated(self, tr):
        self.last_result = tr
        self.translated.emit(tr)

    def _open_in_main(self):
        self.open_in_main.emit(self.last_result or self.panel.source_text())
        self.close()

    def closeEvent(self, e):
        if not self._done:
            self._done = True
            self.finished.emit(self.last_result)
        super().closeEvent(e)

    # --- Bố trí các thanh công cụ -------------------------------------------

    def _position_result_panel(self):
        """Đặt bong bóng kết quả cạnh khung chọn, không đè lên chữ đang dịch."""
        area = QRectF(self.rect()).adjusted(12, 12, -12, -12)
        font_px = self.fontInfo().pixelSize() or 20
        want_w = min(max(26 * font_px, 460), area.width())
        want_h = min(max(22 * font_px, 400), area.height())
        min_w, min_h = min(420, want_w), min(320, want_h)
        sel = self.view_rect(self.sel) if self.sel else QRectF(area.center(), QSize(0, 0))
        gap = 16

        def clamp(v, lo, hi):
            return max(lo, min(v, hi))

        space_right = area.right() - sel.right() - gap
        space_left = sel.left() - gap - area.left()
        space_below = area.bottom() - sel.bottom() - gap
        space_above = sel.top() - gap - area.top()
        chosen = None
        if max(space_right, space_left) >= min_w:          # bên phải hoặc trái
            w = min(want_w, max(space_right, space_left))
            x = sel.right() + gap if space_right >= space_left else sel.left() - gap - w
            y = clamp(sel.top(), area.top(), area.bottom() - want_h)
            chosen = QRectF(x, y, w, want_h)
        elif max(space_below, space_above) >= min_h:       # bên dưới hoặc trên
            h = min(want_h, max(space_below, space_above))
            y = sel.bottom() + gap if space_below >= space_above else sel.top() - gap - h
            x = clamp(sel.left(), area.left(), area.right() - want_w)
            chosen = QRectF(x, y, want_w, h)
        else:  # khung gần kín màn hình: đặt ở góc dưới bên phải
            chosen = QRectF(area.right() - want_w, area.bottom() - want_h, want_w, want_h)
        self.result_frame.setGeometry(chosen.toAlignedRect())
        self.result_frame.raise_()

    def _update_ui(self):
        result_shown = self.result_frame.isVisible()
        self.hint.setText(HINT_RESULT if result_shown else
                          HINT_SELECTED if self.sel else HINT_IDLE)

        # Thanh trên cùng: ẩn khi đang kéo, né xuống dưới nếu đè lên khung.
        self.top_bar.adjustSize()
        bw = min(self.top_bar.sizeHint().width(), self.width() - 24)
        bh = self.top_bar.sizeHint().height()
        top = QRect((self.width() - bw) // 2, 12, bw, bh)
        bottom = QRect((self.width() - bw) // 2, self.height() - bh - 12, bw, bh)
        sel_view = self.view_rect(self.sel) if self.sel else QRectF()
        avoid = [sel_view] + ([QRectF(self.result_frame.geometry())] if result_shown else [])
        place = top
        if any(QRectF(top).intersects(r) for r in avoid if not r.isEmpty()):
            if not any(QRectF(bottom).intersects(r) for r in avoid if not r.isEmpty()):
                place = bottom
        self.top_bar.setGeometry(place)
        self.top_bar.setVisible(not self._dragging)

        # Nút Dịch/Bỏ chọn ngay dưới (hoặc trên) khung chọn.
        show_actions = bool(self.sel) and not result_shown and not self._dragging
        self.action_bar.setVisible(show_actions)
        if show_actions:
            self.action_bar.adjustSize()
            s = self.action_bar.sizeHint()
            x = int(sel_view.right()) - s.width()
            y = int(sel_view.bottom()) + 10
            if y + s.height() > self.height() - 8:
                y = int(sel_view.top()) - s.height() - 10
            if y < 8:
                y = int(sel_view.bottom()) - s.height() - 10
            x = min(max(x, 8), self.width() - s.width() - 8)
            self.action_bar.setGeometry(x, y, s.width(), s.height())
            self.action_bar.raise_()
        self.update()

    # --- Vẽ -----------------------------------------------------------------

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#000000"))
        p.save()
        p.translate(self.offset)
        p.scale(self.scale, self.scale)
        if self.scale < 1:
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawPixmap(0, 0, self.pixmap)
        p.restore()

        # Làm tối mọi chỗ trừ khung đang chọn.
        dim = QPainterPath()
        dim.addRect(QRectF(self.rect()))
        if self.sel:
            r = self.view_rect(self.sel)
            dim.addRect(r)
        dim.setFillRule(Qt.FillRule.OddEvenFill)
        p.fillPath(dim, DIM_COLOR)

        if self.sel:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(QPen(QColor("#000000"), 5))
            p.drawRect(r)
            p.setPen(QPen(FRAME_COLOR, 3))
            p.drawRect(r)
            if not self.result_frame.isVisible():
                p.setPen(QPen(QColor("#000000"), 1.5))
                p.setBrush(QColor("#FFFFFF"))
                for _, hr in self._handle_rects():
                    p.drawRect(hr)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        self._paint_magnifier(p)

    def _paint_magnifier(self, p: QPainter):
        """Kính lúp nhỏ cạnh con trỏ để khoanh chính xác chữ nhỏ."""
        if (self._hover is None or self.result_frame.isVisible()
                or self._mode in (_Mode.PAN, _Mode.MOVE)
                or (self.sel and self._mode == _Mode.NONE)):
            return
        center = self.to_image(self._hover)
        if not self._image_bounds().contains(center):
            return
        size = MAGNIFIER
        src_size = size / (self.scale * MAGNIFY)
        src = QRectF(center.x() - src_size / 2, center.y() - src_size / 2, src_size, src_size)

        pos = self._hover + QPointF(28, 28)
        if pos.x() + size > self.width():
            pos.setX(self._hover.x() - 28 - size)
        if pos.y() + size > self.height():
            pos.setY(self._hover.y() - 28 - size)
        dst = QRectF(pos, QSize(size, size))

        p.fillRect(dst, QColor("#000000"))
        p.drawPixmap(dst, self.pixmap, src)
        p.setPen(QPen(QColor(255, 0, 0, 200), 1))
        c = dst.center()
        p.drawLine(QPointF(dst.left(), c.y()), QPointF(dst.right(), c.y()))
        p.drawLine(QPointF(c.x(), dst.top()), QPointF(c.x(), dst.bottom()))
        p.setPen(QPen(QColor("#000000"), 3))
        p.drawRect(dst)
        p.setPen(QPen(FRAME_COLOR, 2))
        p.drawRect(dst)


def grab_screen(screen) -> QImage:
    """Chụp toàn bộ một màn hình ở độ phân giải thật (đã tính scale DPI)."""
    image = screen.grabWindow(0).toImage()
    image.setDevicePixelRatio(1.0)
    return image


def screen_under_cursor():
    return QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
