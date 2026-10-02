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
DEFAULT_MODEL_PATH = Path("/home/asuna/whisper.cpp/whisper-base-ov")


@dataclass(slots=True)
class AudioConfig:
    device: str | int = "default"
    sample_rate: int = 16000
    channels: int = 1
    block_size: int = 512


@dataclass(slots=True)
class VADConfig:
    threshold: float = 0.55
    silence_timeout_ms: int = 220
    min_speech_duration_ms: int = 120
    max_speech_duration_s: float = 4.0
    pre_roll_ms: int = 200


@dataclass(slots=True)
class ASRConfig:
    backend: str = "openvino"  # "openvino"
    model_path: str = str(DEFAULT_MODEL_PATH)
    preferred_device: str = "NPU"
    fallback_device: str = "CPU"
    language: str = "en"
    cache_dir: str = os.path.expanduser("~/.cache/voicectl/ov_cache")


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
            ),
            vad=VADConfig(
                threshold=float(vad_data.get("threshold", 0.55)),
                silence_timeout_ms=int(vad_data.get("silence_timeout_ms", 220)),
                min_speech_duration_ms=int(vad_data.get("min_speech_duration_ms", 120)),
                max_speech_duration_s=float(vad_data.get("max_speech_duration_s", 4.0)),
                pre_roll_ms=int(vad_data.get("pre_roll_ms", 200)),
            ),
            asr=ASRConfig(
                backend=asr_data.get("backend", "openvino"),
                model_path=asr_data.get("model_path", str(DEFAULT_MODEL_PATH)),
                preferred_device=asr_data.get("preferred_device", "NPU"),
                fallback_device=asr_data.get("fallback_device", "CPU"),
                language=asr_data.get("language", "en"),
                cache_dir=asr_data.get("cache_dir", os.path.expanduser("~/.cache/voicectl/ov_cache")),
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
# Active mode on startup: "presentation", "normal", or "off"
default_mode = "presentation"

# Wake word for normal mode (e.g. "computer volume up")
wake_word = "computer"
require_wake_word_normal = false

# Desktop notifications via notify-send
notify_on_mode_change = true
notify_on_command = false
log_level = "INFO"

[audio]
# Input device name or index, or "default" for system PipeWire microphone
device = "default"
sample_rate = 16000
channels = 1
block_size = 512

[vad]
# Voice Activity Detection (Silero VAD ONNX)
threshold = 0.5
silence_timeout_ms = 400
min_speech_duration_ms = 180
max_speech_duration_s = 8.0
pre_roll_ms = 300

[asr]
# Speech recognition backend: "openvino"
backend = "openvino"
model_path = "/home/asuna/whisper.cpp/whisper-base-ov"
# Hardware inference device priority: NPU -> CPU fallback
preferred_device = "NPU"
fallback_device = "CPU"
language = "en"
cache_dir = "~/.cache/voicectl/ov_cache"

[volume]
# Volume change step for WirePlumber (0.05 = 5%)
step = 0.05
# Maximum volume cap (1.0 = 100%)
limit = 1.0

[paths]
commands_file = "~/.config/voicectl/commands.yaml"
scripts_dir = "~/.config/voicectl/scripts"
"""
