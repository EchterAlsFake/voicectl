"""Configuration management for voicectl."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_DIR = Path(os.path.expanduser("~/.config/voicectl"))
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.toml"
DEFAULT_COMMANDS_PATH = DEFAULT_CONFIG_DIR / "commands.yaml"
DEFAULT_SCRIPTS_DIR = DEFAULT_CONFIG_DIR / "scripts"
MODEL_PRESETS: dict[str, str] = {
    "base": "/home/asuna/whisper.cpp/whisper-base-ov",
    "small": "/home/asuna/whisper.cpp/whisper-small-ov",
    "large-turbo": "/home/asuna/whisper.cpp/whisper-large-turbo-ov",
}
DEFAULT_MODEL_PATH = Path(MODEL_PRESETS["small"])


@dataclass(slots=True)
class AudioConfig:
    device: str | int = "default"
    sample_rate: int = 16000
    channels: int = 1
    block_size: int = 512
    gain: float = 1.0


@dataclass(slots=True)
class VADConfig:
    threshold: float = 0.45
    silence_timeout_ms: int = 220
    min_speech_duration_ms: int = 120
    max_speech_duration_s: float = 4.0
    pre_roll_ms: int = 300


@dataclass(slots=True)
class ASRConfig:
    backend: str = "openvino"  # "openvino"
    model: str = "small"       # "base", "small", "large-turbo", or custom directory path
    model_path: str = ""       # Optional explicit path override
    preferred_device: str = "NPU"
    fallback_device: str = "CPU"
    language: str = "en"
    cache_dir: str = os.path.expanduser("~/.cache/voicectl/ov_cache")
    normalize_audio: bool = True  # Software AGC / Peak normalization for far-field capture
    highpass_filter: bool = True  # 80 Hz high-pass rumble filter

    def resolve_model_path(self) -> str:
        """Resolve model preset or custom directory path."""
        if self.model_path and Path(self.model_path).expanduser().is_dir():
            return str(Path(self.model_path).expanduser())
        if self.model in MODEL_PRESETS:
            return MODEL_PRESETS[self.model]
        custom = Path(self.model).expanduser()
        if custom.is_dir():
            return str(custom)
        return MODEL_PRESETS.get("small", MODEL_PRESETS["base"])


@dataclass(slots=True)
class VolumeConfig:
    step: float = 0.05
    limit: float = 1.0


@dataclass(slots=True)
class GeneralConfig:
    default_mode: str = "presentation"  # "presentation", "normal", "off"
    wake_word: str = "computer"
    require_wake_word_normal: bool = False
    notify_on_mode_change: bool = True
    notify_on_command: bool = False
    log_level: str = "INFO"


@dataclass(slots=True)
class Config:
    general: GeneralConfig = field(default_factory=GeneralConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    vad: VADConfig = field(default_factory=VADConfig)
    asr: ASRConfig = field(default_factory=ASRConfig)
    volume: VolumeConfig = field(default_factory=VolumeConfig)
    commands_path: str = str(DEFAULT_COMMANDS_PATH)
    scripts_dir: str = str(DEFAULT_SCRIPTS_DIR)

    @classmethod
    def load(cls, config_path: Path | str | None = None) -> Config:
        path = Path(config_path or DEFAULT_CONFIG_PATH).expanduser()
        if not path.is_file():
            # Return defaults if file doesn't exist yet
            return cls()

        with open(path, "rb") as f:
            data = tomllib.load(f)

        gen_data = data.get("general", {})
        aud_data = data.get("audio", {})
        vad_data = data.get("vad", {})
        asr_data = data.get("asr", {})
        vol_data = data.get("volume", {})

        return cls(
            general=GeneralConfig(
                default_mode=gen_data.get("default_mode", "presentation"),
                wake_word=gen_data.get("wake_word", "computer"),
                require_wake_word_normal=gen_data.get("require_wake_word_normal", False),
                notify_on_mode_change=gen_data.get("notify_on_mode_change", True),
                notify_on_command=gen_data.get("notify_on_command", False),
                log_level=gen_data.get("log_level", "INFO"),
            ),
            audio=AudioConfig(
                device=aud_data.get("device", "default"),
                sample_rate=int(aud_data.get("sample_rate", 16000)),
                channels=int(aud_data.get("channels", 1)),
                block_size=int(aud_data.get("block_size", 512)),
                gain=float(aud_data.get("gain", 1.0)),
            ),
            vad=VADConfig(
                threshold=float(vad_data.get("threshold", 0.45)),
                silence_timeout_ms=int(vad_data.get("silence_timeout_ms", 220)),
                min_speech_duration_ms=int(vad_data.get("min_speech_duration_ms", 120)),
                max_speech_duration_s=float(vad_data.get("max_speech_duration_s", 4.0)),
                pre_roll_ms=int(vad_data.get("pre_roll_ms", 300)),
            ),
            asr=ASRConfig(
                backend=asr_data.get("backend", "openvino"),
                model=asr_data.get("model", "small"),
                model_path=asr_data.get("model_path", ""),
                preferred_device=asr_data.get("preferred_device", "NPU"),
                fallback_device=asr_data.get("fallback_device", "CPU"),
                language=asr_data.get("language", "en"),
                cache_dir=asr_data.get("cache_dir", os.path.expanduser("~/.cache/voicectl/ov_cache")),
                normalize_audio=bool(asr_data.get("normalize_audio", True)),
                highpass_filter=bool(asr_data.get("highpass_filter", True)),
            ),
            volume=VolumeConfig(
                step=float(vol_data.get("step", 0.05)),
                limit=float(vol_data.get("limit", 1.0)),
            ),
            commands_path=data.get("paths", {}).get("commands_file", str(DEFAULT_COMMANDS_PATH)),
            scripts_dir=data.get("paths", {}).get("scripts_dir", str(DEFAULT_SCRIPTS_DIR)),
        )


DEFAULT_CONFIG_TOML = """# voicectl configuration file
# Default location: ~/.config/voicectl/config.toml

