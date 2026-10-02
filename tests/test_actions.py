"""Unit tests for allowlisted action dispatchers."""

import pytest
from voicectl.actions.keyboard import KeyAction, KEY_MAP
from voicectl.actions.audio import VolumeAction
from voicectl.actions.media import MediaAction, ALLOWLISTED_PLAYERCTL_COMMANDS
from voicectl.actions.hyprland import HyprlandAction, ALLOWLISTED_HYPRLAND_DISPATCHERS
from voicectl.actions.script import ScriptAction


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
