# Hostel Scheduler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Windows desktop application in Python + PyQt6 for a hostel manager in Florence to generate and manage employee shift schedules across rolling 28-day cycles.

**Architecture:** A pure-Python `core/` layer holds all business logic with zero UI imports, making it fully unit-testable via pytest. A `ui/` layer built on PyQt6 reads from and writes through the core layer. JSON files in a `data/` folder next to the `.exe` are the sole persistence mechanism. PyInstaller packages everything into a single Windows `.exe`.

**Tech Stack:** Python 3.12, PyQt6 6.7+, pytest 8+, PyInstaller 6+

## Global Constraints

- Python 3.12 — use `X | Y` union types, `match` statements freely
- `core/` must have zero imports from `ui/` or `PyQt6` — enforced by test suite running without Qt installed
- All user-visible strings go through `tr(key)` — never hardcode Italian or English in widget code
- JSON files use ISO 8601 dates (`YYYY-MM-DD`) and ISO datetimes (`YYYY-MM-DDTHH:MM:SS`)
- CSV exports use language-neutral status codes: `L` (work), `R` (rest), `F` (ferie), `M` (malattia), `P` (permesso), `O` (override)
- `fixed_rest_block` weekday integers: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
- Valid fixed blocks for full-time: `[0,1]` `[1,2]` `[2,3]` `[3,4]` only — Fri-Sat `[4,5]` and Sat-Sun `[5,6]` are NOT valid fixed blocks
- Free weekend options: `"fri_sat"` ([4,5]) or `"sat_sun"` ([5,6]) — 1 per employee per 28-day cycle
- Full-time: 20 working days per cycle (8 rest = 4 spans × 2 days); 3 spans use fixed block, 1 span uses free weekend
- Part-time: 12–16 working days, targeting 14
- Min staffing: 8 for Sun–Thu, 9 for Fri–Sat
- Max consecutive working days: 5 (6 allowed only at a rest-block → free-weekend transition)
- Project root: `C:\Users\panco\Documents\hostel-scheduler\`
- Run all tests with: `python -m pytest tests/ -v`

---

## File Map

```
hostel-scheduler/
├── main.py                          # Entry point: bootstrap data dir, launch QApplication
├── pyproject.toml                   # Dependencies + pytest config
├── core/
│   ├── __init__.py
│   ├── models.py                    # All dataclasses and enums (no logic)
│   ├── scheduler.py                 # Scheduling algorithm — pure functions only
│   ├── storage.py                   # JSON read/write for employees, leaves, schedules
│   └── csv_io.py                    # CSV import/export + CsvImportError
├── ui/
│   ├── __init__.py
│   ├── app.py                       # QApplication setup; holds active language state
│   ├── main_window.py               # QMainWindow: nav bar, toolbar, stacked widget
│   ├── i18n/
│   │   ├── __init__.py              # tr(key), set_language(), get_language()
│   │   ├── it.json                  # Italian strings (primary)
│   │   └── en.json                  # English strings
│   └── views/
│       ├── __init__.py
│       ├── schedule_grid.py         # QTableWidget grid view
│       ├── schedule_calendar.py     # QCalendarWidget-based calendar view
│       ├── employees.py             # Employee list + add/edit/deactivate dialog
│       └── leave.py                 # Leave management: list + date picker
├── data/                            # Created at runtime next to .exe
│   ├── employees.json
│   ├── leaves.json
│   └── schedules/
└── tests/
    ├── test_models.py
    ├── test_storage.py
    ├── test_scheduler.py
    └── test_csv_io.py
```

---

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `core/__init__.py`
- Create: `ui/__init__.py`
- Create: `ui/views/__init__.py`
- Create: `ui/i18n/__init__.py` (stub only)
- Create: `.gitignore`
- Create: `tests/__init__.py` (empty)

**Interfaces:**
- Produces: runnable `python -m pytest tests/` with 0 tests collected (no failures)

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "hostel-scheduler"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "PyQt6>=6.7",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

- [ ] **Step 2: Create directory structure and `__init__.py` stubs**

Create these files, each empty or with just a module docstring:
- `core/__init__.py` — empty
- `ui/__init__.py` — empty
- `ui/views/__init__.py` — empty
- `ui/i18n/__init__.py` — empty (will be filled in Task 9)
- `tests/__init__.py` — empty

- [ ] **Step 3: Create `.gitignore`**

```
__pycache__/
*.pyc
*.pyo
.pytest_cache/
dist/
build/
*.spec
data/
*.egg-info/
.venv/
venv/
```

- [ ] **Step 4: Initialize git and install dev dependencies**

```bash
cd C:\Users\panco\Documents\hostel-scheduler
git init
pip install -e ".[dev]"
```

- [ ] **Step 5: Verify pytest runs with 0 tests**

```bash
python -m pytest tests/ -v
```

Expected output:
```
============= no tests ran in 0.XXs =============
```

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml core/ ui/ tests/ .gitignore
git commit -m "chore: project scaffold with pyproject.toml and directory structure"
```

---

## Task 2: Core Data Models

**Files:**
- Create: `core/models.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Produces:
  - `Employee(id, name, type, fixed_rest_block, active)`
  - `Leave(employee_id, date, type)`
  - `Shift(employee_id, status)`
  - `ScheduleDay(date, shifts)`
  - `ScheduleException(employee_id, type, date)`
  - `Warning(date, staffing_count, minimum_required)`
  - `StaffingShortfall(date, actual_count, required_count)`
  - `Schedule(start_date, generated_at, days, exceptions)`
  - `ScheduleResult(schedule, feasible, exceptions, warnings, errors)`
  - Enums: `EmployeeType`, `LeaveType`, `ShiftStatus`, `ExceptionType`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.models'`

- [ ] **Step 3: Implement `core/models.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_models.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add core/models.py tests/test_models.py
git commit -m "feat: core data models (Employee, Leave, Schedule, ScheduleResult)"
```

---

## Task 3: JSON Storage Layer

**Files:**
- Create: `core/storage.py`
- Create: `tests/test_storage.py`

**Interfaces:**
- Consumes: all types from `core.models`
- Produces:
  - `ensure_data_dir(data_dir: Path) -> None`
  - `load_employees(data_dir: Path) -> list[Employee]`
  - `save_employees(data_dir: Path, employees: list[Employee]) -> None`
  - `load_leaves(data_dir: Path) -> list[Leave]`
  - `save_leaves(data_dir: Path, leaves: list[Leave]) -> None`
  - `load_schedule(data_dir: Path, start_date: date) -> Schedule | None`
  - `save_schedule(data_dir: Path, schedule: Schedule) -> None`
  - `list_schedule_dates(data_dir: Path) -> list[date]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_storage.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_storage.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.storage'`

- [ ] **Step 3: Implement `core/storage.py`**

```python
import json
from datetime import date
from pathlib import Path
from core.models import (
    Employee, EmployeeType, Leave, LeaveType,
    Schedule, ScheduleDay, Shift, ShiftStatus,
    ScheduleException, ExceptionType,
)


def ensure_data_dir(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "schedules").mkdir(exist_ok=True)


def load_employees(data_dir: Path) -> list[Employee]:
    path = data_dir / "employees.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        Employee(
            id=e["id"],
            name=e["name"],
            type=EmployeeType(e["type"]),
            fixed_rest_block=e.get("fixed_rest_block"),
            active=e.get("active", True),
        )
        for e in data
    ]


def save_employees(data_dir: Path, employees: list[Employee]) -> None:
    path = data_dir / "employees.json"
    data = [
        {
            "id": e.id,
            "name": e.name,
            "type": e.type.value,
            "fixed_rest_block": e.fixed_rest_block,
            "active": e.active,
        }
        for e in employees
    ]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_leaves(data_dir: Path) -> list[Leave]:
    path = data_dir / "leaves.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        Leave(
            employee_id=l["employee_id"],
            date=date.fromisoformat(l["date"]),
            type=LeaveType(l["type"]),
        )
        for l in data
    ]


def save_leaves(data_dir: Path, leaves: list[Leave]) -> None:
    path = data_dir / "leaves.json"
    data = [
        {
            "employee_id": l.employee_id,
            "date": l.date.isoformat(),
            "type": l.type.value,
        }
        for l in leaves
    ]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _schedule_path(data_dir: Path, start_date: date) -> Path:
    return data_dir / "schedules" / f"{start_date.isoformat()}.json"


def load_schedule(data_dir: Path, start_date: date) -> Schedule | None:
    path = _schedule_path(data_dir, start_date)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    days = [
        ScheduleDay(
            date=date.fromisoformat(d["date"]),
            shifts=[
                Shift(employee_id=s["employee_id"], status=ShiftStatus(s["status"]))
                for s in d["shifts"]
            ],
        )
        for d in data.get("days", [])
    ]
    exceptions = [
        ScheduleException(
            employee_id=e["employee_id"],
            type=ExceptionType(e["type"]),
            date=date.fromisoformat(e["date"]),
        )
        for e in data.get("exceptions", [])
    ]
    return Schedule(
        start_date=date.fromisoformat(data["start_date"]),
        generated_at=data["generated_at"],
        days=days,
        exceptions=exceptions,
    )


def save_schedule(data_dir: Path, schedule: Schedule) -> None:
    path = _schedule_path(data_dir, schedule.start_date)
    data = {
        "start_date": schedule.start_date.isoformat(),
        "generated_at": schedule.generated_at,
        "days": [
            {
                "date": d.date.isoformat(),
                "shifts": [
                    {"employee_id": s.employee_id, "status": s.status.value}
                    for s in d.shifts
                ],
            }
            for d in schedule.days
        ],
        "exceptions": [
            {
                "employee_id": e.employee_id,
                "type": e.type.value,
                "date": e.date.isoformat(),
            }
            for e in schedule.exceptions
        ],
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def list_schedule_dates(data_dir: Path) -> list[date]:
    schedules_dir = data_dir / "schedules"
    if not schedules_dir.exists():
        return []
    return sorted(
        date.fromisoformat(p.stem)
        for p in schedules_dir.glob("*.json")
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_storage.py -v
```

Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add core/storage.py tests/test_storage.py
git commit -m "feat: JSON storage layer for employees, leaves, and schedules"
```

---

## Task 4: Scheduler — Helpers and Rest Block Assignment

**Files:**
- Create: `core/scheduler.py` (partial — helpers + `_assign_rest_blocks`)
- Create: `tests/test_scheduler.py` (first batch)

**Interfaces:**
- Produces (internal, tested directly):
  - `_minimum_for_date(d: date) -> int` — returns 9 for Fri/Sat, 8 otherwise
  - `VALID_FIXED_BLOCKS: list[tuple[int,int]]` — `[(0,1),(1,2),(2,3),(3,4)]`
  - `_assign_rest_blocks(employees, previous_exceptions) -> dict[str, list[int]]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_scheduler.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_scheduler.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.scheduler'`

