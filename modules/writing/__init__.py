"""写作辅助与结构检查模块。"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True)
class WritingMetrics:
    """英语写作基础统计指标。"""

    word_count: int
    sentence_count: int
    paragraph_count: int
    avg_sentence_words: float


class WritingAssistant:
    """提供写作文本的字数、句长与段落结构统计。"""

    _WORD_RE = re.compile(r"[A-Za-z0-9'-]+")
    _SENTENCE_SPLIT_RE = re.compile(r"[.!?]+")

    def analyze_draft(self, text: str) -> WritingMetrics:
        paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
        words = self._WORD_RE.findall(text)
        sentences = [s.strip() for s in self._SENTENCE_SPLIT_RE.split(text) if s.strip()]
        word_count = len(words)
        sentence_count = len(sentences)
        avg = round(word_count / sentence_count, 2) if sentence_count else 0.0
        return WritingMetrics(
            word_count=word_count,
            sentence_count=sentence_count,
            paragraph_count=len(paragraphs),
            avg_sentence_words=avg,
        )
