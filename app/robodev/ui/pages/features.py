"""Bước 3 - Tính năng: bật/tắt hành vi và chỉnh thông số."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QGridLayout, QLineEdit, QSlider, QSpinBox

from robodev.core import profile
from robodev.ui.binding import Binder, get
from robodev.ui.pages.base import Page
from robodev.ui.widgets import Banner, Card, ColorButton, Toggle, form_row, hbox, label, vbox


def spin(lo, hi, step=1, suffix=""):
    box = QSpinBox()
    box.setRange(lo, hi)
    box.setSingleStep(step)
    box.setSuffix(suffix)
    box.setMinimumWidth(118)
    box.setAlignment(Qt.AlignRight)
    return box


def slider_with_value(lo, hi, suffix="%"):
    slider = QSlider(Qt.Horizontal)
    slider.setRange(lo, hi)
    slider.setMinimumWidth(180)
    value = label("", "h3")
    value.setMinimumWidth(44)
    value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    slider.valueChanged.connect(lambda v: value.setText(f"{v}{suffix}"))
    return slider, hbox(slider, value, spacing=10)


class FeaturesPage(Page):
    title = "Tính năng"
    subtitle = "Bật/tắt hành vi của robot và chỉnh thông số. Thay đổi được gửi xuống mạch khi bạn bấm Áp dụng."
    icon = "sliders"

    def __init__(self, state, window):
        super().__init__(state, window)
        self.b = Binder(state)
        self.groups = {}       # tên nhóm -> (card, các module cần có)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(18)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.addWidget(self._motion(), 0, 0)
        grid.addWidget(self._obstacle(), 0, 1)
        grid.addWidget(self._led(), 1, 0)
        grid.addWidget(self._wander(), 1, 1)
        grid.addWidget(self._screen(), 2, 0)
        grid.addWidget(self._emotion_card(), 2, 1)
        self.content.addLayout(grid)
        for card, _, _ in self.groups.values():
            card.body.addStretch(1)
        self.emotion_table = self._emotions()
        self.content.addWidget(self.emotion_table)
        self.content.addStretch(1)

        state.project_changed.connect(self.refresh)
        state.mode_changed.connect(lambda _: self.update_availability())
        self.refresh()

    # Nhóm ------------------------------------------------------------------------------
    def _group(self, key, title, subtitle, icon, needs):
        card = Card(title, subtitle, icon)
        note = Banner("", "info")
        note.hide()
        card.add(note)
        self.groups[key] = (card, needs, note)
        return card

    def _motion(self):
        card = self._group("motion", "Di chuyển", "Tốc độ và chiều quay của hai bánh.", "motor", ["motors"])
        s1, row1 = slider_with_value(30, 100)
        s2, row2 = slider_with_value(30, 100)
        self.b.bind(s1, ("cfg", "motors", "default_speed"))
        self.b.bind(s2, ("cfg", "motors", "slow_speed"))
        card.add(form_row("Tốc độ thường", row1, "Khi AI bảo đi tới, lùi, quay."))
        card.add(form_row("Tốc độ chậm", row2, "Dùng khi buồn, khi lùi khỏi vật cản."))
        for key, title, hint in (("invert_left", "Đảo chiều bánh trái", "Bật nếu bánh trái quay ngược."),
                                 ("invert_right", "Đảo chiều bánh phải", "Bật nếu bánh phải quay ngược."),
                                 ("swap_sides", "Đổi bánh trái ↔ phải", "Bật nếu robot rẽ ngược hướng.")):
            card.add(form_row(title, self.b.bind(Toggle(), ("hw", "motors", key)), hint))
        return card

    def _obstacle(self):
        card = self._group("obstacle", "Vật cản", "Robot tự dừng và lùi lại khi có vật phía trước.", "radar",
                           ["sensor", "motors"])
        card.add(form_row("Tự dừng khi gặp vật cản", self.b.bind(Toggle(), ("cfg", "features", "obstacle_stop"),
                                                                  lambda _: self.update_availability())))
        self.stop_mm = self.b.bind(spin(30, 1000, 10, " mm"), ("cfg", "obstacle", "stop_distance_mm"))
        self.back_ms = self.b.bind(spin(0, 3000, 50, " ms"), ("cfg", "obstacle", "back_off_ms"))
        card.add(form_row("Khoảng cách dừng", self.stop_mm, "Gần hơn khoảng này là dừng."))
        card.add(form_row("Lùi lại trong", self.back_ms))
        card.add(form_row("Báo cho AI biết", self.b.bind(Toggle(), ("cfg", "features", "obstacle_report"),
                                                         lambda _: self.update_availability()),
                          "AI sẽ phản ứng, ví dụ: “Ái, đừng chặn đường mình!”"))
        self.report_text = QLineEdit()
        self.b.bind(self.report_text, ("cfg", "obstacle", "report_text"))
        card.add(vbox(label("Câu gửi cho AI", "muted"), self.report_text, spacing=4))
        return card

    def _wander(self):
        card = self._group("wander", "Đi dạo", "Khi rảnh, robot tự đi loanh quanh và né vật cản (bật bằng giọng nói).",
                           "robot", ["sensor", "motors"])
        fwd, row_fwd = slider_with_value(30, 100)
        turn, row_turn = slider_with_value(30, 100)
        self.b.bind(fwd, ("cfg", "wander", "forward_speed"))
        self.b.bind(turn, ("cfg", "wander", "turn_speed"))
        card.add(form_row("Tốc độ đi", row_fwd))
        card.add(form_row("Tốc độ quay", row_turn))
        lo = self.b.bind(spin(2000, 60000, 1000, " ms"), ("cfg", "wander", "interval_min_ms"))
        hi = self.b.bind(spin(2000, 60000, 1000, " ms"), ("cfg", "wander", "interval_max_ms"))
        card.add(form_row("Nghỉ giữa hai lần đi", hbox(lo, label("đến", "muted"), hi, spacing=8)))
        card.add(form_row("Cần khoảng trống", self.b.bind(spin(100, 2000, 50, " mm"), ("cfg", "wander", "clear_distance_mm")),
                          "Chỉ đi tới khi phía trước trống hơn khoảng này."))
        return card

    def _led(self):
        card = self._group("led", "Đèn LED", "Màu đèn theo trạng thái của robot.", "led", ["led"])
        card.add(form_row("Bật đèn theo trạng thái", self.b.bind(Toggle(), ("cfg", "features", "led"),
                                                                  lambda _: self.update_availability())))
        bright, row = slider_with_value(1, 100)
        self.b.bind(bright, ("cfg", "led", "brightness"))
        card.add(form_row("Độ sáng", row, "Đèn onboard rất sáng: 5-15% là đủ."))
        swatches = QGridLayout()
        swatches.setHorizontalSpacing(12)
        swatches.setVerticalSpacing(8)
        for i, (key, text) in enumerate(profile.LED_STATES):
            btn = self.b.bind(ColorButton(title=f"Màu khi {text.lower()}"), ("cfg", "led", key))
            swatches.addLayout(hbox(btn, label(text, "muted"), "stretch", spacing=8), i // 3, i % 3)
        card.add(label("Màu theo trạng thái", "caption"))
        card.add(swatches)
        return card

    def _screen(self):
        card = self._group("screen", "Màn hình", "Nội dung hiển thị trên LCD.", "display", ["lcd"])
        card.add(form_row("Chỉ hiện khuôn mặt", self.b.bind(Toggle(), ("cfg", "features", "hide_subtitle")),
                          "Ẩn phụ đề vì font hiện tại thiếu nhiều chữ tiếng Việt có dấu."))
        return card

    def _emotion_card(self):
        card = self._group("emotion", "Cử động theo cảm xúc", "Robot xoay hoặc lùi khi AI vui, buồn, ngạc nhiên...",
                           "sparkle", ["motors"])
        card.add(form_row("Bật cử động theo cảm xúc", self.b.bind(Toggle(), ("cfg", "features", "emotion_motion"),
                                                                   lambda _: self.update_availability())))
        card.add(form_row("Nghỉ tối thiểu giữa hai cử động",
                          self.b.bind(spin(0, 60000, 500, " ms"), ("cfg", "emotion_motion", "cooldown_ms"))))
        self.emotion_hint = label("Bật chế độ Nâng cao (góc dưới bên trái) để chỉnh từng cảm xúc.", "faint", wrap=True)
        card.add(self.emotion_hint)
        return card

    def _emotions(self):
        card = Card("Hành động cho từng cảm xúc", "AI chọn cảm xúc theo câu nói; robot làm hành động tương ứng.",
                    "sparkle")
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        for col, text in enumerate(("Cảm xúc", "Hành động", "Tốc độ", "Thời gian", "Màu đèn")):
            grid.addWidget(label(text.upper(), "caption"), 0, col)
        for row, emotion in enumerate(profile.EMOTIONS, start=1):
            grid.addWidget(label(profile.EMOTION_LABELS[emotion], "h3"), row, 0)
            action = QComboBox()
            for value in profile.ACTIONS:
                action.addItem(profile.ACTION_LABELS[value], value)
            self.b.bind(action, ("cfg", "emotion_motion", emotion, "action"))
            grid.addWidget(action, row, 1)
            grid.addWidget(self.b.bind(spin(30, 100, 5, "%"), ("cfg", "emotion_motion", emotion, "speed")), row, 2)
            grid.addWidget(self.b.bind(spin(100, 5000, 50, " ms"), ("cfg", "emotion_motion", emotion, "ms")), row, 3)
            color = ColorButton(title="Màu đèn")
            self.b.bind(color, ("cfg", "led", "moods", emotion))
            grid.addWidget(color, row, 4)
        grid.setColumnStretch(5, 1)
        card.add(grid)
        return card

    # Cập nhật --------------------------------------------------------------------------
    def refresh(self):
        self.b.load()
        self.update_availability()

    def on_show(self):
        self.refresh()

    def update_availability(self):
        hw = self.state.project["hw"]
        cfg = self.state.project["cfg"]
        names = {"motors": "Động cơ", "sensor": "Cảm biến khoảng cách", "led": "Đèn LED", "lcd": "Màn hình"}
        for key, (card, needs, note) in self.groups.items():
            missing = [names[m] for m in needs if not hw.get(m, {}).get("enabled", True)]
            if missing:
                note.set("Đang tắt module <b>" + ", ".join(missing) + "</b> ở bước Nối chân, nên nhóm này không có hiệu lực.",
                         "info")
            note.setVisible(bool(missing))
            for i in range(card.body.count()):
                item = card.body.itemAt(i)
                widget = item.widget()
                if widget is note or widget is None and item.layout() is card.header:
                    continue
                self._enable(item, not missing)
        self.stop_mm.setEnabled(bool(get(cfg, ("features", "obstacle_stop"))) and self.stop_mm.isEnabled())
        self.back_ms.setEnabled(bool(get(cfg, ("features", "obstacle_stop"))) and self.back_ms.isEnabled())
        self.report_text.setEnabled(bool(get(cfg, ("features", "obstacle_report"))) and self.report_text.isEnabled())
        self.emotion_table.setVisible(self.state.advanced)
        self.emotion_hint.setVisible(not self.state.advanced)

    def _enable(self, item, on):
        if item.widget() is not None:
            item.widget().setEnabled(on)
        elif item.layout() is not None:
            lay = item.layout()
            for i in range(lay.count()):
                self._enable(lay.itemAt(i), on)

