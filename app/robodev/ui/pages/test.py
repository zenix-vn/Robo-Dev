"""Bước 6 - Kiểm tra: kiểm tra từng module và xem log trực tiếp."""
import html
import re
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QFileDialog, QLabel, QLineEdit, QPlainTextEdit, QScrollArea, QWidget)

from robodev.core import catalog
from robodev.ui import icons, theme
from robodev.ui.pages.base import Page
from robodev.ui.widgets import Banner, Card, Chip, LevelBar, Segmented, button, hbox, label, tool, vbox

LEVEL = re.compile(r"^([EWID]) \(\d+\)")
LEVEL_COLORS = {"E": "#F97066", "W": "#FDB022", "I": "#D0D5DD", "D": "#98A2B3"}

# module -> (tiêu đề, mô tả, các bước [(mã bước, nhãn nút)], câu hỏi xác nhận)
TESTS = {
    "speaker": ("Loa", "Phát một tiếng bíp ngắn.", [("tone", "Phát âm thử")], "Bạn có nghe thấy tiếng bíp không?"),
    "mic": ("Microphone", "Đo mức âm thanh trong 1 giây. Hãy vỗ tay hoặc nói to khi đang đo.",
            [("level", "Đo mức âm")], None),
    "lcd": ("Màn hình", "Hiện dải màu đỏ, xanh lá, xanh dương và khung viền.", [("colors", "Hiện màu thử")],
            "Màn hình có hiện đúng thứ tự đỏ, xanh lá, xanh dương không?"),
    "sensor": ("Cảm biến khoảng cách", "Đọc khoảng cách. Đưa tay lại gần cảm biến rồi đo lại.", [("read", "Đo khoảng cách")],
               None),
    "motors": ("Động cơ", "Quay từng bánh chậm trong 1 giây. Kê robot lên để bánh không chạm đất.",
               [("left_fwd", "Trái ▲"), ("left_back", "Trái ▼"), ("right_fwd", "Phải ▲"), ("right_back", "Phải ▼")],
               "Bánh có quay đúng bên và đúng chiều không?"),
    "led": ("Đèn LED", "Đổi màu đèn trên mạch.", [("red", "Đỏ"), ("green", "Xanh lá"), ("blue", "Xanh dương"),
                                                 ("off", "Tắt")], "Đèn có sáng đúng màu không?"),
    "button": ("Nút BOOT", "Bấm “Bắt đầu” rồi nhấn nút BOOT trên mạch trong 15 giây.", [("wait", "Bắt đầu")], None),
}


