"""CPU-only ASR fallback implementation."""

from __future__ import annotations

from voicectl.asr.openvino import OpenVINOASR
from voicectl.config import ASRConfig


class CPUASR(OpenVINOASR):
    """Explicit CPU speech recognizer backend."""

    def __init__(self, config: ASRConfig) -> None:
        cpu_config = ASRConfig(
            backend=config.backend,
            model_path=config.model_path,
            preferred_device="CPU",
            fallback_device="CPU",
            language=config.language,
            cache_dir=config.cache_dir,
        )
        super().__init__(cpu_config)
