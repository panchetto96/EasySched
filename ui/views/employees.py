from typing import Callable
import uuid
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QDialog, QFormLayout, QLineEdit, QComboBox,
    QDialogButtonBox, QMessageBox,
)
from PyQt6.QtCore import Qt
from core.models import Employee, EmployeeType
from core.storage import load_employees, save_employees
from ui.app import get_data_dir
from ui.i18n import tr

_VALID_BLOCKS = [
    (None, tr("employee.rest_block_algo")),
    ([0, 1], "Lun–Mar"),
    ([1, 2], "Mar–Mer"),
    ([2, 3], "Mer–Gio"),
    ([3, 4], "Gio–Ven"),
]


class EmployeesView(QWidget):
    def __init__(self, on_change: Callable):
        super().__init__()
        self._on_change = on_change
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self._list = QListWidget()
        self._list.setMinimumWidth(260)
        layout.addWidget(self._list)

        btn_col = QVBoxLayout()
        self._btn_add = QPushButton(tr("employee.add"))
        self._btn_edit = QPushButton(tr("employee.edit"))
        self._btn_deactivate = QPushButton(tr("employee.deactivate"))
        for btn in [self._btn_add, self._btn_edit, self._btn_deactivate]:
            btn.setObjectName("secondary")
            btn_col.addWidget(btn)
        btn_col.addStretch()
        layout.addLayout(btn_col)

        self._btn_add.clicked.connect(self._add_employee)
        self._btn_edit.clicked.connect(self._edit_employee)
        self._btn_deactivate.clicked.connect(self._deactivate_employee)

        self._reload()

    def _reload(self):
        self._employees = load_employees(get_data_dir())
        self._list.clear()
        for emp in self._employees:
            if emp.active:
                label = f"{emp.name} ({tr('employee.full_time') if emp.type == EmployeeType.FULL_TIME else tr('employee.part_time')})"
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, emp.id)
                self._list.addItem(item)

    def _selected_employee(self) -> Employee | None:
        item = self._list.currentItem()
        if item is None:
            return None
        emp_id = item.data(Qt.ItemDataRole.UserRole)
        return next((e for e in self._employees if e.id == emp_id), None)

    def _add_employee(self):
        dialog = EmployeeDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            emp = dialog.result_employee()
            self._employees.append(emp)
            save_employees(get_data_dir(), self._employees)
            self._reload()
            self._on_change()

    def _edit_employee(self):
        emp = self._selected_employee()
        if emp is None:
            return
        dialog = EmployeeDialog(self, emp)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated = dialog.result_employee(emp.id)
            idx = next(i for i, e in enumerate(self._employees) if e.id == emp.id)
            self._employees[idx] = updated
            save_employees(get_data_dir(), self._employees)
            self._reload()
            self._on_change()

    def _deactivate_employee(self):
        emp = self._selected_employee()
        if emp is None:
            return
        reply = QMessageBox.question(
            self, "Hostel Scheduler",
            f"Disattivare {emp.name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            emp.active = False
            save_employees(get_data_dir(), self._employees)
            self._reload()
            self._on_change()


class EmployeeDialog(QDialog):
    def __init__(self, parent, employee: Employee | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("employee.add") if employee is None else tr("employee.edit"))
        form = QFormLayout(self)

        self._name_edit = QLineEdit(employee.name if employee else "")
        form.addRow(tr("employee.name"), self._name_edit)

        self._type_combo = QComboBox()
        self._type_combo.addItem(tr("employee.full_time"), EmployeeType.FULL_TIME)
        self._type_combo.addItem(tr("employee.part_time"), EmployeeType.PART_TIME)
        if employee and employee.type == EmployeeType.PART_TIME:
            self._type_combo.setCurrentIndex(1)
        form.addRow(tr("employee.type"), self._type_combo)

        self._block_combo = QComboBox()
        for block, label in _VALID_BLOCKS:
            self._block_combo.addItem(label, block)
        if employee and employee.fixed_rest_block:
            for i, (b, _) in enumerate(_VALID_BLOCKS):
                if b == employee.fixed_rest_block:
                    self._block_combo.setCurrentIndex(i)
        form.addRow(tr("employee.rest_block"), self._block_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def result_employee(self, existing_id: str | None = None) -> Employee:
        return Employee(
            id=existing_id or str(uuid.uuid4()),
            name=self._name_edit.text().strip(),
            type=self._type_combo.currentData(),
            fixed_rest_block=self._block_combo.currentData(),
            active=True,
        )