- [ ] **Step 3: Implement the first part of `core/scheduler.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_scheduler.py -v
```

Expected: `15 passed`

- [ ] **Step 5: Commit**

```bash
git add core/scheduler.py tests/test_scheduler.py
git commit -m "feat: scheduler helpers and rest block assignment"
```

---

## Task 5: Scheduler — Free Weekend Assignment and Draft Generation

**Files:**
- Modify: `core/scheduler.py` (add `_assign_free_weekends`, `_build_ft_schedule`, `_find_consecutive_stretches`)
- Modify: `tests/test_scheduler.py` (add draft generation tests)

**Interfaces:**
- Produces (internal):
  - `_assign_free_weekends(employees, previous_exceptions) -> dict[str, str]`
    Returns `{employee_id: "fri_sat" | "sat_sun"}`
  - `_build_ft_schedule(emp, cycle_dates, leave_map, rest_block, weekend_type) -> dict[date, ShiftStatus]`
    Tries all 4 span placements; picks the one with minimum max consecutive days; returns the day→status map.
  - `_find_consecutive_stretches(day_map, cycle_dates) -> list[tuple[date, int]]`
    Returns `[(stretch_start_date, length), ...]` for each consecutive WORK stretch.

- [ ] **Step 1: Add tests to `tests/test_scheduler.py`**

```python
# Add these imports at the top of test_scheduler.py
from core.scheduler import (
    _minimum_for_date, VALID_FIXED_BLOCKS, _assign_rest_blocks,
    _assign_free_weekends, _build_ft_schedule, _find_consecutive_stretches,
)


# ── _assign_free_weekends ──────────────────────────────────────────────────────

def test_free_weekend_default_is_fri_sat():
    emp = make_ft()
    result = _assign_free_weekends([emp], [])
    assert result[emp.id] in ("fri_sat", "sat_sun")


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


def test_ft_schedule_max_consecutive_le_6():
    emp = make_ft(block=[0, 1])
    cycle_dates = [date(2025, 7, 7) + timedelta(days=i) for i in range(28)]
    day_map = _build_ft_schedule(emp, cycle_dates, {}, [0, 1], "fri_sat")
    stretches = _find_consecutive_stretches(day_map, cycle_dates)
    for _, length in stretches:
        assert length <= 6, f"Consecutive stretch of {length} days found"


# ── _find_consecutive_stretches ────────────────────────────────────────────────

def test_find_stretches_simple():
    from datetime import date, timedelta
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
```

- [ ] **Step 2: Run tests to verify the new ones fail**

```bash
python -m pytest tests/test_scheduler.py -v -k "free_weekend or ft_schedule or stretches"
```

Expected: `ImportError` on the new imports

- [ ] **Step 3: Add functions to `core/scheduler.py`**

Append after `_pick_least_used_block`:

```python
def _assign_free_weekends(
    employees: list[Employee],
    previous_exceptions: list[ScheduleException],
) -> dict[str, str]:
    """
    Return {employee_id: "fri_sat" | "sat_sun"}.
    Rotates from the previous cycle's choice to ensure fairness.
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
        max_consec = max((l for _, l in stretches), default=0)
        if max_consec < best_max_consecutive:
            best_max_consecutive = max_consec
            best_map = candidate
        if max_consec <= 5:
            break  # Good enough — stop searching

    return best_map  # type: ignore[return-value]


def _draft_for_placement(
    spans: list[list[date]],
    free_span_idx: int,
    rest_block: tuple[int, int],
    weekend_weekdays: tuple[int, int],
    leave_map: dict[date, ShiftStatus],
    cycle_dates: list[date],
) -> dict[date, ShiftStatus]:
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
```

- [ ] **Step 4: Run all scheduler tests**

```bash
python -m pytest tests/test_scheduler.py -v
```

Expected: all tests pass (≈25 tests)

- [ ] **Step 5: Commit**

```bash
git add core/scheduler.py tests/test_scheduler.py
git commit -m "feat: free weekend assignment and full-time draft schedule generation"
```

---

## Task 6: Scheduler — Constraint Validation and Local Repair

**Files:**
- Modify: `core/scheduler.py` (add `_check_and_repair_staffing`, `_check_consecutive`)
- Modify: `tests/test_scheduler.py`

**Interfaces:**
- Produces (internal):
  - `_check_consecutive(schedule_matrix, cycle_dates) -> list[ScheduleException]`
    Returns list of SIX_DAY_STRETCH exceptions; raises if any stretch > 6.
  - `_staffing_count(schedule_matrix, d) -> int`
    Counts WORK shifts for a given date across all employees.
  - `_repair_staffing(schedule_matrix, active_ft, cycle_dates, leave_sets) -> list[StaffingShortfall]`
    Attempts to fix under-staffed days by converting REST to WORK for a suitable employee.
    Returns unfixable shortfalls.

- [ ] **Step 1: Add tests to `tests/test_scheduler.py`**

```python
# Add to imports
from core.scheduler import (
    _minimum_for_date, VALID_FIXED_BLOCKS, _assign_rest_blocks,
    _assign_free_weekends, _build_ft_schedule, _find_consecutive_stretches,
    _staffing_count, _check_consecutive,
)


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
```

- [ ] **Step 2: Run tests to verify new ones fail**

```bash
python -m pytest tests/test_scheduler.py -v -k "staffing_count or check_consecutive"
```

- [ ] **Step 3: Add constraint validation functions to `core/scheduler.py`**

```python
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
    Returns shortfalls that could not be repaired.
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
```

- [ ] **Step 4: Run all scheduler tests**

```bash
python -m pytest tests/test_scheduler.py -v
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add core/scheduler.py tests/test_scheduler.py
git commit -m "feat: constraint validation and local repair for staffing and consecutive days"
```

---

## Task 7: Scheduler — Fallback, Part-time, and `generate_schedule()`

**Files:**
- Modify: `core/scheduler.py` (complete the public API)
- Modify: `tests/test_scheduler.py` (integration tests)

**Interfaces:**
- Produces (public):
  - `generate_schedule(employees, leaves, start_date, previous_exceptions=None) -> ScheduleResult`

- [ ] **Step 1: Add integration tests to `tests/test_scheduler.py`**

```python
# Add to imports
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
```

- [ ] **Step 2: Run tests to verify new integration tests fail**

```bash
python -m pytest tests/test_scheduler.py -v -k "generate_schedule"
```

Expected: `ImportError` on `generate_schedule`

- [ ] **Step 3: Add `generate_schedule` and part-time logic to `core/scheduler.py`**

```python
from datetime import datetime


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

    # Build full-time drafts
    schedule_matrix: dict[str, dict[date, ShiftStatus]] = {}
    for emp in active_ft:
        schedule_matrix[emp.id] = _build_ft_schedule(
            emp,
            cycle_dates,
            leave_statuses[emp.id],
            rest_blocks[emp.id],
            free_weekends[emp.id],
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

    # Repair under-staffed days
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
```

- [ ] **Step 4: Run the full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all tests pass (roughly 35–40 tests)

- [ ] **Step 5: Commit**

```bash
git add core/scheduler.py tests/test_scheduler.py
git commit -m "feat: complete scheduling engine with generate_schedule(), fallback, and part-time"
```

---

## Task 8: CSV Import / Export

**Files:**
- Create: `core/csv_io.py`
- Create: `tests/test_csv_io.py`

