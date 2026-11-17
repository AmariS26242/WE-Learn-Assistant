"""页面结构与课程学习模式识别分析模块。"""

from __future__ import annotations

from dataclasses import dataclass

from adapters.web.edge_adapter import PageStructureSummary


@dataclass(slots=True)
class PageClassification:
    """页面内容类型识别结果。"""

    category: str
    has_media: bool
    summary: str


class PageInspector:
    """根据页面 DOM 结构摘要判断可能的学习场景，辅助课程与任务整理。"""

    def classify(self, summary: PageStructureSummary) -> PageClassification:
        has_media = summary.has_audio or summary.has_video
        if summary.has_audio and not summary.has_video:
            return PageClassification(
                category="listening",
                has_media=True,
                summary="检测到音频组件，推测为听力练习或音频课程页",
            )
        if summary.has_video:
            return PageClassification(
                category="video_course",
                has_media=True,
                summary="检测到视频组件，推测为视频讲解页",
            )
        if summary.input_count > 0:
            return PageClassification(
                category="interactive_exercise",
                has_media=has_media,
                summary="检测到输入控件，推测为阅读填空或写作交互页",
            )
        return PageClassification(
            category="reading_or_navigation",
            has_media=has_media,
            summary="未检测到音视频或交互输入控件，推测为课程导航或阅读资料页",
        )
