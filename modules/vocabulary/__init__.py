"""词汇提取与复习卡片整理模块。"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass


@dataclass(slots=True)
class VocabCard:
    """词汇复习条目。"""

    word: str
    frequency: int
    note: str = ""


class VocabularyAssistant:
    """从阅读文本中统计高频英文词汇以便制作复习清单。"""

    _WORD_RE = re.compile(r"\b[a-zA-Z]{4,}\b")
    _STOPWORDS = frozenset(
        {"that", "this", "with", "from", "have", "will", "would", "there", "their", "about", "which"}
    )

    def extract_candidates(self, text: str, *, top_n: int = 20) -> list[VocabCard]:
        tokens = [
            word.lower()
            for word in self._WORD_RE.findall(text)
            if word.lower() not in self._STOPWORDS
        ]
        counts = Counter(tokens)
        return [VocabCard(word=w, frequency=freq) for w, freq in counts.most_common(top_n)]