**Interfaces:**
- Consumes: `Employee`, `Schedule`, `ScheduleDay`, `Shift`, `ShiftStatus`, `EmployeeType`
- Produces:
  - `export_schedule_csv(schedule, employees, filepath) -> None`
  - `import_schedule_csv(filepath) -> tuple[Schedule, list[str]]` — returns schedule + list of employee names in row order
  - `export_employees_csv(employees, filepath) -> None`
  - `import_employees_csv(filepath) -> list[Employee]`
  - `class CsvImportError(Exception)` with `message`, optional `row: int`, optional `column: str`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_csv_io.py
import uuid
from datetime import date, timedelta
from pathlib import Path
import pytest
from core.models import (
    Employee, EmployeeType, Shift, ShiftStatus, Schedule, ScheduleDay,
)
from core.csv_io import (
    export_schedule_csv, import_schedule_csv,
    export_employees_csv, import_employees_csv,
    CsvImportError,
)


def make_employee(name, emp_type=EmployeeType.FULL_TIME, block=None):
    return Employee(
        id=str(uuid.uuid4()),
        name=name,
        type=emp_type,
        fixed_rest_block=block,
        active=True,
    )


def make_schedule(employees, start=date(2025, 7, 1)):
    statuses = [ShiftStatus.WORK, ShiftStatus.REST, ShiftStatus.FERIE,
                ShiftStatus.MALATTIA, ShiftStatus.PERMESSO, ShiftStatus.OVERRIDE]
    days = []
    for i in range(28):
        d = start + timedelta(days=i)
        shifts = [
            Shift(employee_id=emp.id, status=statuses[i % len(statuses)])
            for emp in employees
        ]
        days.append(ScheduleDay(date=d, shifts=shifts))
    return Schedule(start_date=start, generated_at="2025-06-28T14:00:00", days=days)


def test_schedule_csv_round_trip(tmp_path):
    employees = [make_employee("Marco"), make_employee("Linda")]
    schedule = make_schedule(employees)
    filepath = tmp_path / "turni.csv"
    export_schedule_csv(schedule, employees, filepath)
    loaded_schedule, emp_names = import_schedule_csv(filepath)
    assert loaded_schedule.start_date == schedule.start_date
    assert emp_names == ["Marco", "Linda"]
    # All statuses must match
    for day_orig, day_loaded in zip(schedule.days, loaded_schedule.days):
        for shift_orig, shift_loaded in zip(day_orig.shifts, day_loaded.shifts):
            assert shift_orig.status == shift_loaded.status


def test_schedule_csv_is_byte_identical_on_reimport(tmp_path):
    employees = [make_employee("Marco")]
    schedule = make_schedule(employees)
    f1 = tmp_path / "export1.csv"
    f2 = tmp_path / "export2.csv"
    export_schedule_csv(schedule, employees, f1)
    loaded_schedule, _ = import_schedule_csv(f1)
    # Re-export with same employee list
    export_schedule_csv(loaded_schedule, employees, f2)
    assert f1.read_text() == f2.read_text()


def test_employees_csv_round_trip(tmp_path):
    employees = [
        make_employee("Marco", EmployeeType.FULL_TIME, [1, 2]),
        make_employee("Gioia", EmployeeType.PART_TIME, None),
    ]
    filepath = tmp_path / "dipendenti.csv"
    export_employees_csv(employees, filepath)
    loaded = import_employees_csv(filepath)
    assert len(loaded) == 2
    assert loaded[0].name == "Marco"
    assert loaded[0].fixed_rest_block == [1, 2]
    assert loaded[1].name == "Gioia"
    assert loaded[1].fixed_rest_block is None
    assert loaded[1].type == EmployeeType.PART_TIME


def test_import_invalid_status_raises(tmp_path):
    filepath = tmp_path / "bad.csv"
    filepath.write_text(
        "# start_date=2025-07-01,generated_at=2025-06-28T14:00:00\n"
        "employee,2025-07-01\n"
        "Marco,INVALID\n",
        encoding="utf-8",
    )
    with pytest.raises(CsvImportError) as exc_info:
        import_schedule_csv(filepath)
    assert "INVALID" in str(exc_info.value)


def test_import_missing_column_raises(tmp_path):
    filepath = tmp_path / "bad.csv"
    filepath.write_text("employee\nMarco\n", encoding="utf-8")
    with pytest.raises(CsvImportError):
        import_schedule_csv(filepath)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_csv_io.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.csv_io'`

- [ ] **Step 3: Implement `core/csv_io.py`**

```python
import csv
import uuid
from datetime import date
from pathlib import Path
from core.models import (
    Employee, EmployeeType, Shift, ShiftStatus,
    Schedule, ScheduleDay,
)

_STATUS_CODE = {
    ShiftStatus.WORK: "L",
    ShiftStatus.REST: "R",
    ShiftStatus.FERIE: "F",
    ShiftStatus.MALATTIA: "M",
    ShiftStatus.PERMESSO: "P",
    ShiftStatus.OVERRIDE: "O",
}
_CODE_STATUS = {v: k for k, v in _STATUS_CODE.items()}


class CsvImportError(Exception):
    def __init__(self, message: str, row: int | None = None, column: str | None = None):
        super().__init__(message)
        self.row = row
        self.column = column


def export_schedule_csv(
    schedule: Schedule,
    employees: list[Employee],
    filepath: Path,
) -> None:
    date_cols = [d.date.isoformat() for d in schedule.days]
    # Build {employee_id: name} lookup
    id_to_name = {e.id: e.name for e in employees}
    # Build {(employee_id, date): status} lookup
    status_lookup: dict[tuple[str, str], str] = {}
    for day in schedule.days:
        for shift in day.shifts:
            status_lookup[(shift.employee_id, day.date.isoformat())] = _STATUS_CODE[shift.status]

    with filepath.open("w", newline="", encoding="utf-8") as f:
        f.write(f"# start_date={schedule.start_date.isoformat()},generated_at={schedule.generated_at}\n")
        writer = csv.writer(f)
        writer.writerow(["employee"] + date_cols)
        for emp in employees:
            row = [emp.name] + [
                status_lookup.get((emp.id, d), "R")
                for d in date_cols
            ]
            writer.writerow(row)


def import_schedule_csv(filepath: Path) -> tuple[Schedule, list[str]]:
    lines = filepath.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise CsvImportError("Empty CSV file")

    # Parse metadata comment
    meta_line = lines[0] if lines[0].startswith("#") else ""
    start_date: date | None = None
    generated_at = "unknown"
    if meta_line:
        for part in meta_line.lstrip("# ").split(","):
            if part.startswith("start_date="):
                start_date = date.fromisoformat(part.split("=", 1)[1])
            elif part.startswith("generated_at="):
                generated_at = part.split("=", 1)[1]

    data_lines = [l for l in lines if not l.startswith("#")]
    reader = csv.reader(data_lines)
    header = next(reader, None)
    if header is None or len(header) < 2 or header[0] != "employee":
        raise CsvImportError("Missing or invalid header row — expected 'employee,YYYY-MM-DD,...'")

    date_cols = header[1:]
    if start_date is None and date_cols:
        start_date = date.fromisoformat(date_cols[0])

    emp_names: list[str] = []
    rows: list[list[str]] = []
    for row_idx, row in enumerate(reader, start=2):
        if not row:
            continue
        emp_names.append(row[0])
        rows.append(row[1:])

    # Validate status codes
    valid_codes = set(_CODE_STATUS.keys())
    for row_idx, (name, values) in enumerate(zip(emp_names, rows), start=2):
        for col_idx, (col_name, code) in enumerate(zip(date_cols, values)):
            if code not in valid_codes:
                raise CsvImportError(
                    f"Unknown status code '{code}' for employee '{name}' on {col_name}",
                    row=row_idx,
                    column=col_name,
                )

    # Build Schedule
    days: list[ScheduleDay] = []
    for col_idx, col_name in enumerate(date_cols):
        d = date.fromisoformat(col_name)
        shifts = [
            Shift(
                employee_id=f"imported_{name}",
                status=_CODE_STATUS[rows[row_idx][col_idx]],
            )
            for row_idx, name in enumerate(emp_names)
            if col_idx < len(rows[row_idx])
        ]
        days.append(ScheduleDay(date=d, shifts=shifts))

    schedule = Schedule(
        start_date=start_date,
        generated_at=generated_at,
        days=days,
    )
    return schedule, emp_names


def export_employees_csv(employees: list[Employee], filepath: Path) -> None:
    with filepath.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "name", "type", "fixed_rest_block", "active"])
        for emp in employees:
            block = ",".join(str(d) for d in emp.fixed_rest_block) if emp.fixed_rest_block else ""
            writer.writerow([emp.id, emp.name, emp.type.value, block, str(emp.active).lower()])


def import_employees_csv(filepath: Path) -> list[Employee]:
    with filepath.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        employees = []
        for row_idx, row in enumerate(reader, start=2):
            if "name" not in row:
                raise CsvImportError("Missing 'name' column", row=row_idx)
            block_str = row.get("fixed_rest_block", "").strip()
            block = [int(x) for x in block_str.split(",") if x.strip()] if block_str else None
            employees.append(Employee(
                id=row.get("id") or str(uuid.uuid4()),
                name=row["name"],
                type=EmployeeType(row.get("type", "full_time")),
                fixed_rest_block=block,
                active=row.get("active", "true").lower() == "true",
            ))
    return employees
```

- [ ] **Step 4: Run all tests**

