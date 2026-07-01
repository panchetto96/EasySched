from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class EmployeeType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"


class LeaveType(str, Enum):
    FERIE = "ferie"
    MALATTIA = "malattia"
    PERMESSO = "permesso"


class ShiftStatus(str, Enum):
    WORK = "work"
    REST = "rest"
    FERIE = "ferie"
    MALATTIA = "malattia"
    PERMESSO = "permesso"
    OVERRIDE = "override"


class ExceptionType(str, Enum):
    SIX_DAY_STRETCH = "six_day_stretch"
    FALLBACK_ACTIVATED = "fallback_activated"
    FREE_WEEKEND_FRI_SAT = "free_weekend_fri_sat"
    FREE_WEEKEND_SAT_SUN = "free_weekend_sat_sun"


@dataclass
class Employee:
    id: str
    name: str
    type: EmployeeType
    fixed_rest_block: list[int] | None  # [weekday, weekday] or None
    active: bool = True


@dataclass
class Leave:
    employee_id: str
    date: date
    type: LeaveType


@dataclass
class Shift:
    employee_id: str
    status: ShiftStatus


@dataclass
class ScheduleDay:
    date: date
    shifts: list[Shift] = field(default_factory=list)


@dataclass
class ScheduleException:
    employee_id: str
    type: ExceptionType
    date: date


@dataclass
class Warning:
    date: date
    staffing_count: int
    minimum_required: int


@dataclass
class StaffingShortfall:
    date: date
    actual_count: int
    required_count: int


@dataclass
class Schedule:
    start_date: date
    generated_at: str  # ISO datetime string
    days: list[ScheduleDay] = field(default_factory=list)
    exceptions: list[ScheduleException] = field(default_factory=list)


@dataclass
class ScheduleResult:
    schedule: Schedule | None
    feasible: bool
    exceptions: list[ScheduleException] = field(default_factory=list)
    warnings: list[Warning] = field(default_factory=list)
    errors: list[StaffingShortfall] = field(default_factory=list)
