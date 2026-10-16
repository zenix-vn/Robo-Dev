"""Cửa sổ chính: thanh bên (các bước, hồ sơ, thiết bị), các trang, thanh Áp dụng và thông báo."""
import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu, QMessageBox,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from robodev import APP_NAME, __version__, paths
from robodev.core import jobs, link, pins, profile
from robodev.ui import icons, theme
from robodev.ui.pages.commands import CommandsPage
from robodev.ui.pages.device import DevicePage
from robodev.ui.pages.features import FeaturesPage
from robodev.ui.pages.flash import FlashPage
from robodev.ui.pages.pins import PinsPage
from robodev.ui.pages.test import TestPage
from robodev.ui.widgets import Dot, Toast, Toggle, button, hbox, tool, vbox

PAGES = [("device", DevicePage), ("pins", PinsPage), ("features", FeaturesPage), ("commands", CommandsPage),
         ("flash", FlashPage), ("test", TestPage)]
JOB_LABELS = {"check": "Đang kiểm tra mạch", "flash": "Đang nạp firmware", "apply": "Đang áp dụng cấu hình",
              "wifi": "Đang cài Wi-Fi", "run": "Đang chạy thử lệnh"}


class NavItem(QPushButton):
    def __init__(self, index, title, icon_name):
        super().__init__()
        self.setObjectName("NavItem")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(44)
        self.icon_name = icon_name
        self.icon_label = QLabel()
        self.text_label = QLabel(f"{title}")
        self.num = QLabel(str(index))
        self.mark = QLabel()
        self.mark.setFixedSize(18, 18)
        for w in (self.icon_label, self.text_label, self.num, self.mark):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(12)
        lay.addWidget(self.icon_label)
        lay.addWidget(self.text_label, 1)
        lay.addWidget(self.mark)
        self.num.hide()
        self.toggled.connect(lambda _: self.restyle())
        self.status = None
        self.restyle()

    def set_status(self, status):
        self.status = status
        if status == "ok":
            self.mark.setPixmap(icons.pixmap("check-circle", theme.c("success"), 18))
        elif status == "error":
            self.mark.setPixmap(icons.pixmap("alert", theme.c("warning"), 18))
        else:
            self.mark.clear()

    def restyle(self):
        on = self.isChecked()
        color = theme.c("sidebar_strong") if on else theme.c("sidebar_text")
        accent = theme.c("sidebar_accent") if on else theme.c("sidebar_muted")
        self.icon_label.setPixmap(icons.pixmap(self.icon_name, accent, 19))
        self.text_label.setStyleSheet(f"color: {color}; font-weight: {600 if on else 500}; background: transparent;")


