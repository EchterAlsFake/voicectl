"""Voice Activity Detection using Silero VAD (ONNX) with low-latency hysteresis."""

from __future__ import annotations

import logging
import time
from typing import Callable, Iterator

import numpy as np
import torch
import silero_vad

from voicectl.config import VADConfig

logger = logging.getLogger(__name__)


class SileroVADDetector:
    """Detects speech segments and segments continuous audio into complete utterances with minimal latency."""

    def __init__(self, config: VADConfig, sample_rate: int = 16000) -> None:
        self.config = config
        self.sample_rate = sample_rate

        # Hysteresis thresholds for crisp boundaries
        self.start_threshold = max(0.55, config.threshold)
        self.end_threshold = max(0.20, config.threshold - 0.20)  # e.g. 0.35 when threshold=0.55

        self.silence_timeout_chunks = max(3, int((config.silence_timeout_ms / 1000.0) * sample_rate / 512))
        self.min_speech_chunks = max(2, int((config.min_speech_duration_ms / 1000.0) * sample_rate / 512))
        self.max_chunks = int((config.max_speech_duration_s * sample_rate) / 512)

        logger.info("Initializing Silero VAD ONNX (start_th=%.2f, end_th=%.2f, timeout_chunks=%d)...",
                    self.start_threshold, self.end_threshold, self.silence_timeout_chunks)
        self.model = silero_vad.load_silero_vad(onnx=True)
        self.reset()

    def set_max_duration(self, max_seconds: float) -> None:
        """Dynamically adjust max utterance duration (e.g. 2.0s for presentation mode)."""
        self.max_chunks = max(self.min_speech_chunks + self.silence_timeout_chunks,
                              int((max_seconds * self.sample_rate) / 512))
        logger.debug("VAD max chunks adjusted to %d (%.1fs)", self.max_chunks, max_seconds)

    def reset(self) -> None:
        """Reset internal speech accumulation state."""
        self.is_speech_active = False
        self.consecutive_silence_chunks = 0
        self.speech_chunks: list[np.ndarray] = []
        if hasattr(self.model, "reset_states"):
            self.model.reset_states()

    def process_chunk(self, chunk: np.ndarray, pre_roll: list[np.ndarray] | None = None) -> np.ndarray | None:
        """Process a 512-sample audio chunk (float32, 16kHz).

        Returns:
            np.ndarray of completed utterance trimmed of trailing silence if concluded, otherwise None.
        """
        if len(chunk) != 512:
            if len(chunk) < 512:
                padded = np.zeros(512, dtype=np.float32)
                padded[:len(chunk)] = chunk
                chunk_tensor = torch.from_numpy(padded)
            else:
                chunk_tensor = torch.from_numpy(chunk[:512])
        else:
            chunk_tensor = torch.from_numpy(chunk)

        try:
            speech_prob = self.model(chunk_tensor, self.sample_rate).item()
        except Exception as e:
            logger.debug("VAD inference error: %s", e)
            return None

        if not self.is_speech_active:
            # Trigger speech start only on confident speech probability
            if speech_prob >= self.start_threshold:
                self.is_speech_active = True
                self.consecutive_silence_chunks = 0
                self.speech_chunks = []
                if pre_roll:
                    self.speech_chunks.extend(pre_roll)
                self.speech_chunks.append(chunk)
                logger.debug("VAD: speech start (prob=%.2f)", speech_prob)
            return None

        # Speech is currently active:
        self.speech_chunks.append(chunk)

        if speech_prob >= self.start_threshold:
            # Clear speech continuing; reset silence counter
            self.consecutive_silence_chunks = 0
        elif speech_prob < self.end_threshold:
            # Clear silence
            self.consecutive_silence_chunks += 1
            if self.consecutive_silence_chunks >= self.silence_timeout_chunks:
                logger.debug("VAD: silence timeout reached (%d chunks = %.0fms)",
                             self.consecutive_silence_chunks,
                             (self.consecutive_silence_chunks * 512 / self.sample_rate) * 1000)
                return self._finalize_utterance()
        else:
            # Ambiguous zone [end_threshold, start_threshold] (e.g. trailing breath / murmur)
            # Count slowly towards silence timeout so trailing noise doesn't trap utterance open indefinitely
            self.consecutive_silence_chunks += 1
            if self.consecutive_silence_chunks >= (self.silence_timeout_chunks + 3):
                return self._finalize_utterance()

        # Hard cutoff if max duration reached (e.g. in noisy rooms)
        if len(self.speech_chunks) >= self.max_chunks:
            logger.debug("VAD: max duration reached (%d chunks)", len(self.speech_chunks))
            return self._finalize_utterance()

        return None

    def _finalize_utterance(self) -> np.ndarray | None:
        """Finalize, trim trailing silence, and validate accumulated utterance."""
        total_chunks = len(self.speech_chunks)
        chunks = self.speech_chunks
        silence_to_trim = min(self.consecutive_silence_chunks, total_chunks)
        self.reset()

        # Check if duration meets minimum threshold
        speech_chunks_count = total_chunks - silence_to_trim
        if speech_chunks_count < self.min_speech_chunks:
            logger.debug("Discarding short utterance (%d speech chunks < min %d)",
                         speech_chunks_count, self.min_speech_chunks)
            return None

        # Trim trailing silence so Whisper doesn't spend time encoding dead air
        if silence_to_trim > 0 and len(chunks) > silence_to_trim:
            chunks = chunks[:-silence_to_trim]

        utterance = np.concatenate(chunks).astype(np.float32)
        rms = float(np.sqrt(np.mean(utterance**2)))
        if rms < 0.003:
            logger.debug("Discarding near-silent utterance (RMS=%.5f)", rms)
            return None

        duration_ms = (len(utterance) / self.sample_rate) * 1000
        logger.info("VAD utterance captured: duration=%.0fms (trimmed %d silence chunks), rms=%.4f",
                    duration_ms, silence_to_trim, rms)
        return utterance
