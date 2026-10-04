"""Command normalization, matching, and allowlisted action mapping."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import yaml

from voicectl.actions.base import Action
from voicectl.actions.keyboard import KeyAction, TypeTextAction
from voicectl.actions.audio import VolumeAction
from voicectl.actions.media import MediaAction
from voicectl.actions.hyprland import HyprlandAction
from voicectl.actions.script import ScriptAction
from voicectl.actions.screenshot import ScreenshotAction
from voicectl.actions.brightness import BrightnessAction
from voicectl.actions.power import PowerProfileAction
from voicectl.actions.app import AppLauncherAction
from voicectl.actions.compound import CompoundAction
from voicectl.config import Config
from voicectl.parser import NaturalCommandParser

logger = logging.getLogger(__name__)

# Filler phrases that can be safely stripped from natural speech commands
COMMON_FILLERS = [
    r"^please\s+",
    r"^can you\s+",
    r"^could you\s+",
    r"^would you\s+",
    r"^kindly\s+",
    r"^just\s+",
]


def normalize_text(text: str) -> str:
    """Normalize transcribed text: lowercase, remove punctuation, collapse whitespace."""
    if not text:
        return ""
    # Lowercase
    cleaned = text.lower().strip()
    # Replace punctuation with space
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    # Collapse multiple whitespaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def clean_natural_speech(text: str, wake_word: str | None = None) -> str:
    """Clean natural speech by optionally stripping wake word and leading fillers."""
    normalized = normalize_text(text)

    # Strip wake word if present at the start (check configured wake word + jarvis/computer)
    ww_candidates = {"jarvis", "computer"}
    if wake_word:
        ww_candidates.add(normalize_text(wake_word))

    for ww in ww_candidates:
        pattern = rf"^(?:hey\s+|hi\s+|ok\s+)?{re.escape(ww)}\b\s*"
        if re.search(pattern, normalized):
            normalized = re.sub(pattern, "", normalized).strip()
            break

    # Strip conversational fillers
    for filler in COMMON_FILLERS:
        normalized = re.sub(filler, "", normalized).strip()

    return normalized


def strip_articles(text: str) -> str:
    """Strip English articles (the, a, an) to match concise command aliases."""
    cleaned = re.sub(r"\b(the|a|an)\b", " ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


@dataclass(slots=True)
class CommandDefinition:
    id: str
    action: Action
    phrases: list[str]
    description: str = ""
    profiles: list[str] = field(default_factory=lambda: ["presentation", "normal"])


def build_default_commands(config: Config) -> dict[str, CommandDefinition]:
    """Build built-in default allowlisted commands."""
    vol_step = config.volume.step
    vol_limit = config.volume.limit

    defs: list[CommandDefinition] = [
        # Presentation controls
        CommandDefinition(
            id="next_slide",
            action=KeyAction("Right"),
            phrases=["next slide", "next slides", "next", "continue", "go forward", "advance slide", "forward"],
            description="Advance to next slide (Right Arrow)",
            profiles=["presentation", "normal"],
        ),
        CommandDefinition(
            id="previous_slide",
            action=KeyAction("Left"),
            phrases=["previous slide", "previous slides", "previous", "back", "go back", "slide back", "last slide"],
            description="Return to previous slide (Left Arrow)",
            profiles=["presentation", "normal"],
        ),
        CommandDefinition(
            id="start_presentation",
            action=KeyAction("F5"),
            phrases=["start presentation", "start slideshow", "presentation mode", "play presentation"],
            description="Start presentation (F5)",
            profiles=["presentation", "normal"],
        ),
        CommandDefinition(
            id="exit_presentation",
            action=KeyAction("Escape"),
            phrases=["exit presentation", "stop presentation", "close presentation", "end presentation", "escape"],
            description="Exit presentation (Escape)",
            profiles=["presentation", "normal"],
        ),
        CommandDefinition(
            id="black_screen",
            action=KeyAction("b"),
            phrases=["black screen", "blank screen", "black"],
            description="Toggle black screen in presentation (b)",
            profiles=["presentation"],
        ),
        CommandDefinition(
            id="white_screen",
            action=KeyAction("w"),
            phrases=["white screen", "white"],
            description="Toggle white screen in presentation (w)",
            profiles=["presentation"],
        ),

        # Audio volume controls
        CommandDefinition(
            id="volume_up",
            action=VolumeAction("up", step=vol_step, limit=vol_limit),
            phrases=[
                "volume up", "louder", "turn volume up", "increase volume",
                "make it louder", "sound up", "raise volume", "turn the volume up", "turn it up"
            ],
            description=f"Raise volume by {int(vol_step*100)}%",
            profiles=["presentation", "normal"],
        ),
        CommandDefinition(
            id="volume_down",
            action=VolumeAction("down", step=vol_step, limit=vol_limit),
            phrases=[
                "volume down", "quieter", "turn volume down", "decrease volume",
                "make it quieter", "sound down", "lower volume", "turn the volume down", "turn it down"
            ],
            description=f"Lower volume by {int(vol_step*100)}%",
            profiles=["presentation", "normal"],
        ),
        CommandDefinition(
            id="mute",
            action=VolumeAction("mute"),
            phrases=["mute", "unmute", "toggle mute", "mute audio", "silence", "mute the sound"],
            description="Toggle audio mute",
            profiles=["presentation", "normal"],
        ),

        # Media playback controls
        CommandDefinition(
            id="play_pause",
            action=MediaAction("play-pause"),
            phrases=["play pause", "toggle playback"],
            description="Toggle media play/pause",
            profiles=["normal"],
        ),
        CommandDefinition(
            id="play",
            action=MediaAction("play"),
            phrases=["play", "resume", "play music", "start music", "resume playback", "start playback"],
            description="Resume media playback",
            profiles=["normal", "presentation"],
        ),
        CommandDefinition(
            id="pause",
            action=MediaAction("pause"),
            phrases=["pause", "pause music", "stop music", "pause playback", "stop playback"],
            description="Pause media playback",
            profiles=["normal", "presentation"],
        ),
        CommandDefinition(
            id="next_track",
            action=MediaAction("next"),
            phrases=["next track", "next song", "skip track", "skip song"],
            description="Skip to next media track",
            profiles=["normal"],
        ),
        CommandDefinition(
            id="previous_track",
            action=MediaAction("previous"),
            phrases=["previous track", "previous song", "last song", "track back"],
            description="Return to previous media track",
            profiles=["normal"],
        ),

        # Hyprland window manager controls
        CommandDefinition(
            id="fullscreen",
            action=HyprlandAction("fullscreen"),
            phrases=["toggle fullscreen", "fullscreen window"],
            description="Toggle active window fullscreen",
            profiles=["normal"],
        ),

        # Screenshot controls
        CommandDefinition(
            id="screenshot",
            action=ScreenshotAction(mode="region", clipboard=True),
            phrases=[
                "screenshot",
                "take screenshot",
                "take a screenshot",
                "do screenshot",
                "do a screenshot",
                "make screenshot",
                "make a screenshot",
                "capture screen",
                "screen capture",
                "screen shot",
                "take screen shot",
                "take a screen shot",
            ],
            description="Take a screenshot (saves and copies to clipboard)",
            profiles=["presentation", "normal"],
        ),
        CommandDefinition(
            id="screenshot_no_clipboard",
            action=ScreenshotAction(mode="region", clipboard=False),
            phrases=[
                "screenshot without clipboard",
                "screenshot no clipboard",
                "take screenshot without clipboard",
                "take a screenshot without clipboard",
                "do screenshot without clipboard",
                "do a screenshot without clipboard",
                "make screenshot without clipboard",
                "make a screenshot without clipboard",
                "screen shot without clipboard",
                "take screen shot without clipboard",
                "take a screen shot without clipboard",
                "capture screen without clipboard",
                "screen capture without clipboard",
                "screenshot without the clipboard",
                "take screenshot without the clipboard",
                "take a screenshot without the clipboard",
            ],
            description="Take a screenshot without copying to clipboard",
            profiles=["presentation", "normal"],
        ),
    ]

    return {cmd.id: cmd for cmd in defs}


def parse_action_from_dict(action_data: dict[str, Any], config: Config) -> Action | None:
    """Safely parse an allowlisted action from YAML configuration."""
    act_type = str(action_data.get("type", "")).lower()

    if act_type == "key":
        key = str(action_data.get("key", ""))
        mods = action_data.get("modifiers", [])
        return KeyAction(key=key, modifiers=mods if isinstance(mods, list) else None)

    elif act_type == "volume":
        sub_type = str(action_data.get("action", "up")).lower()
        step = float(action_data.get("step", config.volume.step))
        limit = float(action_data.get("limit", config.volume.limit))
        val = action_data.get("value")
        val_float = float(val) if val is not None else None
        return VolumeAction(action_type=sub_type, step=step, limit=limit, value=val_float)

    elif act_type == "brightness":
        val = int(action_data.get("value", 50))
        rel = bool(action_data.get("relative", False))
        step_dir = str(action_data.get("step", ""))
        return BrightnessAction(value=val, relative=rel, step=step_dir)

    elif act_type in ("power", "power_profile"):
        prof = str(action_data.get("profile", "balanced"))
        return PowerProfileAction(profile=prof)

    elif act_type == "app":
        app_name = str(action_data.get("app", ""))
        exec_cmd = action_data.get("exec", app_name)
        target = action_data.get("target")
        return AppLauncherAction(app_name=app_name, exec_cmd=exec_cmd, target_arg=target)

    elif act_type == "compound":
        sub_list = action_data.get("actions", [])
        sub_actions = []
        for s in sub_list:
            if isinstance(s, dict):
                act = parse_action_from_dict(s, config)
                if act:
                    sub_actions.append(act)
        return CompoundAction(actions=sub_actions)

    elif act_type == "media":
        cmd = str(action_data.get("command", "play-pause"))
        return MediaAction(command=cmd)

    elif act_type == "hyprland":
        disp = str(action_data.get("dispatcher", ""))
        args = str(action_data.get("args", ""))
        return HyprlandAction(dispatcher=disp, args=args)

    elif act_type == "script":
        path = str(action_data.get("path", ""))
        return ScriptAction(script_path=path)

    elif act_type == "screenshot":
        clipboard = bool(action_data.get("clipboard", True))
        mode = str(action_data.get("mode", "region"))
        return ScreenshotAction(mode=mode, clipboard=clipboard)

    elif act_type in ("type", "type_text", "typing"):
        text = str(action_data.get("text", ""))
        delay = int(action_data.get("delay", 1))
        return TypeTextAction(text=text, delay_ms=delay)

    logger.warning("Unknown action type: %s", act_type)
    return None


class CommandMatcher:
    """Matches speech transcripts to allowlisted commands according to active profile."""

    def __init__(self, config: Config, parser: NaturalCommandParser | None = None) -> None:
        self.config = config
        self.commands: dict[str, CommandDefinition] = {}
        self.parser = parser or NaturalCommandParser(config)
        self.load_commands()

    def load_commands(self) -> None:
        """Load commands from commands.yaml or use defaults."""
        self.commands = build_default_commands(self.config)

        path = Path(self.config.commands_path).expanduser()
        if not path.is_file():
            logger.info("Commands file %s not found; using built-in defaults", path)
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not isinstance(data, dict) or "commands" not in data:
                return

            for cmd_id, item in data["commands"].items():
                if not isinstance(item, dict):
                    continue
                act_data = item.get("action", {})
                action = parse_action_from_dict(act_data, self.config)
                if not action:
                    continue

                phrases = [str(p) for p in item.get("phrases", [])]
                profiles = item.get("profiles", ["presentation", "normal"])
                desc = str(item.get("description", ""))

                self.commands[cmd_id] = CommandDefinition(
                    id=cmd_id,
                    action=action,
                    phrases=phrases,
                    description=desc,
                    profiles=profiles,
                )
            logger.info("Loaded %d commands from %s", len(self.commands), path)
        except Exception as e:
            logger.error("Failed to parse commands YAML %s: %s", path, e)

    def match(self, raw_transcript: str, mode: str) -> CommandDefinition | None:
        """Match a transcription string against allowlisted commands in the active mode.

        In 'presentation' mode:
            - Strict full-utterance matching only.
            - Never triggers if the phrase is embedded inside an unrelated sentence.
        In 'normal' mode:
            - Respects wake-word if require_wake_word_normal is configured.
            - Supports natural phrasing and conversational fillers.
        In 'off' mode:
            - Always returns None.
        """
        if mode == "off":
            return None

        norm = normalize_text(raw_transcript)
        if not norm:
            return None

        if mode == "presentation":
            # Presentation mode: Conservative exact match against allowed phrases
            for cmd in self.commands.values():
                if "presentation" not in cmd.profiles:
                    continue

                for phrase in cmd.phrases:
                    phrase_norm = normalize_text(phrase)
                    # Exact full-utterance equality
                    if norm == phrase_norm:
                        return cmd
            return None

        elif mode == "normal":
            # Normal mode
            # Check wake word requirement if configured
            ww_cleaned, had_wake = self.parser.strip_wake_word(norm)
            if self.config.general.require_wake_word_normal and not had_wake:
                logger.debug("Normal mode: required wake word missing from '%s'", norm)
                return None

            cleaned = clean_natural_speech(norm, wake_word=self.config.general.wake_word)

            if not cleaned:
                return None

            # 1. Exact match on cleaned utterance against static commands
            for cmd in self.commands.values():
                if "normal" not in cmd.profiles:
                    continue
                for phrase in cmd.phrases:
                    p_norm = normalize_text(phrase)
                    if cleaned == p_norm:
                        return cmd

            # 2. Check with article stripping (e.g. "pause the music" -> "pause music")
            cleaned_no_art = strip_articles(cleaned)
            for cmd in self.commands.values():
                if "normal" not in cmd.profiles:
                    continue
                for phrase in cmd.phrases:
                    p_no_art = strip_articles(normalize_text(phrase))
                    if cleaned_no_art == p_no_art:
                        return cmd

            # 3. Dynamic natural command & compound action parsing (prioritized over loose suffix match)
            dynamic_act = self.parser.parse(raw_transcript)
            if dynamic_act:
                return CommandDefinition(
                    id="dynamic_action",
                    action=dynamic_act,
                    phrases=[raw_transcript],
                    description=dynamic_act.description,
                    profiles=["normal"],
                )

            # 4. Check if cleaned utterance ends with one of the specific command phrases
            all_pairs = []
            for cmd in self.commands.values():
                if "normal" not in cmd.profiles:
                    continue
                for phrase in cmd.phrases:
                    p_norm = normalize_text(phrase)
                    # Don't loose-suffix match very short single words like "back" or "next"
                    if p_norm and len(p_norm) > 4:
                        all_pairs.append((cmd, p_norm, strip_articles(p_norm)))

            all_pairs.sort(key=lambda item: len(item[1]), reverse=True)

            for cmd, p_norm, p_no_art in all_pairs:
                if cleaned.endswith(" " + p_norm):
                    return cmd
                if p_no_art and cleaned_no_art.endswith(" " + p_no_art):
                    return cmd

        return None
