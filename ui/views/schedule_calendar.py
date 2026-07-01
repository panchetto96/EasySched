from datetime import date, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from core.models import Employee, Schedule, ShiftStatus
from ui.i18n import tr


class ScheduleCalendarView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._placeholder = QLabel(tr("schedule.no_schedule"))
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: #666; font-size: 15px;")
        layout.addWidget(self._placeholder)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._inner = QWidget()
        self._grid = QGridLayout(self._inner)
        scroll.setWidget(self._inner)
        scroll.hide()
        self._scroll = scroll
        layout.addWidget(scroll)

    def load(self, schedule: Schedule | None, employees: list[Employee], start_date: date):
        if schedule is None:
            self._placeholder.show()
            self._scroll.hide()
            return
        self._placeholder.hide()
        self._scroll.show()
        self._build_calendar(schedule, [e for e in employees if e.active], start_date)

    def _build_calendar(self, schedule: Schedule, employees: list[Employee], start_date: date):
        # Clear existing widgets
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cycle_dates = [start_date + timedelta(days=i) for i in range(28)]
        # Build staffing lookup
        status_lookup: dict[tuple[str, date], ShiftStatus] = {}
        for day in schedule.days:
            for shift in day.shifts:
                status_lookup[(shift.employee_id, day.date)] = shift.status

        id_to_name = {e.id: e.name for e in employees}
        min_staffing = {d: (9 if d.weekday() in (4, 5) else 8) for d in cycle_dates}

        COLS = 7
        # Weekday headers
        for col in range(COLS):
            lbl = QLabel(tr(f"weekday.short.{col}"))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-weight: bold; color: #444;")
            self._grid.addWidget(lbl, 0, col)

        # Offset: first day of cycle to its weekday column
        first_weekday = start_date.weekday()
        for i, d in enumerate(cycle_dates):
            col = (first_weekday + i) % COLS
            row = 1 + (first_weekday + i) // COLS

            cell = QFrame()
            cell.setStyleSheet("border: 1px solid #dde3ec; border-radius: 3px; background: white;")
            cell.setMinimumSize(140, 80)
            vbox = QVBoxLayout(cell)
            vbox.setContentsMargins(4, 2, 4, 2)
            vbox.setSpacing(1)

            # Day number header
            date_lbl = QLabel(str(d.day))
            date_lbl.setStyleSheet("font-weight: bold; font-size: 12px; color: #333;")
            vbox.addWidget(date_lbl)

            # Count working employees
            workers = [
                id_to_name[emp.id]
                for emp in employees
                if status_lookup.get((emp.id, d)) == ShiftStatus.WORK
                and emp.id in id_to_name
            ]
            required = min_staffing[d]
            if len(workers) < required:
                cell.setStyleSheet(
                    "border: 1px solid #f5c6cb; border-radius: 3px; background: #fff5f5;"
                )

            for name in workers[:6]:  # Show at most 6 names
                lbl = QLabel(name)
                lbl.setStyleSheet("font-size: 10px; color: #1a6b3a;")
                vbox.addWidget(lbl)
            if len(workers) > 6:
                more = QLabel(f"+ {len(workers) - 6} altri")
                more.setStyleSheet("font-size: 9px; color: #888;")
                vbox.addWidget(more)

            self._grid.addWidget(cell, row, col)
