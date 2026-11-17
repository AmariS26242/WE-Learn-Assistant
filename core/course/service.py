"""课程与章节业务服务。"""

from __future__ import annotations

from core.storage.models import Chapter, Course, OperationLog
from core.storage.repositories import ChapterRepository, CourseRepository, OperationLogRepository


class CourseService:
    """课程与章节的识别整理、增删改查服务。"""

    def __init__(
        self,
        course_repo: CourseRepository,
        chapter_repo: ChapterRepository,
        log_repo: OperationLogRepository | None = None,
    ) -> None:
        self.course_repo = course_repo
        self.chapter_repo = chapter_repo
        self.log_repo = log_repo

    def create_course(
        self,
        title: str,
        *,
        code: str = "",
        platform: str = "welearn",
        description: str = "",
    ) -> Course:
        course = self.course_repo.create(
            Course(
                title=title,
                code=code,
                platform=platform,
                description=description,
            )
        )
        self._log("course.create", f"创建课程: {course.title}", {"course_id": course.id})
        return course

    def list_courses(self) -> list[Course]:
        return self.course_repo.list_all()

    def get_course(self, course_id: int) -> Course | None:
        return self.course_repo.get(course_id)

    def update_course(self, course: Course) -> Course:
        updated = self.course_repo.update(course)
        self._log("course.update", f"更新课程: {updated.title}", {"course_id": updated.id})
        return updated

    def delete_course(self, course_id: int) -> bool:
        deleted = self.course_repo.delete(course_id)
        if deleted:
            self._log("course.delete", f"删除课程 id={course_id}", {"course_id": course_id})
        return deleted

    def add_chapter(self, course_id: int, title: str, *, order_index: int = 0) -> Chapter:
        if self.course_repo.get(course_id) is None:
            raise ValueError(f"关联课程 id={course_id} 不存在")
        chapter = self.chapter_repo.create(
            Chapter(course_id=course_id, title=title, order_index=order_index)
        )
        self._log(
            "chapter.create",
            f"添加章节: {chapter.title}",
            {"course_id": course_id, "chapter_id": chapter.id},
        )
        return chapter

    def list_chapters(self, course_id: int) -> list[Chapter]:
        return self.chapter_repo.list_by_course(course_id)

    def _log(self, action: str, message: str, details: dict[str, object]) -> None:
        if self.log_repo is None:
            return
        self.log_repo.create(
            OperationLog(actor="course_service", action=action, message=message),
            details=details,
        )
