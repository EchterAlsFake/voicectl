"""Media playback control using playerctl."""

from __future__ import annotations

import logging
import shutil
import subprocess
from voicectl.actions.base import Action, get_user_env

logger = logging.getLogger(__name__)

ALLOWLISTED_PLAYERCTL_COMMANDS = {
    "play": "play",
    "pause": "pause",
    "play-pause": "play-pause",
    "play_pause": "play-pause",
    "next": "next",
    "previous": "previous",
    "stop": "stop",
}


class MediaAction(Action):
    """Controls MPRIS media players via playerctl."""

    def __init__(self, command: str) -> None:
        clean = command.strip().lower()
        if clean not in ALLOWLISTED_PLAYERCTL_COMMANDS:
            raise ValueError(f"Command '{command}' is not an allowlisted media command")
        self.command = ALLOWLISTED_PLAYERCTL_COMMANDS[clean]

    @property
    def description(self) -> str:
        return f"media:{self.command}"

    def execute(self) -> bool:
        if not shutil.which("playerctl"):
            logger.error("playerctl is not installed or not in PATH")
            return False

        cmd = ["playerctl", self.command]
        env = get_user_env()
        try:
            res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=2.0)
            if res.returncode != 0:
                logger.debug("playerctl returned %d: %s", res.returncode, res.stderr.strip())
                # playerctl returns 1 if no player is active; that's not fatal
                return False
            return True
        except Exception as e:
            logger.error("Error executing playerctl: %s", e)
            return False
