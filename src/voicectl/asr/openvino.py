"""Intel OpenVINO GenAI Whisper ASR backend with automatic NPU -> CPU fallback."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
import numpy as np

import openvino_genai as ov_genai

from voicectl.asr.base import ASRBackend
from voicectl.config import ASRConfig

logger = logging.getLogger(__name__)


class OpenVINOASR(ASRBackend):
    """OpenVINO Whisper Pipeline running on Intel NPU with seamless CPU fallback."""

    def __init__(self, config: ASRConfig) -> None:
        self.config = config
        self.model_path = str(Path(config.model_path).expanduser())
        self.cache_dir = str(Path(config.cache_dir).expanduser())
        os.makedirs(self.cache_dir, exist_ok=True)

        self._active_device = config.preferred_device.upper()
        self._pipe: ov_genai.WhisperPipeline | None = None

        self._init_pipeline()

    def _init_pipeline(self) -> None:
        """Attempt to load the pipeline on preferred device, then fallback."""
        target_device = self._active_device
        logger.info("Initializing OpenVINO WhisperPipeline on %s from %s...",
                    target_device, self.model_path)
        try:
            t0 = time.perf_counter()
            self._pipe = ov_genai.WhisperPipeline(
                self.model_path,
                target_device,
                CACHE_DIR=self.cache_dir
            )
            load_time = time.perf_counter() - t0
            logger.info("OpenVINO pipeline successfully loaded on %s in %.2fs",
                        target_device, load_time)
            self._active_device = target_device
        except Exception as e:
            if target_device != "CPU":
                logger.warning("Failed to initialize OpenVINO pipeline on %s: %s. Falling back to CPU.",
                               target_device, e)
                try:
                    t0 = time.perf_counter()
                    self._pipe = ov_genai.WhisperPipeline(
                        self.model_path,
                        "CPU",
                        CACHE_DIR=self.cache_dir
                    )
                    load_time = time.perf_counter() - t0
                    self._active_device = "CPU"
                    logger.info("OpenVINO CPU fallback loaded in %.2fs", load_time)
                except Exception as cpu_err:
                    logger.error("Failed to initialize OpenVINO on CPU: %s", cpu_err)
                    raise
            else:
                logger.error("Failed to initialize OpenVINO pipeline on CPU: %s", e)
                raise

    @property
    def backend_name(self) -> str:
        return "OpenVINO"

    @property
    def device_name(self) -> str:
        return self._active_device

    def transcribe(self, audio: np.ndarray, language: str = "en") -> tuple[str, float]:
        """Transcribe 16kHz mono audio on NPU with automatic CPU fallback."""
        if self._pipe is None:
            raise RuntimeError("OpenVINO pipeline is not initialized")

        # Format audio into 1D float32 contiguous array
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        audio = np.ascontiguousarray(audio, dtype=np.float32)

        # Pad very short audio to at least 0.5s (8000 samples) for reliable mel filterbank
        if len(audio) < 8000:
            padded = np.zeros(8000, dtype=np.float32)
            padded[:len(audio)] = audio
            audio = padded

        lang_tag = f"<|{language}|>" if not language.startswith("<|") else language

        t0 = time.perf_counter()
        try:
            res = self._pipe.generate(
                audio.tolist(),
                language=lang_tag,
                task="transcribe",
                max_new_tokens=32
            )
        except Exception as e:
            if self._active_device != "CPU":
                logger.warning("NPU inference failed (%s). Triggering automatic CPU fallback...", e)
                self._active_device = "CPU"
                self._init_pipeline()
                t0 = time.perf_counter()
                res = self._pipe.generate(
                    audio.tolist(),
                    language=lang_tag,
                    task="transcribe",
                    max_new_tokens=32
                )
            else:
                raise

        dt_ms = (time.perf_counter() - t0) * 1000.0
        text = res.texts[0].strip() if res.texts else ""
        return text, dt_ms