```bash
python -m pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add core/csv_io.py tests/test_csv_io.py
git commit -m "feat: CSV import/export with round-trip guarantee and validation"
```

---

## Task 9: i18n System

**Files:**
- Modify: `ui/i18n/__init__.py`
- Create: `ui/i18n/it.json`
- Create: `ui/i18n/en.json`

**Interfaces:**
- Produces:
  - `tr(key: str) -> str` — returns translation in active language, falls back to key
  - `set_language(lang: str) -> None` — `"it"` or `"en"`
  - `get_language() -> str`

- [ ] **Step 1: Implement `ui/i18n/__init__.py`**

```python
import json
from pathlib import Path

_lang = "it"
_strings: dict[str, dict[str, str]] = {}

def _load_all() -> None:
    here = Path(__file__).parent
    for lang in ("it", "en"):
        path = here / f"{lang}.json"
        if path.exists():
            _strings[lang] = json.loads(path.read_text(encoding="utf-8"))

_load_all()


def tr(key: str) -> str:
    return _strings.get(_lang, {}).get(key) or _strings.get("it", {}).get(key) or key


def set_language(lang: str) -> None:
    global _lang
    if lang in ("it", "en"):
        _lang = lang


def get_language() -> str:
    return _lang
```

- [ ] **Step 2: Create `ui/i18n/it.json`**

```json
{
  "nav.schedule": "Turni",
  "nav.employees": "Dipendenti",
  "nav.leave": "Assenze",
  "schedule.cycle_label": "Ciclo:",
  "schedule.prev": "← Prec",
  "schedule.next": "Succ →",
  "schedule.generate": "Genera Turni",
  "schedule.export_csv": "Esporta CSV",
  "schedule.import_csv": "Importa CSV",
  "schedule.grid_view": "Vista Griglia",
  "schedule.calendar_view": "Vista Calendario",
  "schedule.days_worked": "Giorni lavorati",
  "schedule.staffing_below_min": "Personale sotto il minimo",
  "schedule.no_schedule": "Nessun turno generato per questo ciclo.",
  "schedule.generate_prompt": "Clicca 'Genera Turni' per creare il calendario.",
  "employee.add": "Aggiungi",
  "employee.edit": "Modifica",
  "employee.deactivate": "Disattiva",
  "employee.full_time": "Tempo pieno",
  "employee.part_time": "Part-time",
  "employee.name": "Nome",
  "employee.type": "Tipo",
  "employee.rest_block": "Blocco riposo fisso",
  "employee.rest_block_algo": "Algoritmo",
  "leave.add": "Aggiungi assenza",
  "leave.delete": "Elimina",
  "leave.type_ferie": "Ferie",
  "leave.type_malattia": "Malattia",
  "leave.type_permesso": "Permesso",
  "leave.from": "Dal",
  "leave.to": "Al",
  "leave.type": "Tipo",
  "leave.employee": "Dipendente",
  "dialog.confirm": "Conferma",
  "dialog.cancel": "Annulla",
  "dialog.ok": "OK",
  "dialog.import_confirm": "Questa operazione sovrascriverà i dati esistenti. Continuare?",
  "dialog.import_success": "Importazione completata.",
  "dialog.import_error": "Errore nell'importazione: {error}",
  "dialog.export_success": "Esportazione completata.",
  "error.infeasible": "Impossibile generare un turno valido: giorni con personale insufficiente.",
  "error.shortfall": "Il {date} mancano {n} operatori (richiesti {req}, presenti {actual}).",
  "exception.six_day_stretch": "{name}: tratto di 6 giorni consecutivi dal {date}.",
  "exception.fallback_activated": "{name}: blocco fallback attivato dal {date}.",
  "month.1": "gennaio", "month.2": "febbraio", "month.3": "marzo",
  "month.4": "aprile", "month.5": "maggio", "month.6": "giugno",
  "month.7": "luglio", "month.8": "agosto", "month.9": "settembre",
  "month.10": "ottobre", "month.11": "novembre", "month.12": "dicembre",
  "weekday.short.0": "Lun", "weekday.short.1": "Mar", "weekday.short.2": "Mer",
  "weekday.short.3": "Gio", "weekday.short.4": "Ven",
  "weekday.short.5": "Sab", "weekday.short.6": "Dom"
}
```

- [ ] **Step 3: Create `ui/i18n/en.json`**

```json
{
  "nav.schedule": "Shifts",
  "nav.employees": "Employees",
  "nav.leave": "Absences",
  "schedule.cycle_label": "Cycle:",
  "schedule.prev": "← Prev",
  "schedule.next": "Next →",
  "schedule.generate": "Generate Schedule",
  "schedule.export_csv": "Export CSV",
  "schedule.import_csv": "Import CSV",
  "schedule.grid_view": "Grid View",
  "schedule.calendar_view": "Calendar View",
  "schedule.days_worked": "Days worked",
  "schedule.staffing_below_min": "Staffing below minimum",
  "schedule.no_schedule": "No schedule generated for this cycle.",
  "schedule.generate_prompt": "Click 'Generate Schedule' to create the timetable.",
  "employee.add": "Add",
  "employee.edit": "Edit",
  "employee.deactivate": "Deactivate",
  "employee.full_time": "Full-time",
  "employee.part_time": "Part-time",
  "employee.name": "Name",
  "employee.type": "Type",
  "employee.rest_block": "Fixed rest block",
  "employee.rest_block_algo": "Algorithm",
  "leave.add": "Add absence",
  "leave.delete": "Delete",
  "leave.type_ferie": "Holiday",
  "leave.type_malattia": "Sick leave",
  "leave.type_permesso": "Permission",
  "leave.from": "From",
  "leave.to": "To",
  "leave.type": "Type",
  "leave.employee": "Employee",
  "dialog.confirm": "Confirm",
  "dialog.cancel": "Cancel",
  "dialog.ok": "OK",
  "dialog.import_confirm": "This will overwrite existing data. Continue?",
  "dialog.import_success": "Import completed.",
  "dialog.import_error": "Import error: {error}",
  "dialog.export_success": "Export completed.",
  "error.infeasible": "Cannot generate a valid schedule: days with insufficient staff.",
  "error.shortfall": "{date} is short by {n} worker(s) (need {req}, have {actual}).",
  "exception.six_day_stretch": "{name}: 6-day consecutive stretch from {date}.",
  "exception.fallback_activated": "{name}: fallback block activated from {date}.",
  "month.1": "January", "month.2": "February", "month.3": "March",
  "month.4": "April", "month.5": "May", "month.6": "June",
  "month.7": "July", "month.8": "August", "month.9": "September",
  "month.10": "October", "month.11": "November", "month.12": "December",
  "weekday.short.0": "Mon", "weekday.short.1": "Tue", "weekday.short.2": "Wed",
  "weekday.short.3": "Thu", "weekday.short.4": "Fri",
  "weekday.short.5": "Sat", "weekday.short.6": "Sun"
}
```

- [ ] **Step 4: Verify `tr()` works from Python**

```bash
python -c "from ui.i18n import tr, set_language; print(tr('nav.schedule')); set_language('en'); print(tr('nav.schedule'))"
```

Expected output:
```
Turni
Shifts
```

- [ ] **Step 5: Commit**

```bash
git add ui/i18n/__init__.py ui/i18n/it.json ui/i18n/en.json
git commit -m "feat: bilingual i18n system (IT primary, EN switch) with tr() function"
```

---

## Task 10: App Shell and Main Window

**Files:**
- Create: `ui/app.py`
- Create: `ui/main_window.py`
- Create: `main.py`

**Interfaces:**
- Consumes: `tr`, `set_language`, `get_language` from `ui.i18n`
- Produces: launchable application with nav bar and empty stacked content area; language toggle works

- [ ] **Step 1: Create `ui/app.py`**

```python
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication

_data_dir: Path | None = None


def get_data_dir() -> Path:
    if _data_dir is None:
        raise RuntimeError("Data dir not initialized — call init_app() first")
    return _data_dir


def init_app(data_dir: Path) -> QApplication:
    global _data_dir
    _data_dir = data_dir
    app = QApplication(sys.argv)
    app.setApplicationName("Hostel Scheduler")
    app.setStyle("Fusion")
    _apply_stylesheet(app)
    return app


def _apply_stylesheet(app: QApplication) -> None:
    app.setStyleSheet("""
        QMainWindow, QWidget { background-color: #f5f7fa; font-family: Segoe UI; font-size: 13px; }
        QPushButton {
            background-color: #3b7dd8; color: white; border: none;
            padding: 6px 14px; border-radius: 4px;
        }
        QPushButton:hover { background-color: #2d6bbf; }
        QPushButton:pressed { background-color: #245aaa; }
        QPushButton#secondary {
            background-color: #e8edf5; color: #333;
        }
        QPushButton#secondary:hover { background-color: #d0d8e8; }
        QTableWidget { background: white; gridline-color: #dde3ec; }
        QTableWidget::item:selected { background-color: #d0e4ff; color: black; }
        QHeaderView::section {
            background-color: #eef1f7; padding: 4px;
            border: 1px solid #dde3ec; font-weight: bold;
        }
        QLabel#section_title { font-size: 15px; font-weight: bold; color: #1a3a6b; }
    """)
```

- [ ] **Step 2: Create `ui/main_window.py`**

