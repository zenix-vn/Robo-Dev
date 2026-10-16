"""Bảng màu, kiểu chữ và stylesheet chung. Mọi màu trong giao diện lấy từ đây."""
from PySide6.QtGui import QColor, QFont, QPalette

FONT_FAMILY = "Segoe UI Variable Text"
FONT_FALLBACK = ["Segoe UI", "Inter", "Arial"]
MONO_FAMILY = "Cascadia Mono"

LIGHT = {
    "bg": "#F5F6FA",
    "surface": "#FFFFFF",
    "surface_alt": "#F9FAFB",
    "border": "#E4E7EC",
    "border_strong": "#D0D5DD",
    "text": "#101828",
    "text_soft": "#344054",
    "muted": "#667085",
    "faint": "#98A2B3",
    "primary": "#4F46E5",
    "primary_hover": "#4338CA",
    "primary_soft": "#EEF2FF",
    "primary_text": "#3730A3",
    "success": "#12B76A",
    "success_soft": "#ECFDF3",
    "success_text": "#027A48",
    "warning": "#F79009",
    "warning_soft": "#FFFAEB",
    "warning_text": "#B54708",
    "danger": "#F04438",
    "danger_soft": "#FEF3F2",
    "danger_text": "#B42318",
    "info_soft": "#F0F9FF",
    "info_text": "#026AA2",
    "sidebar": "#0B1221",
    "sidebar_hover": "#16203A",
    "sidebar_active": "#1E2A4A",
    "sidebar_text": "#CBD5E1",
    "sidebar_muted": "#64748B",
    "console_bg": "#0B1221",
    "console_text": "#D0D5DD",
    "board": "#1B2536",
    "board_edge": "#2C3A52",
    "pad": "#C9A227",
    "shadow": "#1018280F",
}

DARK = dict(LIGHT)
DARK.update({
    "bg": "#0C111D",
    "surface": "#141A28",
    "surface_alt": "#182032",
    "border": "#232C3F",
    "border_strong": "#33405A",
    "text": "#F2F4F7",
    "text_soft": "#D0D5DD",
    "muted": "#98A2B3",
    "faint": "#667085",
    "primary": "#6366F1",
    "primary_hover": "#818CF8",
    "primary_soft": "#1E1B4B",
    "primary_text": "#C7D2FE",
    "success_soft": "#052E1C",
    "success_text": "#6CE9A6",
    "warning_soft": "#2D1B05",
    "warning_text": "#FEC84B",
    "danger_soft": "#2D0F0D",
    "danger_text": "#FDA29B",
    "info_soft": "#062033",
    "info_text": "#7CD4FD",
    "sidebar": "#070B14",
    "sidebar_hover": "#111829",
    "sidebar_active": "#1A2440",
    "console_bg": "#070B14",
    "board": "#18202F",
    "board_edge": "#2C3A52",
})

_current = {"name": "light", "colors": LIGHT}


def colors():
    return _current["colors"]


def c(name):
    return _current["colors"][name]


def qc(name):
    return QColor(_current["colors"][name])


def tint(color, alpha=0.13):
    """Màu nhạt dùng làm nền (stylesheet hiểu #AARRGGBB nên không ghép chuỗi hex 8 chữ số)."""
    q = QColor(color)
    return f"rgba({q.red()},{q.green()},{q.blue()},{int(alpha * 255)})"


def is_dark():
    return _current["name"] == "dark"


def app_font(size=10):
    font = QFont(FONT_FAMILY, size)
    font.setFamilies([FONT_FAMILY] + FONT_FALLBACK)
    font.setHintingPreference(QFont.PreferNoHinting)
    return font


def mono_font(size=9):
    font = QFont(MONO_FAMILY, size)
    font.setFamilies([MONO_FAMILY, "Consolas", "Courier New"])
    font.setStyleHint(QFont.Monospace)
    return font


def apply(app, name="light"):
    _current["name"] = name
    _current["colors"] = DARK if name == "dark" else LIGHT
    k = _current["colors"]
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(k["bg"]))
    palette.setColor(QPalette.WindowText, QColor(k["text"]))
    palette.setColor(QPalette.Base, QColor(k["surface"]))
    palette.setColor(QPalette.AlternateBase, QColor(k["surface_alt"]))
    palette.setColor(QPalette.Text, QColor(k["text"]))
    palette.setColor(QPalette.Button, QColor(k["surface"]))
    palette.setColor(QPalette.ButtonText, QColor(k["text"]))
    palette.setColor(QPalette.Highlight, QColor(k["primary"]))
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.PlaceholderText, QColor(k["faint"]))
    palette.setColor(QPalette.ToolTipBase, QColor(k["text"]))
    palette.setColor(QPalette.ToolTipText, QColor(k["surface"]))
    app.setPalette(palette)
    app.setFont(app_font())
    app.setStyleSheet(stylesheet(k))


