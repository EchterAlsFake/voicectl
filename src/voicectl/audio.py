"""Audio capture and device management using sounddevice and PipeWire."""

from __future__ import annotations

import collections
import logging
import queue
import threading
import time
from typing import Callable, Iterator

import numpy as np
import sounddevice as sd

from voicectl.config import AudioConfig

logger = logging.getLogger(__name__)


def list_input_devices() -> list[dict[str, object]]:
    """List available audio input devices."""
    devices = []
    default_dev = sd.default.device[0]
    for idx, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            devices.append({
                "index": idx,
                "name": dev["name"],
                "channels": dev["max_input_channels"],
                "default_samplerate": dev["default_samplerate"],
                "is_default": (idx == default_dev),
            })
    return devices


def get_default_microphone_name() -> str:
    """Get the name of the default input microphone."""
    try:
        dev_id = sd.default.device[0]
        if dev_id is not None and dev_id >= 0:
            info = sd.query_devices(dev_id)
            return str(info.get("name", "Unknown"))
    except Exception as e:
        logger.debug("Failed to query default microphone: %s", e)
    return "Default System Microphone"


class AudioCapture:
    """Captures mono audio stream with pre-roll buffering."""

    def __init__(self, config: AudioConfig, pre_roll_ms: int = 300) -> None:
        self.config = config
        self.sample_rate = config.sample_rate
        self.block_size = config.block_size
        self.device = config.device if config.device != "default" else None

        # Pre-roll ring buffer holds blocks prior to speech trigger
        blocks_in_pre_roll = max(1, int((pre_roll_ms / 1000.0) * self.sample_rate / self.block_size))
        self.pre_roll = collections.deque(maxlen=blocks_in_pre_roll)

        self.gain = float(getattr(config, "gain", 1.0))

        self._queue: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=100)
        self._stream: sd.InputStream | None = None
        self._running = False
        self._lock = threading.Lock()

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info: object, status: sd.CallbackFlags) -> None:
        if status:
            logger.debug("Audio input status flag: %s", status)
        if not self._running:
            return

        # indata is float32 shape (frames, channels)
        chunk = indata[:, 0].copy()
        if self.gain != 1.0:
            chunk = chunk * self.gain
        try:
            self._queue.put_nowait(chunk)
        except queue.Full:
            # Drop oldest if queue is backed up
            try:
                _ = self._queue.get_nowait()
                self._queue.put_nowait(chunk)
            except (queue.Empty, queue.Full):
                pass

    def start(self) -> None:
        """Start the audio input stream."""
        with self._lock:
            if self._running:
                return
            self._running = True

            logger.info("Opening audio stream: device=%s, sr=%d, block_size=%d",
                        self.device or "default", self.sample_rate, self.block_size)
            try:
                self._stream = sd.InputStream(
                    device=self.device,
                    samplerate=self.sample_rate,
                    channels=1,
                    dtype="float32",
                    blocksize=self.block_size,
                    callback=self._audio_callback,
                )
                self._stream.start()
            except Exception as e:
                self._running = False
                logger.error("Failed to start sounddevice InputStream: %s", e)
                raise

    def stop(self) -> None:
        """Stop the audio input stream."""
        with self._lock:
            self._running = False
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception as e:
                    logger.debug("Error stopping audio stream: %s", e)
                finally:
                    self._stream = None
            # Push sentinel to unblock any waiting consumer
            self._queue.put(None)

    def read_block(self, timeout: float = 1.0) -> np.ndarray | None:
        """Read a single block of audio samples."""
        try:
            chunk = self._queue.get(timeout=timeout)
            if chunk is None:
                return None
            self.pre_roll.append(chunk)
            return chunk
        except queue.Empty:
            return None

    def get_pre_roll(self) -> list[np.ndarray]:
        """Return a copy of the current pre-roll buffer chunks."""
        return list(self.pre_roll)

    def is_active(self) -> bool:
        return self._running and self._stream is not None and self._stream.active
