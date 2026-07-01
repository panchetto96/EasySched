import uuid
from datetime import date, timedelta
from core.models import Employee, EmployeeType, ExceptionType, ScheduleException, ShiftStatus
from core.scheduler import (
    _minimum_for_date, VALID_FIXED_BLOCKS, _assign_rest_blocks,
    _assign_free_weekends, _build_ft_schedule, _find_consecutive_stretches,
    _staffing_count, _check_consecutive,
    generate_schedule,
)
from core.models import Leave, LeaveType


FULL_ROSTER = [
    Employee(id=str(uuid.uuid4()), name=n, type=EmployeeType.FULL_TIME,
             fixed_rest_block=None, active=True)
    for n in ["Marco","Linda","Luca","Varinia","Emilia","Leia","Jo",
              "Denise","Maurizio","Pia","Luisa","Ivo","Surbhi","Julian"]
] + [
    Employee(id=str(uuid.uuid4()), name=n, type=EmployeeType.PART_TIME,
             fixed_rest_block=None, active=True)
    for n in ["Gioia", "Guido"]
]

START = date(2025, 7, 7)  # Monday


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


# ── _staffing_count ────────────────────────────────────────────────────────────

def test_staffing_count_counts_work_only():
    emp1, emp2, emp3 = make_ft("A"), make_ft("B"), make_ft("C")
    d = date(2025, 7, 7)
    matrix = {
        emp1.id: {d: ShiftStatus.WORK},
        emp2.id: {d: ShiftStatus.REST},
        emp3.id: {d: ShiftStatus.WORK},
    }
    assert _staffing_count(matrix, d) == 2


# ── _check_consecutive ────────────────────────────────────────────────────────

def test_check_consecutive_no_violations():
    emp = make_ft(block=[0, 1])
    cycle_dates = [date(2025, 7, 7) + timedelta(days=i) for i in range(28)]
    day_map = _build_ft_schedule(emp, cycle_dates, {}, [0, 1], "fri_sat")
    matrix = {emp.id: day_map}
    exceptions = _check_consecutive(matrix, cycle_dates)
    # Allow zero or a few 6-day exceptions, but no 7+ violations
    for exc in exceptions:
        assert exc.type == ExceptionType.SIX_DAY_STRETCH


def test_check_consecutive_detects_six_day_stretch():
    # Build a schedule with a known 6-day stretch
    d0 = date(2025, 7, 7)  # Monday
    cycle_dates = [d0 + timedelta(days=i) for i in range(28)]
    emp = make_ft()
    # Manually set: work Mon-Sat (6 days), rest Sun, work Mon...
    day_map = {}
    for i, d in enumerate(cycle_dates):
        if i in (6, 13, 20, 27):  # Sundays
            day_map[d] = ShiftStatus.REST
        elif i in (7, 8):  # Two rest days in second week
            day_map[d] = ShiftStatus.REST
        else:
            day_map[d] = ShiftStatus.WORK
    matrix = {emp.id: day_map}
    exceptions = _check_consecutive(matrix, cycle_dates)
    # There should be at least one SIX_DAY_STRETCH exception
    six_day = [e for e in exceptions if e.type == ExceptionType.SIX_DAY_STRETCH]
    assert len(six_day) >= 1


# ── generate_schedule integration tests ───────────────────────────────────────

def test_generate_schedule_is_feasible():
    result = generate_schedule(FULL_ROSTER, [], START)
    assert result.feasible
    assert result.schedule is not None


def test_generate_schedule_correct_work_days_ft():
    result = generate_schedule(FULL_ROSTER, [], START)
    assert result.feasible
    ft_employees = [e for e in FULL_ROSTER if e.type == EmployeeType.FULL_TIME]
    for emp in ft_employees:
        work_count = sum(
            1 for day in result.schedule.days
            for shift in day.shifts
            if shift.employee_id == emp.id and shift.status == ShiftStatus.WORK
        )
        assert work_count == 20, f"{emp.name} has {work_count} work days, expected 20"


def test_generate_schedule_min_staffing_met():
    result = generate_schedule(FULL_ROSTER, [], START)
    assert result.feasible
    for day in result.schedule.days:
        required = _minimum_for_date(day.date)
        actual = sum(1 for s in day.shifts if s.status == ShiftStatus.WORK)
        assert actual >= required, (
            f"{day.date} ({day.date.strftime('%A')}) has {actual} workers, needs {required}"
        )


def test_generate_schedule_no_excessive_consecutive():
    result = generate_schedule(FULL_ROSTER, [], START)
    assert result.feasible
    for emp in FULL_ROSTER:
        if emp.type != EmployeeType.FULL_TIME:
            continue
        day_map = {}
        for day in result.schedule.days:
            for shift in day.shifts:
                if shift.employee_id == emp.id:
                    day_map[day.date] = shift.status
        cycle_dates = [START + timedelta(days=i) for i in range(28)]
        stretches = _find_consecutive_stretches(day_map, cycle_dates)
        for start_d, length in stretches:
            assert length <= 6, f"{emp.name}: {length} consecutive days from {start_d}"


def test_generate_schedule_part_time_range():
    result = generate_schedule(FULL_ROSTER, [], START)
    assert result.feasible
    pt_employees = [e for e in FULL_ROSTER if e.type == EmployeeType.PART_TIME]
    for emp in pt_employees:
        work_count = sum(
            1 for day in result.schedule.days
            for shift in day.shifts
            if shift.employee_id == emp.id and shift.status == ShiftStatus.WORK
        )
        assert 12 <= work_count <= 16, f"{emp.name} has {work_count} work days (12-16 required)"


def test_generate_schedule_leave_respected():
    emp = FULL_ROSTER[0]
    leave_dates = [date(2025, 7, 7), date(2025, 7, 8), date(2025, 7, 9)]
    leaves = [Leave(employee_id=emp.id, date=d, type=LeaveType.FERIE) for d in leave_dates]
    result = generate_schedule(FULL_ROSTER, leaves, START)
    for day in result.schedule.days:
        if day.date in leave_dates:
            for shift in day.shifts:
                if shift.employee_id == emp.id:
                    assert shift.status == ShiftStatus.FERIE


def test_generate_schedule_exceptions_carry_forward():
    result1 = generate_schedule(FULL_ROSTER, [], START)
    # Use exceptions from first cycle to inform second cycle
    next_start = START + timedelta(days=28)
    result2 = generate_schedule(FULL_ROSTER, [], next_start, result1.schedule.exceptions)
    assert result2.feasible


def test_infeasible_when_too_many_on_leave():
    # Put 10 of 14 FT employees on leave for an entire cycle — impossible to staff
    ft = [e for e in FULL_ROSTER if e.type == EmployeeType.FULL_TIME]
    on_leave = ft[:10]
    leaves = [
        Leave(employee_id=e.id, date=START + timedelta(days=i), type=LeaveType.FERIE)
        for e in on_leave
        for i in range(28)
    ]
    result = generate_schedule(FULL_ROSTER, leaves, START)
    assert not result.feasible
    assert len(result.errors) > 0
