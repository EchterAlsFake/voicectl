"""Command-line interface for voicectl."""

from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def get_socket_path() -> Path:
    """Determine the path to the voicectl IPC socket."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir and os.path.isdir(runtime_dir):
        return Path(runtime_dir) / "voicectl.sock"
    return Path(f"/tmp/voicectl-{os.getuid()}.sock")


def send_ipc_request(request: dict[str, Any], timeout: float = 2.0) -> dict[str, Any] | None:
    """Send a JSON request to the running daemon over the UNIX domain socket."""
    sock_path = get_socket_path()
    if not sock_path.exists():
        return None

    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(str(sock_path))
            sock.sendall(json.dumps(request).encode("utf-8"))
            data = sock.recv(4096)
            if data:
                return json.loads(data.decode("utf-8"))
    except Exception as e:
        logger.debug("IPC request failed: %s", e)
    return None


def cmd_start(args: argparse.Namespace) -> None:
    """Start the voicectl user service via systemd."""
    print("Starting voicectl systemd user service...")
    res = subprocess.run(["systemctl", "--user", "start", "voicectl.service"], capture_output=True, text=True)
    if res.returncode == 0:
        time.sleep(0.5)
        print("voicectl service started successfully.")
        cmd_status(args)
    else:
        print(f"Error starting voicectl service: {res.stderr.strip()}", file=sys.stderr)
        sys.exit(res.returncode)


def cmd_stop(args: argparse.Namespace) -> None:
    """Stop the voicectl user service via systemd."""
    print("Stopping voicectl systemd user service...")
    res = subprocess.run(["systemctl", "--user", "stop", "voicectl.service"], capture_output=True, text=True)
    if res.returncode == 0:
        print("voicectl service stopped.")
    else:
        print(f"Error stopping voicectl service: {res.stderr.strip()}", file=sys.stderr)
        sys.exit(res.returncode)


def cmd_status(args: argparse.Namespace) -> None:
    """Show live status of voicectl daemon and audio subsystems."""
    resp = send_ipc_request({"action": "status"})
    as_json = getattr(args, "json", False)

    if resp and resp.get("ok"):
        data = resp.get("data", {})
        if as_json:
            data["available"] = True
            print(json.dumps(data))
            return

        print("========================================")
        print("            voicectl status             ")
        print("========================================")
        print(f"Service:          {data.get('service', 'running')}")
        print(f"Mode:             {data.get('mode', 'unknown').upper()}")
        print(f"Microphone:       {data.get('microphone', 'unknown')}")
        print(f"ASR backend:      {data.get('asr_backend', 'unknown')}")
        print(f"Model:            {data.get('model', 'unknown')}")
        print(f"Inference device: {data.get('inference_device', 'unknown')}")
        print(f"VAD:              {data.get('vad', 'unknown')}")
        print(f"Last command:     {data.get('last_command', 'none')}")
        print(f"Last transcript:  \"{data.get('last_transcript', 'none')}\"")
        print(f"Last latency:     {data.get('last_latency_ms', 0)} ms")
        print(f"Total commands:   {data.get('total_commands', 0)}")
        print(f"Uptime:           {data.get('uptime_seconds', 0)} s")
        print("========================================")
    else:
        # Check systemd user service state
        res = subprocess.run(["systemctl", "--user", "is-active", "voicectl.service"], capture_output=True, text=True)
        state = res.stdout.strip() or "inactive"
        if as_json:
            print(json.dumps({"service": state, "mode": "off", "available": False}))
            return

        print("========================================")
        print("            voicectl status             ")
        print("========================================")
        print(f"Service:          {state} (daemon not responding on socket)")
        print("Run 'voicectl start' to start the service,")
        print("or 'voicectl run' to launch in the foreground.")
        print("========================================")


def cmd_toggle(args: argparse.Namespace) -> None:
    """Toggle/cycle the daemon operational mode."""
    as_json = getattr(args, "json", False)
    resp = send_ipc_request({"action": "toggle_mode"})
    if resp and resp.get("ok"):
        new_mode = resp.get("mode", "presentation")
        if as_json:
            print(json.dumps({"mode": new_mode, "ok": True}))
        else:
            print(f"Mode cycled to: {new_mode}")
    else:
        if as_json:
            print(json.dumps({"ok": False, "error": "Daemon not running"}))
        else:
            print("Error: voicectl daemon is not running. Start it with 'voicectl start'.", file=sys.stderr)
        sys.exit(1)


def cmd_mode(args: argparse.Namespace) -> None:
    """Set the daemon operational mode (off, normal, presentation, toggle)."""
    target_mode = args.mode.lower()
    as_json = getattr(args, "json", False)

    if target_mode == "toggle":
        cmd_toggle(args)
        return

    resp = send_ipc_request({"action": "set_mode", "mode": target_mode})
    if resp and resp.get("ok"):
        new_mode = resp.get("mode", target_mode)
        if as_json:
            print(json.dumps({"mode": new_mode, "ok": True}))
        else:
            print(f"Mode changed to: {new_mode}")
    else:
        err = resp.get("error", "Failed to change mode") if resp else "voicectl daemon is not running"
        if as_json:
            print(json.dumps({"ok": False, "error": err}))
        else:
            print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)


def cmd_devices(args: argparse.Namespace) -> None:
    """List available audio capture devices."""
    from voicectl.audio import list_input_devices
    devices = list_input_devices()
    print("Available audio input devices:")
    print("------------------------------------------------------------")
    for d in devices:
        default_tag = " [DEFAULT]" if d["is_default"] else ""
        print(f"[{d['index']}] {d['name']}{default_tag}")
        print(f"    Channels: {d['channels']} | Sample rate: {d['default_samplerate']} Hz")
    print("------------------------------------------------------------")


def cmd_test_mic(args: argparse.Namespace) -> None:
    """Record 2 seconds of audio to test microphone capture and levels."""
    import numpy as np
    import sounddevice as sd
    from voicectl.audio import get_default_microphone_name

    duration = 2.0
    sr = 16000
    print(f"Testing default microphone: '{get_default_microphone_name()}'")
    print(f"Recording {duration}s of audio at {sr}Hz... Speak into the microphone!")
    try:
        rec = sd.rec(int(duration * sr), samplerate=sr, channels=1, dtype="float32")
        sd.wait()
        rec_data = rec[:, 0]
        rms = float(np.sqrt(np.mean(rec_data**2)))
        peak = float(np.max(np.abs(rec_data)))
        print(f"Capture successful!")
        print(f"  Samples recorded: {len(rec_data)}")
        print(f"  RMS Energy:       {rms:.5f}")
        print(f"  Peak Amplitude:   {peak:.5f}")
        if rms < 0.002:
            print("  Note: Signal is very quiet. Check your mic mute / volume in wpctl or pavucontrol.")
        else:
            print("  Status: Microphone is healthy and receiving audio.")
    except Exception as e:
        print(f"Error capturing audio: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_test_asr(args: argparse.Namespace) -> None:
    """Test speech recognition directly on a WAV file or by recording a sample."""
    import numpy as np
    import soundfile as sf
    from voicectl.asr.factory import create_asr_backend

    cfg = Config.load()
    asr = create_asr_backend(cfg.asr)

    if args.file:
        file_path = Path(args.file).expanduser()
        if not file_path.is_file():
            print(f"Error: file not found: {file_path}", file=sys.stderr)
            sys.exit(1)
        print(f"Loading audio file: {file_path}")
        audio_data, sr = sf.read(str(file_path))
        if audio_data.ndim > 1:
            audio_data = audio_data.mean(axis=1)
        if sr != 16000:
            from scipy import signal
            num_samples = int(len(audio_data) * 16000 / sr)
            audio_data = signal.resample(audio_data, num_samples).astype(np.float32)
    else:
        import sounddevice as sd
        duration = 3.0
        sr = 16000
        print(f"Recording {duration}s of speech... Speak a command (e.g. 'next slide') now!")
        rec = sd.rec(int(duration * sr), samplerate=sr, channels=1, dtype="float32")
        sd.wait()
        audio_data = rec[:, 0]

    print(f"Running ASR inference on {asr.backend_name} ({asr.device_name})...")
    text, dt_ms = asr.transcribe(audio_data, language=cfg.asr.language)
    print("----------------------------------------")
    print(f"Recognized text:  \"{text}\"")
    print(f"Inference device: {asr.device_name}")
    print(f"Latency:          {dt_ms:.1f} ms")
    print("----------------------------------------")


def cmd_test_command(args: argparse.Namespace) -> None:
    """Test normalization, command matching, and action execution for a given phrase."""
    phrase = args.phrase
    mode = args.mode or "presentation"

    # First try via running daemon
    resp = send_ipc_request({"action": "test_command", "phrase": phrase})
    if resp and resp.get("ok"):
        print(f"Phrase:         \"{phrase}\"")
        print(f"Matched command:{resp.get('matched')}")
        print(f"Action:         {resp.get('action')}")
        print(f"Action latency: {resp.get('latency_ms')} ms")
        print(f"Executed:       {resp.get('executed')}")
        return

    # If daemon not running, test locally with CommandMatcher
    from voicectl.config import Config
    from voicectl.commands import CommandMatcher, normalize_text
    cfg = Config.load()
    matcher = CommandMatcher(cfg)
    norm = normalize_text(phrase)
    cmd = matcher.match(phrase, mode=mode)
    print(f"Input phrase:     \"{phrase}\"")
    print(f"Normalized text:  \"{norm}\"")
    print(f"Mode:             {mode}")
    if cmd:
        print(f"Matched command:  {cmd.id} ({cmd.description})")
        print(f"Action:           {cmd.action.description}")
        t0 = time.perf_counter()
        ok = cmd.action.execute()
        dt_ms = (time.perf_counter() - t0) * 1000
        print(f"Action executed:  {ok} ({dt_ms:.1f} ms)")
    else:
        print("Matched command:  NONE")


def cmd_run(args: argparse.Namespace) -> None:
    """Run voicectl daemon directly in the foreground."""
    from voicectl.daemon import run_daemon
    run_daemon(args.config)


def main() -> None:
    parser = argparse.ArgumentParser(prog="voicectl", description="Local offline voice control system for Hyprland")
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # start / stop / status
    sub_start = subparsers.add_parser("start", help="Start voicectl systemd user service")
    sub_stop = subparsers.add_parser("stop", help="Stop voicectl systemd user service")
    sub_status = subparsers.add_parser("status", help="Show live voicectl status")
    sub_status.add_argument("--json", action="store_true", help="Output status as JSON")

    # mode
    sub_mode = subparsers.add_parser("mode", help="Change operational mode")
    sub_mode.add_argument("mode", choices=["presentation", "normal", "off", "toggle"], help="Target mode")
    sub_mode.add_argument("--json", action="store_true", help="Output result as JSON")

    # toggle
    sub_toggle = subparsers.add_parser("toggle", help="Cycle operational mode")
    sub_toggle.add_argument("--json", action="store_true", help="Output result as JSON")

    # devices
    subparsers.add_parser("devices", help="List audio input devices")

    # test-mic
    subparsers.add_parser("test-mic", help="Test microphone capture and energy level")

    # test-asr
    sub_asr = subparsers.add_parser("test-asr", help="Test speech recognition on live mic or WAV file")
    sub_asr.add_argument("--file", "-f", help="Optional WAV file path to transcribe")

    # test-command
    sub_cmd = subparsers.add_parser("test-command", help="Test command matching and action dispatch")
    sub_cmd.add_argument("phrase", help="Spoken phrase to test (e.g. 'next slide')")
    sub_cmd.add_argument("--mode", "-m", choices=["presentation", "normal"], default="presentation", help="Mode profile to test against")

    # run / daemon
    sub_run = subparsers.add_parser("run", help="Run voicectl daemon in the foreground")
    sub_run.add_argument("--config", "-c", help="Path to custom config.toml")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
        "mode": cmd_mode,
        "toggle": cmd_toggle,
        "devices": cmd_devices,
        "test-mic": cmd_test_mic,
        "test-asr": cmd_test_asr,
        "test-command": cmd_test_command,
        "run": cmd_run,
    }

    fn = dispatch.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
