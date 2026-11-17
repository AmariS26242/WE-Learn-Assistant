"""SQLite 数据库连接、事务与基础版本迁移管理。"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from core.storage.models import utc_now_iso


class DatabaseError(RuntimeError):
    """数据库操作异常。"""


class MigrationError(DatabaseError):
    """数据库结构迁移异常。"""


MIGRATIONS: list[tuple[int, str, str]] = [
    (
        1,
        "init_core_tables",
        """
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            code TEXT NOT NULL DEFAULT '',
            platform TEXT NOT NULL DEFAULT 'welearn',
            description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            order_index INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            chapter_id INTEGER NULL,
            title TEXT NOT NULL,
            task_type TEXT NOT NULL DEFAULT 'general',
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'in_progress', 'completed', 'failed', 'skipped')),
            error_message TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE,
            FOREIGN KEY (chapter_id) REFERENCES chapters (id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS operation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NULL,
            actor TEXT NOT NULL DEFAULT 'system',
            action TEXT NOT NULL,
            level TEXT NOT NULL DEFAULT 'INFO',
            message TEXT NOT NULL,
            details_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_chapters_course ON chapters (course_id, order_index);
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status);
        CREATE INDEX IF NOT EXISTS idx_tasks_course ON tasks (course_id, chapter_id);
        CREATE INDEX IF NOT EXISTS idx_logs_task ON operation_logs (task_id, created_at);
        """,
    ),
]


class DatabaseManager:
    """SQLite 数据库管理与版本迁移器。"""

    def __init__(self, db_path: str | Path = "data/we_learn_assistant.db") -> None:
        self.db_path = Path(db_path)
        self._in_memory = str(db_path) == ":memory:"
        self._shared_conn: sqlite3.Connection | None = None

    def initialize(self) -> int:
        """确保数据库目录存在并执行未应用的版本迁移，返回当前版本号。"""
        if not self._in_memory:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return self.migrate()

    def _open_connection(self) -> sqlite3.Connection:
        try:
            target = ":memory:" if self._in_memory else str(self.db_path)
            conn = sqlite3.connect(target, timeout=15.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            return conn
        except sqlite3.Error as exc:
            raise DatabaseError(f"无法打开 SQLite 数据库: {exc}") from exc

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """提供带事务自动提交与回滚保护的数据库连接上下文。"""
        if self._in_memory:
            if self._shared_conn is None:
                self._shared_conn = self._open_connection()
            conn = self._shared_conn
            try:
                yield conn
                conn.commit()
            except sqlite3.Error as exc:
                conn.rollback()
                raise DatabaseError(f"数据库执行失败: {exc}") from exc
            return

        conn = self._open_connection()
        try:
            yield conn
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise DatabaseError(f"数据库执行失败: {exc}") from exc
        finally:
            conn.close()

    def close(self) -> None:
        """关闭内存模式下的共享连接。"""
        if self._shared_conn is not None:
            self._shared_conn.close()
            self._shared_conn = None

    def get_schema_version(self) -> int:
        """获取当前数据库迁移版本号，未初始化时返回 0。"""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            ).fetchone()
            if row is None:
                return 0
            ver_row = conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS current_version FROM schema_migrations"
            ).fetchone()
            return int(ver_row["current_version"]) if ver_row else 0

    def migrate(self, migrations: list[tuple[int, str, str]] | None = None) -> int:
        """按版本号顺序幂等执行迁移脚本。"""
        active_migrations = migrations if migrations is not None else MIGRATIONS
        try:
            with self.connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        applied_at TEXT NOT NULL
                    )
                    """
                )
                applied_rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
                applied = {int(row["version"]) for row in applied_rows}

                for version, name, sql in sorted(active_migrations, key=lambda item: item[0]):
                    if version in applied:
                        continue
                    conn.executescript(sql)
                    conn.execute(
                        "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                        (version, name, utc_now_iso()),
                    )
        except DatabaseError:
            raise
        except Exception as exc:
            raise MigrationError(f"数据库迁移失败: {exc}") from exc

        return self.get_schema_version()
