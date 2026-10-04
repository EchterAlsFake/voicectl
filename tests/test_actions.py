"""Unit tests for allowlisted action dispatchers."""

import pytest
from unittest.mock import patch
from voicectl.actions.keyboard import KeyAction, TypeTextAction, KEY_MAP
from voicectl.actions.audio import VolumeAction
from voicectl.actions.media import MediaAction, ALLOWLISTED_PLAYERCTL_COMMANDS
from voicectl.actions.hyprland import HyprlandAction, ALLOWLISTED_HYPRLAND_DISPATCHERS
from voicectl.actions.script import ScriptAction
from voicectl.actions.screenshot import ScreenshotAction


def test_keyboard_action_mapping():
    act_right = KeyAction("Right")
    assert act_right.key_sym == "Right"
    assert act_right.description == "key:Right"

    act_esc = KeyAction("ESC")
    assert act_esc.key_sym == "Escape"
    assert act_esc.description == "key:Escape"

    act_f5 = KeyAction("F5")
    assert act_f5.key_sym == "F5"

    act_mod = KeyAction("Right", modifiers=["Alt", "Control"])
    assert act_mod.description == "key:Alt+Control+Right"


def test_volume_action():
    act_up = VolumeAction("up", step=0.05, limit=1.0)
    assert act_up.step == 0.05
    assert act_up.limit == 1.0
    assert "volume:+5%" in act_up.description

    act_mute = VolumeAction("mute")
    assert act_mute.description == "volume:toggle_mute"


def test_media_action_allowlist():
    for cmd in ["play", "pause", "play-pause", "next", "previous"]:
        act = MediaAction(cmd)
        assert act.command in ALLOWLISTED_PLAYERCTL_COMMANDS.values()

    # Disallowed command must raise ValueError
    with pytest.raises(ValueError):
        MediaAction("rm -rf /")

    with pytest.raises(ValueError):
        MediaAction("bash")


def test_hyprland_action_allowlist():
    act = HyprlandAction("fullscreen")
    assert act.dispatcher == "fullscreen"
    assert "hyprland:fullscreen" in act.description

    with pytest.raises(ValueError):
        HyprlandAction("malicious_command")


def test_script_action_security(tmp_path):
    # Non-existent script must raise FileNotFoundError
    with pytest.raises(FileNotFoundError):
        ScriptAction("/non/existent/script.sh")

    # Non-executable script must raise PermissionError
    test_file = tmp_path / "test.sh"
    test_file.write_text("#!/bin/sh\necho hello\n")
    with pytest.raises(PermissionError):
        ScriptAction(str(test_file))


def test_screenshot_action_mapping():
    act = ScreenshotAction()
    assert act.mode == "region"
    assert act.clipboard is True
    assert act.description == "screenshot:region:with_clipboard"

    act_no_clip = ScreenshotAction(clipboard=False)
    assert act_no_clip.mode == "region"
    assert act_no_clip.clipboard is False
    assert act_no_clip.description == "screenshot:region:no_clipboard"

    act_full = ScreenshotAction(mode="full", clipboard=False)
    assert act_full.mode == "full"
    assert act_full.description == "screenshot:full:no_clipboard"

    with pytest.raises(ValueError):
        ScreenshotAction(mode="invalid_mode")


@patch("shutil.which")
@patch("subprocess.Popen")
def test_screenshot_action_execution_dms(mock_popen, mock_which):
    mock_which.side_effect = lambda cmd: "/usr/bin/dms" if cmd == "dms" else None

    # Screenshot with clipboard
    act = ScreenshotAction(mode="region", clipboard=True)
    assert act.execute() is True
    mock_popen.assert_called_with(["dms", "screenshot"], env=mock_popen.call_args.kwargs["env"])

    # Screenshot without clipboard
    act_no_clip = ScreenshotAction(mode="region", clipboard=False)
    assert act_no_clip.execute() is True
    mock_popen.assert_called_with(["dms", "screenshot", "--no-clipboard"], env=mock_popen.call_args.kwargs["env"])

    # Full screenshot without clipboard
    act_full_no_clip = ScreenshotAction(mode="full", clipboard=False)
    assert act_full_no_clip.execute() is True
    mock_popen.assert_called_with(["dms", "screenshot", "full", "--no-clipboard"], env=mock_popen.call_args.kwargs["env"])


def test_type_text_action():
    act = TypeTextAction("Hello world!")
    assert "type:'Hello world!'" in act.description
    assert act.text == "Hello world!"
    assert act.delay_ms == 1

    act_long = TypeTextAction("This is a very long text that exceeds thirty characters")
    assert act_long.description.endswith("...'")


@patch("shutil.which")
@patch("subprocess.run")
def test_type_text_action_execution(mock_run, mock_which):
    mock_which.return_value = "/usr/bin/wtype"
    mock_run.return_value.returncode = 0

    act = TypeTextAction("Hello from Jarvis", delay_ms=2)
    assert act.execute() is True
    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args[0] == ["wtype", "-d", "2", "--", "Hello from Jarvis"]


