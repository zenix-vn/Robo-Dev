"""Chạy Robo Dev:  python -m robodev  [--demo]  [--theme light|dark]  [--shot THƯ_MỤC]"""
import argparse
import os
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from robodev import APP_NAME
from robodev.core import link
from robodev.ui import icons, theme
from robodev.ui.main_window import PAGES, MainWindow
from robodev.ui.state import AppState
from robodev.ui.widgets import WheelGuard


def main(argv=None):
    parser = argparse.ArgumentParser(prog="robodev")
    parser.add_argument("--demo", action="store_true", help="chọn sẵn mạch mô phỏng")
    parser.add_argument("--theme", choices=["light", "dark"])
    parser.add_argument("--shot", metavar="DIR", help="chụp ảnh từng trang vào DIR rồi thoát")
    parser.add_argument("--open", metavar="FILE", help="mở hồ sơ")
    args = parser.parse_args(argv)

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("RoboDev")
    app.setStyle("Fusion")
    wheel_guard = WheelGuard(app)
    app.installEventFilter(wheel_guard)

    state = AppState()
    # Dừng phiên xem log và việc nền trước khi giao diện bị hủy
    app.aboutToQuit.connect(lambda: (state.runner.stop(), state.runner.stop_monitor()))
    name = args.theme or state.settings.value("theme", "light")
    theme.apply(app, name)
    app.setWindowIcon(QIcon(icons.pixmap("robot", "#6366F1", 64)))

    path = args.open or state.settings.value("last_project", "")
    if path and os.path.isfile(path):
        try:
            state.open(path)
            state.mark_applied()
        except (OSError, ValueError):
            pass

    holder = {}

    def build(theme_name=None):
        old = holder.get("window")
        if theme_name:
            theme.apply(app, theme_name)
        window = MainWindow(state, rebuild=build)
        if old is not None:
            window.restoreGeometry(old.saveGeometry())
            page = state.settings.value("last_page", "device")
            old._rebuilding = True  # noqa: SLF001
            old.close()
            old.deleteLater()
            window.go(page)
        holder["window"] = window
        if args.shot:
            window.setAttribute(Qt.WA_DontShowOnScreen)
        window.show()
        return window

    window = build()
    if args.demo:
        index = window.port_combo.findData(link.DEMO_PORT)
        window.port_combo.setCurrentIndex(index)

    if args.shot:
        os.makedirs(args.shot, exist_ok=True)
        window.resize(1360, 860)

        def shoot(i=0):
            if i >= len(PAGES):
                app.quit()
                return
            key = PAGES[i][0]
            window.go(key)
            QTimer.singleShot(250, lambda: (window.grab().save(os.path.join(args.shot, f"{i + 1}-{key}.png")),
                                            shoot(i + 1)))

        QTimer.singleShot(400, shoot)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
