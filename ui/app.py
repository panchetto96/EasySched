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
        QMainWindow { background-color: #FAF7F2; }
        QWidget {
            background-color: #FAF7F2;
            color: #1C140D;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 13px;
        }

        /* ── Primary button (terracotta) ── */
        QPushButton {
            background-color: #C2410C;
            color: #ffffff;
            border: none;
            padding: 7px 18px;
            border-radius: 6px;
            font-weight: 600;
            letter-spacing: 0.3px;
        }
        QPushButton:hover  { background-color: #9A3412; }
        QPushButton:pressed { background-color: #7C2D12; }

        /* ── Secondary button ── */
        QPushButton#secondary {
            background-color: #ffffff;
            color: #3D2B1F;
            border: 1.5px solid #C8B8A8;
        }
        QPushButton#secondary:hover  { background-color: #FAF7F2; border-color: #A08C7A; }
        QPushButton#secondary:pressed { background-color: #F0E8DF; }

        /* ── Table ── */
        QTableWidget {
            background: #ffffff;
            color: #1C140D;
            gridline-color: #D6CBC0;
            border: 1px solid #D6CBC0;
            border-radius: 6px;
        }
        QTableWidget::item { padding: 2px; }
        QTableWidget::item:selected { background-color: #FED7AA; color: #1C140D; }
        QHeaderView::section {
            background-color: #292217;
            color: #F5EDE3;
            padding: 6px 4px;
            border: none;
            font-weight: 700;
            font-size: 11px;
            letter-spacing: 0.5px;
        }

        /* ── List widget ── */
        QListWidget {
            background: #ffffff;
            color: #1C140D;
            border: 1px solid #D6CBC0;
            border-radius: 6px;
        }
        QListWidget::item { padding: 5px 8px; }
        QListWidget::item:selected { background-color: #FED7AA; color: #1C140D; }

        /* ── Form inputs ── */
        QLineEdit, QComboBox, QDateEdit, QSpinBox {
            background: #ffffff;
            color: #1C140D;
            border: 1.5px solid #C8B8A8;
            border-radius: 5px;
            padding: 5px 8px;
            selection-background-color: #FED7AA;
        }
        QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
            border-color: #C2410C;
        }
        QComboBox::drop-down { border: none; width: 20px; }

        /* ── Labels ── */
        QLabel { color: #1C140D; background-color: transparent; }
        QLabel#section_title { font-size: 16px; font-weight: 700; color: #9A3412; }

        /* ── Scroll areas ── */
        QScrollArea { background: #FAF7F2; border: none; }

        /* ── Dialog ── */
        QDialog { background-color: #ffffff; }
        QDialog QWidget { background-color: #ffffff; }
        QDialogButtonBox QPushButton { min-width: 80px; }

        /* ── Message box ── */
        QMessageBox { background-color: #ffffff; }
        QMessageBox QLabel { color: #1C140D; }
    """)
