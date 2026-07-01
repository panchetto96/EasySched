from datetime import date, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QHeaderView, QMenu, QApplication,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QFont
from core.models import Employee, Schedule, ShiftStatus
from core.storage import save_schedule
from ui.app import get_data_dir
from ui.i18n import tr

_STATUS_COLOR = {
    ShiftStatus.WORK:     QColor("#16a34a"),   # vivid green
    ShiftStatus.REST:     QColor("#94a3b8"),   # slate gray
    ShiftStatus.FERIE:    QColor("#2563eb"),   # vivid blue
    ShiftStatus.MALATTIA: QColor("#ea580c"),   # vivid orange
    ShiftStatus.PERMESSO: QColor("#d97706"),   # vivid amber
    ShiftStatus.OVERRIDE: QColor("#7c3aed"),   # vivid purple
}
_STATUS_TEXT = {
    ShiftStatus.WORK:     QColor("#ffffff"),
    ShiftStatus.REST:     QColor("#ffffff"),
    ShiftStatus.FERIE:    QColor("#ffffff"),
    ShiftStatus.MALATTIA: QColor("#ffffff"),
    ShiftStatus.PERMESSO: QColor("#ffffff"),
    ShiftStatus.OVERRIDE: QColor("#ffffff"),
}
_STATUS_LABEL = {
    ShiftStatus.WORK:     "L",
    ShiftStatus.REST:     "R",
    ShiftStatus.FERIE:    "F",
    ShiftStatus.MALATTIA: "M",
    ShiftStatus.PERMESSO: "P",
    ShiftStatus.OVERRIDE: "O",
}
_VALID_OVERRIDES = list(ShiftStatus)


class ScheduleGridView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._placeholder = QLabel(tr("schedule.no_schedule"))
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: #666; font-size: 15px;")
        layout.addWidget(self._placeholder)
        self._table = QTableWidget()
        self._table.hide()
        layout.addWidget(self._table)
        self._schedule: Schedule | None = None
        self._employees: list[Employee] = []
        self._start_date: date = date.today()

    def load(self, schedule: Schedule | None, employees: list[Employee], start_date: date):
        self._schedule = schedule
        self._employees = [e for e in employees if e.active]
        self._start_date = start_date
        if schedule is None:
            self._placeholder.setText(tr("schedule.generate_prompt"))
            self._placeholder.show()
            self._table.hide()
            return
        self._placeholder.hide()
        self._table.show()
        self._build_table()

    def _build_table(self):
        schedule = self._schedule
        employees = self._employees
        cycle_dates = [self._start_date + timedelta(days=i) for i in range(28)]

        # Build lookup: (employee_id, date) -> ShiftStatus
        status_lookup: dict[tuple[str, date], ShiftStatus] = {}
        for day in schedule.days:
            for shift in day.shifts:
                status_lookup[(shift.employee_id, day.date)] = shift.status

        n_rows = len(employees) + 1  # +1 for staffing totals row
        n_cols = len(cycle_dates) + 1  # +1 for row totals column
        self._table.setRowCount(n_rows)
        self._table.setColumnCount(n_cols)

        # Column headers: "D Xxx" (e.g. "1 Lun")
        headers = []
        for d in cycle_dates:
            wd = tr(f"weekday.short.{d.weekday()}")
            headers.append(f"{d.day} {wd}")
        headers.append(tr("schedule.days_worked"))
        self._table.setHorizontalHeaderLabels(headers)

        # Row headers: employee names
        row_labels = [e.name for e in employees] + [tr("schedule.staffing_below_min")]
        self._table.setVerticalHeaderLabels(row_labels)

        min_staffing = {d: (9 if d.weekday() in (4, 5) else 8) for d in cycle_dates}

        # Fill cells
        daily_counts: dict[date, int] = {d: 0 for d in cycle_dates}
        for row_idx, emp in enumerate(employees):
            work_count = 0
            for col_idx, d in enumerate(cycle_dates):
                status = status_lookup.get((emp.id, d), ShiftStatus.REST)
                item = self._make_cell(status)
                self._table.setItem(row_idx, col_idx, item)
                if status == ShiftStatus.WORK:
                    work_count += 1
                    daily_counts[d] += 1
            # Row total
            total_item = QTableWidgetItem(f"{work_count}/28")
            total_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._table.setItem(row_idx, 28, total_item)

        # Staffing totals row
        for col_idx, d in enumerate(cycle_dates):
            count = daily_counts[d]
            required = min_staffing[d]
            item = QTableWidgetItem(str(count))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            font = QFont()
            font.setBold(True)
            item.setFont(font)
            if count < required:
                item.setBackground(QBrush(QColor("#dc2626")))
                item.setForeground(QBrush(QColor("#ffffff")))
            else:
                item.setBackground(QBrush(QColor("#f0fdf4")))
                item.setForeground(QBrush(QColor("#166534")))
            self._table.setItem(len(employees), col_idx, item)

        # Resize
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setMinimumSectionSize(36)
        self._table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        # Context menu for override
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)

    def _make_cell(self, status: ShiftStatus) -> QTableWidgetItem:
        item = QTableWidgetItem(_STATUS_LABEL[status])
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setBackground(QBrush(_STATUS_COLOR[status]))
        item.setForeground(QBrush(_STATUS_TEXT[status]))
        font = QFont()
        font.setBold(True)
        item.setFont(font)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        return item

    def _show_context_menu(self, pos):
        idx = self._table.indexAt(pos)
        if not idx.isValid():
            return
        row, col = idx.row(), idx.column()
        if col >= 28 or row >= len(self._employees):
            return
        emp = self._employees[row]
        d = self._start_date + timedelta(days=col)

        menu = QMenu(self)
        for status in _VALID_OVERRIDES:
            action = menu.addAction(f"{_STATUS_LABEL[status]} — {status.value}")
            action.triggered.connect(lambda _, s=status: self._apply_override(emp, d, s))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _apply_override(self, emp: Employee, d: date, status: ShiftStatus):
        if self._schedule is None:
            return
        for day in self._schedule.days:
            if day.date == d:
                for shift in day.shifts:
                    if shift.employee_id == emp.id:
                        shift.status = ShiftStatus.OVERRIDE if status == shift.status else status
                        break
        save_schedule(get_data_dir(), self._schedule)
        self._build_table()
