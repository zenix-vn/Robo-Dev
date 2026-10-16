"""Thành phần giao diện dùng chung."""
from PySide6.QtCore import (Property, QEasingCurve, QEvent, QObject, QPoint, QPropertyAnimation, QRectF, QSize, Qt,
                            QTimer, Signal)
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QAbstractButton, QAbstractScrollArea, QAbstractSpinBox, QApplication, QButtonGroup,
                               QColorDialog, QComboBox, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
                               QPushButton, QSizePolicy, QSlider, QToolButton, QVBoxLayout, QWidget)

from robodev.ui import icons, theme


# ----------------------------------------------------------------------------------------
# Tiện ích
# ----------------------------------------------------------------------------------------
def repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def set_prop(widget, name, value):
    if widget.property(name) != value:
        widget.setProperty(name, value)
        repolish(widget)


def label(text="", role=None, wrap=False, selectable=False):
    lab = QLabel(text)
    if role:
        lab.setProperty("role", role)
    if wrap:
        lab.setWordWrap(True)
    if selectable:
        lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return lab


def hbox(*items, spacing=8, margins=(0, 0, 0, 0)):
    lay = QHBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    for item in items:
        _add(lay, item)
    return lay


def vbox(*items, spacing=8, margins=(0, 0, 0, 0)):
    lay = QVBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    for item in items:
        _add(lay, item)
    return lay


def _add(lay, item):
    if item is None:
        return
    if item == "stretch":
        lay.addStretch(1)
    elif isinstance(item, int):
        lay.addSpacing(item)
    elif isinstance(item, QWidget):
        lay.addWidget(item)
    else:
        lay.addLayout(item)


def button(text, kind=None, icon=None, size=None, tooltip=None, on_click=None):
    btn = QPushButton(text)
    btn.setCursor(Qt.PointingHandCursor)
    if kind:
        btn.setProperty("kind", kind)
    if size:
        btn.setProperty("size", size)
    if icon:
        color = "#FFFFFF" if kind == "primary" else theme.c("primary") if kind == "link" else theme.c("text_soft")
        btn.setIcon(icons.icon(icon, color, 16))
        btn.setIconSize(QSize(16, 16))
    if tooltip:
        btn.setToolTip(tooltip)
    if on_click:
        btn.clicked.connect(on_click)
    return btn


def tool(icon_name, tooltip, on_click=None, color=None, size=18):
    btn = QToolButton()
    btn.setCursor(Qt.PointingHandCursor)
    btn.setIcon(icons.icon(icon_name, color or theme.c("muted"), size))
    btn.setIconSize(QSize(size, size))
    btn.setToolTip(tooltip)
    if on_click:
        btn.clicked.connect(on_click)
    return btn


def icon_label(name, color, size=18):
    lab = QLabel()
    lab.setPixmap(icons.pixmap(name, color, size))
    lab.setFixedSize(size, size)
    return lab


class WheelGuard(QObject):
    """Ô chọn, ô số, thanh trượt chỉ đổi giá trị bằng con lăn khi đã được bấm chọn (có focus).

    Chưa chọn thì con lăn cuộn trang như bình thường, tránh lỡ tay đổi chân GPIO khi cuộn qua.
    """
    GUARDED = (QComboBox, QAbstractSpinBox, QSlider)

    def eventFilter(self, obj, event):  # noqa: N802
        if not isinstance(obj, self.GUARDED):
            return False
        if event.type() == QEvent.Polish:
            obj.setFocusPolicy(Qt.StrongFocus)
        elif event.type() == QEvent.Wheel and not obj.hasFocus():
            area = obj.parentWidget()
            while area is not None and not isinstance(area, QAbstractScrollArea):
                area = area.parentWidget()
            if area is not None:
                QApplication.sendEvent(area.verticalScrollBar(), event)
            return True
        return False


