import uuid
from datetime import date, timedelta
from core.models import Employee, EmployeeType, ExceptionType, ScheduleException, ShiftStatus
from core.scheduler import (
    _minimum_for_date, VALID_FIXED_BLOCKS, _assign_rest_blocks,
    _assign_free_weekends, _build_ft_schedule, _find_consecutive_stretches,
)


def make_ft(name="E", block=None) -> Employee:
    return Employee(
        id=str(uuid.uuid4()),
        name=name,
        type=EmployeeType.FULL_TIME,
        fixed_rest_block=block,
        active=True,
    )


def make_pt(name="P") -> Employee:
    return Employee(
        id=str(uuid.uuid4()),
        name=name,
        type=EmployeeType.PART_TIME,
        fixed_rest_block=None,
        active=True,
    )


# ── _minimum_for_date ──────────────────────────────────────────────────────────

def test_minimum_friday_is_9():
    assert _minimum_for_date(date(2025, 7, 4)) == 9   # Friday


def test_minimum_saturday_is_9():
    assert _minimum_for_date(date(2025, 7, 5)) == 9   # Saturday


def test_minimum_sunday_is_8():
    assert _minimum_for_date(date(2025, 7, 6)) == 8   # Sunday


def test_minimum_monday_through_thursday_is_8():
    # 2025-07-07 Mon, 08 Tue, 09 Wed, 10 Thu
    for d in [date(2025, 7, 7), date(2025, 7, 8), date(2025, 7, 9), date(2025, 7, 10)]:
        assert _minimum_for_date(d) == 8


# ── VALID_FIXED_BLOCKS ─────────────────────────────────────────────────────────

def test_valid_blocks_excludes_sat_sun():
    assert (5, 6) not in VALID_FIXED_BLOCKS


def test_valid_blocks_excludes_fri_sat():
    assert (4, 5) not in VALID_FIXED_BLOCKS


def test_valid_blocks_are_consecutive():
    for a, b in VALID_FIXED_BLOCKS:
        assert b == a + 1


def test_valid_blocks_count():
    assert len(VALID_FIXED_BLOCKS) == 4  # Mon-Tue, Tue-Wed, Wed-Thu, Thu-Fri


# ── _assign_rest_blocks ────────────────────────────────────────────────────────

def test_employee_with_explicit_block_keeps_it():
    emp = make_ft(block=[2, 3])
    result = _assign_rest_blocks([emp], [])
    assert result[emp.id] == [2, 3]


def test_employee_with_none_block_gets_valid_assignment():
    emp = make_ft(block=None)
    result = _assign_rest_blocks([emp], [])
    assert tuple(result[emp.id]) in VALID_FIXED_BLOCKS


def test_assignment_distributes_blocks():
    employees = [make_ft(block=None) for _ in range(8)]
    result = _assign_rest_blocks(employees, [])
    assigned = [tuple(result[e.id]) for e in employees]
    # Each of the 4 valid blocks should be assigned at least once
    for block in VALID_FIXED_BLOCKS:
        assert block in assigned, f"Block {block} was never assigned"


def test_no_sat_sun_block_ever_assigned():
    employees = [make_ft(block=None) for _ in range(20)]
    result = _assign_rest_blocks(employees, [])
    for emp_id, block in result.items():
        assert block != [5, 6], f"Sat-Sun block assigned to {emp_id}"
        assert block != [4, 5], f"Fri-Sat block assigned to {emp_id}"


# ── _assign_free_weekends ──────────────────────────────────────────────────────

def test_free_weekend_default_is_fri_sat():
    emp = make_ft()
    result = _assign_free_weekends([emp], [])
    assert result[emp.id] == "fri_sat"


def test_free_weekend_rotates_from_previous():
    emp = make_ft()
    prev = [
        ScheduleException(
            employee_id=emp.id,
            type=ExceptionType.FREE_WEEKEND_FRI_SAT,
            date=date(2025, 7, 1),
        )
    ]
    result = _assign_free_weekends([emp], prev)
    assert result[emp.id] == "sat_sun"


