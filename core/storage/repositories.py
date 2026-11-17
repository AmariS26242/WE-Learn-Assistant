"""SQLite 数据仓储层（Course、Chapter、Task、OperationLog CRUD 与查询）。"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from core.logging_utils import mask_sensitive_text, safe_json_dumps
from core.storage.database import DatabaseError, DatabaseManager
from core.storage.models import Chapter, Course, OperationLog, Task, TaskStatus, utc_now_iso


def _row_to_course(row: sqlite3.Row) -> Course:
    return Course(
        id=int(row["id"]),
        title=str(row["title"]),
        code=str(row["code"]),
        platform=str(row["platform"]),
        description=str(row["description"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _row_to_chapter(row: sqlite3.Row) -> Chapter:
    return Chapter(
        id=int(row["id"]),
        course_id=int(row["course_id"]),
        title=str(row["title"]),
        order_index=int(row["order_index"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _row_to_task(row: sqlite3.Row) -> Task:
    return Task(
        id=int(row["id"]),
        course_id=int(row["course_id"]),
        chapter_id=int(row["chapter_id"]) if row["chapter_id"] is not None else None,
        title=str(row["title"]),
        task_type=str(row["task_type"]),
        status=TaskStatus(str(row["status"])),
        error_message=str(row["error_message"]),
        metadata_json=str(row["metadata_json"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _row_to_log(row: sqlite3.Row) -> OperationLog:
    return OperationLog(
        id=int(row["id"]),
        task_id=int(row["task_id"]) if row["task_id"] is not None else None,
        actor=str(row["actor"]),
        action=str(row["action"]),
        level=str(row["level"]),
        message=str(row["message"]),
        details_json=str(row["details_json"]),
        created_at=str(row["created_at"]),
    )


class CourseRepository:
    """课程仓储。"""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def create(self, course: Course) -> Course:
        if not course.title.strip():
            raise ValueError("课程名称不能为空")
        now = utc_now_iso()
        course.created_at = course.created_at or now
        course.updated_at = now
        with self.db.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO courses (title, code, platform, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    course.title.strip(),
                    course.code.strip(),
                    course.platform.strip(),
                    course.description.strip(),
                    course.created_at,
                    course.updated_at,
                ),
            )
            course.id = int(cur.lastrowid)
        return course

    def get(self, course_id: int) -> Course | None:
        with self.db.connection() as conn:
            row = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
        return _row_to_course(row) if row else None

    def list_all(self) -> list[Course]:
        with self.db.connection() as conn:
            rows = conn.execute("SELECT * FROM courses ORDER BY id ASC").fetchall()
        return [_row_to_course(row) for row in rows]

    def update(self, course: Course) -> Course:
        if course.id is None:
            raise ValueError("更新课程必须提供 id")
        if not course.title.strip():
            raise ValueError("课程名称不能为空")
        course.updated_at = utc_now_iso()
        with self.db.connection() as conn:
            cur = conn.execute(
                """
                UPDATE courses
                SET title = ?, code = ?, platform = ?, description = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    course.title.strip(),
                    course.code.strip(),
                    course.platform.strip(),
                    course.description.strip(),
                    course.updated_at,
                    course.id,
                ),
            )
            if cur.rowcount == 0:
                raise DatabaseError(f"课程 id={course.id} 不存在")
        return course

    def delete(self, course_id: int) -> bool:
        with self.db.connection() as conn:
            cur = conn.execute("DELETE FROM courses WHERE id = ?", (course_id,))
        return cur.rowcount > 0


class ChapterRepository:
    """章节仓储。"""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def create(self, chapter: Chapter) -> Chapter:
        if not chapter.title.strip():
            raise ValueError("章节名称不能为空")
        now = utc_now_iso()
        chapter.created_at = chapter.created_at or now
        chapter.updated_at = now
        with self.db.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO chapters (course_id, title, order_index, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    chapter.course_id,
                    chapter.title.strip(),
                    chapter.order_index,
                    chapter.created_at,
                    chapter.updated_at,
                ),
            )
            chapter.id = int(cur.lastrowid)
        return chapter

    def get(self, chapter_id: int) -> Chapter | None:
        with self.db.connection() as conn:
            row = conn.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,)).fetchone()
        return _row_to_chapter(row) if row else None

    def list_by_course(self, course_id: int) -> list[Chapter]:
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM chapters WHERE course_id = ? ORDER BY order_index ASC, id ASC",
                (course_id,),
            ).fetchall()
        return [_row_to_chapter(row) for row in rows]

    def update(self, chapter: Chapter) -> Chapter:
        if chapter.id is None:
            raise ValueError("更新章节必须提供 id")
        if not chapter.title.strip():
            raise ValueError("章节名称不能为空")
        chapter.updated_at = utc_now_iso()
        with self.db.connection() as conn:
            cur = conn.execute(
                """
                UPDATE chapters
                SET title = ?, order_index = ?, updated_at = ?
                WHERE id = ?
                """,
                (chapter.title.strip(), chapter.order_index, chapter.updated_at, chapter.id),
            )
            if cur.rowcount == 0:
                raise DatabaseError(f"章节 id={chapter.id} 不存在")
        return chapter

    def delete(self, chapter_id: int) -> bool:
        with self.db.connection() as conn:
            cur = conn.execute("DELETE FROM chapters WHERE id = ?", (chapter_id,))
        return cur.rowcount > 0


