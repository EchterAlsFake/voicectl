"""Hyprland window manager integration via hyprctl."""

from __future__ import annotations

import logging
import shutil
import subprocess
from voicectl.actions.base import Action, get_user_env

logger = logging.getLogger(__name__)

ALLOWLISTED_HYPRLAND_DISPATCHERS = {
    "workspace",
    "movetoworkspace",
    "fullscreen",
    "togglefloating",
    "killactive",
    "togglespecialworkspace",
    "dpms",
}


class HyprlandAction(Action):
    """Executes safe, allowlisted hyprctl dispatch commands."""

    def __init__(self, dispatcher: str, args: str = "") -> None:
        clean_disp = dispatcher.strip().lower()
        if clean_disp not in ALLOWLISTED_HYPRLAND_DISPATCHERS:
            raise ValueError(f"Dispatcher '{dispatcher}' is not in allowlisted Hyprland dispatchers")
        self.dispatcher = clean_disp
        self.args = args.strip()

    @property
    def description(self) -> str:
        return f"hyprland:{self.dispatcher} {self.args}".strip()

    def execute(self) -> bool:
        if not shutil.which("hyprctl"):
            logger.error("hyprctl is not installed or not in PATH")
            return False

        cmd = ["hyprctl", "dispatch", self.dispatcher]
        if self.args:
            cmd.append(self.args)

        env = get_user_env()
        try:
            res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=2.0)
            if res.returncode != 0:
                logger.error("hyprctl failed (code %d): %s", res.returncode, res.stderr.strip())
                return False
            return True
        except Exception as e:
            logger.error("Error executing hyprctl: %s", e)
            return False
