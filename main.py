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
