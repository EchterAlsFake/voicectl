"""Unit tests for Voice Activity Detection."""

import numpy as np
import pytest
from voicectl.config import VADConfig
from voicectl.vad import SileroVADDetector


def test_vad_silence():
    cfg = VADConfig(threshold=0.5, silence_timeout_ms=300, min_speech_duration_ms=100)
    detector = SileroVADDetector(cfg)

    # Stream of silence chunks should not produce utterances
    silence_chunk = np.zeros(512, dtype=np.float32)
    for _ in range(20):
        res = detector.process_chunk(silence_chunk)
        assert res is None


def test_vad_reset():
    cfg = VADConfig()
    detector = SileroVADDetector(cfg)
    detector.is_speech_active = True
    detector.speech_chunks.append(np.zeros(512, dtype=np.float32))

    detector.reset()
    assert not detector.is_speech_active
    assert len(detector.speech_chunks) == 0
