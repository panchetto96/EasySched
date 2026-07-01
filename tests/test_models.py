import uuid
from datetime import date
from core.models import (
    Employee, EmployeeType, Leave, LeaveType, Shift, ShiftStatus,
    ScheduleDay, ScheduleException, ExceptionType, Schedule,
    ScheduleResult, Warning, StaffingShortfall,
)


def test_employee_full_time():
    emp = Employee(
        id=str(uuid.uuid4()),
        name="Marco",
        type=EmployeeType.FULL_TIME,
        fixed_rest_block=[1, 2],
        active=True,
    )
    assert emp.type == EmployeeType.FULL_TIME
    assert emp.fixed_rest_block == [1, 2]


def test_employee_no_fixed_block():
    emp = Employee(
        id=str(uuid.uuid4()),
        name="Gioia",
        type=EmployeeType.PART_TIME,
        fixed_rest_block=None,
        active=True,
    )
    assert emp.fixed_rest_block is None


def test_leave_types():
    for lt in [LeaveType.FERIE, LeaveType.MALATTIA, LeaveType.PERMESSO]:
        leave = Leave(employee_id="x", date=date(2025, 7, 1), type=lt)
        assert leave.type == lt


def test_shift_statuses():
    for ss in ShiftStatus:
        shift = Shift(employee_id="x", status=ss)
        assert shift.status == ss


def test_schedule_result_defaults():
    result = ScheduleResult(schedule=None, feasible=False)
    assert result.exceptions == []
    assert result.warnings == []
    assert result.errors == []
