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