[general]
# Startup mode: "presentation", "normal", or "off"
default_mode = "presentation"

# Wake word for normal mode (e.g. "computer volume up")
wake_word = "computer"
require_wake_word_normal = false

# Desktop notifications via notify-send
notify_on_mode_change = true
notify_on_command = false
log_level = "INFO"

[audio]
# Input device name or index, or "default" for PipeWire default microphone
device = "default"
sample_rate = 16000
channels = 1
block_size = 512
# Software mic gain multiplier (e.g. 1.0 = nominal, 1.5 = +3.5dB, 2.0 = +6dB)
gain = 1.0

[vad]
# Low-latency Silero VAD (ONNX) with dual-threshold hysteresis
# Lower threshold (e.g. 0.45) provides higher sensitivity for far-field capture
threshold = 0.45
silence_timeout_ms = 220
min_speech_duration_ms = 120
max_speech_duration_s = 4.0
pre_roll_ms = 300

[asr]
# Speech recognition backend: "openvino"
backend = "openvino"

# Model preset:
#   "small"       - 244M params, ~270-310ms NPU latency (Recommended: great far-field accuracy + speed)
#   "large-turbo" - 809M params, ~560-600ms NPU latency (Maximum accuracy, robust natural language)
#   "base"        - 74M params, ~120ms NPU latency (Ultra-fast baseline)
# Or specify a custom absolute directory path
model = "small"

# Hardware inference device priority: NPU -> CPU fallback
preferred_device = "NPU"
fallback_device = "CPU"
language = "en"
cache_dir = "~/.cache/voicectl/ov_cache"

# Far-field enhancement: Software AGC / Peak normalization & 80Hz rumble filter
normalize_audio = true
highpass_filter = true

[volume]
# Volume change step for WirePlumber (0.05 = 5%)
step = 0.05
# Maximum volume cap (1.0 = 100%)
limit = 1.0

[paths]
commands_file = "~/.config/voicectl/commands.yaml"
scripts_dir = "~/.config/voicectl/scripts"
"""
