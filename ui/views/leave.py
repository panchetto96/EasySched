"""Stub implementation — will be replaced by Task 14."""
from PyQt6.QtWidgets import QWidget


class LeaveView(QWidget):
    def __init__(self, on_change=None, parent=None):
        super().__init__(parent)
        self._on_change = on_change