class TestCard(Card):
    def __init__(self, page, module):
        super().__init__(padding=16, spacing=10, shadow=False)
        self.page, self.module = page, module
        title, desc, steps, question = TESTS[module]
        mod = catalog.module(module)
        badge = QLabel()
        badge.setFixedSize(34, 34)
        badge.setAlignment(Qt.AlignCenter)
        badge.setPixmap(icons.pixmap(icons.MODULE_ICONS[module], mod.color, 18))
        badge.setStyleSheet(f"background: {theme.tint(mod.color)}; border-radius: 10px;")
        self.chip = Chip("Chưa kiểm tra", "neutral")
        head = hbox(badge, spacing=12)
        head.addLayout(vbox(label(title, "h3"), label(desc, "faint", wrap=True), spacing=1), 1)
        head.addWidget(self.chip, 0, Qt.AlignTop)
        self.add(head)
        self.buttons = []
        row = hbox(spacing=6)
        for step, text in steps:
            btn = button(text, None if len(steps) > 1 else "primary", "play" if len(steps) == 1 else None, size="sm",
                         on_click=lambda _=False, s=step: page.run_test(module, s))
            self.buttons.append(btn)
            row.addWidget(btn)
        row.addStretch(1)
        self.add(row)
        self.level = None
        if module == "mic":
            self.level = LevelBar()
            self.add(self.level)
        self.detail = label("", "muted", wrap=True)
        self.detail.hide()
        self.add(self.detail)
        self.question = None
        if question:
            self.question = QWidget()
            q = vbox(label(question, "h3", wrap=True),
                     hbox(button("Đúng", None, "check", size="sm", on_click=lambda: self.answer(True)),
                          button("Không", None, "x", size="sm", on_click=lambda: self.answer(False)), "stretch",
                          spacing=6), spacing=6)
            self.question.setLayout(q)
            self.question.hide()
            self.add(self.question)
        self.fix = Banner("", "info")
        self.fix.hide()
        self.add(self.fix)

    def set_enabled_state(self, enabled, reason=""):
        for btn in self.buttons:
            btn.setEnabled(enabled)
        if reason and self.chip.text() in ("Chưa kiểm tra", "Không khả dụng", "Đang tắt"):
            self.chip.set(reason, "neutral")
        elif not reason and self.chip.text() in ("Không khả dụng", "Đang tắt"):
            self.chip.set("Chưa kiểm tra", "neutral")

    def running(self):
        self.chip.set("Đang chạy...", "info")
        self.fix.hide()
        if self.question:
            self.question.hide()

    def result(self, ok, text):
        self.detail.setText(text)
        self.detail.setVisible(bool(text))
        if self.level is not None:
            m = re.search(r"avg_abs=(\d+)", text)
            if m:
                self.level.set(min(1.0, int(m.group(1)) / 3000))
        if not ok:
            self.chip.set("Lỗi", "error")
            self.show_fix(None)
            return
        if self.question:
            self.chip.set("Chờ xác nhận", "warning")
            self.question.show()
        else:
            self.chip.set("Đạt", "ok")
            if self.module == "mic" and "avg_abs=" in text:
                m = re.search(r"avg_abs=(\d+)", text)
                if m and int(m.group(1)) < 50:
                    self.chip.set("Quá nhỏ", "warning")
                    self.show_fix("mic_quiet")

    def answer(self, yes):
        self.question.hide()
        if yes:
            self.chip.set("Đạt", "ok")
            self.fix.hide()
        else:
            self.chip.set("Chưa đúng", "error")
            self.show_fix(self.module)

    def show_fix(self, key):
        tips = {
            None: "Mạch báo lỗi. Kiểm tra lại dây của module này ở bước Nối chân và đối chiếu với log bên phải.",
            "speaker": "Kiểm tra dây LRC, BCLK, DIN và nguồn Vin của MAX98357A. Loa: đỏ vào +, đen vào −.",
            "lcd": "Nếu màu bị đảo, bật/tắt “Đảo màu” ở thẻ Màn hình (bước Nối chân, chế độ Nâng cao). "
                   "Nếu không hiện gì, kiểm tra dây SCL, SDA, DC, RST.",
            "motors": "Bánh quay ngược chiều → bật “Đảo chiều bánh” ở bước Tính năng. Bánh trái/phải bị đổi → bật "
                      "“Đổi bánh trái ↔ phải”.",
            "led": "Đèn sai màu → đổi “Thứ tự màu” (GRB/RGB) ở thẻ Đèn LED, bước Nối chân (chế độ Nâng cao).",
            "mic_quiet": "Mức âm rất nhỏ: kiểm tra chân L/R của mic phải nối 3V3, và dây WS, SCK, SD.",
        }
        self.fix.set(tips.get(key, tips[None]), "info")
        self.fix.show()


