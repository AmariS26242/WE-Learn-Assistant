"""听力播放与材料整理辅助模块。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ListeningSegment:
    """听力文本片段结构。"""

    index: int
    start_sec: float
    end_sec: float
    transcript: str = ""

    @property
    def duration_sec(self) -> float:
        return max(0.0, self.end_sec - self.start_sec)


class ListeningAssistant:
    """提供听力分段整理与播放速率建议（纯学习辅助，不修改平台播放记录）。"""

    SUPPORTED_RATES: tuple[float, ...] = (0.75, 1.0, 1.25, 1.5)

    def normalize_playback_rate(self, rate: float) -> float:
        return min(self.SUPPORTED_RATES, key=lambda candidate: abs(candidate - rate))

    def build_segments(self, lines: list[str], *, seconds_per_line: float = 5.0) -> list[ListeningSegment]:
        segments: list[ListeningSegment] = []
        cursor = 0.0
        for idx, raw in enumerate(lines, start=1):
            text = raw.strip()
            if not text:
                continue
            segments.append(
                ListeningSegment(
                    index=idx,
                    start_sec=cursor,
                    end_sec=cursor + seconds_per_line,
                    transcript=text,
                )
            )
            cursor += seconds_per_line
        return segments
