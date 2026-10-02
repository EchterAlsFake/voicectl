"""Voice Activity Detection using Silero VAD (ONNX)."""

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
    """Detects speech segments and segments continuous audio into complete utterances."""

    def __init__(self, config: VADConfig, sample_rate: int = 16000) -> None:
        self.config = config
        self.sample_rate = sample_rate
        self.threshold = config.threshold
        self.silence_timeout_chunks = max(1, int((config.silence_timeout_ms / 1000.0) * sample_rate / 512))
        self.min_speech_chunks = max(1, int((config.min_speech_duration_ms / 1000.0) * sample_rate / 512))
        self.max_chunks = int((config.max_speech_duration_s * sample_rate) / 512)

        logger.info("Initializing Silero VAD ONNX model...")
        self.model = silero_vad.load_silero_vad(onnx=True)
        self.reset()

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
            np.ndarray of completed utterance if an utterance just concluded, otherwise None.
        """
        if len(chunk) != 512:
            # Silero expects 512 samples at 16kHz
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

        is_voice = speech_prob >= self.threshold

        if is_voice:
            if not self.is_speech_active:
                # Speech just started!
                self.is_speech_active = True
                self.consecutive_silence_chunks = 0
                self.speech_chunks = []
                # Prepend pre-roll buffer to prevent cutting off the first syllable
                if pre_roll:
                    self.speech_chunks.extend(pre_roll)
                logger.debug("VAD: speech start (prob=%.2f)", speech_prob)

            self.speech_chunks.append(chunk)
            self.consecutive_silence_chunks = 0

            # Force cut if utterance reached maximum duration
            if len(self.speech_chunks) >= self.max_chunks:
                logger.debug("VAD: max duration reached (%d chunks)", len(self.speech_chunks))
                return self._finalize_utterance()

        else:
            if self.is_speech_active:
                # Still within a speech segment, but current chunk is silent
                self.speech_chunks.append(chunk)
                self.consecutive_silence_chunks += 1

                if self.consecutive_silence_chunks >= self.silence_timeout_chunks:
                    # Speech segment concluded
                    logger.debug("VAD: speech end detected after %d chunks of silence",
                                 self.consecutive_silence_chunks)
                    return self._finalize_utterance()

        return None

    def _finalize_utterance(self) -> np.ndarray | None:
        """Finalize and validate current accumulated speech utterance."""
        total_chunks = len(self.speech_chunks)
        chunks = self.speech_chunks
        self.reset()

        # Check if duration meets minimum threshold
        if total_chunks < self.min_speech_chunks:
            logger.debug("Discarding short utterance (%d chunks < min %d)",
                         total_chunks, self.min_speech_chunks)
            return None

        utterance = np.concatenate(chunks).astype(np.float32)
        # Check energy / RMS to ensure it's not silent hiss
        rms = float(np.sqrt(np.mean(utterance**2)))
        if rms < 0.003:
            logger.debug("Discarding near-silent utterance (RMS=%.5f)", rms)
            return None

        duration_ms = (len(utterance) / self.sample_rate) * 1000
        logger.info("VAD utterance captured: duration=%.0fms, samples=%d, rms=%.4f",
                    duration_ms, len(utterance), rms)
        return utterance