class TestPage(Page):
    title = "Kiểm tra"
    subtitle = "Thử từng module trên mạch thật và xem log trực tiếp để tìm chỗ nối sai."
    icon = "activity"

    def __init__(self, state, window):
        super().__init__(state, window, scroll=False)
        self.paused = False
        self.lines = []           # (level, text) để lọc lại

        body = hbox(spacing=20)
        # Trái: các bài kiểm tra
        left = QWidget()
        left.setObjectName("Page")
        left_lay = vbox(spacing=12)
        left.setLayout(left_lay)
        self.cards = {}
        for module in TESTS:
            card = TestCard(self, module)
            self.cards[module] = card
            left_lay.addWidget(card)
        left_lay.addStretch(1)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setWidget(left)
        area.setMinimumWidth(440)
        body.addWidget(area, 5)

        # Phải: log
        log_card = Card(padding=14, spacing=10, shadow=False)
        self.live = Chip("Chưa mở log", "neutral")
        self.start_btn = button("Mở log", "primary", "play", size="sm", on_click=self.toggle_monitor)
        self.reset_btn = button("Khởi động lại", None, "refresh", size="sm",
                                on_click=lambda: self.state.runner.send(("reset",)))
        self.filter = Segmented([("all", "Tất cả"), ("W", "Cảnh báo"), ("E", "Lỗi")])
        self.filter.set("all")
        self.filter.changed.connect(lambda _: self.rerender())
        self.search = QLineEdit()
        self.search.setPlaceholderText("Tìm trong log...")
        self.search.addAction(icons.icon("search", theme.c("faint"), 16), QLineEdit.LeadingPosition)
        self.search.textChanged.connect(lambda _: self.rerender())
        self.search.setMaximumWidth(220)
        self.pause_btn = tool("pause", "Tạm dừng cuộn", self.toggle_pause)
        log_card.add(hbox(label("Log của mạch", "h2"), self.live, "stretch", self.reset_btn, self.start_btn, spacing=8))
        log_card.add(hbox(self.filter, "stretch", self.search, self.pause_btn,
                          tool("clear", "Xóa màn hình", self.clear_log), tool("save", "Lưu log ra file", self.save_log),
                          spacing=6))
        self.console = QPlainTextEdit()
        self.console.setObjectName("Console")
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(5000)
        self.console.setLineWrapMode(QPlainTextEdit.NoWrap)
        log_card.add(self.console, 1)
        self.cmd = QLineEdit()
        self.cmd.setObjectName("ConsoleInput")
        self.cmd.setPlaceholderText("Gửi lệnh tới mạch, ví dụ RD_INFO  (Enter để gửi)")
        self.cmd.returnPressed.connect(self.send_command)
        log_card.add(hbox(self.cmd, button("Gửi", None, "send", size="sm", on_click=self.send_command), spacing=6))
        body.addWidget(log_card, 6)
        self.content.addLayout(body, 1)

        self.flush_timer = QTimer(self)
        self.flush_timer.timeout.connect(self.flush)
        self.flush_timer.start(80)
        self.pending = []

        state.port_changed.connect(lambda _: self.update_state())
        state.busy_changed.connect(lambda _: self.update_state())
        state.device_changed.connect(self.update_state)
        state.project_changed.connect(self.update_state)
        state.runner.started.connect(lambda job: self.update_state())
        state.runner.finished.connect(lambda job, ok, msg: self.update_state())
        self.update_state()

    # Phiên log --------------------------------------------------------------------------
    def on_show(self):
        if self.state.port and not self.state.runner.monitoring and not self.state.runner.busy:
            self.state.runner.start_monitor(self.state.port)
        self.update_state()

    def toggle_monitor(self):
        runner = self.state.runner
        if runner.monitoring:
            runner.stop_monitor()
        else:
            runner.start_monitor(self.state.port)
        QTimer.singleShot(150, self.update_state)

    def update_state(self):
        st = self.state
        runner = st.runner
        on = runner.monitoring
        self.live.set(("Đang xem · " + ("mô phỏng" if st.is_demo else st.port)) if on else
                      ("Đang bận việc khác" if runner.busy else "Chưa mở log"), "ok" if on else "neutral")
        self.start_btn.setText("Dừng log" if on else "Mở log")
        self.start_btn.setIcon(icons.icon("stop" if on else "play", "#FFFFFF", 16))
        self.start_btn.setEnabled(bool(st.port) and not runner.busy)
        self.reset_btn.setEnabled(on)
        self.cmd.setEnabled(on)
        hw = st.project["hw"]
        for module, card in self.cards.items():
            enabled_module = hw.get(module, {}).get("enabled", True)
            if not enabled_module:
                card.set_enabled_state(False, "Đang tắt")
            elif not on:
                card.set_enabled_state(False, "Không khả dụng" if not st.port else "")
                for btn in card.buttons:
                    btn.setToolTip("Mở log trước để chạy kiểm tra")
            else:
                card.set_enabled_state(True)
                for btn in card.buttons:
                    btn.setToolTip("")

    def run_test(self, module, step):
        if self.state.runner.send(("test", module, step)):
            self.cards[module].running()

    def send_command(self):
        text = self.cmd.text().strip()
        if text and self.state.runner.send(text):
            self.cmd.clear()

    # Log --------------------------------------------------------------------------------
    def on_event(self, job_id, event):
        kind = event[0]
        if kind == "log":
            self.pending.append(event[1])
        elif job_id == "monitor":
            if kind == "test":
                _, module, step, ok, text = event
                if module in self.cards:
                    self.cards[module].result(ok, text)
            elif kind == "firmware":
                self.state.set_firmware(event[1])
            elif kind == "done":
                self.pending.append(f"[Robo Dev] {event[2]}")
                QTimer.singleShot(50, self.update_state)

    def flush(self):
        if not self.pending:
            return
        batch, self.pending = self.pending, []
        stamp = time.strftime("%H:%M:%S")
        html_lines = []
        for line in batch:
            m = LEVEL.match(line)
            level = m.group(1) if m else ("R" if line.startswith("[Robo Dev]") else ">" if line.startswith(">") else "I")
            self.lines.append((stamp, level, line))
            if self._visible(level, line):
                html_lines.append(self._html(stamp, level, line))
        if len(self.lines) > 8000:
            self.lines = self.lines[-6000:]
        if html_lines and not self.paused:
            self.console.appendHtml("<br>".join(html_lines))
            self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())
        elif html_lines:
            cursor_pos = self.console.verticalScrollBar().value()
            self.console.appendHtml("<br>".join(html_lines))
            self.console.verticalScrollBar().setValue(cursor_pos)

    def _visible(self, level, line):
        f = self.filter.value()
        if f == "E" and level != "E":
            return False
        if f == "W" and level not in ("E", "W"):
            return False
        query = self.search.text().strip().lower()
        return not query or query in line.lower()

    @staticmethod
    def _html(stamp, level, line):
        color = LEVEL_COLORS.get(level, "#D0D5DD")
        if level == "R":
            color = "#A5B4FC"
        elif level == ">":
            color = "#6CE9A6"
        elif "_OK" in line or "PONG" in line:
            color = "#6CE9A6"
        elif "_ERR" in line:
            color = "#F97066"
        return (f"<span style='color:#475467'>{stamp}</span>&nbsp;&nbsp;"
                f"<span style='color:{color}; white-space:pre'>{html.escape(line)}</span>")

    def rerender(self):
        self.console.clear()
        out = [self._html(s, lv, ln) for s, lv, ln in self.lines if self._visible(lv, ln)]
        if out:
            self.console.appendHtml("<br>".join(out[-3000:]))

    def toggle_pause(self):
        self.paused = not self.paused
        self.pause_btn.setIcon(icons.icon("play" if self.paused else "pause", theme.c("muted"), 18))
        self.pause_btn.setToolTip("Tiếp tục cuộn" if self.paused else "Tạm dừng cuộn")

    def clear_log(self):
        self.lines.clear()
        self.console.clear()

    def save_log(self):
        path, _ = QFileDialog.getSaveFileName(self, "Lưu log", time.strftime("robodev-log-%Y%m%d-%H%M%S.txt"),
                                              "Văn bản (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(f"{s} {ln}" for s, _, ln in self.lines))
            self.window.toast("Đã lưu log")