def test_free_weekend_rotates_back():
    emp = make_ft()
    prev = [
        ScheduleException(
            employee_id=emp.id,
            type=ExceptionType.FREE_WEEKEND_SAT_SUN,
            date=date(2025, 7, 1),
        )
    ]
    result = _assign_free_weekends([emp], prev)
    assert result[emp.id] == "fri_sat"


# ── _build_ft_schedule ─────────────────────────────────────────────────────────

def test_ft_schedule_has_exactly_20_work_days():
    # Start Monday 2025-07-07, block Mon-Tue [0,1], free weekend fri_sat
    emp = make_ft(block=[0, 1])
    cycle_dates = [date(2025, 7, 7) + timedelta(days=i) for i in range(28)]
    day_map = _build_ft_schedule(emp, cycle_dates, {}, [0, 1], "fri_sat")
    work_days = sum(1 for s in day_map.values() if s == ShiftStatus.WORK)
    assert work_days == 20


def test_ft_schedule_has_exactly_8_rest_days():
    emp = make_ft(block=[0, 1])
    cycle_dates = [date(2025, 7, 7) + timedelta(days=i) for i in range(28)]
    day_map = _build_ft_schedule(emp, cycle_dates, {}, [0, 1], "fri_sat")
    rest_days = sum(1 for s in day_map.values() if s == ShiftStatus.REST)
    assert rest_days == 8


def test_ft_schedule_leave_days_excluded_from_work():
    emp = make_ft(block=[0, 1])
    cycle_dates = [date(2025, 7, 7) + timedelta(days=i) for i in range(28)]
    leave_date = date(2025, 7, 10)  # Thursday (normally a work day for Mon-Tue block)
    leave_map = {leave_date: ShiftStatus.FERIE}
    day_map = _build_ft_schedule(emp, cycle_dates, leave_map, [0, 1], "fri_sat")
    assert day_map[leave_date] == ShiftStatus.FERIE


def test_ft_schedule_leave_days_reduce_work_rest_total():
    emp = make_ft(block=[0, 1])
    cycle_dates = [date(2025, 7, 7) + timedelta(days=i) for i in range(28)]
    leave_date = date(2025, 7, 10)
    leave_map = {leave_date: ShiftStatus.FERIE}
    day_map = _build_ft_schedule(emp, cycle_dates, leave_map, [0, 1], "fri_sat")
    work_days = sum(1 for s in day_map.values() if s == ShiftStatus.WORK)
    rest_days = sum(1 for s in day_map.values() if s == ShiftStatus.REST)
    # Leave day is not WORK or REST, so total is 27
    assert work_days + rest_days == 27
    assert day_map[leave_date] == ShiftStatus.FERIE


def test_ft_schedule_max_consecutive_le_6():
    emp = make_ft(block=[0, 1])
    cycle_dates = [date(2025, 7, 7) + timedelta(days=i) for i in range(28)]
    day_map = _build_ft_schedule(emp, cycle_dates, {}, [0, 1], "fri_sat")
    stretches = _find_consecutive_stretches(day_map, cycle_dates)
    for _, length in stretches:
        assert length <= 6, f"Consecutive stretch of {length} days found"


# ── _find_consecutive_stretches ────────────────────────────────────────────────

def test_find_stretches_simple():
    start = date(2025, 7, 7)
    dates = [start + timedelta(days=i) for i in range(7)]
    # Work Mon-Wed, rest Thu-Fri, work Sat-Sun
    day_map = {
        dates[0]: ShiftStatus.WORK,
        dates[1]: ShiftStatus.WORK,
        dates[2]: ShiftStatus.WORK,
        dates[3]: ShiftStatus.REST,
        dates[4]: ShiftStatus.REST,
        dates[5]: ShiftStatus.WORK,
        dates[6]: ShiftStatus.WORK,
    }
    stretches = _find_consecutive_stretches(day_map, dates)
    lengths = [length for _, length in stretches]
    assert 3 in lengths
    assert 2 in lengths
