"""Bước 2 - Nối chân: khai báo module nào có mặt và nối vào GPIO nào."""
from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGridLayout, QLabel, QScrollArea, QSpinBox, QWidget)

from robodev.core import catalog, pins, profile
from robodev.ui import icons, theme
from robodev.ui.devkit import DevkitView
from robodev.ui.pages.base import Page
from robodev.ui.widgets import (Banner, Card, Chip, Segmented, Toggle, button, clear_layout, hbox, label, set_prop,
                                vbox)

UNUSED = pins.UNUSED


class PinCombo(QComboBox):
    """Ô chọn GPIO, mỗi mục có chấm màu cho biết chân trống, đã dùng hay bị cấm."""

    def __init__(self, page, module, signal):
        super().__init__()
        self.page, self.module, self.signal = page, module, signal
        self.setMinimumWidth(150)
        self.setMaxVisibleItems(18)
        self.setCursor(Qt.PointingHandCursor)
        if signal.optional:
            self.addItem("Không dùng", UNUSED)
        for gpio in catalog.board().header_gpios:
            self.addItem(catalog.board().label(gpio), gpio)
        self.currentIndexChanged.connect(self._changed)
        self.installEventFilter(self)

    def eventFilter(self, obj, event):  # noqa: N802
        if event.type() == QEvent.FocusIn:
            self.page.set_active(self.module.key, self.signal.key)
        return False

    def value(self):
        return self.currentData()

    def set_value(self, gpio):
        self.blockSignals(True)
        index = self.findData(gpio)
        self.setCurrentIndex(index if index >= 0 else 0)
        self.blockSignals(False)

    def showPopup(self):  # noqa: N802
        self.decorate()
        super().showPopup()

    def decorate(self):
        hw = self.page.state.project["hw"]
        board = catalog.board()
        model = self.model()
        for i in range(self.count()):
            gpio = self.itemData(i)
            if gpio == UNUSED:
                continue
            kind, detail = pins.pin_state(gpio, hw)
            text = board.label(gpio)
            mine = kind in ("used", "conflict") and any(m == self.module.key and s == self.signal.key for m, s in detail)
            hint = pins.choice_hint(gpio, hw, self.module.key)
            enabled = True
            if kind in ("used", "conflict") and not mine:
                users = ", ".join(f"{catalog.module(m).name} {catalog.module(m).signal(s).label}" for m, s in detail)
                text += f"   ·  {users}"
                color = theme.c("faint")
            elif hint == "error":
                color = theme.c("danger")
                text += "   ·  không dùng được"
                enabled = mine
            elif hint == "warning":
                color = theme.c("warning")
                text += "   ·  cẩn thận"
            else:
                color = theme.c("success")
            self.setItemText(i, text)
            self.setItemIcon(i, QIcon(icons.pixmap("dot", color, 14)))
            item = model.item(i)
            if item is not None:
                flags = item.flags()
                item.setFlags(flags | Qt.ItemIsEnabled if enabled else flags & ~Qt.ItemIsEnabled)
        self.setIconSize(QSize(14, 14))

    def hidePopup(self):  # noqa: N802
        super().hidePopup()
        board = catalog.board()
        for i in range(self.count()):
            gpio = self.itemData(i)
            if gpio != UNUSED:
                self.setItemText(i, board.label(gpio))
                self.setItemIcon(i, QIcon())

    def _changed(self, _):
        self.page.assign(self.module.key, self.signal.key, self.value(), advance=False)


