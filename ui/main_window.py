from datetime import date, timedelta
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame, QFileDialog, QMessageBox,
)
from PyQt6.QtCore import Qt
from ui.i18n import tr, set_language, get_language
from ui.app import get_data_dir
from core import storage

_active_window: "MainWindow | None" = None


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hostel Scheduler")
        self.resize(1280, 800)
        self._cycle_start = date.today().replace(day=1)
        self._schedule = None
        self._employees = storage.load_employees(get_data_dir())
        self._leaves = storage.load_leaves(get_data_dir())
        self._build_ui()
        self._refresh_schedule()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_nav_bar())
        root.addWidget(self._build_toolbar())
        self._stack = QStackedWidget()
        root.addWidget(self._stack)
        self._add_views()

    def _build_nav_bar(self):
        bar = QFrame()
        bar.setStyleSheet("background-color: #0f172a;")
        bar.setFixedHeight(52)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(4)

        def nav_btn(key, idx):
            btn = QPushButton(tr(key))
            btn.setStyleSheet(
                "color: #cbd5e1; background: transparent; font-size: 14px; "
                "font-weight: 600; padding: 6px 16px; border-radius: 6px;"
                "border: none;"
            )
            btn.clicked.connect(lambda _, i=idx: self._stack.setCurrentIndex(i))
            return btn

        layout.addWidget(nav_btn("nav.schedule", 0))
        layout.addWidget(nav_btn("nav.employees", 1))
        layout.addWidget(nav_btn("nav.leave", 2))
        layout.addStretch()

        self._lang_btn = QPushButton("IT | EN")
        self._lang_btn.setStyleSheet(
            "color: #64748b; background: transparent; font-size: 12px; "
            "padding: 4px 10px; border: 1px solid #334155; border-radius: 4px;"
        )
        self._lang_btn.clicked.connect(self._toggle_language)
        layout.addWidget(self._lang_btn)
        return bar

    def _build_toolbar(self):
        bar = QFrame()
        bar.setStyleSheet(
            "background-color: #ffffff; border-bottom: 2px solid #e2e8f0;"
        )
        bar.setFixedHeight(48)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        self._cycle_label = QLabel()
        self._cycle_label.setStyleSheet(
            "color: #1e293b; font-size: 14px; font-weight: 700; "
            "background: transparent; padding-right: 12px;"
        )
        layout.addWidget(self._cycle_label)

        def tb_btn(key, cb, secondary=False):
            btn = QPushButton(tr(key))
            if secondary:
                btn.setObjectName("secondary")
            btn.clicked.connect(cb)
            layout.addWidget(btn)
            return btn

        tb_btn("schedule.prev", self._prev_cycle, secondary=True)
        tb_btn("schedule.next", self._next_cycle, secondary=True)
        layout.addSpacing(16)
        tb_btn("schedule.generate", self._generate_schedule)
        tb_btn("schedule.export_csv", self._export_csv, secondary=True)
        tb_btn("schedule.import_csv", self._import_csv, secondary=True)
        layout.addStretch()
        self._update_cycle_label()
        return bar

    def _add_views(self):
        from ui.views.schedule_grid import ScheduleGridView
        from ui.views.schedule_calendar import ScheduleCalendarView
        from ui.views.employees import EmployeesView
        from ui.views.leave import LeaveView

        # Schedule page: grid + calendar tabs
        schedule_page = QWidget()
        vbox = QVBoxLayout(schedule_page)
        vbox.setContentsMargins(8, 8, 8, 8)

        tab_bar = QHBoxLayout()
        self._btn_grid = QPushButton(tr("schedule.grid_view"))
        self._btn_cal = QPushButton(tr("schedule.calendar_view"))
        self._btn_grid.setObjectName("secondary")
        self._btn_cal.setObjectName("secondary")
        tab_bar.addWidget(self._btn_grid)
        tab_bar.addWidget(self._btn_cal)
        tab_bar.addStretch()
        vbox.addLayout(tab_bar)

        self._view_stack = QStackedWidget()
        self._grid_view = ScheduleGridView()
        self._cal_view = ScheduleCalendarView()
        self._view_stack.addWidget(self._grid_view)
        self._view_stack.addWidget(self._cal_view)
        vbox.addWidget(self._view_stack)

        self._btn_grid.clicked.connect(lambda: self._view_stack.setCurrentIndex(0))
        self._btn_cal.clicked.connect(lambda: self._view_stack.setCurrentIndex(1))

        self._stack.addWidget(schedule_page)

        self._employees_view = EmployeesView(on_change=self._reload_employees)
        self._stack.addWidget(self._employees_view)

        self._leave_view = LeaveView(on_change=self._reload_leaves)
        self._stack.addWidget(self._leave_view)

    def _update_cycle_label(self):
        end = self._cycle_start + timedelta(days=27)
        months_it = {i: tr(f"month.{i}") for i in range(1, 13)}
        label = (
            f"{tr('schedule.cycle_label')} "
            f"{self._cycle_start.day} {months_it[self._cycle_start.month]} "
            f"– {end.day} {months_it[end.month]} {end.year}"
        )
        self._cycle_label.setText(label)

    def _prev_cycle(self):
        self._cycle_start -= timedelta(days=28)
        self._update_cycle_label()
        self._refresh_schedule()

    def _next_cycle(self):
        self._cycle_start += timedelta(days=28)
        self._update_cycle_label()
        self._refresh_schedule()

    def _refresh_schedule(self):
        data_dir = get_data_dir()
        self._schedule = storage.load_schedule(data_dir, self._cycle_start)
        self._grid_view.load(self._schedule, self._employees, self._cycle_start)
        self._cal_view.load(self._schedule, self._employees, self._cycle_start)

    def _generate_schedule(self):
        from core.scheduler import generate_schedule
        data_dir = get_data_dir()
        # Load previous cycle exceptions for fairness
        prev_start = self._cycle_start - timedelta(days=28)
        prev_schedule = storage.load_schedule(data_dir, prev_start)
        prev_exceptions = prev_schedule.exceptions if prev_schedule else []

        result = generate_schedule(
            self._employees, self._leaves, self._cycle_start, prev_exceptions
        )
        if result.feasible:
            storage.save_schedule(data_dir, result.schedule)
            self._schedule = result.schedule
        else:
            self._show_infeasibility(result)
        self._grid_view.load(self._schedule, self._employees, self._cycle_start)
        self._cal_view.load(self._schedule, self._employees, self._cycle_start)

    def _show_infeasibility(self, result):
        lines = [tr("error.infeasible")]
        for err in result.errors[:5]:
            lines.append(
                tr("error.shortfall")
                .replace("{date}", err.date.isoformat())
                .replace("{n}", str(err.required_count - err.actual_count))
                .replace("{req}", str(err.required_count))
                .replace("{actual}", str(err.actual_count))
            )
        QMessageBox.warning(self, "Hostel Scheduler", "\n".join(lines))

    def _export_csv(self):
        if self._schedule is None:
            return
        from core.csv_io import export_schedule_csv
        path, _ = QFileDialog.getSaveFileName(
            self, tr("schedule.export_csv"), "", "CSV (*.csv)"
        )
        if path:
            export_schedule_csv(self._schedule, self._employees, __import__("pathlib").Path(path))
            QMessageBox.information(self, "Hostel Scheduler", tr("dialog.export_success"))

    def _import_csv(self):
        from core.csv_io import import_schedule_csv, CsvImportError
        from pathlib import Path
        path, _ = QFileDialog.getOpenFileName(self, tr("schedule.import_csv"), "", "CSV (*.csv)")
        if not path:
            return
        reply = QMessageBox.question(
            self, "Hostel Scheduler", tr("dialog.import_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            schedule, _ = import_schedule_csv(Path(path))
            storage.save_schedule(get_data_dir(), schedule)
            self._schedule = schedule
            self._grid_view.load(self._schedule, self._employees, self._cycle_start)
            self._cal_view.load(self._schedule, self._employees, self._cycle_start)
            QMessageBox.information(self, "Hostel Scheduler", tr("dialog.import_success"))
        except CsvImportError as e:
            QMessageBox.critical(
                self, "Hostel Scheduler",
                tr("dialog.import_error").replace("{error}", str(e))
            )

    def _toggle_language(self):
        lang = "en" if get_language() == "it" else "it"
        set_language(lang)
        self._retranslate()

    def _retranslate(self):
        global _active_window
        # Re-build the entire UI — simplest correct approach for a small app
        self.close()
        _active_window = MainWindow()
        _active_window.show()

    def _reload_employees(self):
        self._employees = storage.load_employees(get_data_dir())
        self._refresh_schedule()

    def _reload_leaves(self):
        self._leaves = storage.load_leaves(get_data_dir())
