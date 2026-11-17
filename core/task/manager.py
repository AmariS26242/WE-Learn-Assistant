"""统一任务状态机、操作记录与异常恢复管理器。"""

from __future__ import annotations

import json
from typing import Any

from core.logging_utils import mask_sensitive_text, safe_json_dumps
from core.storage.models import OperationLog, Task, TaskStatus
from core.storage.repositories import OperationLogRepository, TaskRepository


class TaskNotFoundError(LookupError):
    """指定任务不存在。"""


class InvalidTaskTransitionError(ValueError):
    """非法的任务状态转换。"""


ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {
        TaskStatus.IN_PROGRESS,
        TaskStatus.SKIPPED,
        TaskStatus.FAILED,
    },
    TaskStatus.IN_PROGRESS: {
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.SKIPPED,
        TaskStatus.PENDING,
    },
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: {
        TaskStatus.PENDING,
        TaskStatus.IN_PROGRESS,
        TaskStatus.SKIPPED,
    },
    TaskStatus.SKIPPED: {
        TaskStatus.PENDING,
    },
}


class TaskManager:
    """负责任务创建、状态流转校验、操作日志审计及异常恢复。"""

    def __init__(
        self,
        task_repo: TaskRepository,
        log_repo: OperationLogRepository,
    ) -> None:
        self.task_repo = task_repo
        self.log_repo = log_repo

    def create_task(
        self,
        course_id: int,
        title: str,
        *,
        chapter_id: int | None = None,
        task_type: str = "general",
        metadata: dict[str, Any] | None = None,
        actor: str = "task_manager",
    ) -> Task:
        task = self.task_repo.create(
            Task(
                course_id=course_id,
                chapter_id=chapter_id,
                title=title,
                task_type=task_type,
                status=TaskStatus.PENDING,
                metadata_json=safe_json_dumps(metadata),
            )
        )
        self.log_repo.create(
            OperationLog(
                task_id=task.id,
                actor=actor,
                action="task.create",
                level="INFO",
                message=f"创建任务: {task.title}",
            ),
            details={"status": task.status.value, "task_type": task.task_type},
        )
        return task

    def get_task(self, task_id: int) -> Task:
        task = self.task_repo.get(task_id)
        if task is None:
            raise TaskNotFoundError(f"任务 id={task_id} 不存在")
        return task

    def list_tasks(
        self,
        *,
        course_id: int | None = None,
        status: TaskStatus | None = None,
    ) -> list[Task]:
        return self.task_repo.list_all(course_id=course_id, status=status)

    def transition(
        self,
        task_id: int,
        target_status: TaskStatus,
        *,
        actor: str = "task_manager",
        reason: str = "",
        error_message: str = "",
    ) -> Task:
        task = self.get_task(task_id)
        current_status = task.status

        if current_status == target_status:
            return task

        allowed = ALLOWED_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            raise InvalidTaskTransitionError(
                f"不允许将任务状态从 {current_status.value} 转换为 {target_status.value}"
            )

        task.status = target_status
        if target_status == TaskStatus.FAILED:
            task.error_message = mask_sensitive_text(error_message or reason or "未知执行异常")
        elif target_status in {TaskStatus.PENDING, TaskStatus.COMPLETED, TaskStatus.SKIPPED}:
            task.error_message = ""

        updated = self.task_repo.update(task)
        level = "ERROR" if target_status == TaskStatus.FAILED else "INFO"
        msg = f"任务状态流转: {current_status.value} -> {target_status.value}"
        if reason:
            msg = f"{msg} ({reason})"

        self.log_repo.create(
            OperationLog(
                task_id=updated.id,
                actor=actor,
                action="task.transition",
                level=level,
                message=msg,
            ),
            details={
                "from": current_status.value,
                "to": target_status.value,
                "error_message": updated.error_message,
            },
        )
        return updated

    def mark_failed_from_exception(
        self,
        task_id: int,
        exc: Exception,
        *,
        actor: str = "task_manager",
    ) -> Task:
        """异常捕获后将任务标为 failed 并记录脱敏错误详情。"""
        task = self.get_task(task_id)
        if task.status == TaskStatus.COMPLETED:
            return task
        return self.transition(
            task_id,
            TaskStatus.FAILED,
            actor=actor,
            reason=f"异常中断: {type(exc).__name__}",
            error_message=f"{type(exc).__name__}: {exc}",
        )

    def recover_on_startup(self, *, actor: str = "recovery") -> list[int]:
        """应用重启后将遗留的 in_progress 任务恢复为 pending，防止死锁。"""
        recovered_ids = self.task_repo.reset_in_progress_to_pending()
        for task_id in recovered_ids:
            self.log_repo.create(
                OperationLog(
                    task_id=task_id,
                    actor=actor,
                    action="task.recover",
                    level="WARNING",
                    message=f"重启恢复: 任务 id={task_id} 从 in_progress 重置为 pending",
                ),
                details={"from": TaskStatus.IN_PROGRESS.value, "to": TaskStatus.PENDING.value},
            )
        return recovered_ids

    def update_metadata(self, task_id: int, patch: dict[str, Any]) -> Task:
        task = self.get_task(task_id)
        try:
            current = json.loads(task.metadata_json) if task.metadata_json else {}
            if not isinstance(current, dict):
                current = {}
        except json.JSONDecodeError:
            current = {}
        current.update(patch)
        task.metadata_json = safe_json_dumps(current)
        return self.task_repo.update(task)
