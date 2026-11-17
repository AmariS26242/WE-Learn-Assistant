"""任务状态转换、操作日志与异常恢复测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.scheduler.queue import TaskScheduler
from core.storage.database import DatabaseManager
from core.storage.models import Course, TaskStatus
from core.storage.repositories import (
    CourseRepository,
    OperationLogRepository,
    TaskRepository,
)
from core.task.manager import InvalidTaskTransitionError, TaskManager, TaskNotFoundError


def _setup_manager(db_path: Path) -> tuple[DatabaseManager, int, TaskManager, OperationLogRepository]:
    db = DatabaseManager(db_path)
    db.initialize()
    course = CourseRepository(db).create(Course(title="综合教程"))
    task_repo = TaskRepository(db)
    log_repo = OperationLogRepository(db)
    manager = TaskManager(task_repo, log_repo)
    return db, int(course.id), manager, log_repo


def test_valid_and_invalid_task_transitions(tmp_path: Path) -> None:
    _, course_id, manager, log_repo = _setup_manager(tmp_path / "tasks.db")
    task = manager.create_task(course_id, "阅读词汇整理", task_type="vocabulary")
    assert task.status == TaskStatus.PENDING

    in_prog = manager.transition(int(task.id), TaskStatus.IN_PROGRESS, reason="开始")
    assert in_prog.status == TaskStatus.IN_PROGRESS

    done = manager.transition(int(task.id), TaskStatus.COMPLETED, reason="完成")
    assert done.status == TaskStatus.COMPLETED

    # 已完成任务不能再逆向流转
    with pytest.raises(InvalidTaskTransitionError):
        manager.transition(int(task.id), TaskStatus.PENDING)

    logs = log_repo.list_recent(task_id=task.id)
    assert len(logs) >= 3


def test_task_not_found_and_recovery_on_restart(tmp_path: Path) -> None:
    db_file = tmp_path / "recover.db"
    _, course_id, manager1, _ = _setup_manager(db_file)
    task = manager1.create_task(course_id, "长时听力辅助")
    manager1.transition(int(task.id), TaskStatus.IN_PROGRESS)

    # 模拟进程意外中断后重启
    db2 = DatabaseManager(db_file)
    manager2 = TaskManager(TaskRepository(db2), OperationLogRepository(db2))
    recovered_ids = manager2.recover_on_startup()
    assert recovered_ids == [task.id]
    reloaded = manager2.get_task(int(task.id))
    assert reloaded.status == TaskStatus.PENDING

    with pytest.raises(TaskNotFoundError):
        manager2.get_task(40404)


def test_scheduler_executes_and_captures_exception(tmp_path: Path) -> None:
    _, course_id, manager, _ = _setup_manager(tmp_path / "sched.db")
    scheduler = TaskScheduler(manager)

    def ok_handler(task) -> None:
        manager.update_metadata(int(task.id), {"handled": True})

    def failing_handler(_task) -> None:
        raise RuntimeError("模拟故障 token=secret_abc_123456")

    scheduler.register_handler("reading", ok_handler)
    scheduler.register_handler("broken", failing_handler)

    t1 = manager.create_task(course_id, "正常阅读任务", task_type="reading")
    t2 = manager.create_task(course_id, "异常任务", task_type="broken")

    res1 = scheduler.run_task(int(t1.id))
    assert res1.status == TaskStatus.COMPLETED

    res2 = scheduler.run_task(int(t2.id))
    assert res2.status == TaskStatus.FAILED
    assert "secret_abc_123456" not in res2.error_message
    assert "se***" in res2.error_message
