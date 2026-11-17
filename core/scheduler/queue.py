"""基于统一任务状态机的安全任务调度器。"""

from __future__ import annotations

from collections.abc import Callable

from core.storage.models import Task, TaskStatus
from core.task.manager import TaskManager


class TaskScheduler:
    """按队列顺序执行已注册的辅助任务处理器，提供统一异常捕获与状态落库。"""

    def __init__(self, task_manager: TaskManager) -> None:
        self.task_manager = task_manager
        self._handlers: dict[str, Callable[[Task], None]] = {}

    def register_handler(self, task_type: str, handler: Callable[[Task], None]) -> None:
        self._handlers[task_type] = handler

    def next_pending_task(self, *, course_id: int | None = None) -> Task | None:
        pending = self.task_manager.list_tasks(course_id=course_id, status=TaskStatus.PENDING)
        return pending[0] if pending else None

    def run_task(self, task_id: int, *, actor: str = "scheduler") -> Task:
        task = self.task_manager.get_task(task_id)
        handler = self._handlers.get(task.task_type)
        if handler is None:
            return self.task_manager.transition(
                task_id,
                TaskStatus.FAILED,
                actor=actor,
                reason="未找到对应的任务处理器",
                error_message=f"未注册任务类型: {task.task_type}",
            )

        self.task_manager.transition(
            task_id,
            TaskStatus.IN_PROGRESS,
            actor=actor,
            reason="开始执行任务",
        )
        try:
            handler(self.task_manager.get_task(task_id))
        except Exception as exc:  # noqa: BLE001
            return self.task_manager.mark_failed_from_exception(task_id, exc, actor=actor)

        return self.task_manager.transition(
            task_id,
            TaskStatus.COMPLETED,
            actor=actor,
            reason="任务执行完成",
        )
