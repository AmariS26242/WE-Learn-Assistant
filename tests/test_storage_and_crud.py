"""SQLite 数据持久化、迁移与 CRUD 测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.course.service import CourseService
from core.storage.database import MIGRATIONS, DatabaseError, DatabaseManager, MigrationError
from core.storage.models import Chapter, Course, OperationLog, Task, TaskStatus
from core.storage.repositories import (
    ChapterRepository,
    CourseRepository,
    OperationLogRepository,
    TaskRepository,
)


def test_database_migration_and_idempotency(tmp_path: Path) -> None:
    db_file = tmp_path / "app.db"
    db = DatabaseManager(db_file)

    assert db.get_schema_version() == 0
    version_first = db.initialize()
    assert version_first == MIGRATIONS[-1][0]
    assert db.initialize() == version_first


def test_database_migration_error_handling(tmp_path: Path) -> None:
    db = DatabaseManager(tmp_path / "broken.db")
    with pytest.raises((DatabaseError, MigrationError)):
        db.migrate([(1, "broken_sql", "CREATE TABLE bad_syntax (")])


def test_sqlite_persistence_across_restart(tmp_path: Path) -> None:
    db_file = tmp_path / "persist.db"

    db1 = DatabaseManager(db_file)
    db1.initialize()
    course_repo1 = CourseRepository(db1)
    chapter_repo1 = ChapterRepository(db1)
    task_repo1 = TaskRepository(db1)

    created_course = course_repo1.create(Course(title="大学英语读写", code="ENG101"))
    assert created_course.id is not None
    created_chapter = chapter_repo1.create(
        Chapter(course_id=created_course.id, title="Unit 1", order_index=1)
    )
    created_task = task_repo1.create(
        Task(
            course_id=created_course.id,
            chapter_id=created_chapter.id,
            title="精读课文整理",
            task_type="reading",
        )
    )

    # 模拟重启：用新的 DatabaseManager 实例重新连接同一个 SQLite 文件
    db2 = DatabaseManager(db_file)
    course_repo2 = CourseRepository(db2)
    chapter_repo2 = ChapterRepository(db2)
    task_repo2 = TaskRepository(db2)

    loaded_course = course_repo2.get(created_course.id)
    assert loaded_course is not None
    assert loaded_course.title == "大学英语读写"
    assert loaded_course.code == "ENG101"

    loaded_chapters = chapter_repo2.list_by_course(created_course.id)
    assert len(loaded_chapters) == 1
    assert loaded_chapters[0].title == "Unit 1"

    loaded_task = task_repo2.get(created_task.id or -1)
    assert loaded_task is not None
    assert loaded_task.status == TaskStatus.PENDING


def test_course_chapter_and_task_crud(tmp_path: Path) -> None:
    db = DatabaseManager(tmp_path / "crud.db")
    db.initialize()
    course_repo = CourseRepository(db)
    chapter_repo = ChapterRepository(db)
    task_repo = TaskRepository(db)
    log_repo = OperationLogRepository(db)
    service = CourseService(course_repo, chapter_repo, log_repo=log_repo)

    course = service.create_course("视听说教程", code="LIS201", description="第一学期")
    assert course.id is not None

    course.title = "视听说教程（修订）"
    updated = service.update_course(course)
    assert updated.title == "视听说教程（修订）"

    chapter = service.add_chapter(course.id, "Unit 2", order_index=2)
    assert chapter.id is not None

    task = task_repo.create(Task(course_id=course.id, chapter_id=chapter.id, title="听力分段"))
    assert task.id is not None
    task.title = "听力分段复习"
    task_repo.update(task)
    assert task_repo.get(task.id).title == "听力分段复习"

    assert task_repo.delete(task.id) is True
    assert task_repo.get(task.id) is None

    assert service.delete_course(course.id) is True
    assert service.get_course(course.id) is None
    assert chapter_repo.list_by_course(course.id) == []


def test_crud_validation_and_missing_id_errors(tmp_path: Path) -> None:
    db = DatabaseManager(tmp_path / "errors.db")
    db.initialize()
    course_repo = CourseRepository(db)
    task_repo = TaskRepository(db)
    log_repo = OperationLogRepository(db)

    with pytest.raises(ValueError):
        course_repo.create(Course(title="   "))

    with pytest.raises(DatabaseError):
        course_repo.update(Course(id=9999, title="不存在的课程"))

    with pytest.raises(DatabaseError):
        task_repo.create(Task(course_id=9999, title="外键缺失任务"))

    log = log_repo.create(OperationLog(action="test", message="ok"))
    assert log.id is not None
