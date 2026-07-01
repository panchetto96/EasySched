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
