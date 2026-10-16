"""Gắn điều khiển với một khóa trong hồ sơ: đọc lại khi hồ sơ đổi, ghi vào hồ sơ khi người dùng sửa."""
from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QPlainTextEdit, QSlider, QSpinBox

from robodev.ui.widgets import ColorButton, Toggle


def get(data, path, default=None):
    for key in path:
        if not isinstance(data, dict) or key not in data:
            return default
        data = data[key]
    return data


def put(data, path, value):
    for key in path[:-1]:
        data = data.setdefault(key, {})
    data[path[-1]] = value


class Binder:
    def __init__(self, state):
        self.state = state
        self.items = []       # (widget, path, kind, extra)

    def bind(self, widget, path, on_change=None):
        self.items.append((widget, tuple(path), on_change))
        if isinstance(widget, (Toggle, QCheckBox)):
            widget.toggled.connect(lambda v, p=path, cb=on_change: self._write(p, bool(v), cb))
        elif isinstance(widget, (QSpinBox, QSlider)):
            widget.valueChanged.connect(lambda v, p=path, cb=on_change: self._write(p, int(v), cb))
        elif isinstance(widget, QComboBox):
            widget.currentIndexChanged.connect(lambda _, w=widget, p=path, cb=on_change: self._write(p, w.currentData(), cb))
        elif isinstance(widget, QLineEdit):
            widget.textEdited.connect(lambda v, p=path, cb=on_change: self._write(p, v, cb))
        elif isinstance(widget, QPlainTextEdit):
            widget.textChanged.connect(lambda w=widget, p=path, cb=on_change: self._write(p, w.toPlainText(), cb))
        elif isinstance(widget, ColorButton):
            widget.changed.connect(lambda v, p=path, cb=on_change: self._write(p, list(v), cb))
        return widget

    def _write(self, path, value, callback):
        if get(self.state.project, path) == value:
            return
        put(self.state.project, path, value)
        self.state.touch()
        if callback:
            callback(value)

    def load(self):
        for widget, path, _ in self.items:
            value = get(self.state.project, path)
            widget.blockSignals(True)
            try:
                if isinstance(widget, (Toggle, QCheckBox)):
                    widget.setChecked(bool(value))
                elif isinstance(widget, (QSpinBox, QSlider)):
                    widget.setValue(int(value if value is not None else 0))
                elif isinstance(widget, QComboBox):
                    index = widget.findData(value)
                    widget.setCurrentIndex(index if index >= 0 else 0)
                elif isinstance(widget, QLineEdit):
                    if widget.text() != (value or ""):
                        widget.setText(value or "")
                elif isinstance(widget, QPlainTextEdit):
                    if widget.toPlainText() != (value or ""):
                        widget.setPlainText(value or "")
                elif isinstance(widget, ColorButton):
                    widget.set(value or [255, 255, 255])
            finally:
                widget.blockSignals(False)
            if isinstance(widget, Toggle):
                widget.set_offset(1.0 if widget.isChecked() else 0.0)
