"""口语录音质量本地检查模块。"""

from __future__ import annotations

import array
import wave
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AudioQualityReport:
    """本地 WAV 录音基础质量报告。"""

    file_name: str
    sample_rate: int
    channels: int
    duration_sec: float
    peak_ratio: float
    is_too_quiet: bool
    is_valid: bool
    notes: str


class SpeakingQualityChecker:
    """仅检查用户本地口语录音文件质量，不生成或伪造任何录音数据。"""

    def inspect_wav(self, file_path: str | Path, *, min_peak_ratio: float = 0.03) -> AudioQualityReport:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"录音文件不存在: {path.name}")

        with wave.open(str(path), "rb") as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            sample_rate = wf.getframerate()
            frame_count = wf.getnframes()
            raw = wf.readframes(frame_count)

        duration_sec = round(frame_count / sample_rate, 2) if sample_rate > 0 else 0.0
        peak_ratio = 0.0
        if sample_width == 2 and raw:
            samples = array.array("h", raw)
            peak = max((abs(s) for s in samples), default=0)
            peak_ratio = round(peak / 32768.0, 4)

        is_too_quiet = peak_ratio < min_peak_ratio
        is_valid = duration_sec >= 0.5 and not is_too_quiet
        notes = "录音音量与时长正常" if is_valid else "录音音量过低或时长不足，建议重录"
        return AudioQualityReport(
            file_name=path.name,
            sample_rate=sample_rate,
            channels=channels,
            duration_sec=duration_sec,
            peak_ratio=peak_ratio,
            is_too_quiet=is_too_quiet,
            is_valid=is_valid,
            notes=notes,
        )
