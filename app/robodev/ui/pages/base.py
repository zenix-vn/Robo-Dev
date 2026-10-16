"""Khung chung của một trang: tiêu đề, mô tả, nút hành động và vùng nội dung cuộn được."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from robodev.ui.widgets import label

MAX_WIDTH = 1180


class Page(QWidget):
    title = ""
    subtitle = ""
    icon = "chip"

    def __init__(self, state, window, scroll=True):
        super().__init__()
        self.state = state
        self.window = window
        self.setObjectName("Page")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        head = QWidget()
        head_lay = QHBoxLayout(head)
        head_lay.setContentsMargins(36, 28, 36, 18)
        texts = QVBoxLayout()
        texts.setSpacing(4)
        self.title_label = label(self.title)
        self.title_label.setObjectName("PageTitle")
        self.subtitle_label = label(self.subtitle, wrap=True)
        self.subtitle_label.setObjectName("PageSubtitle")
        texts.addWidget(self.title_label)
        texts.addWidget(self.subtitle_label)
        head_lay.addLayout(texts, 1)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(8)
        head_lay.addLayout(self.actions)
        outer.addWidget(head)

        self.inner = QWidget()
        self.inner.setObjectName("Page")
        self.content = QVBoxLayout(self.inner)
        self.content.setContentsMargins(36, 4, 36, 110)
        self.content.setSpacing(18)
        if scroll:
            area = QScrollArea()
            area.setObjectName("PageScroll")
            area.setWidgetResizable(True)
            area.setFrameShape(QScrollArea.NoFrame)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            area.setWidget(self.inner)
            outer.addWidget(area, 1)
        else:
            self.content.setContentsMargins(36, 4, 36, 24)
            outer.addWidget(self.inner, 1)

    def add_action(self, widget):
        self.actions.addWidget(widget)

    def on_show(self):
        """Gọi mỗi khi trang được mở."""

    def on_event(self, job_id, event):
        """Sự kiện từ việc nền (mọi trang đều nhận, tự lọc theo job_id)."""

    def refresh(self):
        """Đọc lại hồ sơ vào các điều khiển."""
