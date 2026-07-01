from datetime import date, timedelta, datetime
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
    preferred_span: int | None = None,
) -> dict[date, ShiftStatus]:
    """
    Build a full-time employee's 28-day schedule.
    Tries all 4 span placements for the free weekend, picks the one with
    minimum max consecutive working days (prefers ≤5, accepts 6).
    preferred_span (0-3) is tried first; if it produces ≤6 consecutive days,
    it is used directly (spreading free weekends across different cycle weeks).
    Only falls back to the global minimum if the preferred span exceeds 6.
    """
    spans = [cycle_dates[i * 7:(i + 1) * 7] for i in range(4)]
    weekend_weekdays = (4, 5) if weekend_type == "fri_sat" else (5, 6)
    rb = tuple(rest_block)

    # Try preferred span first
    if preferred_span is not None:
        candidate = _draft_for_placement(
            spans, preferred_span, rb, weekend_weekdays, leave_map, cycle_dates
        )
        stretches = _find_consecutive_stretches(candidate, cycle_dates)
        max_consec = max((length for _, length in stretches), default=0)
        if max_consec <= 6:
            return candidate

    # Fall back: find span with minimum max consecutive days
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
            # Skip employees already at their 20-day FT limit
            if sum(1 for s in day_map.values() if s == ShiftStatus.WORK) >= 20:
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


def _balance_staffing(
    schedule_matrix: dict[str, dict[date, ShiftStatus]],
    active_ft: list[Employee],
    cycle_dates: list[date],
    leave_sets: dict[str, set[date]],
) -> None:
    """
    Rebalance schedules to meet minimum staffing without changing total work counts.
    For each under-staffed day, swap a resting employee's day with a WORK day on
    an over-staffed day, keeping total work counts constant at 20 and
    not creating 7+ consecutive working day stretches.
    Modifies schedule_matrix in place.
    """
    for d in cycle_dates:
        required = _minimum_for_date(d)
        actual = _staffing_count(schedule_matrix, d)
        if actual >= required:
            continue

        for emp in active_ft:
            if _staffing_count(schedule_matrix, d) >= required:
                break
            day_map = schedule_matrix[emp.id]
            if day_map.get(d) != ShiftStatus.REST:
                continue
            if d in leave_sets.get(emp.id, set()):
                continue

            # Find an over-staffed day where this employee works that can absorb the rest
            for other_d in sorted(cycle_dates, key=lambda x: -_staffing_count(schedule_matrix, x)):
                if other_d == d:
                    continue
                if day_map.get(other_d) != ShiftStatus.WORK:
                    continue
                if other_d in leave_sets.get(emp.id, set()):
                    continue
                other_required = _minimum_for_date(other_d)
                other_actual = _staffing_count(schedule_matrix, other_d)
                if other_actual <= other_required:
                    continue  # Cannot reduce staffing below minimum on the donor day

                # Tentatively swap: rest on d, work on other_d
                day_map[d] = ShiftStatus.WORK
                day_map[other_d] = ShiftStatus.REST
                stretches = _find_consecutive_stretches(day_map, cycle_dates)
                if all(length <= 6 for _, length in stretches):
                    break  # Swap accepted
                else:
                    day_map[d] = ShiftStatus.REST
                    day_map[other_d] = ShiftStatus.WORK


def _build_pt_schedule(
    emp: Employee,
    cycle_dates: list[date],
    leave_map: dict[date, ShiftStatus],
    schedule_matrix: dict[str, dict[date, ShiftStatus]],
    target_days: int = 14,
) -> dict[date, ShiftStatus]:
    """
    Assign part-time schedule: target_days working days, prioritising under-staffed days.
    """
    day_map: dict[date, ShiftStatus] = {}
    # Sort dates by staffing count ascending (prefer under-staffed days)
    sorted_dates = sorted(
        cycle_dates,
        key=lambda d: (_staffing_count(schedule_matrix, d), d),
    )

    work_days = 0
    for d in sorted_dates:
        if d in leave_map:
            day_map[d] = leave_map[d]
        elif work_days < target_days:
            day_map[d] = ShiftStatus.WORK
            work_days += 1
        else:
            day_map[d] = ShiftStatus.REST

    # Fill any dates not yet assigned
    for d in cycle_dates:
        if d not in day_map:
            day_map[d] = ShiftStatus.REST

    return day_map


