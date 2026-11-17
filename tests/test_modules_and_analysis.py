"""学习辅助模块与页面/兼容性分析模块测试。"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from adapters.web.edge_adapter import PageStructureSummary
from analysis.network import SanitizedNetworkEvent
from analysis.page import PageInspector
from modules.listening import ListeningAssistant
from modules.reading import ReadingAssistant
from modules.speaking import SpeakingQualityChecker
from modules.vocabulary import VocabularyAssistant
from modules.writing import WritingAssistant


def test_learning_modules_and_audio_quality(tmp_path: Path) -> None:
    listening = ListeningAssistant()
    assert listening.normalize_playback_rate(1.3) == 1.25
    segments = listening.build_segments(["Hello world.", "How are you?"])
    assert len(segments) == 2
    assert segments[0].duration_sec == 5.0

    reading = ReadingAssistant()
    outline = reading.summarize_passage("First paragraph.\n\nSecond paragraph with more words.")
    assert outline.paragraph_count == 2
    assert outline.word_count == 7

    writing = WritingAssistant()
    metrics = writing.analyze_draft("Learning English takes practice. Keep reading every day!")
    assert metrics.sentence_count == 2
    assert metrics.word_count == 8

    vocab = VocabularyAssistant()
    cards = vocab.extract_candidates("practice reading practice vocabulary reading practice")
    assert cards[0].word == "practice"
    assert cards[0].frequency == 3

    wav_path = tmp_path / "sample.wav"
    sample_rate = 16000
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = b"".join(
            struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * i / sample_rate)))
            for i in range(sample_rate)
        )
        wf.writeframes(frames)

    report = SpeakingQualityChecker().inspect_wav(wav_path)
    assert report.is_valid is True
    assert report.duration_sec == 1.0


def test_page_inspector_and_network_sanitization() -> None:
    inspector = PageInspector()
    summary = PageStructureSummary(title="Listening Unit", url="https://example.local", has_audio=True)
    result = inspector.classify(summary)
    assert result.category == "listening"

    event = SanitizedNetworkEvent.from_url(
        "GET",
        "https://welearn.sflep.com/api/course?token=secret123",
        status_code=200,
    )
    assert event.host == "welearn.sflep.com"
    assert "secret123" not in event.path