class TaskRepository:
    """任务仓储。"""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def create(self, task: Task) -> Task:
        if not task.title.strip():
            raise ValueError("任务名称不能为空")
        now = utc_now_iso()
        task.created_at = task.created_at or now
        task.updated_at = now
        with self.db.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO tasks (
                    course_id, chapter_id, title, task_type, status,
                    error_message, metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.course_id,
                    task.chapter_id,
                    task.title.strip(),
                    task.task_type.strip() or "general",
                    task.status.value,
                    mask_sensitive_text(task.error_message),
                    task.metadata_json or "{}",
                    task.created_at,
                    task.updated_at,
                ),
            )
            task.id = int(cur.lastrowid)
        return task

    def get(self, task_id: int) -> Task | None:
        with self.db.connection() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_task(row) if row else None

    def list_all(
        self,
        *,
        course_id: int | None = None,
        status: TaskStatus | None = None,
    ) -> list[Task]:
        clauses: list[str] = []
        params: list[Any] = []
        if course_id is not None:
            clauses.append("course_id = ?")
            params.append(course_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status.value)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM tasks {where_sql} ORDER BY id ASC"
        with self.db.connection() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [_row_to_task(row) for row in rows]

    def update(self, task: Task) -> Task:
        if task.id is None:
            raise ValueError("更新任务必须提供 id")
        if not task.title.strip():
            raise ValueError("任务名称不能为空")
        task.updated_at = utc_now_iso()
        masked_error = mask_sensitive_text(task.error_message)
        with self.db.connection() as conn:
            cur = conn.execute(
                """
                UPDATE tasks
                SET course_id = ?, chapter_id = ?, title = ?, task_type = ?,
                    status = ?, error_message = ?, metadata_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    task.course_id,
                    task.chapter_id,
                    task.title.strip(),
                    task.task_type.strip() or "general",
                    task.status.value,
                    masked_error,
                    task.metadata_json or "{}",
                    task.updated_at,
                    task.id,
                ),
            )
            if cur.rowcount == 0:
                raise DatabaseError(f"任务 id={task.id} 不存在")
        task.error_message = masked_error
        return task

    def delete(self, task_id: int) -> bool:
        with self.db.connection() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return cur.rowcount > 0

    def reset_in_progress_to_pending(self) -> list[int]:
        """重启恢复：将意外中断遗留的 in_progress 任务复位为 pending，返回受影响的 task_id 列表。"""
        now = utc_now_iso()
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT id FROM tasks WHERE status = ?",
                (TaskStatus.IN_PROGRESS.value,),
            ).fetchall()
            affected_ids = [int(row["id"]) for row in rows]
            if affected_ids:
                conn.execute(
                    """
                    UPDATE tasks
                    SET status = ?, updated_at = ?
                    WHERE status = ?
                    """,
                    (TaskStatus.PENDING.value, now, TaskStatus.IN_PROGRESS.value),
                )
        return affected_ids


class OperationLogRepository:
    """操作日志仓储（自动执行敏感信息脱敏）。"""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def create(
        self,
        log: OperationLog,
        *,
        details: dict[str, Any] | None = None,
    ) -> OperationLog:
        now = utc_now_iso()
        log.created_at = log.created_at or now
        masked_message = mask_sensitive_text(log.message)
        if details is not None:
            details_json = safe_json_dumps(details)
        else:
            try:
                parsed = json.loads(log.details_json) if log.details_json else {}
                details_json = safe_json_dumps(parsed) if isinstance(parsed, dict) else "{}"
            except json.JSONDecodeError:
                details_json = safe_json_dumps({"raw": log.details_json})

        with self.db.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO operation_logs (
                    task_id, actor, action, level, message, details_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log.task_id,
                    log.actor,
                    log.action,
                    log.level.upper(),
                    masked_message,
                    details_json,
                    log.created_at,
                ),
            )
            log.id = int(cur.lastrowid)
            log.message = masked_message
            log.details_json = details_json
        return log

    def list_recent(
        self,
        *,
        limit: int = 100,
        task_id: int | None = None,
        level: str | None = None,
    ) -> list[OperationLog]:
        clauses: list[str] = []
        params: list[Any] = []
        if task_id is not None:
            clauses.append("task_id = ?")
            params.append(task_id)
        if level is not None:
            clauses.append("level = ?")
            params.append(level.upper())

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM operation_logs {where_sql} ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self.db.connection() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [_row_to_log(row) for row in rows]
