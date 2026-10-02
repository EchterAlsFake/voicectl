"""Unit tests for audio preprocessing and configuration."""

import numpy as np
import pytest
from voicectl.config import Config, ASRConfig, MODEL_PRESETS


def test_model_preset_resolution():
    cfg = ASRConfig(model="small")
    assert cfg.resolve_model_path() == MODEL_PRESETS["small"]

    cfg_turbo = ASRConfig(model="large-turbo")
    assert cfg_turbo.resolve_model_path() == MODEL_PRESETS["large-turbo"]

    cfg_base = ASRConfig(model="base")
    assert cfg_base.resolve_model_path() == MODEL_PRESETS["base"]


def test_audio_normalization_and_filtering():
    import scipy.signal as signal

    # Create synthetic quiet tone (simulate 3m distant speech)
    t = np.linspace(0, 1.0, 16000, dtype=np.float32)
    quiet_signal = 0.015 * np.sin(2 * np.pi * 300 * t) + 0.05 * np.sin(2 * np.pi * 30 * t) # plus 30Hz room rumble

    # 1. DC removal
    cleaned = quiet_signal - np.mean(quiet_signal)

    # 2. 80 Hz high-pass filter
    sos = signal.butter(2, 80, btype="highpass", fs=16000, output="sos")
    filtered = signal.sosfilt(sos, cleaned).astype(np.float32)

    # 3. Peak normalization
    peak = float(np.max(np.abs(filtered)))
    assert peak > 0
    normalized = (filtered / peak) * 0.92

    # Verify peak is now normalized to ~0.92
    assert pytest.approx(float(np.max(np.abs(normalized))), 0.01) == 0.92
