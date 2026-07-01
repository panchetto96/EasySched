from typing import Callable
from datetime import date, timedelta
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QTableWidget, QTableWidgetItem, QComboBox,
    QDateEdit, QLabel, QHeaderView,
)
from PyQt6.QtCore import Qt, QDate
from core.models import Leave, LeaveType
from core.storage import load_employees, load_leaves, save_leaves
from ui.app import get_data_dir
from ui.i18n import tr


class LeaveView(QWidget):
    def __init__(self, on_change: Callable):
        super().__init__()
        self._on_change = on_change
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # Left: employee list
        left = QVBoxLayout()
        left.addWidget(QLabel(tr("leave.employee")))
        self._emp_list = QListWidget()
        self._emp_list.setMaximumWidth(220)
        self._emp_list.currentRowChanged.connect(self._reload_leave_table)
        left.addWidget(self._emp_list)
        layout.addLayout(left)

        # Right: absence controls + table
        right = QVBoxLayout()
        control_row = QHBoxLayout()
        self._from_date = QDateEdit(QDate.currentDate())
        self._from_date.setCalendarPopup(True)
        self._to_date = QDateEdit(QDate.currentDate())
        self._to_date.setCalendarPopup(True)
        self._type_combo = QComboBox()
        self._type_combo.addItem(tr("leave.type_ferie"), LeaveType.FERIE)
        self._type_combo.addItem(tr("leave.type_malattia"), LeaveType.MALATTIA)
        self._type_combo.addItem(tr("leave.type_permesso"), LeaveType.PERMESSO)
        self._btn_add = QPushButton(tr("leave.add"))
        self._btn_add.clicked.connect(self._add_leave)
        control_row.addWidget(QLabel(tr("leave.from")))
        control_row.addWidget(self._from_date)
        control_row.addWidget(QLabel(tr("leave.to")))
        control_row.addWidget(self._to_date)
        control_row.addWidget(QLabel(tr("leave.type")))
        control_row.addWidget(self._type_combo)
        control_row.addWidget(self._btn_add)
        control_row.addStretch()
        right.addLayout(control_row)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Data", tr("leave.type"), ""])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        right.addWidget(self._table)
        layout.addLayout(right)

        self._reload_employees()

    def _reload_employees(self):
        self._employees = [e for e in load_employees(get_data_dir()) if e.active]
        self._all_leaves = load_leaves(get_data_dir())
        self._emp_list.clear()
        for emp in self._employees:
            self._emp_list.addItem(emp.name)

    def _selected_employee(self):
        idx = self._emp_list.currentRow()
        if 0 <= idx < len(self._employees):
            return self._employees[idx]
        return None

    def _reload_leave_table(self):
        emp = self._selected_employee()
        if emp is None:
            self._table.setRowCount(0)
            return
        emp_leaves = [l for l in self._all_leaves if l.employee_id == emp.id]
        emp_leaves.sort(key=lambda l: l.date)
        self._table.setRowCount(len(emp_leaves))
        for row, leave in enumerate(emp_leaves):
            self._table.setItem(row, 0, QTableWidgetItem(leave.date.isoformat()))
            self._table.setItem(row, 1, QTableWidgetItem(leave.type.value))
            btn = QPushButton(tr("leave.delete"))
            btn.setObjectName("secondary")
            btn.clicked.connect(lambda _, l=leave: self._delete_leave(l))
            self._table.setCellWidget(row, 2, btn)

    def _add_leave(self):
        emp = self._selected_employee()
        if emp is None:
            return
        from_qd = self._from_date.date()
        to_qd = self._to_date.date()
        leave_type = self._type_combo.currentData()
        current = date(from_qd.year(), from_qd.month(), from_qd.day())
        end = date(to_qd.year(), to_qd.month(), to_qd.day())
        existing = {(l.employee_id, l.date) for l in self._all_leaves}
        new_leaves = []
        while current <= end:
            if (emp.id, current) not in existing:
                new_leaves.append(Leave(employee_id=emp.id, date=current, type=leave_type))
            current += timedelta(days=1)
        self._all_leaves.extend(new_leaves)
        save_leaves(get_data_dir(), self._all_leaves)
        self._reload_leave_table()
        self._on_change()

    def _delete_leave(self, leave: Leave):
        self._all_leaves = [
            l for l in self._all_leaves
            if not (l.employee_id == leave.employee_id and l.date == leave.date)
        ]
        save_leaves(get_data_dir(), self._all_leaves)
        self._reload_leave_table()
        self._on_change()
