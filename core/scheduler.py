from datetime import date, timedelta, datetime
from core.models import (
    Employee, EmployeeType, Leave, LeaveType,
    Shift, ShiftStatus, ScheduleDay, ScheduleException, ExceptionType,
    Schedule, ScheduleResult, Warning, StaffingShortfall,
)

# Valid fixed rest blocks: consecutive weekday pairs Mon-Fri only
VALID_FIXED_BLOCKS: list[tuple[int, int]] = [(0, 1), (1, 2), (2, 3), (3, 4)]

# Hard limit on consecutive working days
MAX_CONSECUTIVE = 5


def _minimum_for_date(d: date) -> int:
    """Return minimum required staffing: 9 for Fri/Sat, 8 otherwise."""
    return 9 if d.weekday() in (4, 5) else 8


def _assign_rest_blocks(
    employees: list[Employee],
    previous_exceptions: list[ScheduleException],
) -> dict[str, list[int]]:
    """Return {employee_id: [weekday1, weekday2]} for all full-time employees."""
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
    Alternates from previous cycle. WEEKEND_MISSED continues the rotation
    (generate_schedule will try both types for missed employees).
    """
    prev_type: dict[str, str] = {}
    for exc in previous_exceptions:
        if exc.type == ExceptionType.FREE_WEEKEND_FRI_SAT:
            prev_type[exc.employee_id] = "fri_sat"
        elif exc.type == ExceptionType.FREE_WEEKEND_SAT_SUN:
            prev_type[exc.employee_id] = "sat_sun"
        # WEEKEND_MISSED: no entry → falls back to default rotation below

    result: dict[str, str] = {}
    for emp in employees:
        last = prev_type.get(emp.id, "sat_sun")  # default: give fri_sat first
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


def _build_all_fixed_schedule(
    leave_map: dict[date, ShiftStatus],
    rest_block: list[int],
    cycle_dates: list[date],
) -> dict[date, ShiftStatus]:
    """All 4 spans use the fixed rest block — no free weekend this cycle."""
    rb = set(rest_block)
    return {
        d: leave_map.get(d) or (ShiftStatus.REST if d.weekday() in rb else ShiftStatus.WORK)
        for d in cycle_dates
    }


def _build_ft_schedule(
    emp: Employee,
    cycle_dates: list[date],
    leave_map: dict[date, ShiftStatus],
    rest_block: list[int],
    weekend_type: str,
    preferred_span: int | None = None,
) -> tuple[dict[date, ShiftStatus], bool, int]:
    """
    Returns (day_map, weekend_placed, span_idx).

    Tries all 4 span placements for the free weekend, picking the one with the
    fewest consecutive work days (hard limit: MAX_CONSECUTIVE = 5).
    preferred_span is tried first; if it achieves ≤5, it is used directly.
    Falls back to all-fixed-block (no free weekend) if no span achieves ≤5.
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
        if max_consec <= MAX_CONSECUTIVE:
            return candidate, True, preferred_span

    # Scan remaining spans for best ≤ MAX_CONSECUTIVE option
    best_map: dict[date, ShiftStatus] | None = None
    best_max_consecutive = 999
    best_span_idx = -1

    for free_span_idx in range(4):
        if free_span_idx == preferred_span:
            continue  # already tried above
        candidate = _draft_for_placement(
            spans, free_span_idx, rb, weekend_weekdays, leave_map, cycle_dates
        )
        stretches = _find_consecutive_stretches(candidate, cycle_dates)
        max_consec = max((length for _, length in stretches), default=0)
        if max_consec < best_max_consecutive:
            best_max_consecutive = max_consec
            best_map = candidate
            best_span_idx = free_span_idx

    if best_max_consecutive <= MAX_CONSECUTIVE:
        return best_map, True, best_span_idx  # type: ignore[return-value]

    # No span achieves ≤ MAX_CONSECUTIVE for this weekend type
    fallback = _build_all_fixed_schedule(leave_map, rest_block, cycle_dates)
    return fallback, False, -1


