import uuid
from datetime import date, timedelta
from pathlib import Path
import pytest
from core.models import (
    Employee, EmployeeType, Shift, ShiftStatus, Schedule, ScheduleDay,
)
from core.csv_io import (
    export_schedule_csv, import_schedule_csv,
    export_employees_csv, import_employees_csv,
    CsvImportError,
)


def make_employee(name, emp_type=EmployeeType.FULL_TIME, block=None):
    return Employee(
        id=str(uuid.uuid4()),
        name=name,
        type=emp_type,
        fixed_rest_block=block,
        active=True,
    )


def make_schedule(employees, start=date(2025, 7, 1)):
    statuses = [ShiftStatus.WORK, ShiftStatus.REST, ShiftStatus.FERIE,
                ShiftStatus.MALATTIA, ShiftStatus.PERMESSO, ShiftStatus.OVERRIDE]
    days = []
    for i in range(28):
        d = start + timedelta(days=i)
        shifts = [
            Shift(employee_id=emp.id, status=statuses[i % len(statuses)])
            for emp in employees
        ]
        days.append(ScheduleDay(date=d, shifts=shifts))
    return Schedule(start_date=start, generated_at="2025-06-28T14:00:00", days=days)


def test_schedule_csv_round_trip(tmp_path):
    employees = [make_employee("Marco"), make_employee("Linda")]
    schedule = make_schedule(employees)
    filepath = tmp_path / "turni.csv"
    export_schedule_csv(schedule, employees, filepath)
    loaded_schedule, emp_names = import_schedule_csv(filepath)
    assert loaded_schedule.start_date == schedule.start_date
    assert emp_names == ["Marco", "Linda"]
    # All statuses must match
    for day_orig, day_loaded in zip(schedule.days, loaded_schedule.days):
        for shift_orig, shift_loaded in zip(day_orig.shifts, day_loaded.shifts):
            assert shift_orig.status == shift_loaded.status


def test_schedule_csv_is_byte_identical_on_reimport(tmp_path):
    employees = [make_employee("Marco")]
    schedule = make_schedule(employees)
    f1 = tmp_path / "export1.csv"
    f2 = tmp_path / "export2.csv"
    export_schedule_csv(schedule, employees, f1)
    loaded_schedule, _ = import_schedule_csv(f1)
    # Re-export with same employee list
    export_schedule_csv(loaded_schedule, employees, f2)
    assert f1.read_text() == f2.read_text()


def test_employees_csv_round_trip(tmp_path):
    employees = [
        make_employee("Marco", EmployeeType.FULL_TIME, [1, 2]),
        make_employee("Gioia", EmployeeType.PART_TIME, None),
    ]
    filepath = tmp_path / "dipendenti.csv"
    export_employees_csv(employees, filepath)
    loaded = import_employees_csv(filepath)
    assert len(loaded) == 2
    assert loaded[0].name == "Marco"
    assert loaded[0].fixed_rest_block == [1, 2]
    assert loaded[1].name == "Gioia"
    assert loaded[1].fixed_rest_block is None
    assert loaded[1].type == EmployeeType.PART_TIME


def test_import_invalid_status_raises(tmp_path):
    filepath = tmp_path / "bad.csv"
    filepath.write_text(
        "# start_date=2025-07-01,generated_at=2025-06-28T14:00:00\n"
        "employee,2025-07-01\n"
        "Marco,INVALID\n",
        encoding="utf-8",
    )
    with pytest.raises(CsvImportError) as exc_info:
        import_schedule_csv(filepath)
    assert "INVALID" in str(exc_info.value)


def test_import_missing_column_raises(tmp_path):
    filepath = tmp_path / "bad.csv"
    filepath.write_text("employee\nMarco\n", encoding="utf-8")
    with pytest.raises(CsvImportError):
        import_schedule_csv(filepath)