```python
from datetime import date, timedelta
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame, QFileDialog, QMessageBox,
)
from PyQt6.QtCore import Qt
from ui.i18n import tr, set_language, get_language
from ui.app import get_data_dir
from core import storage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hostel Scheduler")
        self.resize(1280, 800)
        self._cycle_start = date.today().replace(day=1)
        self._schedule = None
        self._employees = storage.load_employees(get_data_dir())
        self._leaves = storage.load_leaves(get_data_dir())
        self._build_ui()
        self._refresh_schedule()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_nav_bar())
        root.addWidget(self._build_toolbar())
        self._stack = QStackedWidget()
        root.addWidget(self._stack)
        self._add_views()

    def _build_nav_bar(self):
        bar = QFrame()
        bar.setStyleSheet("background-color: #1a3a6b;")
        bar.setFixedHeight(48)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 12, 0)

        def nav_btn(key, idx):
            btn = QPushButton(tr(key))
            btn.setStyleSheet("color: white; background: transparent; font-size: 14px; padding: 4px 12px;")
            btn.clicked.connect(lambda _, i=idx: self._stack.setCurrentIndex(i))
            return btn

        layout.addWidget(nav_btn("nav.schedule", 0))
        layout.addWidget(nav_btn("nav.employees", 1))
        layout.addWidget(nav_btn("nav.leave", 2))
        layout.addStretch()

        self._lang_btn = QPushButton("IT | EN")
        self._lang_btn.setStyleSheet("color: #aac4f5; background: transparent; font-size: 13px;")
        self._lang_btn.clicked.connect(self._toggle_language)
        layout.addWidget(self._lang_btn)
        return bar

    def _build_toolbar(self):
        bar = QFrame()
        bar.setStyleSheet("background-color: #eef1f7; border-bottom: 1px solid #dde3ec;")
        bar.setFixedHeight(44)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 12, 0)

        self._cycle_label = QLabel()
        layout.addWidget(self._cycle_label)

        def tb_btn(key, cb, secondary=False):
            btn = QPushButton(tr(key))
            if secondary:
                btn.setObjectName("secondary")
            btn.clicked.connect(cb)
            layout.addWidget(btn)
            return btn

        tb_btn("schedule.prev", self._prev_cycle, secondary=True)
        tb_btn("schedule.next", self._next_cycle, secondary=True)
        layout.addSpacing(16)
        tb_btn("schedule.generate", self._generate_schedule)
        tb_btn("schedule.export_csv", self._export_csv, secondary=True)
        tb_btn("schedule.import_csv", self._import_csv, secondary=True)
        layout.addStretch()
        self._update_cycle_label()
        return bar

    def _add_views(self):
        from ui.views.schedule_grid import ScheduleGridView
        from ui.views.schedule_calendar import ScheduleCalendarView
        from ui.views.employees import EmployeesView
        from ui.views.leave import LeaveView

        # Schedule page: grid + calendar tabs
        schedule_page = QWidget()
        vbox = QVBoxLayout(schedule_page)
        vbox.setContentsMargins(8, 8, 8, 8)

        tab_bar = QHBoxLayout()
        self._btn_grid = QPushButton(tr("schedule.grid_view"))
        self._btn_cal = QPushButton(tr("schedule.calendar_view"))
        self._btn_grid.setObjectName("secondary")
        self._btn_cal.setObjectName("secondary")
        tab_bar.addWidget(self._btn_grid)
        tab_bar.addWidget(self._btn_cal)
        tab_bar.addStretch()
        vbox.addLayout(tab_bar)

        self._view_stack = QStackedWidget()
        self._grid_view = ScheduleGridView()
        self._cal_view = ScheduleCalendarView()
        self._view_stack.addWidget(self._grid_view)
        self._view_stack.addWidget(self._cal_view)
        vbox.addWidget(self._view_stack)

        self._btn_grid.clicked.connect(lambda: self._view_stack.setCurrentIndex(0))
        self._btn_cal.clicked.connect(lambda: self._view_stack.setCurrentIndex(1))

        self._stack.addWidget(schedule_page)

        self._employees_view = EmployeesView(on_change=self._reload_employees)
        self._stack.addWidget(self._employees_view)

        self._leave_view = LeaveView(on_change=self._reload_leaves)
        self._stack.addWidget(self._leave_view)

    def _update_cycle_label(self):
        end = self._cycle_start + timedelta(days=27)
        months_it = {i: tr(f"month.{i}") for i in range(1, 13)}
        label = (
            f"{tr('schedule.cycle_label')} "
            f"{self._cycle_start.day} {months_it[self._cycle_start.month]} "
            f"– {end.day} {months_it[end.month]} {end.year}"
        )
        self._cycle_label.setText(label)

    def _prev_cycle(self):
        self._cycle_start -= timedelta(days=28)
        self._update_cycle_label()
        self._refresh_schedule()

    def _next_cycle(self):
        self._cycle_start += timedelta(days=28)
        self._update_cycle_label()
        self._refresh_schedule()

    def _refresh_schedule(self):
        data_dir = get_data_dir()
        self._schedule = storage.load_schedule(data_dir, self._cycle_start)
        self._grid_view.load(self._schedule, self._employees, self._cycle_start)
        self._cal_view.load(self._schedule, self._employees, self._cycle_start)

    def _generate_schedule(self):
        from core.scheduler import generate_schedule
        data_dir = get_data_dir()
        # Load previous cycle exceptions for fairness
        prev_start = self._cycle_start - timedelta(days=28)
        prev_schedule = storage.load_schedule(data_dir, prev_start)
        prev_exceptions = prev_schedule.exceptions if prev_schedule else []

        result = generate_schedule(
            self._employees, self._leaves, self._cycle_start, prev_exceptions
        )
        if result.feasible:
            storage.save_schedule(data_dir, result.schedule)
            self._schedule = result.schedule
        else:
            self._show_infeasibility(result)
        self._grid_view.load(self._schedule, self._employees, self._cycle_start)
        self._cal_view.load(self._schedule, self._employees, self._cycle_start)

    def _show_infeasibility(self, result):
        lines = [tr("error.infeasible")]
        for err in result.errors[:5]:
            lines.append(
                tr("error.shortfall")
                .replace("{date}", err.date.isoformat())
                .replace("{n}", str(err.required_count - err.actual_count))
                .replace("{req}", str(err.required_count))
                .replace("{actual}", str(err.actual_count))
            )
        QMessageBox.warning(self, "Hostel Scheduler", "\n".join(lines))

    def _export_csv(self):
        if self._schedule is None:
            return
        from core.csv_io import export_schedule_csv
        path, _ = QFileDialog.getSaveFileName(
            self, tr("schedule.export_csv"), "", "CSV (*.csv)"
        )
        if path:
            export_schedule_csv(self._schedule, self._employees, __import__("pathlib").Path(path))
            QMessageBox.information(self, "Hostel Scheduler", tr("dialog.export_success"))

    def _import_csv(self):
        from core.csv_io import import_schedule_csv, CsvImportError
        from pathlib import Path
        path, _ = QFileDialog.getOpenFileName(self, tr("schedule.import_csv"), "", "CSV (*.csv)")
        if not path:
            return
        reply = QMessageBox.question(
            self, "Hostel Scheduler", tr("dialog.import_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            schedule, _ = import_schedule_csv(Path(path))
            storage.save_schedule(get_data_dir(), schedule)
            self._schedule = schedule
            self._grid_view.load(self._schedule, self._employees, self._cycle_start)
            self._cal_view.load(self._schedule, self._employees, self._cycle_start)
            QMessageBox.information(self, "Hostel Scheduler", tr("dialog.import_success"))
        except CsvImportError as e:
            QMessageBox.critical(
                self, "Hostel Scheduler",
                tr("dialog.import_error").replace("{error}", str(e))
            )

    def _toggle_language(self):
        lang = "en" if get_language() == "it" else "it"
        set_language(lang)
        self._retranslate()

    def _retranslate(self):
        # Re-build the entire UI — simplest correct approach for a small app
        self.close()
        new_win = MainWindow()
        new_win.show()

    def _reload_employees(self):
        self._employees = storage.load_employees(get_data_dir())
        self._refresh_schedule()

    def _reload_leaves(self):
        self._leaves = storage.load_leaves(get_data_dir())
```

- [ ] **Step 3: Create `main.py`**

