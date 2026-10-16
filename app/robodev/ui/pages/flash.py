"""Bước 5 - Nạp & kết nối: nạp firmware, gửi cấu hình, cài Wi-Fi, nhận mã kích hoạt xiaozhi.me."""
import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFileDialog, QLabel, QLineEdit, QPlainTextEdit,
                               QProgressBar, QPushButton)

from robodev.core import firmware, jobs, link, pins
from robodev.ui import icons, theme
from robodev.ui.pages.base import Page
from robodev.ui.widgets import Banner, Card, StepList, button, hbox, label, vbox

XIAOZHI_URL = "https://xiaozhi.me"


class ChoiceButton(QPushButton):
    """Nút chọn dạng thẻ: kích thước theo nội dung bên trong."""

    def sizeHint(self):  # noqa: N802
        return self.layout().sizeHint()

    def minimumSizeHint(self):  # noqa: N802
        return self.layout().minimumSize()

    def hasHeightForWidth(self):  # noqa: N802
        return True

    def heightForWidth(self, width):  # noqa: N802
        return self.layout().heightForWidth(width)


def choice(title, text, icon_name):
    btn = ChoiceButton()
    btn.setCheckable(True)
    btn.setProperty("choice", "true")
    btn.setCursor(Qt.PointingHandCursor)
    lay = hbox(spacing=12, margins=(16, 14, 16, 14))
    ic = QLabel()
    ic.setPixmap(icons.pixmap(icon_name, theme.c("primary"), 22))
    ic.setAttribute(Qt.WA_TransparentForMouseEvents)
    texts = vbox(label(title, "h3"), label(text, "muted", wrap=True), spacing=2)
    for i in range(texts.count()):
        texts.itemAt(i).widget().setAttribute(Qt.WA_TransparentForMouseEvents)
    lay.addWidget(ic, 0, Qt.AlignTop)
    lay.addLayout(texts, 1)
    btn.setLayout(lay)
    policy = btn.sizePolicy()
    policy.setHeightForWidth(True)
    btn.setSizePolicy(policy)
    return btn


