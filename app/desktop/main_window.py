"""PySide6 桌面主窗口与五大功能页面实现。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from adapters.android.adb_adapter import AdbAdapter
from adapters.web.edge_adapter import EdgeAdapter
from core.config import AppConfig, load_config
from core.course.service import CourseService
from core.logging_utils import mask_sensitive_text
from core.storage.database import DatabaseManager
from core.storage.models import OperationLog, TaskStatus
from core.storage.repositories import (
    ChapterRepository,
    CourseRepository,
    OperationLogRepository,
    TaskRepository,
)
from core.task.manager import InvalidTaskTransitionError, TaskManager


@dataclass(slots=True)
class AppServices:
    """桌面端聚合依赖容器。"""

    config: AppConfig
    db: DatabaseManager
    course_service: CourseService
    task_manager: TaskManager
    log_repo: OperationLogRepository
    edge_adapter: EdgeAdapter
    adb_adapter: AdbAdapter


def build_services(config_path: str | Path | None = None) -> AppServices:
    """初始化配置、SQLite 数据库与各适配器服务。"""
    config = load_config(config_path)
    db = DatabaseManager(config.db_path)
    db.initialize()

    course_repo = CourseRepository(db)
    chapter_repo = ChapterRepository(db)
    task_repo = TaskRepository(db)
    log_repo = OperationLogRepository(db)

    course_service = CourseService(course_repo, chapter_repo, log_repo=log_repo)
    task_manager = TaskManager(task_repo, log_repo)
    recovered = task_manager.recover_on_startup()
    if recovered:
        log_repo.create(
            OperationLog(
                actor="desktop_startup",
                action="startup.recover",
                level="WARNING",
                message=f"启动时恢复了 {len(recovered)} 个未完成任务",
            ),
            details={"recovered_task_ids": recovered},
        )

    return AppServices(
        config=config,
        db=db,
        course_service=course_service,
        task_manager=task_manager,
        log_repo=log_repo,
        edge_adapter=EdgeAdapter(config.web),
        adb_adapter=AdbAdapter(config.android),
    )


class CoursePage(QWidget):
    """课程管理页面。"""

    def __init__(self, services: AppServices, on_data_changed: callable) -> None:
        super().__init__()
        self.services = services
        self.on_data_changed = on_data_changed

        layout = QVBoxLayout(self)

        form_group = QGroupBox("新增课程")
        form_layout = QHBoxLayout(form_group)
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("课程名称（如：全新版大学进阶英语）")
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("课程编号（可选）")
        self.add_btn = QPushButton("添加课程")
        self.add_btn.clicked.connect(self._handle_add_course)
        self.delete_btn = QPushButton("删除选中课程")
        self.delete_btn.clicked.connect(self._handle_delete_course)
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh)

        form_layout.addWidget(self.title_input, 3)
        form_layout.addWidget(self.code_input, 2)
        form_layout.addWidget(self.add_btn)
        form_layout.addWidget(self.delete_btn)
        form_layout.addWidget(self.refresh_btn)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "课程名称", "编号", "平台", "更新时间"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        layout.addWidget(form_group)
        layout.addWidget(self.table)
        self.refresh()

    def refresh(self) -> None:
        courses = self.services.course_service.list_courses()
        self.table.setRowCount(len(courses))
        for row, course in enumerate(courses):
            self.table.setItem(row, 0, QTableWidgetItem(str(course.id or "")))
            self.table.setItem(row, 1, QTableWidgetItem(course.title))
            self.table.setItem(row, 2, QTableWidgetItem(course.code))
            self.table.setItem(row, 3, QTableWidgetItem(course.platform))
            self.table.setItem(row, 4, QTableWidgetItem(course.updated_at))

    def _handle_add_course(self) -> None:
        title = self.title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "提示", "请输入课程名称")
            return
        self.services.course_service.create_course(title, code=self.code_input.text().strip())
        self.title_input.clear()
        self.code_input.clear()
        self.refresh()
        self.on_data_changed()

    def _handle_delete_course(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选中一条课程记录")
            return
        course_id_item = self.table.item(row, 0)
        if course_id_item is None or not course_id_item.text():
            return
        self.services.course_service.delete_course(int(course_id_item.text()))
        self.refresh()
        self.on_data_changed()


class TaskPage(QWidget):
    """任务管理页面。"""

    def __init__(self, services: AppServices, on_data_changed: callable) -> None:
        super().__init__()
        self.services = services
        self.on_data_changed = on_data_changed

        layout = QVBoxLayout(self)

        create_group = QGroupBox("创建学习辅助任务")
        create_layout = QHBoxLayout(create_group)
        self.course_combo = QComboBox()
        self.task_title_input = QLineEdit()
        self.task_title_input.setPlaceholderText("任务名称（如：Unit 1 词汇整理）")
        self.task_type_combo = QComboBox()
        self.task_type_combo.addItems(["listening", "reading", "speaking", "writing", "vocabulary", "general"])
        self.create_btn = QPushButton("新建任务")
        self.create_btn.clicked.connect(self._handle_create_task)

        create_layout.addWidget(QLabel("课程:"))
        create_layout.addWidget(self.course_combo, 2)
        create_layout.addWidget(self.task_title_input, 3)
        create_layout.addWidget(self.task_type_combo, 1)
        create_layout.addWidget(self.create_btn)

        action_layout = QHBoxLayout()
        self.target_status_combo = QComboBox()
        for status in TaskStatus:
            self.target_status_combo.addItem(status.value, status)
        self.transition_btn = QPushButton("变更选中任务状态")
        self.transition_btn.clicked.connect(self._handle_transition)
        self.recover_btn = QPushButton("恢复中断任务")
        self.recover_btn.clicked.connect(self._handle_recover)
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh)

        action_layout.addWidget(QLabel("目标状态:"))
        action_layout.addWidget(self.target_status_combo)
        action_layout.addWidget(self.transition_btn)
        action_layout.addWidget(self.recover_btn)
        action_layout.addStretch(1)
        action_layout.addWidget(self.refresh_btn)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "课程ID", "任务名称", "类型", "状态", "错误信息"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        layout.addWidget(create_group)
        layout.addLayout(action_layout)
        layout.addWidget(self.table)
        self.refresh()

    def refresh(self) -> None:
        current_course_id = self.course_combo.currentData()
        self.course_combo.clear()
        courses = self.services.course_service.list_courses()
        for course in courses:
            self.course_combo.addItem(f"{course.id}: {course.title}", course.id)
        if current_course_id is not None:
            idx = self.course_combo.findData(current_course_id)
            if idx >= 0:
                self.course_combo.setCurrentIndex(idx)

        tasks = self.services.task_manager.list_tasks()
        self.table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            self.table.setItem(row, 0, QTableWidgetItem(str(task.id or "")))
            self.table.setItem(row, 1, QTableWidgetItem(str(task.course_id)))
            self.table.setItem(row, 2, QTableWidgetItem(task.title))
            self.table.setItem(row, 3, QTableWidgetItem(task.task_type))
            self.table.setItem(row, 4, QTableWidgetItem(task.status.value))
            self.table.setItem(row, 5, QTableWidgetItem(task.error_message))

    def _handle_create_task(self) -> None:
        course_id = self.course_combo.currentData()
        if course_id is None:
            QMessageBox.warning(self, "提示", "请先在课程管理页面添加课程")
            return
        title = self.task_title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "提示", "请输入任务名称")
            return
        self.services.task_manager.create_task(
            int(course_id),
            title,
            task_type=self.task_type_combo.currentText(),
            actor="desktop_ui",
        )
        self.task_title_input.clear()
        self.refresh()
        self.on_data_changed()

    def _handle_transition(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选中一条任务")
            return
        task_id = int(self.table.item(row, 0).text())
        target_status: TaskStatus = self.target_status_combo.currentData()
        try:
            self.services.task_manager.transition(
                task_id,
                target_status,
                actor="desktop_ui",
                reason="桌面端手动状态变更",
            )
        except InvalidTaskTransitionError as exc:
            QMessageBox.warning(self, "状态流转受限", str(exc))
            return
        self.refresh()
        self.on_data_changed()

    def _handle_recover(self) -> None:
        recovered = self.services.task_manager.recover_on_startup(actor="desktop_ui")
        QMessageBox.information(self, "异常恢复", f"已恢复 {len(recovered)} 条中断任务为 pending")
        self.refresh()
        self.on_data_changed()


class DeviceStatusPage(QWidget):
    """设备与浏览器状态诊断页面。"""

    def __init__(self, services: AppServices, on_data_changed: callable) -> None:
        super().__init__()
        self.services = services
        self.on_data_changed = on_data_changed

        layout = QVBoxLayout(self)
        btn_layout = QHBoxLayout()

        self.check_edge_btn = QPushButton("检测 Microsoft Edge")
        self.check_edge_btn.clicked.connect(self._check_edge)
        self.check_adb_btn = QPushButton("检测 Android ADB 设备")
        self.check_adb_btn.clicked.connect(self._check_adb)

        btn_layout.addWidget(self.check_edge_btn)
        btn_layout.addWidget(self.check_adb_btn)
        btn_layout.addStretch(1)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("点击上方按钮执行本机 Edge 与 Android ADB 诊断...")

        layout.addLayout(btn_layout)
        layout.addWidget(self.output)

    def _check_edge(self) -> None:
        check = self.services.edge_adapter.check_edge_installed()
        text = json.dumps(check.to_dict(), ensure_ascii=False, indent=2)
        self.output.setPlainText(mask_sensitive_text(text))
        self.services.log_repo.create(
            OperationLog(
                actor="device_page",
                action="edge.check",
                level="INFO" if check.available else "WARNING",
                message=f"Edge 检测结果: available={check.available}",
            ),
            details=check.to_dict(),
        )
        self.on_data_changed()

    def _check_adb(self) -> None:
        report = self.services.adb_adapter.run_diagnostics()
        text = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
        self.output.setPlainText(mask_sensitive_text(text))
        self.services.log_repo.create(
            OperationLog(
                actor="device_page",
                action="adb.diagnostics",
                level="INFO" if report.adb_installed else "WARNING",
                message=f"ADB 诊断完成: installed={report.adb_installed}, devices={report.connected_count}",
            ),
            details=report.to_dict(),
        )
        self.on_data_changed()


class LogsPage(QWidget):
    """测试与操作日志页面。"""

    def __init__(self, services: AppServices) -> None:
        super().__init__()
        self.services = services

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.level_combo = QComboBox()
        self.level_combo.addItems(["ALL", "INFO", "WARNING", "ERROR"])
        self.level_combo.currentTextChanged.connect(self.refresh)
        self.refresh_btn = QPushButton("刷新日志")
        self.refresh_btn.clicked.connect(self.refresh)

        top.addWidget(QLabel("日志级别:"))
        top.addWidget(self.level_combo)
        top.addStretch(1)
        top.addWidget(self.refresh_btn)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "时间", "级别", "动作", "脱敏消息"])
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        layout.addLayout(top)
        layout.addWidget(self.table)
        self.refresh()

    def refresh(self) -> None:
        selected = self.level_combo.currentText()
        level = None if selected == "ALL" else selected
        logs = self.services.log_repo.list_recent(limit=200, level=level)
        self.table.setRowCount(len(logs))
        for row, log in enumerate(logs):
            self.table.setItem(row, 0, QTableWidgetItem(str(log.id or "")))
            self.table.setItem(row, 1, QTableWidgetItem(log.created_at))
            self.table.setItem(row, 2, QTableWidgetItem(log.level))
            self.table.setItem(row, 3, QTableWidgetItem(log.action))
            self.table.setItem(row, 4, QTableWidgetItem(log.message))


class SettingsPage(QWidget):
    """非敏感本地设置页面。"""

    def __init__(self, services: AppServices, on_data_changed: callable) -> None:
        super().__init__()
        self.services = services
        self.on_data_changed = on_data_changed

        layout = QVBoxLayout(self)
        notice = QLabel("安全规范：本页面仅保存非敏感路径与连接参数，严禁输入或保存账号密码、Cookie 或 Token。")
        notice.setWordWrap(True)

        form = QFormLayout()
        self.db_path_input = QLineEdit(services.config.db_path)
        self.target_url_input = QLineEdit(services.config.web.target_url)
        self.cdp_endpoint_input = QLineEdit(services.config.web.cdp_endpoint)
        self.adb_path_input = QLineEdit(services.config.android.adb_path)
        self.headless_checkbox = QCheckBox("无头模式运行 Edge（调试用）")
        self.headless_checkbox.setChecked(services.config.web.headless)

        form.addRow("SQLite 数据库路径:", self.db_path_input)
        form.addRow("WE Learn 目标 URL:", self.target_url_input)
        form.addRow("Edge CDP 调试地址:", self.cdp_endpoint_input)
        form.addRow("ADB 可执行路径:", self.adb_path_input)
        form.addRow("", self.headless_checkbox)

        self.save_btn = QPushButton("保存配置到 config/config.yaml")
        self.save_btn.clicked.connect(self._save_local_config)

        layout.addWidget(notice)
        layout.addLayout(form)
        layout.addWidget(self.save_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)

    def _save_local_config(self) -> None:
        payload = {
            "app": {
                "name": self.services.config.name,
                "log_level": self.services.config.log_level,
                "data_dir": self.services.config.data_dir,
                "screenshot_dir": self.services.config.screenshot_dir,
            },
            "database": {
                "path": self.db_path_input.text().strip() or "data/we_learn_assistant.db",
            },
            "web": {
                "browser": self.services.config.web.browser,
                "headless": self.headless_checkbox.isChecked(),
                "timeout_ms": self.services.config.web.timeout_ms,
                "cdp_endpoint": self.cdp_endpoint_input.text().strip(),
                "target_url": self.target_url_input.text().strip(),
            },
            "android": {
                "adb_path": self.adb_path_input.text().strip() or "adb",
                "command_timeout_sec": self.services.config.android.command_timeout_sec,
            },
            "safety": {
                "mask_logs": True,
                "allow_credential_autofill": False,
            },
        }
        config_file = Path("config/config.yaml")
        config_file.parent.mkdir(parents=True, exist_ok=True)
        with config_file.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(payload, fh, allow_unicode=True, sort_keys=False)

        self.services.log_repo.create(
            OperationLog(
                actor="settings_page",
                action="settings.save",
                level="INFO",
                message="已保存非敏感本地配置到 config/config.yaml",
            )
        )
        self.on_data_changed()
        QMessageBox.information(self, "保存成功", "配置已写入 config/config.yaml（本地文件已被 .gitignore 忽略）")


class MainWindow(QMainWindow):
    """WE-Learn-Assistant 主窗口。"""

    def __init__(self, services: AppServices) -> None:
        super().__init__()
        self.services = services
        self.setWindowTitle("WE-Learn-Assistant（第一阶段基础控制台）")
        self.resize(1024, 660)

        root = QWidget()
        root_layout = QHBoxLayout(root)

        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(180)
        for label in ("课程管理", "任务管理", "设备状态", "测试日志", "设置"):
            self.nav_list.addItem(QListWidgetItem(label))

        self.pages = QStackedWidget()
        self.logs_page = LogsPage(services)
        self.course_page = CoursePage(services, on_data_changed=self._refresh_all_views)
        self.task_page = TaskPage(services, on_data_changed=self._refresh_all_views)
        self.device_page = DeviceStatusPage(services, on_data_changed=self._refresh_all_views)
        self.settings_page = SettingsPage(services, on_data_changed=self._refresh_all_views)

        self.pages.addWidget(self.course_page)
        self.pages.addWidget(self.task_page)
        self.pages.addWidget(self.device_page)
        self.pages.addWidget(self.logs_page)
        self.pages.addWidget(self.settings_page)

        self.nav_list.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav_list.setCurrentRow(0)

        root_layout.addWidget(self.nav_list)
        root_layout.addWidget(self.pages, 1)
        self.setCentralWidget(root)

    def _refresh_all_views(self) -> None:
        self.course_page.refresh()
        self.task_page.refresh()
        self.logs_page.refresh()
