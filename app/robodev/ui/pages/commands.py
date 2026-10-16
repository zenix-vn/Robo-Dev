"""Bước 4 - Lệnh: công cụ MCP có sẵn, lệnh tùy chỉnh ghép từ các bước, prompt cho AI."""
import copy
import webbrowser

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QGridLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMenu, QMessageBox, QPlainTextEdit, QSpinBox, QTabWidget, QWidget)

from robodev.core import jobs, profile
from robodev.ui import icons, theme
from robodev.ui.binding import Binder
from robodev.ui.pages.base import Page
from robodev.ui.widgets import (Banner, Card, Chip, ColorButton, Segmented, Toggle, button, clear_layout, form_row,
                                hbox, label, set_prop, tool, vbox)

XIAOZHI_URL = "https://xiaozhi.me"
STEP_ICONS = {"move": "motor", "led": "led", "emotion": "sparkle", "beep": "speaker", "wait": "pause"}
MOVE_TOOLS = ("forward", "backward", "turn_left", "turn_right")


# ----------------------------------------------------------------------------------------
# Hộp thoại sửa một bước
# ----------------------------------------------------------------------------------------
class StepDialog(QDialog):
    def __init__(self, parent, step):
        super().__init__(parent)
        self.kind = profile.step_kind(step)
        self.setWindowTitle("Bước: " + profile.STEP_KINDS[self.kind])
        self.setMinimumWidth(420)
        lay = vbox(spacing=14, margins=(22, 20, 22, 18))
        self.setLayout(lay)
        lay.addWidget(label(profile.STEP_KINDS[self.kind], "h2"))
        self.fields = {}
        if self.kind == "move":
            move = QComboBox()
            for key in profile.MOVES:
                move.addItem(profile.MOVE_LABELS[key], key)
            move.setCurrentIndex(max(0, move.findData(step.get("move", "forward"))))
            self.fields["move"] = move
            lay.addLayout(form_row("Hướng", move))
            self.fields["speed"] = self._spin(30, 100, step.get("speed", 70), "%", 5)
            lay.addLayout(form_row("Tốc độ", self.fields["speed"]))
            self.fields["ms"] = self._spin(50, 10000, step.get("ms", 500), " ms", 50)
            lay.addLayout(form_row("Thời gian", self.fields["ms"]))
            move.currentIndexChanged.connect(self._sync)
        elif self.kind == "led":
            value = step.get("led", [0, 200, 0])
            mode = Segmented([("color", "Màu"), ("off", "Tắt"), ("auto", "Theo trạng thái")])
            mode.set("color" if isinstance(value, list) else value)
            self.color = ColorButton(value if isinstance(value, list) else [0, 200, 0])
            self.fields["mode"] = mode
            lay.addWidget(mode)
            lay.addLayout(form_row("Màu đèn", self.color))
            mode.changed.connect(lambda _: self._sync())
        elif self.kind == "emotion":
            combo = QComboBox()
            for key in profile.EMOTIONS:
                combo.addItem(profile.EMOTION_LABELS[key], key)
            combo.setCurrentIndex(max(0, combo.findData(step.get("emotion", "happy"))))
            self.fields["emotion"] = combo
            lay.addLayout(form_row("Biểu cảm trên màn hình", combo))
        elif self.kind == "beep":
            self.fields["beep"] = self._spin(100, 5000, step.get("beep", 880), " Hz", 10)
            self.fields["ms"] = self._spin(20, 3000, step.get("ms", 150), " ms", 10)
            lay.addLayout(form_row("Cao độ", self.fields["beep"], "440 Hz = nốt La; số càng lớn tiếng càng cao."))
            lay.addLayout(form_row("Thời gian", self.fields["ms"]))
        else:
            self.fields["wait"] = self._spin(10, 10000, step.get("wait", 500), " ms", 50)
            lay.addLayout(form_row("Chờ", self.fields["wait"]))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Lưu bước")
        buttons.button(QDialogButtonBox.Ok).setProperty("kind", "primary")
        buttons.button(QDialogButtonBox.Cancel).setText("Hủy")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addSpacing(6)
        lay.addWidget(buttons)
        self._sync()

    def _spin(self, lo, hi, value, suffix, step):
        box = QSpinBox()
        box.setRange(lo, hi)
        box.setSingleStep(step)
        box.setSuffix(suffix)
        box.setValue(int(value))
        box.setMinimumWidth(120)
        return box

    def _sync(self):
        if self.kind == "move":
            stop = self.fields["move"].currentData() == "stop"
            self.fields["speed"].setEnabled(not stop)
            self.fields["ms"].setEnabled(not stop)
        elif self.kind == "led":
            self.color.setEnabled(self.fields["mode"].value() == "color")

    def step(self):
        f = self.fields
        if self.kind == "move":
            if f["move"].currentData() == "stop":
                return {"move": "stop"}
            return {"move": f["move"].currentData(), "speed": f["speed"].value(), "ms": f["ms"].value()}
        if self.kind == "led":
            mode = f["mode"].value()
            return {"led": list(self.color.rgb) if mode == "color" else mode}
        if self.kind == "emotion":
            return {"emotion": f["emotion"].currentData()}
        if self.kind == "beep":
            return {"beep": f["beep"].value(), "ms": f["ms"].value()}
        return {"wait": f["wait"].value()}