class MainWindow(QMainWindow):
    def __init__(self, state, rebuild=None):
        super().__init__()
        self.state = state
        self.rebuild = rebuild
        self.setWindowTitle(APP_NAME)
        self.resize(1360, 860)
        self.setMinimumSize(1120, 720)

        root = QWidget()
        root_lay = QHBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)
        self.setCentralWidget(root)
        root_lay.addWidget(self._sidebar())

        self.content = QWidget()
        self.content.setObjectName("Content")
        content_lay = QVBoxLayout(self.content)
        content_lay.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        content_lay.addWidget(self.stack)
        root_lay.addWidget(self.content, 1)

        self.pages = {}
        for key, cls in PAGES:
            page = cls(state, self)
            self.pages[key] = page
            self.stack.addWidget(page)

        self.apply_bar = self._apply_bar()
        self.content.toast_lift = lambda: self.apply_bar.height() + 16 if self.apply_bar.isVisible() else 0
        self.toast_box = Toast(self.content)

        runner = state.runner
        runner.event.connect(self.on_event)
        runner.started.connect(self.on_started)
        runner.finished.connect(self.on_finished)
        state.dirty_changed.connect(lambda _: self.update_apply_bar())
        state.project_changed.connect(self.update_nav)
        state.dirty_changed.connect(lambda _: self.update_nav())
        state.device_changed.connect(self.update_device_box)
        state.busy_changed.connect(lambda _: (self.update_device_box(), self.update_apply_bar()))

        QShortcut(QKeySequence.Save, self, self.save)
        QShortcut(QKeySequence.Open, self, self.open_project)
        QShortcut(QKeySequence.New, self, self.new_project)
        for i, (key, _) in enumerate(PAGES):
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self, lambda k=key: self.go(k))

        self.port_timer = QTimer(self)
        self.port_timer.timeout.connect(self.poll_ports)
        self.port_timer.start(2000)
        self.poll_ports(initial=True)

        self.go(state.settings.value("last_page", "device") or "device")
        self.update_nav()
        self.update_device_box()
        self.update_apply_bar()
        self.update_title()

    # Thanh bên ---------------------------------------------------------------------------
    def _sidebar(self):
        side = QWidget()
        side.setObjectName("Sidebar")
        side.setFixedWidth(268)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(16, 20, 16, 16)
        lay.setSpacing(6)

        logo = QLabel()
        logo.setFixedSize(40, 40)
        logo.setAlignment(Qt.AlignCenter)
        logo.setPixmap(icons.pixmap("robot", "#FFFFFF", 24, 1.8))
        logo.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6366F1, stop:1 #06B6D4);"
                           " border-radius: 11px;")
        brand = QLabel(APP_NAME)
        brand.setObjectName("Brand")
        sub = QLabel(f"ESP32-S3 · v{__version__}")
        sub.setObjectName("BrandSub")
        lay.addLayout(hbox(logo, vbox(brand, sub, spacing=0), "stretch", spacing=12))
        lay.addSpacing(16)

        self.project_btn = QPushButton()
        self.project_btn.setObjectName("ProjectButton")
        self.project_btn.setCursor(Qt.PointingHandCursor)
        self.project_btn.setIcon(icons.icon("file", theme.c("sidebar_accent"), 16))
        menu = QMenu(self.project_btn)
        menu.addAction(icons.icon("plus", theme.c("text_soft"), 16), "Hồ sơ mới", self.new_project, QKeySequence.New)
        menu.addAction(icons.icon("folder", theme.c("text_soft"), 16), "Mở hồ sơ...", self.open_project, QKeySequence.Open)
        menu.addAction(icons.icon("save", theme.c("text_soft"), 16), "Lưu", self.save, QKeySequence.Save)
        menu.addAction("Lưu thành...", self.save_as)
        menu.addSeparator()
        menu.addAction("Mở thư mục hồ sơ", lambda: os.startfile(paths.user_dir()))  # noqa: S606
        self.project_btn.setMenu(menu)
        cap = QLabel("HỒ SƠ")
        cap.setObjectName("SideCaption")
        lay.addWidget(cap)
        lay.addWidget(self.project_btn)
        lay.addSpacing(14)

        cap = QLabel("CÁC BƯỚC")
        cap.setObjectName("SideCaption")
        lay.addWidget(cap)
        self.nav = {}
        for i, (key, cls) in enumerate(PAGES, start=1):
            item = NavItem(i, f"{i}. {cls.title}", cls.icon)
            item.clicked.connect(lambda _=False, k=key: self.go(k))
            item.setToolTip(f"{cls.subtitle}  (Ctrl+{i})")
            self.nav[key] = item
            lay.addWidget(item)
        lay.addStretch(1)

        # Hộp thiết bị
        box = QFrame()
        box.setObjectName("DeviceBox")
        b = QVBoxLayout(box)
        b.setContentsMargins(14, 12, 14, 12)
        b.setSpacing(8)
        self.dev_dot = Dot()
        self.dev_title = QLabel("Mạch")
        self.dev_title.setObjectName("DeviceTitle")
        b.addLayout(hbox(self.dev_dot, self.dev_title, "stretch", spacing=8))
        self.port_combo = QComboBox()
        self.port_combo.setObjectName("PortCombo")
        self.port_combo.currentIndexChanged.connect(self.on_port_selected)
        refresh = tool("refresh", "Tìm lại cổng", lambda: self.poll_ports(force=True), color=theme.c("sidebar_text"), size=16)
        refresh.setObjectName("SideIcon")
        b.addLayout(hbox(self.port_combo, refresh, spacing=4))
        self.dev_sub = QLabel("")
        self.dev_sub.setObjectName("DeviceSub")
        self.dev_sub.setWordWrap(True)
        b.addWidget(self.dev_sub)
        self.busy_label = QLabel("")
        self.busy_label.setObjectName("DeviceTitle")
        self.stop_btn = QPushButton("Dừng")
        self.stop_btn.setProperty("kind", "danger")
        self.stop_btn.setProperty("size", "sm")
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.clicked.connect(self.state.runner.stop)
        self.busy_row = QWidget()
        self.busy_row.setLayout(hbox(self.busy_label, "stretch", self.stop_btn, spacing=6))
        b.addWidget(self.busy_row)
        lay.addWidget(box)
        lay.addSpacing(10)

        # Chế độ + giao diện
        self.adv_toggle = Toggle(self.state.advanced)
        self.adv_toggle.toggled.connect(self.state.set_advanced)
        adv = QLabel("Chế độ nâng cao")
        adv.setStyleSheet(f"color: {theme.c('sidebar_text')};")
        adv.setToolTip("Hiện thêm thông số kỹ thuật: thông số màn hình, bảng cảm xúc, assets...")
        theme_btn = tool("sun" if theme.is_dark() else "moon", "Đổi giao diện sáng/tối", self.toggle_theme,
                         color=theme.c("sidebar_text"), size=17)
        theme_btn.setObjectName("SideIcon")
        lay.addLayout(hbox(self.adv_toggle, adv, "stretch", theme_btn, spacing=10))
        return side

    def _apply_bar(self):
        bar = QFrame(self.content)
        bar.setObjectName("ApplyBar")
        self.apply_text = QLabel("Có thay đổi chưa gửi xuống mạch")
        self.apply_text.setObjectName("ApplyText")
        self.apply_sub = QLabel("")
        self.apply_sub.setObjectName("ApplySub")
        self.revert_btn = button("Hoàn tác", "ghost", on_click=self.state.revert)
        self.revert_btn.setStyleSheet(f"QPushButton {{ color: {theme.c('surface')}; }}"
                                      f"QPushButton:hover {{ background: rgba(255,255,255,0.08); border-color: transparent; }}")
        self.apply_btn = button("Áp dụng xuống mạch", "primary", "send", on_click=self.apply)
        lay = hbox(spacing=12, margins=(20, 12, 12, 12))
        bar.setLayout(lay)
        icon = QLabel()
        icon.setPixmap(icons.pixmap("info", "#A5B4FC", 20))
        lay.addWidget(icon)
        lay.addLayout(vbox(self.apply_text, self.apply_sub, spacing=0), 1)
        lay.addWidget(self.revert_btn)
        lay.addWidget(self.apply_btn)
        bar.hide()
        return bar

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._place_apply_bar()

    def _place_apply_bar(self):
        w = min(760, self.content.width() - 72)
        self.apply_bar.setFixedWidth(w)
        self.apply_bar.adjustSize()
        self.apply_bar.move((self.content.width() - w) // 2, self.content.height() - self.apply_bar.height() - 22)
        self.apply_bar.raise_()

    # Điều hướng ---------------------------------------------------------------------------
    def go(self, key):
        if key not in self.pages:
            key = "device"
        for k, item in self.nav.items():
            item.setChecked(k == key)
        page = self.pages[key]
        self.stack.setCurrentWidget(page)
        self.state.settings.setValue("last_page", key)
        page.on_show()
        self.update_apply_bar()

    def update_nav(self):
        st = self.state
        self.nav["device"].set_status("ok" if st.chip_ok and st.version else None)
        has_errors = any(i.level == "error" for i in pins.validate(st.project["hw"]))
        self.nav["pins"].set_status("error" if has_errors else "ok")
        self.nav["flash"].set_status("ok" if st.activated else None)
        self.project_btn.setText(("  " + st.title) + ("  •" if st.unsaved else ""))
        self.project_btn.setToolTip(st.path or "Hồ sơ chưa lưu")
        self.update_title()

    def update_title(self):
        st = self.state
        name = os.path.basename(st.path) if st.path else "Hồ sơ mới"
        self.setWindowTitle(f"{name}{' *' if st.unsaved else ''} — {APP_NAME}")

    # Thiết bị ---------------------------------------------------------------------------
    def poll_ports(self, initial=False, force=False):
        try:
            ports = link.list_ports()
        except Exception:  # noqa: BLE001
            return
        current = [self.port_combo.itemData(i) for i in range(self.port_combo.count())]
        wanted = [None] + [p.device for p in ports]
        if wanted == current and not force and not initial:
            return
        selected = self.state.port
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        self.port_combo.addItem("Chọn cổng mạch...", None)
        for p in ports:
            ic = {"native": "usb", "uart": "usb", "demo": "sparkle"}.get(p.kind, "chip")
            self.port_combo.addItem(icons.icon(ic, theme.c("muted"), 16), p.label, p.device)
        self.port_combo.blockSignals(False)
        devices = [p.device for p in ports]
        esp = [p.device for p in ports if p.kind in ("uart", "native")]
        if initial:
            last = self.state.settings.value("last_port", "")
            selected = last if last in devices else (esp[0] if esp else None)
        elif selected and selected not in devices:
            self.toast(f"Mất kết nối với {selected}. Kiểm tra cáp USB.", "warning", 4500)
            selected = None
        elif not selected and esp:
            new = [d for d in esp if d not in current]
            if new:
                selected = new[0]
                self.toast(f"Đã thấy mạch trên {selected}", "ok")
        index = self.port_combo.findData(selected) if selected else 0
        self.port_combo.blockSignals(True)
        self.port_combo.setCurrentIndex(max(0, index))
        self.port_combo.blockSignals(False)
        self.state.set_port(selected)
        self.update_device_box()

    def on_port_selected(self, _):
        port = self.port_combo.currentData()
        if self.state.runner.monitoring:
            self.state.runner.stop_monitor()
        self.state.set_port(port)
        if self.stack.currentWidget() is self.pages["test"]:
            self.pages["test"].on_show()

    def update_device_box(self):
        st = self.state
        busy = st.runner.busy
        if not st.port:
            self.dev_dot.set(theme.c("sidebar_muted"))
            self.dev_title.setText("Chưa chọn mạch")
            self.dev_sub.setText("Cắm cáp USB-C vào mạch, hoặc chọn DEMO để dùng thử.")
        else:
            color = theme.c("success") if st.version else "#7CD4FD"
            self.dev_dot.set(color)
            self.dev_title.setText("Mạch mô phỏng" if st.is_demo else f"Mạch trên {st.port}")
            self.dev_sub.setText(st.firmware_label if st.version else "Chưa kiểm tra · bấm Kiểm tra mạch")
        self.busy_row.setVisible(busy)
        self.busy_label.setText(JOB_LABELS.get(st.runner.job_id, "Đang chạy") + "...")
        self.port_combo.setEnabled(not busy)

    # Việc nền ---------------------------------------------------------------------------
    def run_job(self, job_id, func, *args):
        if self.state.runner.busy:
            self.toast("Đang có việc khác chạy. Đợi xong hoặc bấm Dừng.", "warning")
            return False
        return self.state.runner.start(job_id, func, *args)

    def on_started(self, job_id):
        self.update_device_box()

    def on_event(self, job_id, event):
        if event[0] == "firmware":
            self.state.set_firmware(event[1])
        elif event[0] == "caps":
            self.state.set_caps(event[1])
        elif event[0] == "info":
            self.state.set_info(event[1])
        for page in self.pages.values():
            page.on_event(job_id, event)

    def on_finished(self, job_id, ok, message):
        if job_id == "monitor":
            return
        st = self.state
        if ok and job_id in ("apply", "flash"):
            st.mark_applied()
        if job_id in ("flash", "wifi") and ok:
            st.activated = True
        if job_id == "check":
            self.update_nav()
        if job_id == "apply":
            self.toast(message, "ok" if ok else "error", 4500)
        st.busy_changed.emit(False)
        self.update_nav()
        if self.stack.currentWidget() is self.pages["test"]:
            QTimer.singleShot(300, self.pages["test"].on_show)

    def apply(self):
        st = self.state
        if not st.port:
            self.toast("Chọn cổng mạch trước khi áp dụng", "warning")
            return
        if any(i.level == "error" for i in pins.validate(st.project["hw"])):
            self.go("pins")
            self.toast("Cách nối chân đang có lỗi, sửa trước khi áp dụng", "error", 4000)
            return
        errors = profile.validate_commands(st.project.get("commands", {}))
        if errors:
            self.go("commands")
            self.toast(errors[0], "error", 5000)
            return
        self.run_job("apply", jobs.job_apply, st.port, st.project)

    def update_apply_bar(self):
        st = self.state
        show = st.unapplied and self.stack.currentWidget() is not self.pages["flash"]
        busy = st.runner.busy
        if show:
            n = st.changes()
            if busy and st.runner.job_id == "apply":
                self.apply_text.setText("Đang áp dụng xuống mạch...")
            else:
                self.apply_text.setText("Có thay đổi chưa gửi xuống mạch")
            self.apply_sub.setText(f"{n} nhóm cấu hình đã đổi · mạch sẽ khởi động lại, Wi-Fi giữ nguyên"
                                   if st.port else "Chọn cổng mạch để áp dụng")
            self.apply_btn.setEnabled(bool(st.port) and not busy)
            self.revert_btn.setEnabled(not busy)
        self.apply_bar.setVisible(show)
        if show:
            self._place_apply_bar()

    # Hồ sơ --------------------------------------------------------------------------------
    def confirm_discard(self):
        if not self.state.unsaved:
            return True
        box = QMessageBox(self)
        box.setWindowTitle(APP_NAME)
        box.setIcon(QMessageBox.Question)
        box.setText("Lưu thay đổi của hồ sơ trước khi tiếp tục?")
        save = box.addButton("Lưu", QMessageBox.AcceptRole)
        box.addButton("Không lưu", QMessageBox.DestructiveRole)
        cancel = box.addButton("Hủy", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is cancel:
            return False
        if box.clickedButton() is save:
            return self.save()
        return True

    def new_project(self):
        if self.confirm_discard():
            self.state.new()
            self.toast("Đã tạo hồ sơ mới")
            self.update_nav()

    def open_project(self):
        if not self.confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Mở hồ sơ", paths.user_dir(), f"Hồ sơ Robo Dev (*{profile.EXTENSION})")
        if not path:
            return
        try:
            self.state.open(path)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, APP_NAME, f"Không mở được hồ sơ:\n{e}")
            return
        self.toast(f"Đã mở {os.path.basename(path)}")
        self.update_nav()

    def save(self):
        if not self.state.path:
            return self.save_as()
        try:
            self.state.save()
        except OSError as e:
            QMessageBox.warning(self, APP_NAME, f"Không lưu được:\n{e}")
            return False
        self.toast("Đã lưu hồ sơ")
        self.update_nav()
        return True

    def save_as(self):
        name = (self.state.project.get("name") or "robo") + profile.EXTENSION
        path, _ = QFileDialog.getSaveFileName(self, "Lưu hồ sơ", os.path.join(paths.user_dir(), name),
                                              f"Hồ sơ Robo Dev (*{profile.EXTENSION})")
        if not path:
            return False
        if not path.endswith(profile.EXTENSION):
            path = path.removesuffix(".json") + profile.EXTENSION
        self.state.path = path
        return self.save()

    # Khác --------------------------------------------------------------------------------
    def toast(self, text, tone="ok", ms=3200):
        self.toast_box.show_message(text, tone, ms)

    def toggle_theme(self):
        name = "light" if theme.is_dark() else "dark"
        self.state.settings.setValue("theme", name)
        if self.rebuild:
            self.rebuild(name)

    def closeEvent(self, event):  # noqa: N802
        if getattr(self, "_rebuilding", False):
            event.accept()
            return
        if self.state.runner.busy:
            if QMessageBox.question(self, APP_NAME, "Đang có việc chạy (có thể đang nạp firmware). Vẫn thoát?") \
                    != QMessageBox.Yes:
                event.ignore()
                return
            self.state.runner.stop()
        if not self.confirm_discard():
            event.ignore()
            return
        self.state.runner.stop_monitor(wait=False)
        event.accept()

