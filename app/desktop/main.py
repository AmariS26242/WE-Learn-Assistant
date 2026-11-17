"""桌面应用启动入口。"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.desktop.main_window import MainWindow, build_services


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    services = build_services()
    window = MainWindow(services)
    window.show()
    try:
        return app.exec()
    finally:
        services.edge_adapter.close()
        services.db.close()


if __name__ == "__main__":
    raise SystemExit(main())