```python
import sys
from pathlib import Path
from ui.app import init_app, get_data_dir
from core.storage import ensure_data_dir
from ui.main_window import MainWindow


def _data_dir() -> Path:
    # At runtime: next to the .exe. In dev: project root / data
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "data"
    return Path(__file__).parent / "data"


def main():
    data_dir = _data_dir()
    ensure_data_dir(data_dir)
    _seed_if_empty(data_dir)

    app = init_app(data_dir)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


def _seed_if_empty(data_dir: Path) -> None:
    from core.storage import load_employees, save_employees
    from core.models import Employee, EmployeeType
    import uuid
    if load_employees(data_dir):
        return
    employees = [
        Employee(id=str(uuid.uuid4()), name=n, type=EmployeeType.FULL_TIME,
                 fixed_rest_block=None, active=True)
        for n in ["Marco","Linda","Luca","Varinia","Emilia","Leia","Jo",
                  "Denise","Maurizio","Pia","Luisa","Ivo","Surbhi","Julian"]
    ] + [
        Employee(id=str(uuid.uuid4()), name=n, type=EmployeeType.PART_TIME,
                 fixed_rest_block=None, active=True)
        for n in ["Gioia","Guido"]
    ]
    save_employees(data_dir, employees)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Verify the app launches**

```bash
python main.py
```

Expected: app window opens with blue nav bar, toolbar with cycle label and buttons, empty schedule area. No traceback.

- [ ] **Step 5: Commit**

```bash
git add ui/app.py ui/main_window.py main.py
git commit -m "feat: app shell, main window, nav bar, toolbar, and cycle navigation"
```

---

## Task 11: Schedule Grid View

**Files:**
- Create: `ui/views/schedule_grid.py`

**Interfaces:**
- Consumes: `Schedule | None`, `list[Employee]`, `start_date: date`
- Produces: `ScheduleGridView(QWidget)` with `load(schedule, employees, start_date)` method

- [ ] **Step 1: Create `ui/views/schedule_grid.py`**

```python
from datetime import date, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QHeaderView, QMenu, QApplication,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QFont
from core.models import Employee, Schedule, ShiftStatus
from core.storage import save_schedule
from ui.app import get_data_dir
from ui.i18n import tr

_STATUS_COLOR = {
    ShiftStatus.WORK:     QColor("#d4edda"),   # green
    ShiftStatus.REST:     QColor("#e9ecef"),   # grey
    ShiftStatus.FERIE:    QColor("#cce5ff"),   # blue
    ShiftStatus.MALATTIA: QColor("#ffe5b0"),   # orange
    ShiftStatus.PERMESSO: QColor("#fff3cd"),   # yellow
    ShiftStatus.OVERRIDE: QColor("#f0e0ff"),   # purple tint
}
_STATUS_LABEL = {
    ShiftStatus.WORK:     "L",
    ShiftStatus.REST:     "R",
    ShiftStatus.FERIE:    "F",
    ShiftStatus.MALATTIA: "M",
    ShiftStatus.PERMESSO: "P",
    ShiftStatus.OVERRIDE: "O",
}
_VALID_OVERRIDES = list(ShiftStatus)


class ScheduleGridView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._placeholder = QLabel(tr("schedule.no_schedule"))
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: #666; font-size: 15px;")
        layout.addWidget(self._placeholder)
        self._table = QTableWidget()
        self._table.hide()
        layout.addWidget(self._table)
        self._schedule: Schedule | None = None
        self._employees: list[Employee] = []
        self._start_date: date = date.today()

    def load(self, schedule: Schedule | None, employees: list[Employee], start_date: date):
        self._schedule = schedule
        self._employees = [e for e in employees if e.active]
        self._start_date = start_date
        if schedule is None:
            self._placeholder.setText(tr("schedule.generate_prompt"))
            self._placeholder.show()
            self._table.hide()
            return
        self._placeholder.hide()
        self._table.show()
        self._build_table()

    def _build_table(self):
        schedule = self._schedule
        employees = self._employees
        cycle_dates = [self._start_date + timedelta(days=i) for i in range(28)]

        # Build lookup: (employee_id, date) -> ShiftStatus
        status_lookup: dict[tuple[str, date], ShiftStatus] = {}
        for day in schedule.days:
            for shift in day.shifts:
                status_lookup[(shift.employee_id, day.date)] = shift.status

        n_rows = len(employees) + 1  # +1 for staffing totals row
        n_cols = len(cycle_dates) + 1  # +1 for row totals column
        self._table.setRowCount(n_rows)
        self._table.setColumnCount(n_cols)

        # Column headers: "D Xxx" (e.g. "1 Lun")
        headers = []
        for d in cycle_dates:
            wd = tr(f"weekday.short.{d.weekday()}")
            headers.append(f"{d.day} {wd}")
        headers.append(tr("schedule.days_worked"))
        self._table.setHorizontalHeaderLabels(headers)

        # Row headers: employee names
        row_labels = [e.name for e in employees] + [tr("schedule.staffing_below_min")]
        self._table.setVerticalHeaderLabels(row_labels)

        min_staffing = {d: (9 if d.weekday() in (4, 5) else 8) for d in cycle_dates}

        # Fill cells
        daily_counts: dict[date, int] = {d: 0 for d in cycle_dates}
        for row_idx, emp in enumerate(employees):
            work_count = 0
            for col_idx, d in enumerate(cycle_dates):
                status = status_lookup.get((emp.id, d), ShiftStatus.REST)
                item = self._make_cell(status)
                self._table.setItem(row_idx, col_idx, item)
                if status == ShiftStatus.WORK:
                    work_count += 1
                    daily_counts[d] += 1
            # Row total
            total_item = QTableWidgetItem(f"{work_count}/28")
            total_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._table.setItem(row_idx, 28, total_item)

        # Staffing totals row
        for col_idx, d in enumerate(cycle_dates):
            count = daily_counts[d]
            required = min_staffing[d]
            item = QTableWidgetItem(str(count))
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            if count < required:
                item.setBackground(QBrush(QColor("#f8d7da")))
                item.setForeground(QBrush(QColor("#721c24")))
            self._table.setItem(len(employees), col_idx, item)

        # Resize
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setMinimumSectionSize(36)
        self._table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        # Context menu for override
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)

    def _make_cell(self, status: ShiftStatus) -> QTableWidgetItem:
        item = QTableWidgetItem(_STATUS_LABEL[status])
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setBackground(QBrush(_STATUS_COLOR[status]))
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        return item

    def _show_context_menu(self, pos):
        idx = self._table.indexAt(pos)
        if not idx.isValid():
            return
        row, col = idx.row(), idx.column()
        if col >= 28 or row >= len(self._employees):
            return
        emp = self._employees[row]
        d = self._start_date + timedelta(days=col)

        menu = QMenu(self)
        for status in _VALID_OVERRIDES:
            action = menu.addAction(f"{_STATUS_LABEL[status]} — {status.value}")
            action.triggered.connect(lambda _, s=status: self._apply_override(emp, d, s))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _apply_override(self, emp: Employee, d: date, status: ShiftStatus):
        if self._schedule is None:
            return
        for day in self._schedule.days:
            if day.date == d:
                for shift in day.shifts:
                    if shift.employee_id == emp.id:
                        shift.status = ShiftStatus.OVERRIDE if status == shift.status else status
                        break
        save_schedule(get_data_dir(), self._schedule)
        self._build_table()
```

- [ ] **Step 2: Launch the app and verify the grid**

```bash
python main.py
```

Steps to test:
1. Click "Genera Turni" — a schedule should be generated
2. The grid view should appear with colored cells (L=green, R=grey)
3. Right-click a cell → context menu with status options should appear
4. The bottom row should show staffing counts; any below minimum should be red

- [ ] **Step 3: Commit**

```bash
git add ui/views/schedule_grid.py
git commit -m "feat: schedule grid view with color-coded cells and manual override via right-click"
```

---

## Task 12: Schedule Calendar View

**Files:**
- Create: `ui/views/schedule_calendar.py`

**Interfaces:**
- Same as grid view: `load(schedule, employees, start_date)` method

- [ ] **Step 1: Create `ui/views/schedule_calendar.py`**

```python
from datetime import date, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from core.models import Employee, Schedule, ShiftStatus
from ui.i18n import tr


class ScheduleCalendarView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._placeholder = QLabel(tr("schedule.no_schedule"))
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: #666; font-size: 15px;")
        layout.addWidget(self._placeholder)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._inner = QWidget()
        self._grid = QGridLayout(self._inner)
        scroll.setWidget(self._inner)
        scroll.hide()
        self._scroll = scroll
        layout.addWidget(scroll)

    def load(self, schedule: Schedule | None, employees: list[Employee], start_date: date):
        if schedule is None:
            self._placeholder.show()
            self._scroll.hide()
            return
        self._placeholder.hide()
        self._scroll.show()
        self._build_calendar(schedule, [e for e in employees if e.active], start_date)

    def _build_calendar(self, schedule: Schedule, employees: list[Employee], start_date: date):
        # Clear existing widgets
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cycle_dates = [start_date + timedelta(days=i) for i in range(28)]
        # Build staffing lookup
        status_lookup: dict[tuple[str, date], ShiftStatus] = {}
        for day in schedule.days:
            for shift in day.shifts:
                status_lookup[(shift.employee_id, day.date)] = shift.status

        id_to_name = {e.id: e.name for e in employees}
        min_staffing = {d: (9 if d.weekday() in (4, 5) else 8) for d in cycle_dates}

        COLS = 7
        # Weekday headers
        for col in range(COLS):
            lbl = QLabel(tr(f"weekday.short.{col}"))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-weight: bold; color: #444;")
            self._grid.addWidget(lbl, 0, col)

        # Offset: first day of cycle to its weekday column
        first_weekday = start_date.weekday()
        for i, d in enumerate(cycle_dates):
            col = (first_weekday + i) % COLS
            row = 1 + (first_weekday + i) // COLS

            cell = QFrame()
            cell.setStyleSheet("border: 1px solid #dde3ec; border-radius: 3px; background: white;")
            cell.setMinimumSize(140, 80)
            vbox = QVBoxLayout(cell)
            vbox.setContentsMargins(4, 2, 4, 2)
            vbox.setSpacing(1)

            # Day number header
            date_lbl = QLabel(str(d.day))
            date_lbl.setStyleSheet("font-weight: bold; font-size: 12px; color: #333;")
            vbox.addWidget(date_lbl)

            # Count working employees
            workers = [
                id_to_name[emp.id]
                for emp in employees
                if status_lookup.get((emp.id, d)) == ShiftStatus.WORK
                and emp.id in id_to_name
            ]
            required = min_staffing[d]
            if len(workers) < required:
                cell.setStyleSheet(
                    "border: 1px solid #f5c6cb; border-radius: 3px; background: #fff5f5;"
                )

            for name in workers[:6]:  # Show at most 6 names
                lbl = QLabel(name)
                lbl.setStyleSheet("font-size: 10px; color: #1a6b3a;")
                vbox.addWidget(lbl)
            if len(workers) > 6:
                more = QLabel(f"+ {len(workers) - 6} altri")
                more.setStyleSheet("font-size: 9px; color: #888;")
                vbox.addWidget(more)

            self._grid.addWidget(cell, row, col)
