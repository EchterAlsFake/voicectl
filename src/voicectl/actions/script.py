"""Safe execution of explicitly configured custom user scripts."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from voicectl.actions.base import Action, get_user_env

logger = logging.getLogger(__name__)


class ScriptAction(Action):
    """Executes a user-configured script file directly without shell interpretation."""

    def __init__(self, script_path: str) -> None:
        self.path = Path(os.path.expanduser(script_path)).resolve()

        if not self.path.is_file():
            raise FileNotFoundError(f"Configured script does not exist: {self.path}")

        if not os.access(self.path, os.X_OK):
            raise PermissionError(f"Configured script is not executable: {self.path}")

    @property
    def description(self) -> str:
        return f"script:{self.path.name}"

    def execute(self) -> bool:
        env = get_user_env()
        try:
            logger.info("Executing safe user script: %s", self.path)
            res = subprocess.run([str(self.path)], env=env, capture_output=True, text=True, timeout=5.0)
            if res.returncode != 0:
                logger.error("Script '%s' returned code %d: %s", self.path.name, res.returncode, res.stderr.strip())
                return False
            return True
        except Exception as e:
            logger.error("Failed to execute script '%s': %s", self.path.name, e)
            return False