DEFAULT_STEP = {"move": {"move": "forward", "speed": 70, "ms": 500}, "led": {"led": [0, 200, 0]},
                "emotion": {"emotion": "happy"}, "beep": {"beep": 880, "ms": 150}, "wait": {"wait": 500}}


class StepRow(QWidget):
    def __init__(self, editor, index, step, last):
        super().__init__()
        kind = profile.step_kind(step)
        num = label(str(index + 1), "faint")
        num.setFixedWidth(18)
        badge = QLabel()
        badge.setFixedSize(30, 30)
        badge.setAlignment(Qt.AlignCenter)
        badge.setPixmap(icons.pixmap(STEP_ICONS[kind], theme.c("primary"), 16))
        badge.setStyleSheet(f"background: {theme.c('primary_soft')}; border-radius: 8px;")
        text = label(profile.describe_step(step))
        lay = hbox(num, badge, spacing=10, margins=(6, 4, 4, 4))
        if kind == "led" and isinstance(step["led"], list):
            swatch = QLabel()
            swatch.setFixedSize(14, 14)
            r, g, b = step["led"]
            swatch.setStyleSheet(f"background: rgb({r},{g},{b}); border-radius: 7px; border: 1px solid {theme.c('border_strong')};")
            lay.addWidget(swatch)
        lay.addWidget(text, 1)
        up = tool("up", "Lên trên", lambda: editor.move_step(index, -1), size=16)
        down = tool("down", "Xuống dưới", lambda: editor.move_step(index, 1), size=16)
        up.setEnabled(index > 0)
        down.setEnabled(not last)
        lay.addWidget(up)
        lay.addWidget(down)
        lay.addWidget(tool("edit", "Sửa bước", lambda: editor.edit_step(index), size=16))
        lay.addWidget(tool("trash", "Xóa bước", lambda: editor.delete_step(index), color=theme.c("danger"), size=16))
        self.setLayout(lay)
        self.setStyleSheet(f"StepRow {{ background: {theme.c('surface_alt')}; border-radius: 10px; }}")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.mouseDoubleClickEvent = lambda e: editor.edit_step(index)


