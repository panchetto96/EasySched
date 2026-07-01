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
        QMainWindow { background-color: #f1f5f9; }
        QWidget {
            background-color: #f1f5f9;
            color: #0f172a;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 13px;
        }

        /* ── Primary button ── */
        QPushButton {
            background-color: #1d4ed8;
            color: #ffffff;
            border: none;
            padding: 7px 18px;
            border-radius: 6px;
            font-weight: 600;
            letter-spacing: 0.3px;
        }
        QPushButton:hover  { background-color: #2563eb; }
        QPushButton:pressed { background-color: #1e3a8a; }

        /* ── Secondary button ── */
        QPushButton#secondary {
            background-color: #ffffff;
            color: #334155;
            border: 1.5px solid #cbd5e1;
        }
        QPushButton#secondary:hover  { background-color: #f8fafc; border-color: #94a3b8; }
        QPushButton#secondary:pressed { background-color: #e2e8f0; }

        /* ── Table ── */
        QTableWidget {
            background: #ffffff;
            color: #0f172a;
            gridline-color: #e2e8f0;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
        }
        QTableWidget::item { padding: 2px; }
        QTableWidget::item:selected { background-color: #bfdbfe; color: #0f172a; }
        QHeaderView::section {
            background-color: #1e293b;
            color: #f8fafc;
            padding: 6px 4px;
            border: none;
            font-weight: 700;
            font-size: 11px;
            letter-spacing: 0.5px;
        }

        /* ── List widget ── */
        QListWidget {
            background: #ffffff;
            color: #0f172a;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
        }
        QListWidget::item { padding: 5px 8px; }
        QListWidget::item:selected { background-color: #bfdbfe; color: #0f172a; }

        /* ── Form inputs ── */
        QLineEdit, QComboBox, QDateEdit, QSpinBox {
            background: #ffffff;
            color: #0f172a;
            border: 1.5px solid #cbd5e1;
            border-radius: 5px;
            padding: 5px 8px;
            selection-background-color: #bfdbfe;
        }
        QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
            border-color: #3b82f6;
        }
        QComboBox::drop-down { border: none; width: 20px; }

        /* ── Labels ── */
        QLabel { color: #0f172a; background-color: transparent; }
        QLabel#section_title { font-size: 16px; font-weight: 700; color: #1d4ed8; }

        /* ── Scroll areas ── */
        QScrollArea { background: #f1f5f9; border: none; }

        /* ── Dialog ── */
        QDialog { background-color: #ffffff; }
        QDialog QWidget { background-color: #ffffff; }
        QDialogButtonBox QPushButton { min-width: 80px; }

        /* ── Message box ── */
        QMessageBox { background-color: #ffffff; }
        QMessageBox QLabel { color: #0f172a; }
    """)