def _try_second_weekend(
    day_map: dict[date, ShiftStatus],
    cycle_dates: list[date],
    used_span_idx: int,
    rest_block: list[int],
    second_weekend_weekdays: tuple[int, int],
    leave_map: dict[date, ShiftStatus],
) -> tuple[dict[date, ShiftStatus], bool]:
    """
    Attempt to place a second free weekend in a span other than used_span_idx.
    Replaces that span's fixed-block rest with weekend rest.
    Returns (updated_day_map, success). Does NOT modify the original day_map.
    """
    spans = [cycle_dates[i * 7:(i + 1) * 7] for i in range(4)]
    rb = tuple(rest_block)

    for span_idx in range(4):
        if span_idx == used_span_idx:
            continue
        # Build candidate: replace this span's fixed rest with weekend rest
        candidate = dict(day_map)
        for d in spans[span_idx]:
            if d in leave_map:
                candidate[d] = leave_map[d]
            elif d.weekday() in second_weekend_weekdays:
                candidate[d] = ShiftStatus.REST
            else:
                candidate[d] = ShiftStatus.WORK

        stretches = _find_consecutive_stretches(candidate, cycle_dates)
        max_consec = max((length for _, length in stretches), default=0)
        if max_consec <= MAX_CONSECUTIVE:
            return candidate, True

    return day_map, False


def _staffing_count(
    schedule_matrix: dict[str, dict[date, ShiftStatus]],
    d: date,
) -> int:
    return sum(
        1 for day_map in schedule_matrix.values()
        if day_map.get(d) == ShiftStatus.WORK
    )


def _check_consecutive(
    schedule_matrix: dict[str, dict[date, ShiftStatus]],
    cycle_dates: list[date],
) -> list[ScheduleException]:
    """
    Raise ValueError if any employee exceeds MAX_CONSECUTIVE consecutive working days.
    Returns an empty list (no exceptions recorded — ≤ MAX_CONSECUTIVE is the normal limit).
    """
    for emp_id, day_map in schedule_matrix.items():
        stretches = _find_consecutive_stretches(day_map, cycle_dates)
        for stretch_start, length in stretches:
            if length > MAX_CONSECUTIVE:
                raise ValueError(
                    f"Employee {emp_id} has {length} consecutive working days "
                    f"starting {stretch_start} — exceeds maximum of {MAX_CONSECUTIVE}"
                )
    return []