def clear_layout(layout):
    """Gỡ và hủy mọi widget trong layout (ẩn ngay để không vẽ chồng trước khi bị hủy)."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


def divider():
    line = QFrame()
    line.setObjectName("Divider")
    return line


# ----------------------------------------------------------------------------------------
# Khối giao diện
# ----------------------------------------------------------------------------------------
class Card(QFrame):
    def __init__(self, title=None, subtitle=None, icon=None, padding=20, spacing=14, shadow=True):
        super().__init__()
        self.setProperty("card", "true")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(padding, padding, padding, padding)
        self.body.setSpacing(spacing)
        self.header = None
        if title:
            self.title_label = label(title, "h2")
            texts = vbox(self.title_label, spacing=2)
            if subtitle:
                self.subtitle_label = label(subtitle, "muted", wrap=True)
                texts.addWidget(self.subtitle_label)
            self.header = QHBoxLayout()
            self.header.setSpacing(12)
            if icon:
                badge = QLabel()
                badge.setFixedSize(36, 36)
                badge.setAlignment(Qt.AlignCenter)
                badge.setPixmap(icons.pixmap(icon, theme.c("primary"), 20))
                badge.setStyleSheet(f"background: {theme.c('primary_soft')}; border-radius: 10px;")
                self.header.addWidget(badge, 0, Qt.AlignTop)
            self.header.addLayout(texts, 1)
            self.body.addLayout(self.header)
        if shadow:
            effect = QGraphicsDropShadowEffect(self)
            effect.setBlurRadius(18)
            effect.setOffset(0, 2)
            effect.setColor(QColor(16, 24, 40, 14 if not theme.is_dark() else 60))
            self.setGraphicsEffect(effect)

    def add(self, item, stretch=0):
        if isinstance(item, QWidget):
            self.body.addWidget(item, stretch)
        else:
            self.body.addLayout(item, stretch)
        return item

    def add_action(self, widget):
        """Nút/ô điều khiển ở góc phải tiêu đề."""
        if self.header is not None:
            self.header.addWidget(widget, 0, Qt.AlignTop)


class Banner(QFrame):
    ICONS = {"info": "info", "warning": "alert", "error": "x-circle", "success": "check-circle"}
    TEXT = {"info": "info_text", "warning": "warning_text", "error": "danger_text", "success": "success_text"}

    def __init__(self, text="", tone="info", action=None):
        super().__init__()
        self.icon = QLabel()
        self.text = label(text, wrap=True)
        self.text.setTextFormat(Qt.RichText)
        self.text.setOpenExternalLinks(True)
        lay = hbox(self.icon, spacing=10, margins=(14, 11, 14, 11))
        lay.addWidget(self.text, 1)
        if action:
            lay.addWidget(action, 0, Qt.AlignVCenter)
        self.icon.setAlignment(Qt.AlignTop)
        self.setLayout(lay)
        self.set(text, tone)

    def set(self, text, tone=None):
        if tone:
            self.setProperty("banner", tone)
            self.text.setProperty("banner", tone)
            self.icon.setPixmap(icons.pixmap(self.ICONS[tone], theme.c(self.TEXT[tone]), 18))
            repolish(self)
            repolish(self.text)
        self.text.setText(text)


class Chip(QLabel):
    def __init__(self, text="", tone="neutral"):
        super().__init__(text)
        self.setProperty("chip", tone)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

    def set(self, text, tone=None):
        self.setText(text)
        if tone:
            set_prop(self, "chip", tone)


class Toggle(QAbstractButton):
    """Công tắc bật/tắt có hiệu ứng trượt."""

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(40, 22)
        self._offset = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)

    def _animate(self, on):
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def setChecked(self, on):  # noqa: N802 - API Qt
        super().setChecked(on)
        if not self.signalsBlocked():
            return
        self._offset = 1.0 if on else 0.0
        self.update()

    def get_offset(self):
        return self._offset

    def set_offset(self, value):
        self._offset = value
        self.update()

    offset = Property(float, get_offset, set_offset)

    def sizeHint(self):  # noqa: N802
        return QSize(40, 22)

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        off = QColor(theme.c("border_strong"))
        on = QColor(theme.c("primary"))
        if not self.isEnabled():
            off = QColor(theme.c("border"))
            on = QColor(theme.c("faint"))
        t = self._offset
        track = QColor(int(off.red() + (on.red() - off.red()) * t), int(off.green() + (on.green() - off.green()) * t),
                       int(off.blue() + (on.blue() - off.blue()) * t))
        p.setPen(Qt.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(QRectF(0, 0, 40, 22), 11, 11)
        p.setBrush(QColor("#FFFFFF"))
        x = 3 + t * 18
        p.drawEllipse(QRectF(x, 3, 16, 16))
        p.end()


class Segmented(QFrame):
    """Nhóm nút chọn một (kiểu iOS)."""
    changed = Signal(str)

    def __init__(self, options):
        super().__init__()
        self.setObjectName("Segmented")
        lay = hbox(spacing=2, margins=(3, 3, 3, 3))
        self.setLayout(lay)
        self.group = QButtonGroup(self)
        self.buttons = {}
        for key, text in options:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setProperty("segment", "true")
            btn.setCursor(Qt.PointingHandCursor)
            self.group.addButton(btn)
            self.buttons[key] = btn
            lay.addWidget(btn)
            btn.clicked.connect(lambda _=False, k=key: self.changed.emit(k))
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

    def set(self, key):
        if key in self.buttons:
            self.buttons[key].setChecked(True)

    def value(self):
        for key, btn in self.buttons.items():
            if btn.isChecked():
                return key
        return None


class ColorButton(QPushButton):
    changed = Signal(list)

    def __init__(self, rgb=(255, 255, 255), title="Chọn màu"):
        super().__init__()
        self.title = title
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(34, 26)
        self.rgb = list(rgb)
        self.clicked.connect(self._pick)
        self._paint()

    def set(self, rgb):
        self.rgb = list(rgb)
        self._paint()

    def _paint(self):
        r, g, b = self.rgb
        self.setToolTip(f"#{r:02X}{g:02X}{b:02X}")
        self.setStyleSheet(f"QPushButton {{ background: rgb({r},{g},{b}); border: 1px solid {theme.c('border_strong')};"
                           f" border-radius: 7px; padding: 0; min-height: 0; }}"
                           f"QPushButton:hover {{ border: 2px solid {theme.c('primary')}; }}")

    def _pick(self):
        color = QColorDialog.getColor(QColor(*self.rgb), self, self.title)
        if color.isValid():
            self.set([color.red(), color.green(), color.blue()])
            self.changed.emit(self.rgb)


class StepList(QWidget):
    """Danh sách bước có trạng thái: wait / run / ok / fail / skip."""
    ICON = {"wait": ("circle", "faint"), "run": ("refresh", "primary"), "ok": ("check-circle", "success"),
            "fail": ("x-circle", "danger"), "skip": ("skip", "warning")}

    def __init__(self, steps):
        super().__init__()
        self.rows = {}
        lay = vbox(spacing=0)
        self.setLayout(lay)
        for i, (key, title) in enumerate(steps):
            icon = QLabel()
            icon.setFixedSize(22, 22)
            name = label(title, "h3")
            detail = label("", "faint", wrap=True)
            texts = vbox(name, detail, spacing=1)
            row = hbox(icon, spacing=12, margins=(0, 7, 0, 7))
            row.addLayout(texts, 1)
            row.setAlignment(icon, Qt.AlignTop)
            lay.addLayout(row)
            self.rows[key] = (icon, name, detail)
            self.set(key, "wait")
        self._spin = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def set(self, key, state, text=""):
        if key not in self.rows:
            return
        icon, name, detail = self.rows[key]
        ic, color = self.ICON.get(state, self.ICON["wait"])
        icon.setPixmap(icons.pixmap(ic, theme.c(color), 22))
        icon.setProperty("state", state)
        name.setStyleSheet(f"color: {theme.c('faint') if state == 'wait' else theme.c('text')};")
        detail.setText(text)
        detail.setVisible(bool(text))
        if state == "run" and not self._timer.isActive():
            self._timer.start(90)

    def reset(self):
        for key in self.rows:
            self.set(key, "wait")

    def _tick(self):
        running = [k for k, (icon, _, _) in self.rows.items() if icon.property("state") == "run"]
        if not running:
            self._timer.stop()
            return
        self._spin = (self._spin + 30) % 360
        from PySide6.QtGui import QPixmap, QTransform
        base = icons.pixmap("refresh", theme.c("primary"), 22)
        for key in running:
            icon = self.rows[key][0]
            pm = base.transformed(QTransform().rotate(self._spin), Qt.SmoothTransformation)
            pm.setDevicePixelRatio(base.devicePixelRatio())
            canvas = QPixmap(base.size())
            canvas.setDevicePixelRatio(base.devicePixelRatio())
            canvas.fill(Qt.transparent)
            painter = QPainter(canvas)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            w = pm.width() / pm.devicePixelRatio()
            off = (22 - w) / 2
            painter.drawPixmap(QPoint(int(off), int(off)), pm)
            painter.end()
            icon.setPixmap(canvas)


class Toast(QFrame):
    """Thông báo nhỏ ở góc dưới, tự ẩn."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.icon = QLabel()
        self.text = QLabel()
        self.text.setObjectName("ToastText")
        self.setLayout(hbox(self.icon, self.text, spacing=10, margins=(14, 10, 16, 10)))
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text, tone="ok", ms=3200):
        name = {"ok": "check-circle", "warning": "alert", "error": "x-circle", "info": "info"}[tone]
        color = {"ok": "#32D583", "warning": "#FDB022", "error": "#F97066", "info": "#7CD4FD"}[tone]
        self.icon.setPixmap(icons.pixmap(name, color, 18))
        self.text.setText(text)
        self.adjustSize()
        parent = self.parentWidget()
        lift = getattr(parent, "toast_lift", lambda: 0)()
        self.move(parent.width() - self.width() - 28, parent.height() - self.height() - 28 - lift)
        self.raise_()
        self.show()
        self._timer.start(ms)