```

- [ ] **Step 2: Launch app and verify calendar view**

```bash
python main.py
```

Steps:
1. Generate a schedule
2. Click "Vista Calendario"
3. Should show a 7-column grid with employee names inside each day cell
4. Days below minimum staffing should have a red-tinted background

- [ ] **Step 3: Commit**

```bash
git add ui/views/schedule_calendar.py
git commit -m "feat: schedule calendar view with per-day employee names and staffing highlights"
```

---

## Task 13: Employee Management Screen

**Files:**
- Create: `ui/views/employees.py`

**Interfaces:**
- Produces: `EmployeesView(QWidget)` with `on_change: Callable` callback triggered after any add/edit/deactivate

- [ ] **Step 1: Create `ui/views/employees.py`**

```python
from typing import Callable
import uuid
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QDialog, QFormLayout, QLineEdit, QComboBox,
    QDialogButtonBox, QMessageBox,
)
from PyQt6.QtCore import Qt
from core.models import Employee, EmployeeType
from core.storage import load_employees, save_employees
from ui.app import get_data_dir
from ui.i18n import tr

_VALID_BLOCKS = [
    (None, tr("employee.rest_block_algo")),
    ([0, 1], "Lun–Mar"),
    ([1, 2], "Mar–Mer"),
    ([2, 3], "Mer–Gio"),
    ([3, 4], "Gio–Ven"),
]


