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


def _assign_free_weekends(
    employees: list[Employee],
    previous_exceptions: list[ScheduleException],
) -> dict[str, str]:
    """
    Return {employee_id: "fri_sat" | "sat_sun"}.
    Rotates from the previous cycle's choice to ensure fairness.
    Default when no previous: assign "fri_sat" (previous was "sat_sun").
    """
    prev_type: dict[str, str] = {}
    for exc in previous_exceptions:
        if exc.type == ExceptionType.FREE_WEEKEND_FRI_SAT:
            prev_type[exc.employee_id] = "fri_sat"
        elif exc.type == ExceptionType.FREE_WEEKEND_SAT_SUN:
            prev_type[exc.employee_id] = "sat_sun"

    result: dict[str, str] = {}
    for emp in employees:
        last = prev_type.get(emp.id, "sat_sun")  # default: alternate to fri_sat
        result[emp.id] = "sat_sun" if last == "fri_sat" else "fri_sat"
    return result


def _find_consecutive_stretches(
    day_map: dict[date, ShiftStatus],
    cycle_dates: list[date],
) -> list[tuple[date, int]]:
    """Return [(stretch_start, length)] for each consecutive WORK stretch."""
    stretches: list[tuple[date, int]] = []
    streak_start: date | None = None
    streak_len = 0

    for d in cycle_dates:
        if day_map.get(d) == ShiftStatus.WORK:
            if streak_start is None:
                streak_start = d
            streak_len += 1
        else:
            if streak_len > 0:
                stretches.append((streak_start, streak_len))
            streak_start = None
            streak_len = 0

    if streak_len > 0:
        stretches.append((streak_start, streak_len))
    return stretches


def _draft_for_placement(
    spans: list[list[date]],
    free_span_idx: int,
    rest_block: tuple[int, int],
    weekend_weekdays: tuple[int, int],
    leave_map: dict[date, ShiftStatus],
    cycle_dates: list[date],
) -> dict[date, ShiftStatus]:
    """Build one candidate schedule for a given free-weekend span placement."""
    day_map: dict[date, ShiftStatus] = {}
    for span_idx, span in enumerate(spans):
        rest_weekdays = weekend_weekdays if span_idx == free_span_idx else rest_block
        for d in span:
            if d in leave_map:
                day_map[d] = leave_map[d]
            elif d.weekday() in rest_weekdays:
                day_map[d] = ShiftStatus.REST
            else:
                day_map[d] = ShiftStatus.WORK
    return day_map


def _build_ft_schedule(
    emp: Employee,
    cycle_dates: list[date],
    leave_map: dict[date, ShiftStatus],
    rest_block: list[int],
    weekend_type: str,
) -> dict[date, ShiftStatus]:
    """
    Build a full-time employee's 28-day schedule.
    Tries all 4 span placements for the free weekend, picks the one with
    minimum max consecutive working days (prefers ≤5, accepts 6).
    """
    spans = [cycle_dates[i * 7:(i + 1) * 7] for i in range(4)]
    weekend_weekdays = (4, 5) if weekend_type == "fri_sat" else (5, 6)
    rb = tuple(rest_block)

    best_map: dict[date, ShiftStatus] | None = None
    best_max_consecutive = 999

    for free_span_idx in range(4):
        candidate = _draft_for_placement(
            spans, free_span_idx, rb, weekend_weekdays, leave_map, cycle_dates
        )
        stretches = _find_consecutive_stretches(candidate, cycle_dates)
        max_consec = max((length for _, length in stretches), default=0)
        if max_consec < best_max_consecutive:
            best_max_consecutive = max_consec
            best_map = candidate

    return best_map  # type: ignore[return-value]


def _staffing_count(
    schedule_matrix: dict[str, dict[date, ShiftStatus]],
    d: date,
) -> int:
    """Count WORK shifts for a given date across all employees."""
    return sum(
        1 for day_map in schedule_matrix.values()
        if day_map.get(d) == ShiftStatus.WORK
    )


def _check_consecutive(
    schedule_matrix: dict[str, dict[date, ShiftStatus]],
    cycle_dates: list[date],
) -> list[ScheduleException]:
    """
    Scan all employees for consecutive working day violations.
    Records 6-day stretches as exceptions.
    Raises ValueError if any stretch exceeds 6 (caller must handle via fallback).
    """
    exceptions: list[ScheduleException] = []
    for emp_id, day_map in schedule_matrix.items():
        stretches = _find_consecutive_stretches(day_map, cycle_dates)
        for stretch_start, length in stretches:
            if length == 6:
                exceptions.append(ScheduleException(
                    employee_id=emp_id,
                    type=ExceptionType.SIX_DAY_STRETCH,
                    date=stretch_start,
                ))
            elif length > 6:
                raise ValueError(
                    f"Employee {emp_id} has {length} consecutive working days "
                    f"starting {stretch_start} — schedule is infeasible as drafted"
                )
    return exceptions


def _repair_staffing(
    schedule_matrix: dict[str, dict[date, ShiftStatus]],
    active_ft: list[Employee],
    cycle_dates: list[date],
    leave_sets: dict[str, set[date]],
) -> list[StaffingShortfall]:
    """
    For each under-staffed day, try to convert a REST day to WORK for one employee
    who: (a) is resting that day, (b) won't create a 7+ consecutive stretch.
    Returns unfixable shortfalls.
    """
    shortfalls: list[StaffingShortfall] = []
    for d in cycle_dates:
        required = _minimum_for_date(d)
        actual = _staffing_count(schedule_matrix, d)
        if actual >= required:
            continue

        repaired = False
        for emp in active_ft:
            day_map = schedule_matrix[emp.id]
            if day_map.get(d) != ShiftStatus.REST:
                continue
            if d in leave_sets.get(emp.id, set()):
                continue
            # Tentatively flip to WORK and check consecutive days
            day_map[d] = ShiftStatus.WORK
            stretches = _find_consecutive_stretches(day_map, cycle_dates)
            if all(length <= 6 for _, length in stretches):
                repaired = True
                break
            else:
                day_map[d] = ShiftStatus.REST  # revert

        if not repaired:
            shortfalls.append(StaffingShortfall(
                date=d,
                actual_count=actual,
                required_count=required,
            ))
    return shortfalls