# ----------------------------------------------------------------------------------------
# Trang
# ----------------------------------------------------------------------------------------
class CommandsPage(Page):
    title = "Lệnh"
    subtitle = "Những việc AI có thể bảo robot làm. AI đọc phần mô tả để biết khi nào dùng lệnh nào."
    icon = "command"

    def __init__(self, state, window):
        super().__init__(state, window)
        self.legacy = Banner("", "warning")
        self.content.addWidget(self.legacy)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._builtin_tab(), "Lệnh có sẵn")
        self.tabs.addTab(self._custom_tab(), "Lệnh tùy chỉnh")
        self.tabs.addTab(self._prompt_tab(), "Lời dặn cho AI")
        self.content.addWidget(self.tabs)
        self.content.addStretch(1)
        state.project_changed.connect(self.refresh)
        state.device_changed.connect(self.update_legacy)
        state.busy_changed.connect(lambda _: self.update_run_button())
        state.port_changed.connect(lambda _: self.update_run_button())
        self.refresh()
        self.update_legacy()

    # Lệnh có sẵn ------------------------------------------------------------------------
    def _builtin_tab(self):
        page = QWidget()
        lay = vbox(spacing=12, margins=(0, 16, 0, 0))
        page.setLayout(lay)
        self.tool_rows = {}
        card = Card(padding=6, spacing=0, shadow=False)
        for i, name in enumerate(profile.TOOLS):
            row = QWidget()
            row_lay = QGridLayout(row)
            row_lay.setContentsMargins(16, 14, 16, 14)
            row_lay.setHorizontalSpacing(14)
            toggle = Toggle(True)
            toggle.toggled.connect(lambda on, n=name: self._tool_set(n, "enabled", on))
            title = label(profile.TOOL_LABELS[name], "h3")
            mono = label(f"self.robot.{name}", "mono")
            needs = profile.TOOL_NEEDS.get(name, "motors" if name != "get_distance" else "sensor")
            chip = Chip("Cần cảm biến" if needs == "sensor" else "Cần động cơ", "neutral")
            desc = QPlainTextEdit()
            desc.setPlaceholderText(profile.TOOL_DEFAULT_DESC[name])
            desc.setFixedHeight(58)
            desc.textChanged.connect(lambda n=name, d=desc: self._tool_set(n, "description", d.toPlainText().strip()))
            row_lay.addWidget(toggle, 0, 0, Qt.AlignTop)
            row_lay.addLayout(vbox(hbox(title, chip, "stretch", spacing=8), mono, spacing=2), 0, 1)
            row_lay.addWidget(desc, 1, 1)
            extras = None
            if name in MOVE_TOOLS:
                speed = QSpinBox()
                speed.setRange(29, 100)
                speed.setSpecialValueText("Mặc định")
                speed.setSuffix("%")
                speed.valueChanged.connect(lambda v, n=name: self._tool_set(n, "speed", -1 if v == 29 else v))
                dur = QSpinBox()
                dur.setRange(99, 10000)
                dur.setSingleStep(100)
                dur.setSpecialValueText("Mặc định")
                dur.setSuffix(" ms")
                dur.valueChanged.connect(lambda v, n=name: self._tool_set(n, "duration_ms", -1 if v == 99 else v))
                extras = (speed, dur)
                row_lay.addLayout(vbox(label("TỐC ĐỘ", "caption"), speed, label("THỜI GIAN", "caption"), dur, spacing=4),
                                  0, 2, 2, 1, Qt.AlignTop)
            row_lay.setColumnStretch(1, 1)
            self.tool_rows[name] = (toggle, desc, extras, chip, row)
            card.add(row)
            if i < len(profile.TOOLS) - 1:
                sep = QWidget()
                sep.setFixedHeight(1)
                sep.setStyleSheet(f"background: {theme.c('border')};")
                card.add(sep)
        lay.addWidget(label("Để trống mô tả thì firmware dùng mô tả mặc định (tiếng Anh, AI hiểu tốt). "
                            "Tốc độ “Mặc định” lấy theo bước Tính năng.", "muted", wrap=True))
        lay.addWidget(card)
        return page

    def _tool_set(self, name, key, value):
        tools = self.state.project["cfg"].setdefault("mcp_tools", {})
        entry = tools.setdefault(name, {"enabled": True})
        if key == "description" and not value:
            if "description" in entry:
                del entry["description"]
                self.state.touch()
            return
        if key in ("speed", "duration_ms") and value == -1:
            if key in entry:
                del entry[key]
                self.state.touch()
            return
        if entry.get(key) != value:
            entry[key] = value
            self.state.touch()

    def _load_tools(self):
        tools = self.state.project["cfg"].get("mcp_tools", {})
        hw = self.state.project["hw"]
        for name, (toggle, desc, extras, chip, row) in self.tool_rows.items():
            entry = tools.get(name, {})
            for w in (toggle, desc) + (extras or ()):
                w.blockSignals(True)
            toggle.setChecked(entry.get("enabled", True))
            toggle.set_offset(1.0 if toggle.isChecked() else 0.0)
            if desc.toPlainText() != entry.get("description", ""):
                desc.setPlainText(entry.get("description", ""))
            if extras:
                extras[0].setValue(entry.get("speed", -1) if entry.get("speed", -1) != -1 else 29)
                extras[1].setValue(entry.get("duration_ms", -1) if entry.get("duration_ms", -1) != -1 else 99)
            for w in (toggle, desc) + (extras or ()):
                w.blockSignals(False)
            needs = "sensor" if name in ("get_distance", "set_wander") else "motors"
            missing = [m for m in ({"set_wander": ["sensor", "motors"]}.get(name, [needs]))
                       if not hw.get(m, {}).get("enabled", True)]
            chip.set("Module đang tắt" if missing else ("Cần cảm biến" if needs == "sensor" else "Cần động cơ"),
                     "warning" if missing else "neutral")

    # Lệnh tùy chỉnh ---------------------------------------------------------------------
    def _custom_tab(self):
        page = QWidget()
        lay = hbox(spacing=18, margins=(0, 16, 0, 0))
        page.setLayout(lay)

        left = Card(padding=14, spacing=10, shadow=False)
        left.setFixedWidth(280)
        self.cmd_list = QListWidget()
        self.cmd_list.setIconSize(QSize(16, 16))
        self.cmd_list.currentRowChanged.connect(self._select_command)
        add = button("Lệnh mới", "primary", "plus", on_click=self.add_command)
        samples = button("Thêm lệnh mẫu", "ghost", "sparkle", on_click=self.add_samples)
        left.add(label("LỆNH CỦA BẠN", "caption"))
        left.add(self.cmd_list, 1)
        left.add(add)
        left.add(samples)
        self.cmd_count = label("", "faint")
        left.add(self.cmd_count)
        lay.addWidget(left)

        self.editor = Card(padding=22, spacing=14, shadow=False)
        self.empty = vbox(spacing=10)
        empty_icon = QLabel()
        empty_icon.setPixmap(icons.pixmap("command", theme.c("faint"), 40, 1.4))
        empty_icon.setAlignment(Qt.AlignCenter)
        self.empty_box = QWidget()
        self.empty_box.setLayout(vbox("stretch", empty_icon,
                                      self._center(label("Chưa có lệnh nào", "h2")),
                                      self._center(label("Ghép các bước có sẵn (di chuyển, đèn, biểu cảm, tiếng bíp) "
                                                         "thành một lệnh mới. AI sẽ gọi lệnh khi thấy phù hợp.",
                                                         "muted", wrap=True)),
                                      hbox("stretch", button("Tạo lệnh đầu tiên", "primary", "plus",
                                                             on_click=self.add_command), "stretch"),
                                      "stretch", spacing=10))
        self.editor.add(self.empty_box)

        self.form = QWidget()
        form = vbox(spacing=12)
        self.form.setLayout(form)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("vd: chao_hoi")
        self.name_edit.textEdited.connect(self._rename)
        self.name_help = label("", "faint")
        self.full_name = label("", "mono")
        self.desc_edit = QPlainTextEdit()
        self.desc_edit.setPlaceholderText("Mô tả cho AI: lệnh làm gì và khi nào nên gọi. "
                                          "Ví dụ: “Robot vẫy chào. Gọi khi người dùng chào robot.”")
        self.desc_edit.setFixedHeight(76)
        self.desc_edit.textChanged.connect(self._describe)
        delete = button("Xóa lệnh", "danger", "trash", size="sm", on_click=self.delete_command)
        form.addLayout(hbox(label("Tên lệnh", "h3"), "stretch", delete))
        form.addWidget(self.name_edit)
        form.addLayout(hbox(self.full_name, "stretch", self.name_help))
        form.addWidget(label("Mô tả cho AI", "h3"))
        form.addWidget(self.desc_edit)

        add_step = button("Thêm bước", None, "plus", size="sm")
        menu = QMenu(add_step)
        for kind, text in profile.STEP_KINDS.items():
            menu.addAction(icons.icon(STEP_ICONS[kind], theme.c("text_soft"), 16), text,
                           lambda k=kind: self.add_step(k))
        add_step.setMenu(menu)
        self.total = Chip("", "neutral")
        form.addLayout(hbox(label("Các bước", "h3"), self.total, "stretch", add_step, spacing=8))
        self.steps_box = vbox(spacing=6)
        form.addLayout(self.steps_box)
        self.cmd_errors = Banner("", "error")
        form.addWidget(self.cmd_errors)
        self.run_btn = button("Chạy thử trên mạch", "primary", "play", on_click=self.run_command)
        self.run_hint = label("", "faint", wrap=True)
        run_row = hbox(self.run_btn, spacing=12)
        run_row.addWidget(self.run_hint, 1)
        form.addLayout(run_row)
        form.addStretch(1)
        self.run_hint.setSizePolicy(self.run_hint.sizePolicy().horizontalPolicy(), self.run_hint.sizePolicy().verticalPolicy())
        self.editor.add(self.form)
        lay.addWidget(self.editor, 1)
        return page

    @staticmethod
    def _center(widget):
        widget.setAlignment(Qt.AlignCenter)
        return widget

    @property
    def commands(self):
        return self.state.project.setdefault("commands", {})

    def _current(self):
        item = self.cmd_list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _fill_list(self, select=None):
        self.cmd_list.blockSignals(True)
        self.cmd_list.clear()
        for name in self.commands:
            item = QListWidgetItem(icons.icon("command", theme.c("primary"), 16), name)
            item.setData(Qt.UserRole, name)
            self.cmd_list.addItem(item)
        self.cmd_list.blockSignals(False)
        names = list(self.commands)
        if names:
            row = names.index(select) if select in names else 0
            self.cmd_list.setCurrentRow(row)
        self._select_command()
        self.cmd_count.setText(f"{len(names)}/{profile.MAX_COMMANDS} lệnh")

    def _select_command(self, *_):
        name = self._current()
        self.empty_box.setVisible(name is None)
        self.form.setVisible(name is not None)
        if name is None:
            return
        cmd = self.commands[name]
        self.name_edit.setText(name)
        self.full_name.setText(f"AI gọi: self.custom.{name}")
        self.desc_edit.blockSignals(True)
        self.desc_edit.setPlainText(cmd.get("description", ""))
        self.desc_edit.blockSignals(False)
        self._render_steps()

    def _render_steps(self):
        clear_layout(self.steps_box)
        name = self._current()
        steps = self.commands[name].get("steps", []) if name else []
        for i, step in enumerate(steps):
            self.steps_box.addWidget(StepRow(self, i, step, i == len(steps) - 1))
        if not steps:
            hint = label("Chưa có bước nào. Bấm “Thêm bước”.", "faint")
            hint.setAlignment(Qt.AlignCenter)
            hint.setMinimumHeight(48)
            self.steps_box.addWidget(hint)
        total = sum(profile.step_duration(s) for s in steps)
        self.total.set(f"{len(steps)} bước · {total / 1000:.1f} giây", "neutral" if total <= profile.MAX_RUN_MS else "error")
        self._validate()

    def _validate(self):
        name = self._current()
        errors = profile.validate_commands({name: self.commands[name]}) if name else []
        self.cmd_errors.setVisible(bool(errors))
        self.cmd_errors.set("<br>".join(errors), "error")
        valid = bool(name) and profile.COMMAND_NAME.match(name or "")
        set_prop(self.name_edit, "invalid", "false" if valid else "true")
        self.name_help.setText("" if valid else "Chữ thường không dấu, số, dấu _")
        self.update_run_button()

    def add_command(self):
        if len(self.commands) >= profile.MAX_COMMANDS:
            self.window.toast(f"Tối đa {profile.MAX_COMMANDS} lệnh", "warning")
            return
        base, i = "lenh_moi", 1
        name = base
        while name in self.commands:
            i += 1
            name = f"{base}_{i}"
        self.commands[name] = {"description": "", "params": {}, "steps": []}
        self.state.touch()
        self._fill_list(name)
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def add_samples(self):
        added = 0
        for name, cmd in profile.sample_commands().items():
            if name not in self.commands and len(self.commands) < profile.MAX_COMMANDS:
                self.commands[name] = copy.deepcopy(cmd)
                added += 1
        self.state.touch()
        self._fill_list()
        self.window.toast(f"Đã thêm {added} lệnh mẫu" if added else "Lệnh mẫu đã có sẵn", "ok" if added else "info")

    def delete_command(self):
        name = self._current()
        if not name:
            return
        if QMessageBox.question(self, "Xóa lệnh", f"Xóa lệnh “{name}”?") != QMessageBox.Yes:
            return
        del self.commands[name]
        self.state.touch()
        self._fill_list()

    def _rename(self, text):
        old = self._current()
        new = text.strip()
        if not old or not new or new == old:
            self._validate()
            return
        if new in self.commands:
            set_prop(self.name_edit, "invalid", "true")
            self.name_help.setText("Tên đã có")
            return
        # giữ thứ tự lệnh
        self.state.project["commands"] = {(new if k == old else k): v for k, v in self.commands.items()}
        self.state.touch()
        item = self.cmd_list.currentItem()
        item.setText(new)
        item.setData(Qt.UserRole, new)
        self.full_name.setText(f"AI gọi: self.custom.{new}")
        self._validate()

    def _describe(self):
        name = self._current()
        if name:
            self.commands[name]["description"] = self.desc_edit.toPlainText().strip()
            self.state.touch()
            self._validate()

    def add_step(self, kind):
        name = self._current()
        if not name:
            return
        dialog = StepDialog(self, DEFAULT_STEP[kind])
        if dialog.exec() == QDialog.Accepted:
            self.commands[name].setdefault("steps", []).append(dialog.step())
            self.state.touch()
            self._render_steps()

    def edit_step(self, index):
        name = self._current()
        steps = self.commands[name]["steps"]
        dialog = StepDialog(self, steps[index])
        if dialog.exec() == QDialog.Accepted:
            steps[index] = dialog.step()
            self.state.touch()
            self._render_steps()

    def move_step(self, index, delta):
        steps = self.commands[self._current()]["steps"]
        j = index + delta
        if 0 <= j < len(steps):
            steps[index], steps[j] = steps[j], steps[index]
            self.state.touch()
            self._render_steps()

    def delete_step(self, index):
        del self.commands[self._current()]["steps"][index]
        self.state.touch()
        self._render_steps()

    def update_run_button(self):
        st = self.state
        name = self._current()
        reason = ""
        if not st.port:
            reason = "Chọn cổng mạch để chạy thử."
        elif st.prefix == "VOI":
            reason = "Firmware Voi (cũ) chưa hỗ trợ lệnh tùy chỉnh."
        elif name and st.project.get("commands", {}).get(name) != st.applied.get("commands", {}).get(name):
            reason = "Lệnh vừa sửa: bấm Áp dụng để gửi xuống mạch trước khi chạy thử."
        self.run_btn.setEnabled(bool(name) and not reason and not st.runner.busy)
        self.run_hint.setText(reason or "Robot sẽ làm lần lượt các bước. Bấm Dừng ở thanh trên nếu cần.")

    def run_command(self):
        name = self._current()
        if name:
            self.window.run_job("run", jobs.job_run_command, self.state.port, name)

    # Prompt ----------------------------------------------------------------------------
    def _prompt_tab(self):
        page = QWidget()
        lay = vbox(spacing=16, margins=(0, 16, 0, 0))
        page.setLayout(lay)
        self.pb = Binder(self.state)
        card = Card("Tính cách của robot", "Dán đoạn này vào ô “Vai trò / Prompt” của agent trên xiaozhi.me. "
                    "Robo Dev không tự gửi lên máy chủ.", "robot")
        self.robot_name = QLineEdit()
        self.robot_name.setMaximumWidth(260)
        self.pb.bind(self.robot_name, ("name",))
        card.add(form_row("Tên robot", self.robot_name, "Dùng trong lời dặn mẫu."))
        self.prompt = QPlainTextEdit()
        self.prompt.setMinimumHeight(300)
        self.pb.bind(self.prompt, ("prompt",))
        card.add(self.prompt)
        card.add(hbox(button("Sao chép", "primary", "copy", on_click=self.copy_prompt),
                      button("Mở xiaozhi.me", None, "external", on_click=lambda: webbrowser.open(XIAOZHI_URL)),
                      "stretch",
                      button("Tạo lại từ mẫu", "ghost", "refresh", on_click=self.reset_prompt), spacing=8))
        lay.addWidget(card)

        wake = Card("Cụm gọi (wake word)", None, "mic")
        self.wake_label = label("", "h3")
        wake.add(self.wake_label)
        wake.add(label("ESP-SR không có mô hình tiếng Việt nên cụm gọi là phiên âm gần đúng. Đổi cụm gọi cần build "
                       "lại phân vùng assets (chế độ nâng cao, sẽ có ở bản sau). Lúc nào cũng có thể bấm nút BOOT "
                       "để bắt đầu nói chuyện.", "muted", wrap=True))
        lay.addWidget(wake)
        return page

    def copy_prompt(self):
        QGuiApplication.clipboard().setText(self.state.project.get("prompt", ""))
        self.window.toast("Đã sao chép lời dặn. Dán vào xiaozhi.me nhé!")

    def reset_prompt(self):
        self.state.project["prompt"] = profile.DEFAULT_PROMPT.format(name=self.state.project.get("name") or "Robo")
        self.state.touch()
        self.pb.load()

    # Chung -----------------------------------------------------------------------------
    def refresh(self):
        self._load_tools()
        self._fill_list(self._current())
        self.pb.load()
        wake = self.state.project.get("wake", {})
        self.wake_label.setText(f"“{wake.get('display', '')}”  ·  phiên âm: {wake.get('phrase', '')}  ·  ngưỡng {wake.get('threshold', '')}")

    def on_show(self):
        self._load_tools()
        self.update_run_button()

    def update_legacy(self):
        self.legacy.setVisible(self.state.prefix == "VOI")
        self.legacy.set("Firmware Voi (cũ) chỉ có các lệnh có sẵn. <b>Lệnh tùy chỉnh</b> cần firmware Robo Dev.",
                        "warning")
        self.update_run_button()

    def on_event(self, job_id, event):
        if job_id == "run" and event[0] == "done":
            self.window.toast(event[2], "ok" if event[1] else "error", 4500)