class Dot(QWidget):
    """Chấm tròn trạng thái."""

    def __init__(self, color="#98A2B3", size=9):
        super().__init__()
        self.color = color
        self.setFixedSize(size, size)

    def set(self, color):
        self.color = color
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self.color))
        p.drawEllipse(self.rect().adjusted(0, 0, -1, -1))
        p.end()


class LevelBar(QWidget):
    """Thanh đo mức (mic)."""

    def __init__(self):
        super().__init__()
        self.value = 0.0
        self.setFixedHeight(10)

    def set(self, value):
        self.value = max(0.0, min(1.0, value))
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.c("border")))
        p.drawRoundedRect(r, 5, 5)
        if self.value > 0:
            fill = QRectF(r.x(), r.y(), r.width() * self.value, r.height())
            color = theme.c("success") if self.value < 0.8 else theme.c("warning")
            p.setBrush(QColor(color))
            p.drawRoundedRect(fill, 5, 5)
        p.setPen(QPen(QColor(theme.c("border_strong")), 1))
        p.end()


def form_row(title, widget, hint=None):
    """Hàng nhãn + điều khiển, có dòng gợi ý nhỏ phía dưới nhãn."""
    texts = vbox(label(title, "h3"), spacing=1)
    if hint:
        texts.addWidget(label(hint, "faint", wrap=True))
    row = QHBoxLayout()
    row.setSpacing(16)
    row.addLayout(texts, 1)
    if isinstance(widget, QWidget):
        row.addWidget(widget, 0, Qt.AlignVCenter)
    else:
        row.addLayout(widget)
    return row
