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

    # Also build name-based lookup for imported schedules
    name_to_status: dict[tuple[str, str], str] = {}
    for day in schedule.days:
        for shift in day.shifts:
            # Extract name from employee_id if it starts with "imported_"
            if shift.employee_id.startswith("imported_"):
                name = shift.employee_id.replace("imported_", "", 1)
                name_to_status[(name, day.date.isoformat())] = _STATUS_CODE[shift.status]

    with filepath.open("w", newline="", encoding="utf-8") as f:
        f.write(f"# start_date={schedule.start_date.isoformat()},generated_at={schedule.generated_at}\n")
        writer = csv.writer(f)
        writer.writerow(["employee"] + date_cols)
        for emp in employees:
            row = [emp.name] + [
                status_lookup.get((emp.id, d), name_to_status.get((emp.name, d), "R"))
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
