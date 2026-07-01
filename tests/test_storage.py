import uuid
from datetime import date
from pathlib import Path
import pytest
from core.models import (
    Employee, EmployeeType, Leave, LeaveType, Shift, ShiftStatus,
    Schedule, ScheduleDay, ScheduleException, ExceptionType,
)
from core.storage import (
    ensure_data_dir, load_employees, save_employees,
    load_leaves, save_leaves, load_schedule, save_schedule,
    list_schedule_dates,
)


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "data"
    ensure_data_dir(d)
    return d


def make_employee(name="Marco", emp_type=EmployeeType.FULL_TIME, block=None):
    return Employee(
        id=str(uuid.uuid4()),
        name=name,
        type=emp_type,
        fixed_rest_block=block,
        active=True,
    )


def test_ensure_data_dir_creates_dirs(tmp_path):
    d = tmp_path / "new_data"
    ensure_data_dir(d)
    assert d.exists()
    assert (d / "schedules").exists()


def test_employee_round_trip(data_dir):
    employees = [
        make_employee("Marco", EmployeeType.FULL_TIME, [1, 2]),
        make_employee("Gioia", EmployeeType.PART_TIME, None),
    ]
    save_employees(data_dir, employees)
    loaded = load_employees(data_dir)
    assert len(loaded) == 2
    assert loaded[0].name == "Marco"
    assert loaded[0].fixed_rest_block == [1, 2]
    assert loaded[1].fixed_rest_block is None
    assert loaded[1].type == EmployeeType.PART_TIME


def test_load_employees_missing_file_returns_empty(data_dir):
    result = load_employees(data_dir)
    assert result == []


def test_leave_round_trip(data_dir):
    emp_id = str(uuid.uuid4())
    leaves = [
        Leave(employee_id=emp_id, date=date(2025, 7, 3), type=LeaveType.FERIE),
        Leave(employee_id=emp_id, date=date(2025, 7, 4), type=LeaveType.MALATTIA),
    ]
    save_leaves(data_dir, leaves)
    loaded = load_leaves(data_dir)
    assert len(loaded) == 2
    assert loaded[0].date == date(2025, 7, 3)
    assert loaded[0].type == LeaveType.FERIE


def test_schedule_round_trip(data_dir):
    emp_id = str(uuid.uuid4())
    start = date(2025, 7, 1)
    schedule = Schedule(
        start_date=start,
        generated_at="2025-06-28T14:00:00",
        days=[
            ScheduleDay(
                date=date(2025, 7, 1),
                shifts=[Shift(employee_id=emp_id, status=ShiftStatus.WORK)],
            )
        ],
        exceptions=[
            ScheduleException(
                employee_id=emp_id,
                type=ExceptionType.SIX_DAY_STRETCH,
                date=date(2025, 7, 5),
            )
        ],
    )
    save_schedule(data_dir, schedule)
    loaded = load_schedule(data_dir, start)
    assert loaded is not None
    assert loaded.start_date == start
    assert len(loaded.days) == 1
    assert loaded.days[0].shifts[0].status == ShiftStatus.WORK
    assert loaded.exceptions[0].type == ExceptionType.SIX_DAY_STRETCH


def test_load_schedule_missing_returns_none(data_dir):
    assert load_schedule(data_dir, date(2025, 1, 1)) is None


def test_list_schedule_dates(data_dir):
    for d in [date(2025, 7, 1), date(2025, 8, 1)]:
        save_schedule(data_dir, Schedule(start_date=d, generated_at="2025-01-01T00:00:00"))
    dates = list_schedule_dates(data_dir)
    assert dates == [date(2025, 7, 1), date(2025, 8, 1)]
