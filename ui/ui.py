"""Entry helper for launching the PySide6 graphical interface."""

from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QApplication

from ui.app_window import ConnectFourWindow


def run_gui(argv: Optional[list[str]] = None) -> int:
    """Create the Qt application, show the main window, and enter the event loop."""
    fmt = QSurfaceFormat()
    fmt.setSamples(4)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("Connect 4: vs The Devils")

    window = ConnectFourWindow()
    window.show()
    return app.exec()
