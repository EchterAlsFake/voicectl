"""Base class for allowlisted action dispatchers."""

from __future__ import annotations

import logging
import os
import subprocess
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


def get_user_env() -> dict[str, str]:
    """Ensure environment has required Wayland, Hyprland, and DBus variables."""
    env = os.environ.copy()
    uid = os.getuid()
    runtime_dir = env.get("XDG_RUNTIME_DIR", f"/run/user/{uid}")
    env["XDG_RUNTIME_DIR"] = runtime_dir

    # Auto-detect WAYLAND_DISPLAY if missing
    if "WAYLAND_DISPLAY" not in env or not env["WAYLAND_DISPLAY"]:
        for name in ["wayland-1", "wayland-0"]:
            sock = os.path.join(runtime_dir, name)
            if os.path.exists(sock):
                env["WAYLAND_DISPLAY"] = name
                break

    # Auto-detect HYPRLAND_INSTANCE_SIGNATURE if missing
    if "HYPRLAND_INSTANCE_SIGNATURE" not in env or not env["HYPRLAND_INSTANCE_SIGNATURE"]:
        hypr_dir = os.path.join(runtime_dir, "hypr")
        if os.path.isdir(hypr_dir):
            entries = [e for e in os.listdir(hypr_dir) if not e.endswith(".lock")]
            if entries:
                env["HYPRLAND_INSTANCE_SIGNATURE"] = entries[0]

    return env


class Action(ABC):
    """Abstract allowlisted action."""

    @abstractmethod
    def execute(self) -> bool:
        """Execute the action. Returns True on success."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of the action."""
        pass
