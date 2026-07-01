import uuid
from datetime import date
from core.models import Employee, EmployeeType, ExceptionType, ScheduleException
from core.scheduler import _minimum_for_date, VALID_FIXED_BLOCKS, _assign_rest_blocks


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
