"""阅读理解与段落整理辅助模块。"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True)
class ReadingOutline:
    """文章阅读结构摘要。"""

    paragraph_count: int
    word_count: int
    estimated_minutes: float
    paragraphs: list[str]


class ReadingAssistant:
    """提供文章分段、词数统计与重点句提取。"""

    _WORD_RE = re.compile(r"[A-Za-z0-9'-]+")

    def summarize_passage(self, text: str, *, words_per_minute: int = 180) -> ReadingOutline:
        paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
        words = self._WORD_RE.findall(text)
        word_count = len(words)
        minutes = round(word_count / max(words_per_minute, 60), 2)
        return ReadingOutline(
            paragraph_count=len(paragraphs),
            word_count=word_count,
            estimated_minutes=minutes,
            paragraphs=paragraphs,
        )
