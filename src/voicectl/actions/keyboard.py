"""Wayland keyboard event injection using wtype."""

from __future__ import annotations

import logging
import shutil
import subprocess
from voicectl.actions.base import Action, get_user_env

logger = logging.getLogger(__name__)

# Mapping from friendly key names to wtype / XKB keysyms
KEY_MAP = {
    "RIGHT": "Right",
    "LEFT": "Left",
    "UP": "Up",
    "DOWN": "Down",
    "F5": "F5",
    "ESC": "Escape",
    "ESCAPE": "Escape",
    "SPACE": "space",
    "PAGEUP": "Prior",
    "PRIOR": "Prior",
    "PAGEDOWN": "Next",
    "NEXT": "Next",
    "RETURN": "Return",
    "ENTER": "Return",
    "B": "b",
    "W": "w",
}


class KeyAction(Action):
    """Simulates keyboard key presses on Wayland via wtype."""

    def __init__(self, key: str, modifiers: list[str] | None = None) -> None:
        self.raw_key = key
        clean_key = key.strip().upper()
        self.key_sym = KEY_MAP.get(clean_key, key.strip())
        self.modifiers = modifiers or []

    @property
    def description(self) -> str:
        mod_prefix = "+".join(self.modifiers) + "+" if self.modifiers else ""
        return f"key:{mod_prefix}{self.key_sym}"

    def execute(self) -> bool:
        if not shutil.which("wtype"):
            logger.error("wtype is not installed or not in PATH")
            return False

        cmd = ["wtype"]
        for mod in self.modifiers:
            cmd.extend(["-M", mod.lower()])

        cmd.extend(["-k", self.key_sym])

        for mod in reversed(self.modifiers):
            cmd.extend(["-m", mod.lower()])

        env = get_user_env()
        try:
            logger.debug("Executing key event: %s (WAYLAND_DISPLAY=%s)", cmd, env.get("WAYLAND_DISPLAY"))
            res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=2.0)
            if res.returncode != 0:
                logger.error("wtype failed (code %d): %s", res.returncode, res.stderr.strip())
                return False
            return True
        except Exception as e:
            logger.error("Error executing key action %s: %s", self.key_sym, e)
            return False
