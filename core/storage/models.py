"""数据模型与任务状态枚举定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


def utc_now_iso() -> str:
    """返回 ISO-8601 格式的 UTC 时间字符串。"""
    return datetime.now(UTC).isoformat(timespec="seconds")


class TaskStatus(StrEnum):
    """统一任务状态枚举。"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(slots=True)
class Course:
    """课程数据模型。"""

    title: str
    code: str = ""
    platform: str = "welearn"
    description: str = ""
    id: int | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)


@dataclass(slots=True)
class Chapter:
    """课程章节数据模型。"""

    course_id: int
    title: str
    order_index: int = 0
    id: int | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)


@dataclass(slots=True)
class Task:
    """学习辅助任务数据模型。"""

    course_id: int
    title: str
    chapter_id: int | None = None
    task_type: str = "general"
    status: TaskStatus = TaskStatus.PENDING
    error_message: str = ""
    metadata_json: str = "{}"
    id: int | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)


@dataclass(slots=True)
class OperationLog:
    """操作与异常日志模型。"""

    action: str
    message: str
    actor: str = "system"
    level: str = "INFO"
    task_id: int | None = None
    details_json: str = "{}"
    id: int | None = None
    created_at: str = field(default_factory=utc_now_iso)