def stylesheet(k):
    return f"""
* {{ outline: none; }}
QWidget {{ color: {k['text']}; }}
QMainWindow, QWidget#Content, QWidget#Page, QScrollArea#PageScroll > QWidget > QWidget {{ background: {k['bg']}; }}
QScrollArea {{ background: transparent; border: none; }}
QToolTip {{ background: {k['text']}; color: {k['surface']}; border: none; padding: 6px 8px; border-radius: 6px; }}

/* ---------- Sidebar ---------- */
QWidget#Sidebar {{ background: {k['sidebar']}; }}
QLabel#Brand {{ color: #FFFFFF; font-size: 15pt; font-weight: 700; }}
QLabel#BrandSub {{ color: {k['sidebar_muted']}; font-size: 8.5pt; }}
QLabel#SideCaption {{ color: {k['sidebar_muted']}; font-size: 8pt; font-weight: 600; }}
QPushButton#NavItem {{
    background: transparent; color: {k['sidebar_text']}; border: none; border-radius: 10px;
    text-align: left; padding: 9px 12px; font-size: 10pt; font-weight: 500;
}}
QPushButton#NavItem:hover {{ background: {k['sidebar_hover']}; }}
QPushButton#NavItem:checked {{ background: {k['sidebar_active']}; color: #FFFFFF; font-weight: 600; }}
QPushButton#ProjectButton {{
    background: {k['sidebar_hover']}; color: #FFFFFF; border: 1px solid {k['sidebar_active']}; border-radius: 10px;
    text-align: left; padding: 8px 12px; font-weight: 600;
}}
QPushButton#ProjectButton:hover {{ background: {k['sidebar_active']}; }}
QPushButton#ProjectButton::menu-indicator {{ subcontrol-position: right center; right: 10px; }}
QFrame#DeviceBox {{ background: {k['sidebar_hover']}; border: 1px solid {k['sidebar_active']}; border-radius: 12px; }}
QLabel#DeviceTitle {{ color: #FFFFFF; font-weight: 600; }}
QLabel#DeviceSub {{ color: {k['sidebar_muted']}; font-size: 8.5pt; }}
QComboBox#PortCombo {{
    background: {k['sidebar']}; color: #FFFFFF; border: 1px solid {k['sidebar_active']}; border-radius: 8px;
    padding: 5px 8px; min-height: 22px;
}}
QComboBox#PortCombo QAbstractItemView {{ background: {k['surface']}; color: {k['text']}; }}
QToolButton#SideIcon {{ background: transparent; border: none; border-radius: 8px; padding: 5px; }}
QToolButton#SideIcon:hover {{ background: {k['sidebar_active']}; }}

/* ---------- Page header ---------- */
QLabel#PageTitle {{ font-size: 18pt; font-weight: 700; color: {k['text']}; }}
QLabel#PageSubtitle {{ font-size: 10pt; color: {k['muted']}; }}

/* ---------- Typography ---------- */
QLabel[role="h2"] {{ font-size: 12pt; font-weight: 600; color: {k['text']}; }}
QLabel[role="h3"] {{ font-size: 10.5pt; font-weight: 600; color: {k['text']}; }}
QLabel[role="muted"] {{ color: {k['muted']}; }}
QLabel[role="faint"] {{ color: {k['faint']}; font-size: 9pt; }}
QLabel[role="caption"] {{ color: {k['muted']}; font-size: 8.5pt; font-weight: 600; }}
QLabel[role="mono"] {{ font-family: "Cascadia Mono", Consolas; color: {k['text_soft']}; font-size: 9pt; }}
QLabel[role="code"] {{ font-family: "Cascadia Mono", Consolas; font-size: 30pt; font-weight: 700; color: {k['primary_text']}; }}

/* ---------- Card ---------- */
QFrame[card="true"] {{ background: {k['surface']}; border: 1px solid {k['border']}; border-radius: 14px; }}
QFrame[card="soft"] {{ background: {k['surface_alt']}; border: 1px solid {k['border']}; border-radius: 12px; }}
QFrame[card="true"][active="true"] {{ border: 2px solid {k['primary']}; }}
QFrame[card="true"][disabledcard="true"] {{ background: {k['surface_alt']}; }}
QFrame#Divider {{ background: {k['border']}; max-height: 1px; min-height: 1px; border: none; }}

/* ---------- Banner ---------- */
QFrame[banner="info"] {{ background: {k['info_soft']}; border: 1px solid {k['info_soft']}; border-radius: 10px; }}
QFrame[banner="warning"] {{ background: {k['warning_soft']}; border: 1px solid {k['warning_soft']}; border-radius: 10px; }}
QFrame[banner="error"] {{ background: {k['danger_soft']}; border: 1px solid {k['danger_soft']}; border-radius: 10px; }}
QFrame[banner="success"] {{ background: {k['success_soft']}; border: 1px solid {k['success_soft']}; border-radius: 10px; }}
QLabel[banner="info"] {{ color: {k['info_text']}; }}
QLabel[banner="warning"] {{ color: {k['warning_text']}; }}
QLabel[banner="error"] {{ color: {k['danger_text']}; }}
QLabel[banner="success"] {{ color: {k['success_text']}; }}

/* ---------- Chip ---------- */
QLabel[chip] {{ border-radius: 10px; padding: 2px 9px; font-size: 8.5pt; font-weight: 600; }}
QLabel[chip="ok"] {{ background: {k['success_soft']}; color: {k['success_text']}; }}
QLabel[chip="warning"] {{ background: {k['warning_soft']}; color: {k['warning_text']}; }}
QLabel[chip="error"] {{ background: {k['danger_soft']}; color: {k['danger_text']}; }}
QLabel[chip="info"] {{ background: {k['primary_soft']}; color: {k['primary_text']}; }}
QLabel[chip="neutral"] {{ background: {k['surface_alt']}; color: {k['muted']}; border: 1px solid {k['border']}; }}

/* ---------- Buttons ---------- */
QPushButton {{
    background: {k['surface']}; color: {k['text_soft']}; border: 1px solid {k['border_strong']};
    border-radius: 9px; padding: 7px 14px; font-weight: 600; min-height: 20px;
}}
QPushButton:hover {{ background: {k['surface_alt']}; border-color: {k['faint']}; }}
QPushButton:pressed {{ background: {k['border']}; }}
QPushButton:disabled {{ color: {k['faint']}; background: {k['surface_alt']}; border-color: {k['border']}; }}
QPushButton[kind="primary"] {{ background: {k['primary']}; color: #FFFFFF; border: 1px solid {k['primary']}; }}
QPushButton[kind="primary"]:hover {{ background: {k['primary_hover']}; border-color: {k['primary_hover']}; }}
QPushButton[kind="primary"]:disabled {{ background: {k['border']}; color: {k['faint']}; border-color: {k['border']}; }}
QPushButton[kind="danger"] {{ background: {k['surface']}; color: {k['danger_text']}; border: 1px solid {k['border_strong']}; }}
QPushButton[kind="danger"]:hover {{ background: {k['danger_soft']}; border-color: {k['danger']}; }}
QPushButton[kind="ghost"] {{ background: transparent; border: 1px solid transparent; color: {k['text_soft']}; }}
QPushButton[kind="ghost"]:hover {{ background: {k['surface_alt']}; border-color: {k['border']}; }}
QPushButton[kind="link"] {{ background: transparent; border: none; color: {k['primary']}; padding: 2px 4px; }}
QPushButton[kind="link"]:hover {{ color: {k['primary_hover']}; text-decoration: underline; }}
QPushButton[size="lg"] {{ padding: 10px 20px; font-size: 10.5pt; border-radius: 10px; }}
QPushButton[size="sm"] {{ padding: 4px 10px; font-size: 9pt; border-radius: 7px; min-height: 16px; }}
QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 8px; padding: 5px; }}
QToolButton:hover {{ background: {k['surface_alt']}; border-color: {k['border']}; }}

/* Choice cards (radio) */
QPushButton[choice="true"] {{
    background: {k['surface']}; border: 1px solid {k['border_strong']}; border-radius: 12px;
    text-align: left; padding: 12px 14px; color: {k['text']}; font-weight: 500;
}}
QPushButton[choice="true"]:hover {{ border-color: {k['primary']}; }}
QPushButton[choice="true"]:checked {{ border: 2px solid {k['primary']}; background: {k['primary_soft']}; }}

/* Segmented */
QFrame#Segmented {{ background: {k['surface_alt']}; border: 1px solid {k['border']}; border-radius: 10px; }}
QPushButton[segment="true"] {{ background: transparent; border: none; border-radius: 8px; padding: 6px 14px; color: {k['muted']}; font-weight: 600; }}
QPushButton[segment="true"]:checked {{ background: {k['surface']}; color: {k['text']}; border: 1px solid {k['border']}; }}
QPushButton[segment="true"]:hover:!checked {{ color: {k['text']}; }}

/* ---------- Inputs ---------- */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QComboBox {{
    background: {k['surface']}; color: {k['text']}; border: 1px solid {k['border_strong']};
    border-radius: 8px; padding: 6px 9px; selection-background-color: {k['primary']};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus {{ border: 1px solid {k['primary']}; }}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled, QPlainTextEdit:disabled {{ background: {k['surface_alt']}; color: {k['faint']}; border-color: {k['border']}; }}
QLineEdit[invalid="true"] {{ border: 1px solid {k['danger']}; }}
QComboBox {{ padding-right: 24px; min-height: 20px; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {k['surface']}; border: 1px solid {k['border']}; border-radius: 8px; padding: 4px;
    selection-background-color: {k['primary_soft']}; selection-color: {k['text']};
}}
QComboBox[pin="warning"] {{ border: 1px solid {k['warning']}; background: {k['warning_soft']}; }}
QComboBox[pin="error"] {{ border: 1px solid {k['danger']}; background: {k['danger_soft']}; }}
QComboBox[pin="active"] {{ border: 2px solid {k['primary']}; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 16px; border: none; background: transparent; }}

QCheckBox {{ spacing: 8px; color: {k['text_soft']}; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 5px; border: 1px solid {k['border_strong']}; background: {k['surface']}; }}
QCheckBox::indicator:checked {{ background: {k['primary']}; border-color: {k['primary']}; }}
QRadioButton {{ spacing: 8px; }}

QSlider::groove:horizontal {{ height: 6px; background: {k['border']}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {k['primary']}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {k['surface']}; border: 2px solid {k['primary']}; width: 14px; height: 14px; margin: -6px 0; border-radius: 9px; }}
QSlider::groove:horizontal:disabled {{ background: {k['border']}; }}
QSlider::sub-page:horizontal:disabled {{ background: {k['faint']}; }}
QSlider::handle:horizontal:disabled {{ border-color: {k['faint']}; }}

QProgressBar {{ background: {k['border']}; border: none; border-radius: 4px; height: 8px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {k['primary']}; border-radius: 4px; }}
QProgressBar[tone="ok"]::chunk {{ background: {k['success']}; }}

/* ---------- Tabs ---------- */
QTabWidget::pane {{ border: none; }}
QTabBar {{ qproperty-drawBase: 0; border-bottom: 1px solid {k['border']}; }}
QTabBar::tab {{ background: transparent; color: {k['muted']}; padding: 8px 2px; margin-right: 22px; border: none; border-bottom: 2px solid transparent; font-weight: 600; }}
QTabBar::tab:selected {{ color: {k['primary']}; border-bottom: 2px solid {k['primary']}; }}
QTabBar::tab:hover:!selected {{ color: {k['text']}; }}

/* ---------- Lists ---------- */
QListWidget {{ background: {k['surface']}; border: 1px solid {k['border']}; border-radius: 10px; padding: 4px; }}
QListWidget::item {{ border-radius: 8px; padding: 8px 10px; margin: 1px 0; color: {k['text_soft']}; }}
QListWidget::item:selected {{ background: {k['primary_soft']}; color: {k['primary_text']}; }}
QListWidget::item:hover:!selected {{ background: {k['surface_alt']}; }}

/* ---------- Console ---------- */
QPlainTextEdit#Console {{
    background: {k['console_bg']}; color: {k['console_text']}; border: none; border-radius: 12px;
    padding: 10px; font-family: "Cascadia Mono", Consolas; font-size: 9pt;
}}
QLineEdit#ConsoleInput {{ font-family: "Cascadia Mono", Consolas; }}

/* ---------- Scrollbars ---------- */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {k['border_strong']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {k['faint']}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {k['border_strong']}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---------- Apply bar / toast ---------- */
QFrame#ApplyBar {{ background: {k['text']}; border-radius: 14px; }}
QLabel#ApplyText {{ color: {k['surface']}; font-weight: 600; }}
QLabel#ApplySub {{ color: {k['faint']}; }}
QFrame#Toast {{ background: {k['text']}; border-radius: 10px; }}
QLabel#ToastText {{ color: {k['surface']}; font-weight: 500; }}

QMenu {{ background: {k['surface']}; border: 1px solid {k['border']}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 7px 26px 7px 12px; border-radius: 6px; color: {k['text']}; }}
QMenu::item:selected {{ background: {k['primary_soft']}; color: {k['primary_text']}; }}
QMenu::item:disabled {{ color: {k['faint']}; }}
QMenu::separator {{ height: 1px; background: {k['border']}; margin: 5px 8px; }}
QMessageBox, QDialog {{ background: {k['surface']}; }}
"""
