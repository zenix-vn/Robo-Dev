"""Bước 1 - Thiết bị: chọn mạch, kiểm tra chip/firmware, xem linh kiện hỗ trợ."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from robodev import paths
from robodev.core import catalog, jobs
from robodev.ui import icons, theme
from robodev.ui.pages.base import Page
from robodev.ui.widgets import Banner, Card, Chip, button, hbox, icon_label, label, vbox


def rounded_photo(name, w, h, radius=12):
    out = QPixmap(w * 2, h * 2)
    out.setDevicePixelRatio(2)
    out.fill(Qt.transparent)
    src = QPixmap(paths.photo(name)) if name else QPixmap()
    painter = QPainter(out)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, w, h), radius, radius)
    painter.setClipPath(clip)
    painter.fillRect(QRectF(0, 0, w, h), theme.qc("surface_alt"))
    if not src.isNull():
        scaled = src.scaled(w * 2, h * 2, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        scaled.setDevicePixelRatio(2)
        sw, sh = scaled.width() / 2, scaled.height() / 2
        painter.drawPixmap(int((w - sw) / 2), int((h - sh) / 2), scaled)
    painter.end()
    return out


class ResultTile(QWidget):
    def __init__(self, icon, title):
        super().__init__()
        self.icon_name = icon
        self.badge = QLabel()
        self.badge.setFixedSize(36, 36)
        self.badge.setAlignment(Qt.AlignCenter)
        self.title = label(title, "caption")
        self.value = label("Chưa kiểm tra", "h3", wrap=True)
        self.detail = label("", "faint", wrap=True)
        lay = hbox(self.badge, spacing=12)
        lay.addLayout(vbox(self.title, self.value, self.detail, spacing=1), 1)
        lay.setAlignment(self.badge, Qt.AlignTop)
        self.setLayout(lay)
        self.set(None, "Chưa kiểm tra")

    def set(self, ok, value, detail=""):
        tone = {True: ("success_soft", "success_text"), False: ("danger_soft", "danger_text"),
                None: ("surface_alt", "faint"), "warn": ("warning_soft", "warning_text")}[ok]
        self.badge.setStyleSheet(f"background: {theme.c(tone[0])}; border-radius: 10px;")
        self.badge.setPixmap(icons.pixmap(self.icon_name, theme.c(tone[1]), 19))
        self.value.setText(value)
        self.detail.setText(detail)
        self.detail.setVisible(bool(detail))


class ModuleTile(Card):
    def __init__(self, mod):
        super().__init__(padding=0, spacing=0, shadow=False)
        self.mod = mod
        photo = QLabel()
        if mod.photo:
            photo.setPixmap(rounded_photo(mod.photo, 236, 120, 0))
        else:
            photo.setFixedHeight(120)
            photo.setAlignment(Qt.AlignCenter)
            photo.setPixmap(icons.pixmap(icons.MODULE_ICONS[mod.key], theme.c("faint"), 44, 1.4))
            photo.setStyleSheet(f"background: {theme.c('surface_alt')}; border-top-left-radius: 14px;"
                                f" border-top-right-radius: 14px;")
        photo.setFixedHeight(120)
        self.chip = Chip("Đang bật", "ok")
        dot = QLabel()
        dot.setFixedSize(10, 10)
        dot.setStyleSheet(f"background: {mod.color}; border-radius: 5px;")
        name = label(mod.name, "h3")
        top = hbox(dot, name, "stretch", self.chip, spacing=8)
        body = vbox(top, label(mod.part, "muted"), label(mod.summary, "faint", wrap=True), spacing=4,
                    margins=(16, 12, 16, 16))
        self.body.addWidget(photo)
        self.body.addLayout(body)

    def set_enabled_state(self, on):
        if not self.mod.optional:
            self.chip.set("Có sẵn", "info")
        else:
            self.chip.set("Đang bật" if on else "Đã tắt", "ok" if on else "neutral")


class DevicePage(Page):
    title = "Thiết bị"
    subtitle = "Cắm mạch, kiểm tra chip và firmware trước khi làm các bước khác."
    icon = "chip"

    def __init__(self, state, window):
        super().__init__(state, window)
        self.check_btn = button("Kiểm tra mạch", "primary", "refresh", size="lg", on_click=self.check)
        self.add_action(self.check_btn)

        self.no_port = Banner("", "warning")
        self.content.addWidget(self.no_port)

        # Thẻ mạch ---------------------------------------------------------------------
        board = catalog.board()
        hero = Card()
        photo = QLabel()
        photo.setPixmap(rounded_photo(board.photo, 168, 128))
        self.board_name = label(board.name, "h2")
        specs = label(f"Chip {board.chip.upper().replace('ESP32S3', 'ESP32-S3')} · flash {board.flash_mb} MB · PSRAM {board.psram}",
                      "muted")
        self.port_chip = Chip("Chưa chọn cổng", "neutral")
        self.fw_chip = Chip("Firmware: chưa kiểm tra", "neutral")
        chips = hbox(self.port_chip, self.fw_chip, "stretch", spacing=6)
        intro = label("Robo Dev v1 chỉ hỗ trợ đúng mạch này. Trước khi nạp, chương trình đọc chip và dung lượng "
                      "flash để không ghi nhầm lên mạch khác.", "faint", wrap=True)
        texts = vbox(self.board_name, specs, 4, chips, 6, intro, "stretch", spacing=4)
        top = hbox(photo, spacing=20)
        top.addLayout(texts, 1)
        hero.add(top)

        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(14)
        self.t_chip = ResultTile("chip", "CHIP & FLASH")
        self.t_fw = ResultTile("flash", "FIRMWARE")
        self.t_sensor = ResultTile("radar", "CẢM BIẾN")
        self.t_net = ResultTile("wifi", "WI-FI & XIAOZHI.ME")
        for i, tile in enumerate((self.t_chip, self.t_fw, self.t_sensor, self.t_net)):
            grid.addWidget(tile, 0, i)
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {theme.c('border')};")
        hero.add(sep)
        hero.add(grid)
        self.content.addWidget(hero)

        # Hướng dẫn nhanh --------------------------------------------------------------
        guide = Card("Bắt đầu trong 4 bước", "Làm lần lượt; mỗi bước xong sẽ có dấu ✓ ở thanh bên trái.", "sparkle")
        steps = QGridLayout()
        steps.setHorizontalSpacing(14)
        items = [
            ("usb", "Cắm cáp", "Cắm cáp USB-C vào cổng COM để nạp. Cắm thêm cổng USB để đọc log.", None),
            ("refresh", "Kiểm tra mạch", "Bấm “Kiểm tra mạch” để xác nhận chip và firmware.", None),
            ("pins", "Nối chân", "Khai báo dây bạn đã nối, chương trình báo ngay nếu nối sai.", "pins"),
            ("flash", "Nạp & kết nối", "Nạp firmware, nhập Wi-Fi và nhận mã kích hoạt xiaozhi.me.", "flash"),
        ]
        for i, (ic, title, text, page) in enumerate(items):
            box = Card(padding=16, spacing=6, shadow=False)
            box.setProperty("card", "soft")
            num = label(str(i + 1))
            num.setFixedSize(26, 26)
            num.setAlignment(Qt.AlignCenter)
            num.setStyleSheet(f"background: {theme.c('primary')}; color: white; border-radius: 13px; font-weight: 700;")
            box.add(hbox(num, icon_label(ic, theme.c("muted"), 18), "stretch", spacing=8))
            box.add(label(title, "h3"))
            box.add(label(text, "muted", wrap=True))
            if page:
                link = button("Mở bước này →", "link", on_click=lambda _=False, p=page: self.window.go(p))
                box.add(hbox(link, "stretch"))
            box.body.addStretch(1)
            steps.addWidget(box, 0, i)
        guide.add(steps)
        self.content.addWidget(guide)

        # Linh kiện --------------------------------------------------------------------
        self.content.addWidget(label("Linh kiện hỗ trợ trong v1", "h2"))
        mods = QGridLayout()
        mods.setSpacing(16)
        self.tiles = {}
        for i, mod in enumerate(catalog.modules()):
            tile = ModuleTile(mod)
            self.tiles[mod.key] = tile
            mods.addWidget(tile, i // 4, i % 4)
        self.content.addLayout(mods)
        self.content.addStretch(1)

        state.port_changed.connect(lambda _: self.update_device())
        state.device_changed.connect(self.update_device)
        state.project_changed.connect(self.refresh)
        state.busy_changed.connect(lambda _: self.update_device())
        self.refresh()
        self.update_device()

    def refresh(self):
        hw = self.state.project["hw"]
        for key, tile in self.tiles.items():
            tile.set_enabled_state(hw.get(key, {}).get("enabled", True))

    def update_device(self):
        st = self.state
        has_port = bool(st.port)
        self.no_port.setVisible(not has_port)
        self.no_port.set("<b>Chưa thấy mạch.</b> Cắm cáp USB-C vào cổng <b>COM</b> của mạch (cổng có chip CH343). "
                         "Chưa có mạch? Chọn <b>DEMO · không cần mạch</b> ở ô chọn cổng bên trái để dùng thử.",
                         "warning")
        self.check_btn.setEnabled(has_port and not st.runner.busy)
        if not has_port:
            self.port_chip.set("Chưa chọn cổng", "neutral")
        else:
            self.port_chip.set(("Mạch mô phỏng" if st.is_demo else "Cổng " + st.port), "info")
        if st.version:
            self.fw_chip.set("Firmware Robo Dev " + st.version, "ok")
        else:
            self.fw_chip.set("Firmware: chưa kiểm tra", "neutral")

    def check(self):
        if not self.state.port:
            return
        for tile in (self.t_chip, self.t_fw, self.t_sensor, self.t_net):
            tile.set(None, "Đang kiểm tra...")
        self.window.run_job("check", jobs.job_check, self.state.port)

    def on_event(self, job_id, event):
        if job_id != "check":
            return
        kind = event[0]
        if kind == "check":
            self.show_result(event[1])
        elif kind == "done" and not event[1]:
            for tile in (self.t_fw, self.t_sensor, self.t_net):
                if tile.value.text() == "Đang kiểm tra...":
                    tile.set(None, "Chưa kiểm tra")

    def show_result(self, result):
        st = self.state
        ok, message = result["chip"]
        st.chip_ok = ok
        self.t_chip.set(ok, "Đúng mạch" if ok else "Không hỗ trợ", message)
        if not ok:
            return
        fw = result["firmware"]
        if not fw or not fw[0]:
            self.t_fw.set(False, "Chưa có firmware", "Nạp firmware ở bước Nạp & kết nối.")
            self.t_sensor.set(None, "Chưa biết")
            self.t_net.set(None, "Chưa biết")
            return
        st.set_firmware(fw[1])
        info = result.get("info") or {}
        caps = set(info.get("caps", []))
        missing = [text for cap, text in (("hw", "đổi chân lúc chạy"), ("commands", "lệnh tùy chỉnh")) if cap not in caps]
        self.t_fw.set(True, "Robo Dev " + fw[1], ("Bản này chưa có: " + ", ".join(missing) + ".") if missing else "")
        st.info = info
        sensor = info.get("sensor")
        if isinstance(sensor, str) and sensor:
            self.t_sensor.set(True, sensor.upper(), "Trả lời trên I2C")
        elif sensor is True:
            self.t_sensor.set(True, "Có trả lời", "Cảm biến trả lời trên I2C")
        else:
            self.t_sensor.set("warn", "Không thấy", "Kiểm tra dây SDA/SCL, hoặc tắt cảm biến ở bước Nối chân.")
        if "wifi" in info:
            st.activated = info.get("activated")
            if info.get("activated"):
                self.t_net.set(True, "Đã kích hoạt", "Robot đã kết nối xiaozhi.me")
            elif info.get("wifi"):
                self.t_net.set("warn", "Có Wi-Fi", "Chưa kích hoạt xiaozhi.me")
            else:
                self.t_net.set("warn", "Chưa cài Wi-Fi", "Cài ở bước Nạp & kết nối")
        else:
            self.t_net.set(None, "Không rõ", "Firmware cũ không báo trạng thái Wi-Fi")
        st.device_changed.emit()
