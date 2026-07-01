from datetime import date, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt
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
            is_weekend = col in (5, 6)
            lbl.setStyleSheet(
                f"font-weight: 700; font-size: 12px; padding: 6px 0; "
                f"color: {'#dc2626' if is_weekend else '#1e293b'}; background: transparent;"
            )
            self._grid.addWidget(lbl, 0, col)

        # Offset: first day of cycle to its weekday column
        first_weekday = start_date.weekday()
        for i, d in enumerate(cycle_dates):
            col = (first_weekday + i) % COLS
            row = 1 + (first_weekday + i) // COLS

            workers = [
                id_to_name[emp.id]
                for emp in employees
                if status_lookup.get((emp.id, d)) == ShiftStatus.WORK
                and emp.id in id_to_name
            ]
            required = min_staffing[d]
            under = len(workers) < required
            is_weekend_day = d.weekday() in (5, 6)

            cell = QFrame()
            if under:
                cell.setStyleSheet(
                    "QFrame { border: 2px solid #dc2626; border-radius: 6px; "
                    "background: #fef2f2; }"
                )
            elif is_weekend_day:
                cell.setStyleSheet(
                    "QFrame { border: 1px solid #e2e8f0; border-radius: 6px; "
                    "background: #f8fafc; }"
                )
            else:
                cell.setStyleSheet(
                    "QFrame { border: 1px solid #e2e8f0; border-radius: 6px; "
                    "background: #ffffff; }"
                )
            cell.setMinimumSize(140, 88)
            vbox = QVBoxLayout(cell)
            vbox.setContentsMargins(6, 4, 6, 4)
            vbox.setSpacing(2)

            # Day number + weekday count
            header_row = QLabel(
                f"<b style='font-size:13px; color:{'#dc2626' if under else '#0f172a'};'>"
                f"{d.day}</b>"
                f"<span style='font-size:10px; color:#64748b;'>"
                f" &nbsp;{len(workers)}/{required}</span>"
            )
            header_row.setTextFormat(Qt.TextFormat.RichText)
            vbox.addWidget(header_row)

            for name in workers[:6]:
                lbl = QLabel(name)
                lbl.setStyleSheet(
                    "font-size: 10px; color: #166534; background: transparent; padding: 0;"
                )
                vbox.addWidget(lbl)
            if len(workers) > 6:
                more = QLabel(f"+ {len(workers) - 6} altri")
                more.setStyleSheet("font-size: 9px; color: #94a3b8; background: transparent;")
                vbox.addWidget(more)
            vbox.addStretch()

            self._grid.addWidget(cell, row, col)
