from datetime import date, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QHeaderView, QMenu, QApplication, QStyledItemDelegate,
)
from PyQt6.QtCore import Qt, QRect, QRectF, QSize
from PyQt6.QtGui import QColor, QBrush, QFont, QPainter
from core.models import Employee, EmployeeType, Schedule, ShiftStatus
from core.storage import save_schedule
from ui.app import get_data_dir
from ui.i18n import tr

_STATUS_COLOR = {
    ShiftStatus.WORK:     QColor("#166534"),
    ShiftStatus.REST:     QColor("#78716C"),
    ShiftStatus.FERIE:    QColor("#1D4ED8"),
    ShiftStatus.MALATTIA: QColor("#9D174D"),
    ShiftStatus.PERMESSO: QColor("#92400E"),
    ShiftStatus.OVERRIDE: QColor("#5B21B6"),
}
_STATUS_TEXT = {s: QColor("#ffffff") for s in ShiftStatus}
_STATUS_LABEL = {
    ShiftStatus.WORK:     "L",
    ShiftStatus.REST:     "R",
    ShiftStatus.FERIE:    "F",
    ShiftStatus.MALATTIA: "M",
    ShiftStatus.PERMESSO: "P",
    ShiftStatus.OVERRIDE: "O",
}
_VALID_OVERRIDES = list(ShiftStatus)

# Eight distinct avatar colors — deterministic per employee name
_AVATAR_COLORS = [
    "#1D4ED8", "#166534", "#9D174D", "#92400E",
    "#5B21B6", "#0E7490", "#C2410C", "#374151",
]


class _NameDelegate(QStyledItemDelegate):
    """Paints avatar circle + name + employee type for the name column (col 0)."""

    def paint(self, painter: QPainter, option, index):
        emp = index.data(Qt.ItemDataRole.UserRole)
        if not isinstance(emp, Employee):
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        r = option.rect
        painter.fillRect(r, QColor("#FDF6EE"))

        # Bottom separator
        painter.setPen(QColor("#E8DDD2"))
        painter.drawLine(r.left(), r.bottom(), r.right(), r.bottom())

        # Right border separating name col from day cells
        painter.setPen(QColor("#C8B8A8"))
        painter.drawLine(r.right(), r.top(), r.right(), r.bottom())

        # Avatar circle (color stable across sessions — derived from name)
        hash_val = sum(ord(c) for c in emp.name)
        avatar_color = QColor(_AVATAR_COLORS[hash_val % len(_AVATAR_COLORS)])
        cx = float(r.left() + 26)
        cy = float(r.center().y())
        rad = 15.0
        painter.setBrush(QBrush(avatar_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(cx - rad, cy - rad, rad * 2, rad * 2))

        # Initials inside circle
        parts = emp.name.split()
        initials = (parts[0][0] + (parts[1][0] if len(parts) > 1 else "")).upper()
        f_init = QFont("Segoe UI", 8, QFont.Weight.Bold)
        painter.setFont(f_init)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(
            QRect(r.left() + 11, r.top(), 30, r.height()),
            Qt.AlignmentFlag.AlignCenter,
            initials,
        )

        # Employee name
        f_name = QFont("Segoe UI", 11)
        f_name.setBold(True)
        painter.setFont(f_name)
        painter.setPen(QColor("#1C140D"))
        half = r.height() // 2
        name_rect = QRect(r.left() + 50, r.top() + 4, r.width() - 56, half - 2)
        painter.drawText(
            name_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
            emp.name,
        )

        # Employee type label (muted, smaller)
        type_str = tr("employee.full_time") if emp.type == EmployeeType.FULL_TIME else tr("employee.part_time")
        f_type = QFont("Segoe UI", 8)
        painter.setFont(f_type)
        painter.setPen(QColor("#9A7B6B"))
        type_rect = QRect(r.left() + 50, r.top() + half + 2, r.width() - 56, half - 6)
        painter.drawText(
            type_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            type_str,
        )

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(175, 44)


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

        status_lookup: dict[tuple[str, date], ShiftStatus] = {}
        for day in schedule.days:
            for shift in day.shifts:
                status_lookup[(shift.employee_id, day.date)] = shift.status

        # col 0 = name, cols 1–28 = days, col 29 = total worked
        n_rows = len(employees) + 1
        n_cols = len(cycle_dates) + 2
        self._table.setRowCount(n_rows)
        self._table.setColumnCount(n_cols)

        day_headers = []
        for d in cycle_dates:
            wd = tr(f"weekday.short.{d.weekday()}")
            day_headers.append(f"{d.day} {wd}")
        self._table.setHorizontalHeaderLabels(
            [tr("employee.name")] + day_headers + [tr("schedule.days_worked")]
        )

        # Hide row-index vertical header; row height controlled by delegate sizeHint
        self._table.verticalHeader().hide()
        self._table.verticalHeader().setDefaultSectionSize(44)

        self._table.setItemDelegateForColumn(0, _NameDelegate(self._table))

        min_staffing = {d: (9 if d.weekday() in (4, 5) else 8) for d in cycle_dates}
        daily_counts: dict[date, int] = {d: 0 for d in cycle_dates}

        for row_idx, emp in enumerate(employees):
            # Name cell
            name_item = QTableWidgetItem()
            name_item.setData(Qt.ItemDataRole.UserRole, emp)
            name_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._table.setItem(row_idx, 0, name_item)

            work_count = 0
            for col_idx, d in enumerate(cycle_dates):
                status = status_lookup.get((emp.id, d), ShiftStatus.REST)
                self._table.setItem(row_idx, col_idx + 1, self._make_cell(status))
                if status == ShiftStatus.WORK:
                    work_count += 1
                    daily_counts[d] += 1

            total_item = QTableWidgetItem(f"{work_count}/28")
            total_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            total_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._table.setItem(row_idx, 29, total_item)

        # Staffing totals row
        staffing_label = QTableWidgetItem(tr("schedule.staffing_below_min"))
        staffing_label.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        staffing_label.setFlags(Qt.ItemFlag.ItemIsEnabled)
        lbl_font = QFont()
        lbl_font.setBold(True)
        lbl_font.setPointSize(9)
        staffing_label.setFont(lbl_font)
        staffing_label.setBackground(QBrush(QColor("#292217")))
        staffing_label.setForeground(QBrush(QColor("#F5EDE3")))
        self._table.setItem(len(employees), 0, staffing_label)

        for col_idx, d in enumerate(cycle_dates):
            count = daily_counts[d]
            required = min_staffing[d]
            item = QTableWidgetItem(str(count))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            count_font = QFont()
            count_font.setBold(True)
            item.setFont(count_font)
            if count < required:
                item.setBackground(QBrush(QColor("#dc2626")))
                item.setForeground(QBrush(QColor("#ffffff")))
            else:
                item.setBackground(QBrush(QColor("#f0fdf4")))
                item.setForeground(QBrush(QColor("#166534")))
            self._table.setItem(len(employees), col_idx + 1, item)

        # col 0 fixed width; all other columns resize to content
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hh.setMinimumSectionSize(36)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 175)

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
        # col 0 = name, col 29 = total, last row = staffing counts
        if col == 0 or col >= 29 or row >= len(self._employees):
            return
        emp = self._employees[row]
        d = self._start_date + timedelta(days=col - 1)

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