class ModuleCard(Card):
    def __init__(self, page, mod):
        super().__init__(padding=18, spacing=12, shadow=False)
        self.page, self.mod = page, mod
        badge = QLabel()
        badge.setFixedSize(38, 38)
        badge.setAlignment(Qt.AlignCenter)
        badge.setPixmap(icons.pixmap(icons.MODULE_ICONS[mod.key], mod.color, 20))
        badge.setStyleSheet(f"background: {theme.tint(mod.color)}; border-radius: 11px;")
        self.toggle = Toggle(True)
        self.toggle.setVisible(mod.optional)
        self.toggle.setToolTip("Bật nếu bạn có nối module này")
        self.toggle.toggled.connect(self._toggled)
        self.status = Chip("", "neutral")
        head = hbox(badge, spacing=12)
        head.addLayout(vbox(label(mod.name, "h3"), label(mod.part, "faint"), spacing=1), 1)
        head.addWidget(self.status, 0, Qt.AlignVCenter)
        head.addWidget(self.toggle, 0, Qt.AlignVCenter)
        self.add(head)

        self.body_widget = QWidget()
        grid = QGridLayout(self.body_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        self.combos = {}
        for i, sig in enumerate(mod.signals):
            name = label(sig.label + (" (tùy chọn)" if sig.optional else ""), "muted")
            combo = PinCombo(page, mod, sig)
            self.combos[sig.key] = combo
            grid.addWidget(name, i // 2, (i % 2) * 2)
            grid.addWidget(combo, i // 2, (i % 2) * 2 + 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        if len(mod.signals) == 1:
            grid.setColumnStretch(3, 0)
        self.add(self.body_widget)

        self.settings_widget = self._settings()
        if self.settings_widget:
            self.add(self.settings_widget)
        note = f"<b>Nguồn:</b> {mod.power}" + (f"<br>{mod.notes}" if mod.notes else "")
        self.note = label(note, "faint", wrap=True)
        self.note.setTextFormat(Qt.RichText)
        self.add(self.note)
        if mod.key == "button":
            for combo in self.combos.values():
                combo.setEnabled(False)

    def _settings(self):
        """Thông số nâng cao của module (màn hình, cảm biến, đèn)."""
        key = self.mod.key
        if key not in ("lcd", "sensor", "led"):
            return None
        box = QWidget()
        lay = QGridLayout(box)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setHorizontalSpacing(12)
        lay.setVerticalSpacing(8)
        self.extra = {}
        if key == "sensor":
            combo = QComboBox()
            for value, text in (("auto", "Tự nhận"), ("vl53l0x", "VL53L0X"), ("vl6180x", "VL6180X")):
                combo.addItem(text, value)
            combo.currentIndexChanged.connect(lambda _: self.page.set_setting(key, "type", combo.currentData()))
            self.extra["type"] = combo
            lay.addWidget(label("Loại cảm biến", "muted"), 0, 0)
            lay.addWidget(combo, 0, 1)
        elif key == "led":
            combo = QComboBox()
            for value in ("GRB", "RGB"):
                combo.addItem(value, value)
            combo.currentIndexChanged.connect(lambda _: self.page.set_setting(key, "order", combo.currentData()))
            self.extra["order"] = combo
            lay.addWidget(label("Thứ tự màu", "muted"), 0, 0)
            lay.addWidget(combo, 0, 1)
        else:
            row = 0
            for name, text in (("invert", "Đảo màu"), ("mirror_x", "Lật ngang"), ("mirror_y", "Lật dọc"),
                               ("swap_xy", "Xoay 90°")):
                check = QCheckBox(text)
                check.toggled.connect(lambda on, n=name: self.page.set_setting(key, n, on))
                self.extra[name] = check
                lay.addWidget(check, row // 2, row % 2 * 2, 1, 2)
                row += 1
            for i, (name, text, lo, hi) in enumerate((("offset_x", "Lệch X", -80, 80), ("offset_y", "Lệch Y", -80, 80),
                                                       ("clock_mhz", "Tốc độ SPI (MHz)", 1, 80),
                                                       ("spi_mode", "SPI mode", 0, 3))):
                spin = QSpinBox()
                spin.setRange(lo, hi)
                spin.valueChanged.connect(lambda v, n=name: self.page.set_setting(key, n, v))
                self.extra[name] = spin
                lay.addWidget(label(text, "muted"), 2 + i // 2, (i % 2) * 2)
                lay.addWidget(spin, 2 + i // 2, (i % 2) * 2 + 1)
        lay.setColumnStretch(1, 1)
        lay.setColumnStretch(3, 1)
        box.setProperty("advanced", True)
        return box

    def _toggled(self, on):
        self.page.set_enabled(self.mod.key, on)

    def load(self, hw):
        entry = hw.get(self.mod.key, {})
        on = entry.get("enabled", True)
        self.toggle.blockSignals(True)
        self.toggle.setChecked(on)
        self.toggle.blockSignals(False)
        self.body_widget.setEnabled(on)
        for key, combo in self.combos.items():
            combo.set_value(entry.get(key, UNUSED))
        for name, widget in getattr(self, "extra", {}).items():
            widget.blockSignals(True)
            value = entry.get(name)
            if isinstance(widget, QComboBox):
                widget.setCurrentIndex(max(0, widget.findData(value)))
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            else:
                widget.setValue(int(value or 0))
            widget.blockSignals(False)
        set_prop(self, "disabledcard", "true" if not on else "false")

    def show_issues(self, issues, advanced, active):
        mine = [i for i in issues if i.module == self.mod.key]
        on = self.toggle.isChecked() or not self.mod.optional
        if not on:
            self.status.set("Không dùng", "neutral")
        elif any(i.level == "error" for i in mine):
            self.status.set(f"{sum(i.level == 'error' for i in mine)} lỗi", "error")
        elif mine:
            self.status.set("Cần chú ý", "warning")
        else:
            self.status.set("Ổn", "ok")
        for key, combo in self.combos.items():
            levels = {i.level for i in mine if i.signal == key}
            state = "error" if "error" in levels else "warning" if "warning" in levels else ""
            if active == (self.mod.key, key):
                state = "active"
            set_prop(combo, "pin", state)
        if self.settings_widget:
            self.settings_widget.setVisible(advanced and on)
        set_prop(self, "active", "true" if active and active[0] == self.mod.key else "false")


class PinsPage(Page):
    title = "Nối chân"
    subtitle = "Bật những module bạn có và chọn GPIO đúng với dây đã nối. Bấm vào một ô chân rồi bấm lên hình mạch để gán nhanh."
    icon = "pins"

    def __init__(self, state, window):
        super().__init__(state, window, scroll=False)
        self.active = None
        self.add_action(button("Dùng chân mặc định", "ghost", "refresh", on_click=self.reset_defaults))

        self.legacy = Banner("", "warning")
        self.content.addWidget(self.legacy)

        # Thanh trên: cổng log + tóm tắt lỗi
        self.variant = Segmented([("usb", "Cổng USB native"), ("uart", "Cổng COM")])
        self.variant.changed.connect(self.set_variant)
        self.summary = Chip("", "ok")
        variant_help = label("Cổng đọc log", "muted")
        variant_help.setToolTip("Firmware ghi log và nhận lệnh qua cổng này. Hai chân của cổng đó sẽ bị khóa.")
        bar = hbox(variant_help, self.variant, "stretch", self.summary, spacing=10)
        self.content.addLayout(bar)

        body = hbox(spacing=20)
        # Cột trái: danh sách module (cuộn)
        left = QWidget()
        left.setObjectName("Page")
        left_lay = vbox(spacing=14)
        left.setLayout(left_lay)
        self.issues_card = Card("Cần sửa trước khi áp dụng", None, "alert", padding=16, spacing=8, shadow=False)
        self.issue_list = vbox(spacing=6)
        self.issues_card.add(self.issue_list)
        left_lay.addWidget(self.issues_card)
        self.cards = {}
        for mod in catalog.modules():
            card = ModuleCard(self, mod)
            self.cards[mod.key] = card
            left_lay.addWidget(card)
        left_lay.addStretch(1)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setWidget(left)
        body.addWidget(area, 1)

        # Cột phải: hình mạch
        board_card = Card(padding=16, spacing=10, shadow=False)
        self.devkit = DevkitView()
        self.devkit.pinClicked.connect(self.on_pin_clicked)
        self.active_hint = label("", "faint", wrap=True)
        self.active_hint.setAlignment(Qt.AlignCenter)
        board_card.add(self.devkit)
        board_card.add(self.active_hint)
        board_card.add(self._legend())
        board_card.setMaximumWidth(self.devkit.sizeHint().width() + 34)
        board_card.setMinimumWidth(int(self.devkit.sizeHint().width() * 0.75))
        body.addWidget(board_card, 0)
        self.content.addLayout(body, 1)

        state.project_changed.connect(self.refresh)
        state.device_changed.connect(self.update_legacy)
        state.mode_changed.connect(lambda _: self.update_issues())
        self.refresh()
        self.update_legacy()

    def _legend(self):
        items = [("success", "Trống"), ("primary", "Đang dùng"), ("warning", "Cẩn thận"), ("danger", "Trùng / cấm")]
        lay = hbox(spacing=14)
        lay.addStretch(1)
        for color, text in items:
            dot = QLabel()
            dot.setPixmap(icons.pixmap("dot", theme.c(color), 14))
            lay.addLayout(hbox(dot, label(text, "faint"), spacing=3))
        lay.addStretch(1)
        return lay

    # Đọc / ghi hồ sơ ----------------------------------------------------------------------
    @property
    def hw(self):
        return self.state.project["hw"]

    def refresh(self):
        self.variant.set(self.hw.get("variant", "usb"))
        for card in self.cards.values():
            card.load(self.hw)
        self.update_issues()

    def changed(self):
        self.state.touch()
        self.update_issues()

    def assign(self, module, signal, gpio, advance=True):
        self.hw[module][signal] = gpio
        if advance:
            self.cards[module].combos[signal].set_value(gpio)
            mod = catalog.module(module)
            keys = [s.key for s in mod.signals]
            nxt = keys.index(signal) + 1
            self.active = (module, keys[nxt]) if nxt < len(keys) else None
        self.changed()

    def set_enabled(self, module, on):
        self.hw[module]["enabled"] = on
        self.cards[module].body_widget.setEnabled(on)
        set_prop(self.cards[module], "disabledcard", "true" if not on else "false")
        if self.active and self.active[0] == module and not on:
            self.active = None
        self.changed()

    def set_setting(self, module, name, value):
        self.hw[module][name] = value
        self.changed()

    def set_variant(self, variant):
        self.hw["variant"] = variant
        self.changed()

    def reset_defaults(self):
        variant = self.hw.get("variant", "usb")
        self.state.project["hw"] = profile.default_hw()
        self.state.project["hw"]["variant"] = variant
        self.active = None
        self.refresh()
        self.state.touch()
        self.window.toast("Đã đặt lại chân mặc định")

    def set_active(self, module, signal):
        if module == "button":
            return
        self.active = (module, signal)
        self.update_issues()

    def on_pin_clicked(self, gpio):
        if not self.active:
            self.window.toast("Bấm vào một ô chân bên trái trước, rồi bấm lên hình mạch", "info")
            return
        module, signal = self.active
        if pins.choice_hint(gpio, self.hw, module) == "error":
            board = catalog.board()
            rule = board.rules_for(gpio, self.hw.get("variant", "usb"), module)[0]
            self.window.toast(rule.text.format(gpio=gpio), "error", 5000)
            return
        self.assign(module, signal, gpio)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key_Escape and self.active:
            self.active = None
            self.update_issues()
        else:
            super().keyPressEvent(event)

    # Hiển thị ----------------------------------------------------------------------------
    def update_issues(self):
        issues = pins.validate(self.hw)
        errors = [i for i in issues if i.level == "error"]
        warnings = [i for i in issues if i.level == "warning"]
        if errors:
            self.summary.set(f"{len(errors)} lỗi · {len(warnings)} cảnh báo", "error")
        elif warnings:
            self.summary.set(f"Không có lỗi · {len(warnings)} cảnh báo", "warning")
        else:
            self.summary.set("Cách nối hợp lệ", "ok")

        clear_layout(self.issue_list)
        seen = set()
        for issue in errors + warnings:
            if issue.text in seen:
                continue
            seen.add(issue.text)
            color = theme.c("danger") if issue.level == "error" else theme.c("warning")
            dot = QLabel()
            dot.setPixmap(icons.pixmap("x-circle" if issue.level == "error" else "alert", color, 16))
            dot.setFixedWidth(18)
            text = label(issue.text, wrap=True)
            row = QWidget()
            row.setLayout(hbox(dot, text, spacing=8))
            row.layout().setAlignment(dot, Qt.AlignTop)
            text.setSizePolicy(text.sizePolicy().horizontalPolicy(), text.sizePolicy().verticalPolicy())
            self.issue_list.addWidget(row)
            row.layout().setStretch(1, 1)
        self.issues_card.setVisible(bool(seen))
        if errors:
            self.issues_card.title_label.setText("Cần sửa trước khi áp dụng")
        else:
            self.issues_card.title_label.setText("Lưu ý (vẫn áp dụng được)")

        for card in self.cards.values():
            card.show_issues(issues, self.state.advanced, self.active)
        self.devkit.set_hw(self.hw)
        self.devkit.set_active(self.active)
        if self.active:
            mod = catalog.module(self.active[0])
            self.active_hint.setText(f"Đang chọn chân cho <b>{mod.name} {mod.signal(self.active[1]).label}</b>: "
                                     f"bấm một chân trên hình. Nhấn Esc để thôi.")
        else:
            self.active_hint.setText("Rê chuột lên một chân để xem giải thích.")

    def update_legacy(self):
        st = self.state
        self.legacy.setVisible(st.prefix == "VOI")
        self.legacy.set("Mạch đang chạy <b>firmware Voi (cũ)</b>: chân GPIO cố định trong firmware. Thay đổi ở đây "
                        "sẽ có hiệu lực khi bạn nạp <b>firmware Robo Dev</b>.", "warning")

    def has_errors(self):
        return any(i.level == "error" for i in pins.validate(self.hw))
