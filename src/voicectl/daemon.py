"""Core background daemon for voicectl."""

from __future__ import annotations

import json
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

from voicectl.actions.base import get_user_env
from voicectl.asr.base import ASRBackend
from voicectl.asr.factory import create_asr_backend
from voicectl.audio import AudioCapture, get_default_microphone_name
from voicectl.commands import CommandMatcher
from voicectl.config import Config, DEFAULT_CONFIG_PATH
from voicectl.vad import SileroVADDetector

logger = logging.getLogger("voicectl")


def get_socket_path() -> Path:
    """Determine the path to the voicectl IPC socket."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir and os.path.isdir(runtime_dir):
        return Path(runtime_dir) / "voicectl.sock"
    return Path(f"/tmp/voicectl-{os.getuid()}.sock")


def send_desktop_notification(title: str, message: str) -> None:
    """Send a lightweight desktop notification via notify-send."""
    env = get_user_env()
    try:
        subprocess.run(
            ["notify-send", "-a", "voicectl", "-i", "audio-input-microphone", title, message],
            env=env,
            capture_output=True,
            timeout=2.0,
        )
    except Exception as e:
        logger.debug("Failed to send desktop notification: %s", e)


class VoiceCtlDaemon:
    """Main voicectl daemon orchestrating audio, VAD, ASR, and action dispatch."""

    def __init__(self, config_path: Path | str | None = None) -> None:
        self.config = Config.load(config_path)
        self.mode = self.config.general.default_mode.lower()
        self.start_time = time.time()

        self.last_command: str = "none"
        self.last_transcript: str = "none"
        self.last_latency_ms: float = 0.0
        self.total_commands_executed: int = 0

        self._running = False
        self._shutdown_event = threading.Event()

        # Initialize subsystems
        logger.info("Initializing voicectl daemon in '%s' mode...", self.mode)
        self.matcher = CommandMatcher(self.config)
        self.audio = AudioCapture(self.config.audio, pre_roll_ms=self.config.vad.pre_roll_ms)
        self.vad = SileroVADDetector(self.config.vad, sample_rate=self.config.audio.sample_rate)
        self.vad.set_max_duration(2.0 if self.mode == "presentation" else 4.5)
        self.asr: ASRBackend = create_asr_backend(self.config.asr)

        self.socket_path = get_socket_path()
        self._server_socket: socket.socket | None = None
        self._ipc_thread: threading.Thread | None = None

    def set_mode(self, new_mode: str) -> bool:
        """Change the operational mode (presentation, normal, off)."""
        valid_modes = {"presentation", "normal", "off"}
        clean_mode = new_mode.strip().lower()
        if clean_mode not in valid_modes:
            logger.warning("Invalid mode '%s'; must be one of %s", new_mode, valid_modes)
            return False

        old_mode = self.mode
        self.mode = clean_mode
        self.vad.reset()
        self.vad.set_max_duration(2.0 if self.mode == "presentation" else 4.5)
        logger.info("Operating mode changed: %s -> %s", old_mode, self.mode)

        if self.config.general.notify_on_mode_change:
            title = "voicectl"
            msg = f"{clean_mode.capitalize()} mode enabled"
            if clean_mode == "off":
                msg = "Voice control disabled (off)"
            send_desktop_notification(title, msg)

        return True

    def toggle_mode(self) -> str:
        """Cycle mode: presentation -> normal -> off -> presentation."""
        cycle = {"presentation": "normal", "normal": "off", "off": "presentation"}
        next_mode = cycle.get(self.mode, "presentation")
        self.set_mode(next_mode)
        return next_mode

    def get_status_dict(self) -> dict[str, Any]:
        """Return live metrics and status information."""
        return {
            "service": "running",
            "mode": self.mode,
            "microphone": get_default_microphone_name(),
            "asr_backend": self.asr.backend_name,
            "inference_device": self.asr.device_name,
            "vad": "active" if self.audio.is_active() else "inactive",
            "last_command": self.last_command,
            "last_transcript": self.last_transcript,
            "last_latency_ms": round(self.last_latency_ms, 1),
            "total_commands": self.total_commands_executed,
            "uptime_seconds": round(time.time() - self.start_time, 1),
        }

    def _start_ipc_server(self) -> None:
        """Start listening on UNIX domain socket for CLI requests."""
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError:
                pass

        self._server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server_socket.bind(str(self.socket_path))
        self._server_socket.listen(5)
        self._server_socket.settimeout(0.5)

        logger.info("IPC control socket listening at %s", self.socket_path)

        def ipc_worker() -> None:
            while not self._shutdown_event.is_set():
                try:
                    conn, _ = self._server_socket.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break

                with conn:
                    try:
                        data = conn.recv(4096)
                        if not data:
                            continue
                        req = json.loads(data.decode("utf-8"))
                        action = req.get("action", "")

                        resp: dict[str, Any] = {"ok": True}

                        if action == "status":
                            resp["data"] = self.get_status_dict()
                        elif action == "set_mode":
                            req_mode = req.get("mode", "")
                            success = self.set_mode(req_mode)
                            resp["ok"] = success
                            resp["mode"] = self.mode
                        elif action == "toggle_mode":
                            new_m = self.toggle_mode()
                            resp["mode"] = new_m
                        elif action == "test_command":
                            phrase = req.get("phrase", "")
                            cmd = self.matcher.match(phrase, mode=self.mode)
                            if cmd:
                                t0 = time.perf_counter()
                                ok = cmd.action.execute()
                                dt = (time.perf_counter() - t0) * 1000
                                resp["matched"] = cmd.id
                                resp["action"] = cmd.action.description
                                resp["latency_ms"] = round(dt, 1)
                                resp["executed"] = ok
                            else:
                                resp["ok"] = False
                                resp["error"] = f"No command matched for '{phrase}' in mode '{self.mode}'"
                        else:
                            resp["ok"] = False
                            resp["error"] = f"Unknown action '{action}'"

                        conn.sendall(json.dumps(resp).encode("utf-8"))
                    except Exception as e:
                        logger.error("IPC handling error: %s", e)
                        try:
                            conn.sendall(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
                        except Exception:
                            pass

        self._ipc_thread = threading.Thread(target=ipc_worker, daemon=True, name="voicectl-ipc")
        self._ipc_thread.start()

    def start(self) -> None:
        """Start the voicectl daemon processing loop."""
        self._running = True
        self._start_ipc_server()
        self.audio.start()

        if self.config.general.notify_on_mode_change:
            send_desktop_notification("voicectl", f"Started in {self.mode} mode ({self.asr.device_name})")

        logger.info("voicectl daemon running [Mode: %s | Backend: %s (%s) | Mic: %s]",
                    self.mode, self.asr.backend_name, self.asr.device_name, get_default_microphone_name())

        try:
            while self._running and not self._shutdown_event.is_set():
                chunk = self.audio.read_block(timeout=0.2)
                if chunk is None:
                    continue

                if self.mode == "off":
                    # In off mode, discard audio without running VAD or ASR
                    continue

                # Pass chunk to VAD
                utterance = self.vad.process_chunk(chunk, pre_roll=self.audio.get_pre_roll())
                if utterance is None:
                    continue

                # An utterance completed! Transcribe it.
                logger.debug("Transcribing utterance on %s...", self.asr.device_name)
                try:
                    transcript, asr_dt_ms = self.asr.transcribe(utterance, language=self.config.asr.language)
                except Exception as e:
                    logger.error("Speech recognition error: %s", e)
                    continue

                transcript_clean = transcript.strip()
                if not transcript_clean:
                    continue

                self.last_transcript = transcript_clean
                logger.info("Transcript: \"%s\" (ASR latency: %.1fms)", transcript_clean, asr_dt_ms)

                # Match against allowlisted commands
                cmd = self.matcher.match(transcript_clean, mode=self.mode)
                if cmd is None:
                    logger.debug("No matching command in mode '%s' for: \"%s\"", self.mode, transcript_clean)
                    continue

                # Dispatch allowlisted action
                t_act_start = time.perf_counter()
                action_ok = cmd.action.execute()
                act_dt_ms = (time.perf_counter() - t_act_start) * 1000.0
                total_latency_ms = asr_dt_ms + act_dt_ms

                self.last_command = cmd.id
                self.last_latency_ms = total_latency_ms
                self.total_commands_executed += 1

                logger.info("COMMAND MATCHED: [%s] -> %s | Latency: %.1fms (asr=%.1fms, act=%.1fms) | Success=%s",
                            cmd.id, cmd.action.description, total_latency_ms, asr_dt_ms, act_dt_ms, action_ok)

                if self.config.general.notify_on_command:
                    send_desktop_notification("Voice Action", f"{cmd.id} ({total_latency_ms:.0f}ms)")

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received.")
        finally:
            self.stop()

    def stop(self) -> None:
        """Gracefully stop all daemon subsystems."""
        if not self._running:
            return
        self._running = False
        logger.info("Shutting down voicectl daemon...")
        self._shutdown_event.set()

        self.audio.stop()

        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError:
                pass

        logger.info("voicectl daemon stopped.")


def run_daemon(config_path: Path | str | None = None) -> None:
    """Configure logging and run the daemon."""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    daemon = VoiceCtlDaemon(config_path)

    def sig_handler(sig: int, frame: object) -> None:
        logger.info("Signal %d received, stopping...", sig)
        daemon.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    daemon.start()
