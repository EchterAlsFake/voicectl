"""Base abstract class for Speech Recognition backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
import numpy as np


class ASRBackend(ABC):
    """Abstract speech recognition backend."""

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Name of the backend engine."""
        pass

    @property
    @abstractmethod
    def device_name(self) -> str:
        """Hardware device being used (e.g. NPU, CPU)."""
        pass

    @abstractmethod
    def transcribe(self, audio: np.ndarray, language: str = "en") -> tuple[str, float]:
        """Transcribe 16kHz mono audio.

        Returns:
            tuple of (transcript_text, latency_ms)
        """
        pass