class FlashPage(Page):
    title = "Nạp & kết nối"
    subtitle = "Nạp firmware vào mạch, gửi cấu hình, cài Wi-Fi và kích hoạt với xiaozhi.me."
    icon = "flash"

    def __init__(self, state, window):
        super().__init__(state, window)
        body = hbox(spacing=20)
        left = vbox(spacing=18)
        right = vbox(spacing=18)
        body.addLayout(left, 11)
        body.addLayout(right, 9)
        self.content.addLayout(body)

        # 1. Firmware -------------------------------------------------------------------
        fw = Card("Firmware", "Chọn gói firmware và cách nạp.", "flash")
        self.package = QComboBox()
        self.package.currentIndexChanged.connect(self.update_package)
        pick = button("Chọn file...", "ghost", "folder", on_click=self.pick_file)
        row = hbox(spacing=8)
        row.addWidget(self.package, 1)
        row.addWidget(pick)
        fw.add(row)
        self.package_note = label("", "faint", wrap=True)
        fw.add(self.package_note)
        self.mode_fast = choice("Nạp nhanh", "Giữ Wi-Fi và cấu hình. Dùng khi cập nhật firmware.", "refresh")
        self.mode_full = choice("Nạp đầy đủ", "Mạch mới hoặc bị lỗi. Xóa Wi-Fi đã lưu, mất khoảng 2-3 phút.", "flash")
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.mode_fast)
        self.mode_group.addButton(self.mode_full)
        self.mode_fast.setChecked(True)
        fw.add(hbox(self.mode_fast, self.mode_full, spacing=12))
        self.assets = QCheckBox("Nạp cả phân vùng assets (cụm gọi, ảnh khuôn mặt)")
        fw.add(self.assets)
        left.addWidget(fw)

        # 2. Wi-Fi ----------------------------------------------------------------------
        wifi = Card("Wi-Fi", "Robot cần Wi-Fi 2.4 GHz để nói chuyện với xiaozhi.me.", "wifi")
        self.ssid = QComboBox()
        self.ssid.setEditable(True)
        self.ssid.lineEdit().setPlaceholderText("Tên Wi-Fi")
        for name in self.state.settings.value("ssids", [], type=list) or []:
            self.ssid.addItem(name)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("Mật khẩu")
        eye = QAction(icons.icon("eye", theme.c("muted"), 16), "Hiện mật khẩu", self.password)
        eye.setCheckable(True)
        eye.toggled.connect(lambda on: (self.password.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password),
                                        eye.setIcon(icons.icon("eye-off" if on else "eye", theme.c("muted"), 16))))
        self.password.addAction(eye, QLineEdit.TrailingPosition)
        wifi.add(vbox(label("Tên Wi-Fi", "h3"), self.ssid, spacing=4))
        wifi.add(vbox(label("Mật khẩu", "h3"), self.password, spacing=4))
        wifi.add(label("Tên Wi-Fi được nhớ cho lần sau; mật khẩu không được lưu.", "faint"))
        left.addWidget(wifi)

        # Hành động ---------------------------------------------------------------------
        self.go_btn = button("Nạp && kết nối", "primary", "flash", size="lg", on_click=self.start_flash)
        self.apply_btn = button("Chỉ gửi cấu hình", None, "send", on_click=self.start_apply)
        self.wifi_btn = button("Chỉ cài Wi-Fi", None, "wifi", on_click=self.start_wifi)
        self.block = Banner("", "warning")
        left.addWidget(self.block)
        left.addLayout(hbox(self.go_btn, self.apply_btn, self.wifi_btn, "stretch", spacing=10))
        left.addStretch(1)

        # Tiến trình --------------------------------------------------------------------
        prog = Card("Tiến trình", None, "activity")
        self.status = label("Sẵn sàng.", "muted", wrap=True)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setFixedHeight(8)
        prog.add(self.status)
        prog.add(self.bar)
        self.steps = StepList(jobs.FLASH_STEPS + link.ACTIVATION_STEPS)
        prog.add(self.steps)
        self.result = Banner("", "success")
        self.result.hide()
        prog.add(self.result)
        self.log_toggle = button("Xem chi tiết", "link", on_click=self.toggle_log)
        prog.add(hbox(self.log_toggle, "stretch"))
        self.log = QPlainTextEdit()
        self.log.setObjectName("Console")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(3000)
        self.log.setFixedHeight(200)
        self.log.hide()
        prog.add(self.log)
        right.addWidget(prog)

        # Mã kích hoạt ------------------------------------------------------------------
        self.code_card = Card("Mã kích hoạt", "Vào xiaozhi.me → Bảng điều khiển → Thêm thiết bị, rồi nhập mã này.",
                              "sparkle")
        self.code = label("------", "code")
        self.code.setAlignment(Qt.AlignCenter)
        self.code.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.code.setStyleSheet(f"background: {theme.c('primary_soft')}; border-radius: 12px; padding: 14px;")
        self.code_card.add(self.code)
        self.code_card.add(hbox(button("Sao chép mã", "primary", "copy", on_click=self.copy_code),
                                button("Mở xiaozhi.me", None, "external", on_click=lambda: webbrowser.open(XIAOZHI_URL)),
                                "stretch", spacing=8))
        self.code_card.hide()
        right.addWidget(self.code_card)
        right.addStretch(1)

        state.device_changed.connect(self.update_buttons)
        state.port_changed.connect(lambda _: self.update_buttons())
        state.busy_changed.connect(lambda _: self.update_buttons())
        state.mode_changed.connect(lambda _: self.update_buttons())
        state.dirty_changed.connect(lambda _: self.update_buttons())
        self.fill_packages()
        self.update_buttons()

    # Firmware ---------------------------------------------------------------------------
    def fill_packages(self, select=None):
        self.package.blockSignals(True)
        self.package.clear()
        for pkg in self.state.packages:
            self.package.addItem(icons.icon("chip", theme.c("muted"), 16), f"{pkg.name}  ·  {pkg.version}", pkg)
        if not self.state.packages:
            self.package.addItem("Chưa có gói firmware nào trong thư mục firmware/", None)
        self.package.blockSignals(False)
        if select is not None:
            self.package.setCurrentIndex(select)
        self.update_package()

    def current_package(self):
        return self.package.currentData()

    def update_package(self, *_):
        pkg = self.current_package()
        if not pkg:
            self.package_note.setText("Đặt gói firmware (thư mục có manifest.json) vào thư mục firmware/ cạnh chương trình, "
                                      "hoặc bấm “Chọn file...”.")
        else:
            self.package_note.setText(pkg.notes or "Firmware Robo Dev.")
            fast_ok = all(pkg.has(r) for r in firmware.FAST_FILES)
            self.mode_fast.setEnabled(fast_ok)
            if not fast_ok:
                self.mode_full.setChecked(True)
            self.assets.setEnabled(pkg.has("assets"))
        self.update_buttons()

    def pick_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn file firmware", "", "Firmware (*.bin)")
        if path:
            self.state.packages.append(firmware.single_file(path))
            self.fill_packages(len(self.state.packages) - 1)
            self.mode_full.setChecked(True)

    # Nút ------------------------------------------------------------------------------
    def update_buttons(self):
        st = self.state
        reasons = []
        if not st.port:
            reasons.append("Chọn cổng mạch ở thanh bên trái.")
        if any(i.level == "error" for i in pins.validate(st.project["hw"])):
            reasons.append("Cách nối chân đang có lỗi: sửa ở bước <b>Nối chân</b> trước khi nạp.")
        busy = st.runner.busy
        self.block.setVisible(bool(reasons) and not busy)
        self.block.set("<br>".join(reasons), "warning")
        ok = not reasons and not busy
        self.go_btn.setEnabled(ok and self.current_package() is not None)
        self.apply_btn.setEnabled(ok)
        self.wifi_btn.setEnabled(bool(st.port) and not busy)
        self.assets.setVisible(st.advanced)

    def _begin(self, title):
        self.steps.reset()
        self.bar.setValue(0)
        self.bar.setProperty("tone", "")
        self.result.hide()
        self.code_card.hide()
        self.status.setText(title)
        self.log.clear()

    def remember_ssid(self):
        ssid = self.ssid.currentText().strip()
        if not ssid:
            return
        saved = [s for s in (self.state.settings.value("ssids", [], type=list) or []) if s != ssid]
        saved.insert(0, ssid)
        self.state.settings.setValue("ssids", saved[:8])

    def start_flash(self):
        pkg = self.current_package()
        mode = "full" if self.mode_full.isChecked() else "fast"
        self._begin("Đang nạp firmware. Đừng rút cáp cho tới khi xong.")
        self.remember_ssid()
        self.window.run_job("flash", jobs.job_flash, self.state.port, pkg, mode,
                            self.assets.isChecked() and self.assets.isVisible(), self.state.project,
                            self.ssid.currentText().strip(), self.password.text())

    def start_apply(self):
        self._begin("Đang gửi cấu hình xuống mạch...")
        self.window.run_job("apply", jobs.job_apply, self.state.port, self.state.project)

    def start_wifi(self):
        ssid = self.ssid.currentText().strip()
        if not ssid:
            self.window.toast("Nhập tên Wi-Fi trước", "warning")
            self.ssid.setFocus()
            return
        self._begin("Đang cài Wi-Fi và chờ kích hoạt...")
        self.remember_ssid()
        self.window.run_job("wifi", jobs.job_wifi, self.state.port, ssid, self.password.text())

    def toggle_log(self):
        self.log.setVisible(not self.log.isVisible())
        self.log_toggle.setText("Ẩn chi tiết" if self.log.isVisible() else "Xem chi tiết")

    def copy_code(self):
        QGuiApplication.clipboard().setText(self.code.text())
        self.window.toast("Đã sao chép mã kích hoạt")

    # Sự kiện --------------------------------------------------------------------------
    def on_event(self, job_id, event):
        if job_id not in ("flash", "apply", "wifi"):
            return
        kind = event[0]
        if kind == "log":
            self.log.appendPlainText(event[1])
        elif kind == "progress":
            self.bar.setValue(int(event[1]))
        elif kind == "step":
            _, key, state, text = event
            self.steps.set(key, state, text)
            if state == "run" and text:
                self.status.setText(text)
            if key == "flash" and state == "ok":
                self.bar.setValue(100)
                self.bar.setProperty("tone", "ok")
                self.bar.style().polish(self.bar)
        elif kind == "code":
            self.code.setText(event[1])
            self.code_card.show()
        elif kind == "done":
            ok, message = event[1], event[2]
            self.status.setText("Xong." if ok else "Chưa xong.")
            self.result.set(message, "success" if ok else "error")
            self.result.show()

