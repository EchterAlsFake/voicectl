"""Factory for creating ASR backends."""

from __future__ import annotations

import logging
from voicectl.asr.base import ASRBackend
from voicectl.asr.openvino import OpenVINOASR
from voicectl.asr.cpu import CPUASR
from voicectl.config import ASRConfig

logger = logging.getLogger(__name__)


def create_asr_backend(config: ASRConfig) -> ASRBackend:
    """Create and initialize an ASR backend instance according to config."""
    backend_type = config.backend.lower()

    if backend_type == "cpu":
        logger.info("Instantiating CPU ASR backend")
        return CPUASR(config)

    if backend_type == "openvino":
        logger.info("Instantiating OpenVINO ASR backend (preferred device: %s)", config.preferred_device)
        return OpenVINOASR(config)

    logger.warning("Unknown backend '%s', defaulting to OpenVINO", backend_type)
    return OpenVINOASR(config)
