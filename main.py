"""Точка входа."""
from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from src.app import MainWindow, STYLESHEET


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("YouTube Downloader")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
