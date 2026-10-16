"""Hình devkit ESP32-S3 với hai hàng chân, tô màu theo cách gán chân của hồ sơ."""
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from robodev.core import catalog, pins
from robodev.ui import theme

ROW = 23
PAD = 6.5
BOARD_W = 230
TAG_W = 112
TOP = 104


class DevkitView(QWidget):
    pinClicked = Signal(int)

    def __init__(self):
        super().__init__()
        self.board = catalog.board()
        self.hw = {}
        self.active = None          # (module, signal) đang chọn chân bằng cách bấm lên hình
        self.hover = None
        self.setMouseTracking(True)
        rows = max(len(self.board.left), len(self.board.right))
        self._h = TOP + rows * ROW + 58
        self._w = TAG_W * 2 + BOARD_W + 8
        self.setMinimumSize(int(self._w * 0.6), int(self._h * 0.6))
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

    def sizeHint(self):  # noqa: N802
        return QSize(self._w, self._h)

    def _transform(self):
        """Tỉ lệ và độ dời để vẽ hình kích thước gốc vừa với khung hiện tại."""
        scale = min(1.0, self.width() / self._w, self.height() / self._h)
        dx = (self.width() - self._w * scale) / 2
        return scale, dx, 0.0

    def _to_local(self, pos):
        scale, dx, dy = self._transform()
        return QPointF((pos.x() - dx) / scale, (pos.y() - dy) / scale)

    def set_hw(self, hw):
        self.hw = hw
        self.update()

    def set_active(self, active):
        self.active = active
        self.update()

    # Hình học ---------------------------------------------------------------------------
    def _origin(self):
        return TAG_W + 4, 4

    def _pin_pos(self, side, index):
        x0, y0 = self._origin()
        x = x0 + (24 if side == "left" else BOARD_W - 24)
        return QPointF(x, y0 + TOP + index * ROW)

    def _pins(self):
        for side, names in (("left", self.board.left), ("right", self.board.right)):
            for i, name in enumerate(names):
                yield side, i, name, self._pin_pos(side, i)

    def _hit(self, pos):
        for side, i, name, p in self._pins():
            if name.isdigit() and abs(pos.x() - p.x()) < 11 and abs(pos.y() - p.y()) < ROW / 2:
                return int(name)
        for side, i, name, p in self._pins():
            if not name.isdigit():
                continue
            tag = self._tag_rect(side, p)
            if tag.contains(pos):
                return int(name)
        return None

    def _tag_rect(self, side, p):
        x0, _ = self._origin()
        if side == "left":
            return QRectF(x0 - TAG_W + 4, p.y() - 9, TAG_W - 12, 18)
        return QRectF(x0 + BOARD_W + 8, p.y() - 9, TAG_W - 12, 18)

    # Chuột -----------------------------------------------------------------------------
    def mouseMoveEvent(self, event):  # noqa: N802
        gpio = self._hit(self._to_local(event.position()))
        if gpio != self.hover:
            self.hover = gpio
            self.update()
        if gpio is None:
            QToolTip.hideText()
            self.setCursor(Qt.ArrowCursor)
            return
        self.setCursor(Qt.PointingHandCursor if self.active else Qt.ArrowCursor)
        kind, detail = pins.pin_state(gpio, self.hw)
        lines = [f"<b>{self.board.label(gpio)}</b>"]
        if kind in ("used", "conflict") and detail:
            for mod_key, sig_key in detail:
                mod = catalog.module(mod_key)
                lines.append(f"{mod.name} · {mod.signal(sig_key).label}")
            for rule in self.board.rules_for(gpio, self.hw.get("variant", "usb"), detail[0][0]):
                lines.append(f"<span style='color:#FEC84B'>{rule.text.format(gpio=gpio)}</span>")
        elif detail:
            lines += detail
        else:
            lines.append("Chân trống, dùng được.")
        if self.active:
            mod = catalog.module(self.active[0])
            lines.append(f"<i>Bấm để gán cho {mod.name} {mod.signal(self.active[1]).label}</i>")
        QToolTip.showText(event.globalPosition().toPoint(), "<br>".join(lines), self)

    def leaveEvent(self, event):  # noqa: N802
        self.hover = None
        self.update()

    def mousePressEvent(self, event):  # noqa: N802
        gpio = self._hit(self._to_local(event.position()))
        if gpio is not None and event.button() == Qt.LeftButton:
            self.pinClicked.emit(gpio)

    # Vẽ --------------------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        scale, dx, dy = self._transform()
        p.translate(dx, dy)
        p.scale(scale, scale)
        x0, y0 = self._origin()
        rows = max(len(self.board.left), len(self.board.right))
        board = QRectF(x0, y0, BOARD_W, TOP + rows * ROW + 40)

        # Thân mạch
        p.setPen(QPen(QColor(theme.c("board_edge")), 1.2))
        p.setBrush(QColor(theme.c("board")))
        p.drawRoundedRect(board, 14, 14)

        # Module ESP32-S3 (khối kim loại + anten)
        module = QRectF(x0 + 52, y0 + 14, BOARD_W - 104, 76)
        p.setPen(QPen(QColor("#5B6B84"), 1))
        p.setBrush(QColor("#2B3a52"))
        p.drawRoundedRect(module, 6, 6)
        antenna = QRectF(module.x(), module.y(), module.width(), 26)
        p.setBrush(QColor("#22314a"))
        p.drawRoundedRect(antenna, 6, 6)
        p.setPen(QPen(QColor("#6B7C99"), 1.4))
        path = QPainterPath()
        ax = antenna.x() + 14
        path.moveTo(ax, antenna.bottom() - 7)
        for k in range(6):
            path.lineTo(ax + k * 14 + 7, antenna.y() + 7)
            path.lineTo(ax + k * 14 + 14, antenna.bottom() - 7)
        p.drawPath(path)
        p.setPen(QColor("#C8D3E6"))
        f = QFont(theme.app_font(9))
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(module.x(), module.y() + 30, module.width(), 20), Qt.AlignCenter, "ESP32-S3")
        p.setFont(theme.app_font(7))
        p.setPen(QColor("#93A3BD"))
        p.drawText(QRectF(module.x(), module.y() + 48, module.width(), 16), Qt.AlignCenter, "N16R8 · 8MB PSRAM")

        # Hai cổng USB-C
        for k, text in enumerate(("COM", "USB")):
            cx = x0 + BOARD_W / 2 + (-46 if k == 0 else 46)
            rect = QRectF(cx - 22, board.bottom() - 14, 44, 18)
            p.setPen(QPen(QColor("#8C9AB3"), 1))
            p.setBrush(QColor("#4A5872"))
            p.drawRoundedRect(rect, 8, 8)
            p.setPen(QColor("#93A3BD"))
            p.setFont(theme.app_font(7))
            p.drawText(QRectF(cx - 30, board.bottom() - 32, 60, 16), Qt.AlignCenter, text)

        # Chân
        variant = self.hw.get("variant", "usb")
        for side, i, name, pos in self._pins():
            self._draw_pin(p, side, name, pos, variant)
        p.end()

    def _draw_pin(self, p, side, name, pos, variant):
        x0, _ = self._origin()
        text_rect = QRectF(pos.x() + 12, pos.y() - 9, 46, 18) if side == "left" else \
            QRectF(pos.x() - 58, pos.y() - 9, 46, 18)
        align = (Qt.AlignLeft if side == "left" else Qt.AlignRight) | Qt.AlignVCenter

        if not name.isdigit():
            color = {"3V3": "#F97066", "5V": "#F04438", "GND": "#98A2B3", "RST": "#7CD4FD"}.get(name, "#98A2B3")
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.c("pad")).darker(130))
            p.drawRect(QRectF(pos.x() - PAD + 1, pos.y() - PAD + 1, 2 * PAD - 2, 2 * PAD - 2))
            p.setPen(QColor(color))
            p.setFont(theme.app_font(7.5))
            p.drawText(text_rect, align, name)
            return

        gpio = int(name)
        kind, detail = pins.pin_state(gpio, self.hw)
        hovered = gpio == self.hover
        r = PAD + (1.5 if hovered else 0)

        if kind == "used":
            mod = catalog.module(detail[0][0])
            fill, ring = QColor(mod.color), QColor(mod.color).lighter(130)
        elif kind == "conflict":
            fill, ring = QColor(theme.c("danger")), QColor("#FDA29B")
        elif kind == "blocked":
            fill, ring = QColor("#3A4559"), QColor("#56637A")
        elif kind == "caution":
            fill, ring = QColor(theme.c("board")), QColor(theme.c("warning"))
        else:
            fill, ring = QColor(theme.c("board")), QColor(theme.c("pad"))

        if self.active and kind in ("free", "caution"):
            p.setPen(QPen(QColor(theme.c("primary")).lighter(140), 1.5, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(pos, r + 4, r + 4)

        p.setPen(QPen(ring, 2))
        p.setBrush(fill)
        p.drawEllipse(pos, r, r)
        if kind == "blocked":
            p.setPen(QPen(QColor("#8391A8"), 1.4))
            d = r * 0.55
            p.drawLine(QPointF(pos.x() - d, pos.y() - d), QPointF(pos.x() + d, pos.y() + d))
        else:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.c("board")))
            p.drawEllipse(pos, 2.2, 2.2)

        label = self.board.labels.get(name)
        p.setFont(theme.app_font(7.5 if not hovered else 8))
        p.setPen(QColor("#E4E9F2") if kind in ("used", "conflict") else QColor("#7F8EA8") if kind == "blocked"
                 else QColor("#C2CCDC"))
        p.drawText(text_rect, align, f"{name}" + (f" {label}" if label else ""))

        # Nhãn module bên ngoài mạch
        if kind in ("used", "conflict"):
            tag = self._tag_rect(side, pos)
            if len(detail) == 1:
                mod = catalog.module(detail[0][0])
                text = f"{mod.short} · {mod.signal(detail[0][1]).label}"
                base = QColor(mod.color)
            else:
                text = "Trùng chân!"
                base = QColor(theme.c("danger"))
            if kind == "conflict":
                base = QColor(theme.c("danger"))
            bg = QColor(base)
            bg.setAlpha(36 if not theme.is_dark() else 70)
            p.setPen(QPen(base, 1))
            p.setBrush(bg)
            p.drawRoundedRect(tag, 9, 9)
            p.setPen(QColor(theme.c("text")) if not theme.is_dark() else QColor("#F2F4F7"))
            p.setFont(theme.app_font(7.5))
            metrics = p.fontMetrics()
            elided = metrics.elidedText(text, Qt.ElideRight, int(tag.width() - 12))
            p.drawText(tag, Qt.AlignCenter, elided)
            # đường nối
            p.setPen(QPen(base, 1.2))
            if side == "left":
                p.drawLine(QPointF(tag.right(), pos.y()), QPointF(x0, pos.y()))
            else:
                p.drawLine(QPointF(x0 + BOARD_W, pos.y()), QPointF(tag.left(), pos.y()))