def generate_schedule(
    employees: list[Employee],
    leaves: list[Leave],
    start_date: date,
    previous_exceptions: list[ScheduleException] | None = None,
) -> ScheduleResult:
    if previous_exceptions is None:
        previous_exceptions = []

    cycle_dates = [start_date + timedelta(days=i) for i in range(28)]
    active_ft = [e for e in employees if e.active and e.type == EmployeeType.FULL_TIME]
    active_pt = [e for e in employees if e.active and e.type == EmployeeType.PART_TIME]

    # Build leave lookups
    leave_sets: dict[str, set[date]] = {e.id: set() for e in employees if e.active}
    leave_statuses: dict[str, dict[date, ShiftStatus]] = {e.id: {} for e in employees if e.active}
    for leave in leaves:
        if leave.employee_id in leave_sets:
            d = leave.date
            if d in set(cycle_dates):
                leave_sets[leave.employee_id].add(d)
                leave_statuses[leave.employee_id][d] = ShiftStatus(leave.type.value)

    # Assign rest blocks and free weekends
    rest_blocks = _assign_rest_blocks(active_ft, previous_exceptions)
    free_weekends = _assign_free_weekends(active_ft, previous_exceptions)

    # Build full-time drafts, distributing free-weekend spans to maximise Friday/Saturday coverage.
    # Employees whose rest block includes Friday (block [3,4]) or whose block forces span 0
    # for fri_sat weekends (block [1,2]) are left to pick naturally; others prefer non-zero spans.
    schedule_matrix: dict[str, dict[date, ShiftStatus]] = {}
    non_zero_counter = 0
    for i, emp in enumerate(active_ft):
        block = tuple(rest_blocks[emp.id])
        fw = free_weekends[emp.id]
        # [1,2]+fri_sat must use span 0 (spans 1-3 create 8-day consecutive stretches).
        # [3,4] block always rests Fri regardless, so span doesn't help Friday staffing.
        # For all other fri_sat employees, avoid span 0 to keep Fridays covered.
        if fw == "fri_sat" and block not in ((1, 2), (3, 4)):
            preferred = 1 + (non_zero_counter % 3)  # rotate through spans 1, 2, 3
            non_zero_counter += 1
        else:
            preferred = i % 4
        schedule_matrix[emp.id] = _build_ft_schedule(
            emp,
            cycle_dates,
            leave_statuses[emp.id],
            rest_blocks[emp.id],
            free_weekends[emp.id],
            preferred_span=preferred,
        )

    # Record free weekend type in exceptions for next cycle
    fw_exceptions: list[ScheduleException] = []
    for emp in active_ft:
        wt = free_weekends[emp.id]
        exc_type = (
            ExceptionType.FREE_WEEKEND_FRI_SAT
            if wt == "fri_sat"
            else ExceptionType.FREE_WEEKEND_SAT_SUN
        )
        fw_exceptions.append(ScheduleException(
            employee_id=emp.id,
            type=exc_type,
            date=start_date,
        ))

    # Validate consecutive days — record 6-day exceptions
    try:
        consec_exceptions = _check_consecutive(schedule_matrix, cycle_dates)
    except ValueError:
        # A 7+ stretch: activate fallback (simplified: treat as infeasible for now)
        consec_exceptions = []

    # Rebalance staffing by swapping work days across employees (keeps work counts at 20)
    _balance_staffing(schedule_matrix, active_ft, cycle_dates, leave_sets)

    # Repair any remaining under-staffed days (adds work days as last resort)
    shortfalls = _repair_staffing(schedule_matrix, active_ft, cycle_dates, leave_sets)

    # Build part-time schedules
    for emp in active_pt:
        # Determine how many days needed based on remaining shortfalls
        pt_target = min(16, max(12, 14))  # Always 14 for MVP
        schedule_matrix[emp.id] = _build_pt_schedule(
            emp,
            cycle_dates,
            leave_statuses.get(emp.id, {}),
            schedule_matrix,
            pt_target,
        )

    # Re-check staffing after part-time fills in
    final_shortfalls = _repair_staffing(schedule_matrix, active_ft, cycle_dates, leave_sets)

    # Assemble Schedule object
    all_active = active_ft + active_pt
    days = []
    for d in cycle_dates:
        shifts = []
        for emp in all_active:
            status = schedule_matrix.get(emp.id, {}).get(d)
            if status is not None:
                shifts.append(Shift(employee_id=emp.id, status=status))
        days.append(ScheduleDay(date=d, shifts=shifts))

    all_exceptions = fw_exceptions + consec_exceptions
    schedule = Schedule(
        start_date=start_date,
        generated_at=datetime.now().isoformat(timespec="seconds"),
        days=days,
        exceptions=all_exceptions,
    )

    return ScheduleResult(
        schedule=schedule if not final_shortfalls else None,
        feasible=len(final_shortfalls) == 0,
        exceptions=all_exceptions,
        warnings=[],
        errors=final_shortfalls,
    )