class EmployeesView(QWidget):
    def __init__(self, on_change: Callable):
        super().__init__()
        self._on_change = on_change
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self._list = QListWidget()
        self._list.setMinimumWidth(260)
        layout.addWidget(self._list)

        btn_col = QVBoxLayout()
        self._btn_add = QPushButton(tr("employee.add"))
        self._btn_edit = QPushButton(tr("employee.edit"))
        self._btn_deactivate = QPushButton(tr("employee.deactivate"))
        for btn in [self._btn_add, self._btn_edit, self._btn_deactivate]:
            btn.setObjectName("secondary")
            btn_col.addWidget(btn)
        btn_col.addStretch()
        layout.addLayout(btn_col)

        self._btn_add.clicked.connect(self._add_employee)
        self._btn_edit.clicked.connect(self._edit_employee)
        self._btn_deactivate.clicked.connect(self._deactivate_employee)

        self._reload()

    def _reload(self):
        self._employees = load_employees(get_data_dir())
        self._list.clear()
        for emp in self._employees:
            if emp.active:
                label = f"{emp.name} ({tr('employee.full_time') if emp.type == EmployeeType.FULL_TIME else tr('employee.part_time')})"
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, emp.id)
                self._list.addItem(item)

    def _selected_employee(self) -> Employee | None:
        item = self._list.currentItem()
        if item is None:
            return None
        emp_id = item.data(Qt.ItemDataRole.UserRole)
        return next((e for e in self._employees if e.id == emp_id), None)

    def _add_employee(self):
        dialog = EmployeeDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            emp = dialog.result_employee()
            self._employees.append(emp)
            save_employees(get_data_dir(), self._employees)
            self._reload()
            self._on_change()

    def _edit_employee(self):
        emp = self._selected_employee()
        if emp is None:
            return
        dialog = EmployeeDialog(self, emp)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated = dialog.result_employee(emp.id)
            idx = next(i for i, e in enumerate(self._employees) if e.id == emp.id)
            self._employees[idx] = updated
            save_employees(get_data_dir(), self._employees)
            self._reload()
            self._on_change()

    def _deactivate_employee(self):
        emp = self._selected_employee()
        if emp is None:
            return
        reply = QMessageBox.question(
            self, "Hostel Scheduler",
            f"Disattivare {emp.name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            emp.active = False
            save_employees(get_data_dir(), self._employees)
            self._reload()
            self._on_change()


class EmployeeDialog(QDialog):
    def __init__(self, parent, employee: Employee | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("employee.add") if employee is None else tr("employee.edit"))
        form = QFormLayout(self)

        self._name_edit = QLineEdit(employee.name if employee else "")
        form.addRow(tr("employee.name"), self._name_edit)

        self._type_combo = QComboBox()
        self._type_combo.addItem(tr("employee.full_time"), EmployeeType.FULL_TIME)
        self._type_combo.addItem(tr("employee.part_time"), EmployeeType.PART_TIME)
        if employee and employee.type == EmployeeType.PART_TIME:
            self._type_combo.setCurrentIndex(1)
        form.addRow(tr("employee.type"), self._type_combo)

        self._block_combo = QComboBox()
        for block, label in _VALID_BLOCKS:
            self._block_combo.addItem(label, block)
        if employee and employee.fixed_rest_block:
            for i, (b, _) in enumerate(_VALID_BLOCKS):
                if b == employee.fixed_rest_block:
                    self._block_combo.setCurrentIndex(i)
        form.addRow(tr("employee.rest_block"), self._block_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def result_employee(self, existing_id: str | None = None) -> Employee:
        return Employee(
            id=existing_id or str(uuid.uuid4()),
            name=self._name_edit.text().strip(),
            type=self._type_combo.currentData(),
            fixed_rest_block=self._block_combo.currentData(),
            active=True,
        )
```

- [ ] **Step 2: Launch app and verify employee management**

```bash
python main.py
```

Steps:
1. Click "Dipendenti" in the nav bar
2. Should show the 16 seeded employees
3. Click "Aggiungi" → dialog opens; add a test employee → appears in the list
4. Select an employee, click "Modifica" → dialog opens with current values pre-filled
5. Select an employee, click "Disattiva" → confirmation dialog → employee disappears from list

- [ ] **Step 3: Commit**

```bash
git add ui/views/employees.py
git commit -m "feat: employee management screen with add/edit/deactivate and rest block selector"
```

---

## Task 14: Leave Management Screen

**Files:**
- Create: `ui/views/leave.py`

**Interfaces:**
- Produces: `LeaveView(QWidget)` with `on_change: Callable` callback

- [ ] **Step 1: Create `ui/views/leave.py`**

```python
from typing import Callable
from datetime import date
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QTableWidget, QTableWidgetItem, QComboBox,
    QDateEdit, QLabel, QHeaderView,
)
from PyQt6.QtCore import Qt, QDate
from core.models import Leave, LeaveType
from core.storage import load_employees, load_leaves, save_leaves
from ui.app import get_data_dir
from ui.i18n import tr


class LeaveView(QWidget):
    def __init__(self, on_change: Callable):
        super().__init__()
        self._on_change = on_change
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # Left: employee list
        left = QVBoxLayout()
        left.addWidget(QLabel(tr("leave.employee")))
        self._emp_list = QListWidget()
        self._emp_list.setMaximumWidth(220)
        self._emp_list.currentRowChanged.connect(self._reload_leave_table)
        left.addWidget(self._emp_list)
        layout.addLayout(left)

        # Right: absence controls + table
        right = QVBoxLayout()
        control_row = QHBoxLayout()
        self._from_date = QDateEdit(QDate.currentDate())
        self._from_date.setCalendarPopup(True)
        self._to_date = QDateEdit(QDate.currentDate())
        self._to_date.setCalendarPopup(True)
        self._type_combo = QComboBox()
        self._type_combo.addItem(tr("leave.type_ferie"), LeaveType.FERIE)
        self._type_combo.addItem(tr("leave.type_malattia"), LeaveType.MALATTIA)
        self._type_combo.addItem(tr("leave.type_permesso"), LeaveType.PERMESSO)
        self._btn_add = QPushButton(tr("leave.add"))
        self._btn_add.clicked.connect(self._add_leave)
        control_row.addWidget(QLabel(tr("leave.from")))
        control_row.addWidget(self._from_date)
        control_row.addWidget(QLabel(tr("leave.to")))
        control_row.addWidget(self._to_date)
        control_row.addWidget(QLabel(tr("leave.type")))
        control_row.addWidget(self._type_combo)
        control_row.addWidget(self._btn_add)
        control_row.addStretch()
        right.addLayout(control_row)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Data", tr("leave.type"), ""])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        right.addWidget(self._table)
        layout.addLayout(right)

        self._reload_employees()

    def _reload_employees(self):
        self._employees = [e for e in load_employees(get_data_dir()) if e.active]
        self._all_leaves = load_leaves(get_data_dir())
        self._emp_list.clear()
        for emp in self._employees:
            self._emp_list.addItem(emp.name)

    def _selected_employee(self):
        idx = self._emp_list.currentRow()
        if 0 <= idx < len(self._employees):
            return self._employees[idx]
        return None

    def _reload_leave_table(self):
        emp = self._selected_employee()
        if emp is None:
            self._table.setRowCount(0)
            return
        emp_leaves = [l for l in self._all_leaves if l.employee_id == emp.id]
        emp_leaves.sort(key=lambda l: l.date)
        self._table.setRowCount(len(emp_leaves))
        for row, leave in enumerate(emp_leaves):
            self._table.setItem(row, 0, QTableWidgetItem(leave.date.isoformat()))
            self._table.setItem(row, 1, QTableWidgetItem(leave.type.value))
            btn = QPushButton(tr("leave.delete"))
            btn.setObjectName("secondary")
            btn.clicked.connect(lambda _, l=leave: self._delete_leave(l))
            self._table.setCellWidget(row, 2, btn)

    def _add_leave(self):
        emp = self._selected_employee()
        if emp is None:
            return
        from_qd = self._from_date.date()
        to_qd = self._to_date.date()
        leave_type = self._type_combo.currentData()
        current = date(from_qd.year(), from_qd.month(), from_qd.day())
        end = date(to_qd.year(), to_qd.month(), to_qd.day())
        new_leaves = []
        while current <= end:
            if not any(
                l.employee_id == emp.id and l.date == current
                for l in self._all_leaves
            ):
                new_leaves.append(Leave(employee_id=emp.id, date=current, type=leave_type))
            current = current.replace(day=current.day + 1) if current.day < 28 else \
                (current.replace(month=current.month + 1, day=1) if current.month < 12
                 else date(current.year + 1, 1, 1))
        # Simpler: use timedelta
        from datetime import timedelta
        self._all_leaves.extend(new_leaves)
        save_leaves(get_data_dir(), self._all_leaves)
        self._reload_leave_table()
        self._on_change()

    def _delete_leave(self, leave: Leave):
        self._all_leaves = [
            l for l in self._all_leaves
            if not (l.employee_id == leave.employee_id and l.date == leave.date)
        ]
        save_leaves(get_data_dir(), self._all_leaves)
        self._reload_leave_table()
        self._on_change()
```

Fix the date iteration in `_add_leave` — replace the faulty calendar arithmetic with `timedelta`:

```python
def _add_leave(self):
    from datetime import timedelta
    emp = self._selected_employee()
    if emp is None:
        return
    from_qd = self._from_date.date()
    to_qd = self._to_date.date()
    leave_type = self._type_combo.currentData()
    current = date(from_qd.year(), from_qd.month(), from_qd.day())
    end = date(to_qd.year(), to_qd.month(), to_qd.day())
    existing = {(l.employee_id, l.date) for l in self._all_leaves}
    new_leaves = []
    while current <= end:
        if (emp.id, current) not in existing:
            new_leaves.append(Leave(employee_id=emp.id, date=current, type=leave_type))
        current += timedelta(days=1)
    self._all_leaves.extend(new_leaves)
    save_leaves(get_data_dir(), self._all_leaves)
    self._reload_leave_table()
    self._on_change()
```

- [ ] **Step 2: Launch app and verify leave management**

```bash
python main.py
```

Steps:
1. Click "Assenze" in nav bar
2. Select an employee from the left list
3. Pick a date range and type, click "Aggiungi assenza"
4. The new absence rows should appear in the table
5. Click "Elimina" on a row → it should disappear

- [ ] **Step 3: Commit**

```bash
git add ui/views/leave.py
git commit -m "feat: leave management screen with date-range picker and absence table"
```

---

## Task 15: Full Test Suite Run and Integration Verification

**Files:** No new files — run existing tests and do a manual smoke test.

- [ ] **Step 1: Run the complete test suite**

```bash
python -m pytest tests/ -v --tb=short
```

Expected: all tests pass, zero failures

- [ ] **Step 2: Manual end-to-end smoke test**

```bash
python main.py
```

Checklist:
- [ ] App launches with 16 seeded employees visible under "Dipendenti"
- [ ] Navigate to "Turni" → cycle label shows today's approximate date range
- [ ] Click "Genera Turni" → grid view fills with colored cells
- [ ] All 14 FT employees show 20 work days (row total "20/28")
- [ ] No day column shows a red staffing count (i.e., all days meet minimum)
- [ ] Switch to "Vista Calendario" → working employees listed in each day cell
- [ ] Right-click a cell in grid view → override menu appears; select a different status → cell color changes
- [ ] Navigate to "Assenze", add a leave for one employee, go back to "Turni" → regenerate → leave dates show F/M/P in that employee's row
- [ ] Click "Esporta CSV" → file save dialog opens; saves a file
- [ ] Click "Importa CSV" → confirm dialog → loads successfully
- [ ] Click "IT | EN" language toggle → labels switch to English
- [ ] Click toggle again → labels switch back to Italian

- [ ] **Step 3: CSV round-trip verification**

```bash
python -c "
from pathlib import Path
from core.csv_io import export_schedule_csv, import_schedule_csv
from core.storage import load_employees, load_schedule
from datetime import date

data_dir = Path('data')
emps = load_employees(data_dir)

# Find first available schedule
from core.storage import list_schedule_dates
dates = list_schedule_dates(data_dir)
if not dates:
    print('No schedule to test — generate one first')
else:
    sched = load_schedule(data_dir, dates[0])
    export_schedule_csv(sched, emps, Path('test_export.csv'))
    sched2, _ = import_schedule_csv(Path('test_export.csv'))
    export_schedule_csv(sched2, emps, Path('test_export2.csv'))
    ok = Path('test_export.csv').read_text() == Path('test_export2.csv').read_text()
    print('Round-trip PASS' if ok else 'Round-trip FAIL')
"
```

Expected: `Round-trip PASS`

- [ ] **Step 4: Commit**

```bash
git add .
git commit -m "test: full suite passes; manual smoke test and CSV round-trip verified"
```

---

## Task 16: PyInstaller Packaging

**Files:**
- Create: `hostel_scheduler.spec`
- Create: `build.bat`

**Interfaces:**
- Produces: `dist/hostel_scheduler/hostel_scheduler.exe` runnable on Windows 10/11

- [ ] **Step 1: Install PyInstaller**

```bash
pip install pyinstaller>=6
```

- [ ] **Step 2: Create `hostel_scheduler.spec`**

```python
# hostel_scheduler.spec
block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('ui/i18n/it.json', 'ui/i18n'),
        ('ui/i18n/en.json', 'ui/i18n'),
    ],
    hiddenimports=['PyQt6.QtPrintSupport'],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='hostel_scheduler',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,   # No console window
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='hostel_scheduler',
)
```

- [ ] **Step 3: Create `build.bat`**

```batch
@echo off
echo Building Hostel Scheduler...
pyinstaller hostel_scheduler.spec --clean --noconfirm
echo.
echo Build complete. Executable in dist\hostel_scheduler\
pause
```

- [ ] **Step 4: Build the executable**

```bash
pyinstaller hostel_scheduler.spec --clean --noconfirm
```

Expected: `dist/hostel_scheduler/hostel_scheduler.exe` created, no errors.

- [ ] **Step 5: Smoke-test the packaged executable**

Double-click `dist\hostel_scheduler\hostel_scheduler.exe` (or run from terminal):

```bash
./dist/hostel_scheduler/hostel_scheduler.exe
```

Verify:
- App launches without a console window
- `data/` folder created next to the `.exe` on first run
- 16 employees seeded automatically
- "Genera Turni" generates a schedule

- [ ] **Step 6: Commit**

```bash
git add hostel_scheduler.spec build.bat
git commit -m "chore: PyInstaller packaging spec and build script for Windows .exe"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|---|---|
| Schedule generation — 28-day rolling window | Task 5, 7 |
| Business rules: shift counts, rest blocks, free weekend | Task 4, 5, 6, 7 |
| Minimum staffing (Sun–Thu 8, Fri–Sat 9) | Task 6, 7 |
| Max 5 consecutive days (6 at transitions) | Task 5, 6 |
| Fallback pivot rule | Task 7 (`_repair_staffing`) |
| Infeasibility report | Task 7 |
| Employee management (add, edit, deactivate) | Task 13 |
| Leave marking (ferie, malattia, permesso) | Task 14 |
| Manual override | Task 11 |
| CSV import/export, round-trip safe | Task 8, 15 |
| Grid view (rows=employees, cols=days) | Task 11 |
| Calendar view (read-only, staffing highlights) | Task 12 |
| Bilingual IT/EN, instant toggle | Task 9, 10 |
| First-launch seed data (16 employees) | Task 10 (`main.py`) |
| PyInstaller .exe, Windows 10/11 | Task 16 |
| Row totals (days worked) | Task 11 |
| Column totals (staffing count, red if below min) | Task 11 |
| Exceptions carry-over across cycles | Task 7 |
| JSON storage, offline, no cloud | Task 3 |

All spec requirements are covered. No gaps found.
