"""PySide6 桌面主窗口无头启动与页面交互测试。"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.desktop.main_window import MainWindow, build_services


def test_desktop_window_startup_and_pages(tmp_path: Path) -> None:
    cfg_file = tmp_path / "test_config.yaml"
    db_file = tmp_path / "ui.db"
    cfg_file.write_text(
        f"""
app:
  name: "WE-Learn-Assistant"
database:
  path: "{db_file.as_posix()}"
web:
  browser: "msedge"
  headless: true
android:
  adb_path: "adb"
""",
        encoding="utf-8",
    )

    app = QApplication.instance() or QApplication([])
    services = build_services(cfg_file)
    window = MainWindow(services)

    assert window.nav_list.count() == 5
    assert window.pages.count() == 5

    # 在课程页面添加一门课程并验证持久化和任务下拉框联动
    window.course_page.title_input.setText("UI 集成测试课程")
    window.course_page.code_input.setText("UI101")
    window.course_page._handle_add_course()
    assert window.course_page.table.rowCount() == 1
    assert window.task_page.course_combo.count() == 1

    # 在任务页面创建任务并验证日志页面刷新
    window.task_page.task_title_input.setText("UI 测试任务")
    window.task_page._handle_create_task()
    assert window.task_page.table.rowCount() == 1
    assert window.logs_page.table.rowCount() >= 2

    # 切换所有页面确保无异常
    for idx in range(window.nav_list.count()):
        window.nav_list.setCurrentRow(idx)
        assert window.pages.currentIndex() == idx

    app.processEvents()
    window.close()
    services.db.close()
