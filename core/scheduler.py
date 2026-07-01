from datetime import date, timedelta
from core.models import (
    Employee, EmployeeType, Leave, LeaveType,
    Shift, ShiftStatus, ScheduleDay, ScheduleException, ExceptionType,
    Schedule, ScheduleResult, Warning, StaffingShortfall,
)

# Valid fixed rest blocks: consecutive weekday pairs, excluding Fri-Sat [4,5] and Sat-Sun [5,6]
VALID_FIXED_BLOCKS: list[tuple[int, int]] = [(0, 1), (1, 2), (2, 3), (3, 4)]


def _minimum_for_date(d: date) -> int:
    """Return minimum required staffing: 9 for Fri/Sat, 8 otherwise."""
    return 9 if d.weekday() in (4, 5) else 8


def _assign_rest_blocks(
    employees: list[Employee],
    previous_exceptions: list[ScheduleException],
) -> dict[str, list[int]]:
    """
    Return {employee_id: [weekday1, weekday2]} for all full-time employees.
    Employees with an explicit block keep it; others get the least-used valid block.
    """
    result: dict[str, list[int]] = {}
    needs_assignment: list[Employee] = []

    for emp in employees:
        if emp.fixed_rest_block is not None:
            result[emp.id] = list(emp.fixed_rest_block)
        else:
            needs_assignment.append(emp)

    assigned_blocks = list(result.values())
    for emp in needs_assignment:
        block = _pick_least_used_block(assigned_blocks)
        result[emp.id] = list(block)
        assigned_blocks.append(list(block))

    return result


def _pick_least_used_block(existing: list[list[int]]) -> tuple[int, int]:
    counts = {b: 0 for b in VALID_FIXED_BLOCKS}
    for b in existing:
        key = tuple(b)
        if key in counts:
            counts[key] += 1
    return min(counts, key=lambda k: counts[k])