def _repair_staffing(
    schedule_matrix: dict[str, dict[date, ShiftStatus]],
    active_ft: list[Employee],
    cycle_dates: list[date],
    leave_sets: dict[str, set[date]],
) -> list[StaffingShortfall]:
    """
    For each under-staffed day, try to convert a REST day to WORK for one employee
    who: (a) is resting that day, (b) won't create a stretch > MAX_CONSECUTIVE.
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
            if sum(1 for s in day_map.values() if s == ShiftStatus.WORK) >= 20:
                continue
            if d in leave_sets.get(emp.id, set()):
                continue
            day_map[d] = ShiftStatus.WORK
            stretches = _find_consecutive_stretches(day_map, cycle_dates)
            if all(length <= MAX_CONSECUTIVE for _, length in stretches):
                repaired = True
                break
            else:
                day_map[d] = ShiftStatus.REST

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
    Swap-based rebalancer: for each under-staffed day, move a WORK day from an
    over-staffed day to the under-staffed day, keeping total work counts constant
    and never creating a stretch > MAX_CONSECUTIVE.
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
                    continue

                day_map[d] = ShiftStatus.WORK
                day_map[other_d] = ShiftStatus.REST
                stretches = _find_consecutive_stretches(day_map, cycle_dates)
                if all(length <= MAX_CONSECUTIVE for _, length in stretches):
                    break
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
    """Assign part-time schedule: target_days working days, prioritising under-staffed days."""
    day_map: dict[date, ShiftStatus] = {}
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

    # Employees who missed a weekend last cycle — give them priority and try a catch-up
    missed_last_cycle: set[str] = {
        exc.employee_id for exc in previous_exceptions
        if exc.type == ExceptionType.WEEKEND_MISSED
    }

    # Assign rest blocks and initial weekend type preference
    rest_blocks = _assign_rest_blocks(active_ft, previous_exceptions)
    free_weekends = _assign_free_weekends(active_ft, previous_exceptions)

    # Build full-time drafts
    schedule_matrix: dict[str, dict[date, ShiftStatus]] = {}
    # {emp_id: (weekend_given, actual_type, span_idx)}
    weekend_results: dict[str, tuple[bool, str | None, int]] = {}

    non_zero_counter = 0
    for i, emp in enumerate(active_ft):
        block = tuple(rest_blocks[emp.id])
        fw = free_weekends[emp.id]

        if fw == "fri_sat" and block not in ((1, 2), (3, 4)):
            preferred = 1 + (non_zero_counter % 3)
            non_zero_counter += 1
        else:
            preferred = i % 4

        # Try primary weekend type
        day_map, got_weekend, span_idx = _build_ft_schedule(
            emp, cycle_dates, leave_statuses[emp.id],
            rest_blocks[emp.id], fw, preferred_span=preferred,
        )

        # If primary failed, try alternate (important for WEEKEND_MISSED catch-up)
        if not got_weekend:
            alt_fw = "sat_sun" if fw == "fri_sat" else "fri_sat"
            day_map2, got_alt, span_idx2 = _build_ft_schedule(
                emp, cycle_dates, leave_statuses[emp.id],
                rest_blocks[emp.id], alt_fw, preferred_span=None,
            )
            if got_alt:
                day_map, got_weekend, span_idx, fw = day_map2, True, span_idx2, alt_fw

        schedule_matrix[emp.id] = day_map
        weekend_results[emp.id] = (got_weekend, fw if got_weekend else None, span_idx)

    # Catch-up: employees who missed last cycle AND got a weekend this cycle
    # → try to place a second weekend in a different span
    for emp in active_ft:
        if emp.id not in missed_last_cycle:
            continue
        got_weekend, actual_type, span_idx = weekend_results[emp.id]
        if not got_weekend:
            continue  # still couldn't get a weekend — don't attempt second

        second_type = "sat_sun" if actual_type == "fri_sat" else "fri_sat"
        second_weekdays: tuple[int, int] = (4, 5) if second_type == "fri_sat" else (5, 6)

        new_map, got_2nd = _try_second_weekend(
            schedule_matrix[emp.id], cycle_dates, span_idx,
            rest_blocks[emp.id], second_weekdays, leave_statuses[emp.id],
        )
        if got_2nd:
            schedule_matrix[emp.id] = new_map

    # Build exceptions list for next cycle
    fw_exceptions: list[ScheduleException] = []
    for emp in active_ft:
        got_weekend, actual_type, _ = weekend_results[emp.id]
        if got_weekend:
            exc_type = (
                ExceptionType.FREE_WEEKEND_FRI_SAT
                if actual_type == "fri_sat"
                else ExceptionType.FREE_WEEKEND_SAT_SUN
            )
        else:
            exc_type = ExceptionType.WEEKEND_MISSED
        fw_exceptions.append(ScheduleException(
            employee_id=emp.id, type=exc_type, date=start_date,
        ))

    # Validate consecutive days
    try:
        consec_exceptions = _check_consecutive(schedule_matrix, cycle_dates)
    except ValueError:
        consec_exceptions = []

    # Rebalance staffing (swap-based, keeps work counts constant)
    _balance_staffing(schedule_matrix, active_ft, cycle_dates, leave_sets)

    # Repair remaining shortfalls (adds work days as last resort)
    _repair_staffing(schedule_matrix, active_ft, cycle_dates, leave_sets)

    # Build part-time schedules
    for emp in active_pt:
        schedule_matrix[emp.id] = _build_pt_schedule(
            emp, cycle_dates,
            leave_statuses.get(emp.id, {}),
            schedule_matrix,
            target_days=14,
        )

    # Final staffing check
    final_shortfalls = _repair_staffing(schedule_matrix, active_ft, cycle_dates, leave_sets)

    # Assemble Schedule
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
