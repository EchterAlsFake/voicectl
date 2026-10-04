"""Audio volume and mute management using WirePlumber (wpctl)."""

from __future__ import annotations

import logging
import shutil
import subprocess
from voicectl.actions.base import Action, get_user_env

logger = logging.getLogger(__name__)


class VolumeAction(Action):
    """Controls PipeWire audio volume and mute state via WirePlumber wpctl."""

    def __init__(
        self,
        action_type: str,
        step: float = 0.05,
        limit: float = 1.0,
        value: float | None = None,
    ) -> None:
        self.action_type = action_type.lower()  # "up", "down", "mute", "set"
        self.step = step
        self.limit = limit
        self.value = value

    @property
    def description(self) -> str:
        if self.action_type == "up":
            return f"volume:+{int(self.step * 100)}% (limit {int(self.limit * 100)}%)"
        elif self.action_type == "down":
            return f"volume:-{int(self.step * 100)}%"
        elif self.action_type == "mute":
            return "volume:toggle_mute"
        elif self.action_type == "set":
            val_pct = int((self.value if self.value is not None else 0.0) * 100)
            return f"volume:set {val_pct}%"
        return f"volume:{self.action_type}"

    def execute(self) -> bool:
        if not shutil.which("wpctl"):
            logger.error("wpctl is not installed or not in PATH")
            return False

        if self.action_type == "up":
            cmd = ["wpctl", "set-volume", "-l", f"{self.limit:.2f}", "@DEFAULT_AUDIO_SINK@", f"{self.step:.2f}+"]
        elif self.action_type == "down":
            cmd = ["wpctl", "set-volume", "-l", f"{self.limit:.2f}", "@DEFAULT_AUDIO_SINK@", f"{self.step:.2f}-"]
        elif self.action_type == "mute":
            cmd = ["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"]
        elif self.action_type == "set":
            val = max(0.0, min(self.limit, self.value if self.value is not None else 0.5))
            cmd = ["wpctl", "set-volume", "-l", f"{self.limit:.2f}", "@DEFAULT_AUDIO_SINK@", f"{val:.2f}"]
        else:
            logger.error("Unsupported volume action: %s", self.action_type)
            return False

        env = get_user_env()
        try:
            res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=2.0)
            if res.returncode != 0:
                logger.error("wpctl failed (code %d): %s", res.returncode, res.stderr.strip())
                return False
            return True
        except Exception as e:
            logger.error("Error executing wpctl: %s", e)
            return False
