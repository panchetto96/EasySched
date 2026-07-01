"""Stub implementation — will be replaced by Task 11."""
from datetime import date
from PyQt6.QtWidgets import QWidget


class ScheduleGridView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

    def load(self, schedule, employees, cycle_start: date) -> None:
        pass
