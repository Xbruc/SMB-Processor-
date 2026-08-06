from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .ui.main_window import create_window


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("SMB Processor")
    window = create_window()
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
