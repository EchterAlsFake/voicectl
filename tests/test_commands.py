"""Unit tests for voicectl command normalization and matching."""

import pytest
from voicectl.commands import (
    CommandMatcher,
    normalize_text,
    clean_natural_speech,
    build_default_commands,
)
from voicectl.config import Config


def test_normalize_text():
    assert normalize_text("Next slide.") == "next slide"
    assert normalize_text("  NEXT   SLIDE!  ") == "next slide"
    assert normalize_text("Volume Up???") == "volume up"
    assert normalize_text("start presentation, please") == "start presentation please"
    assert normalize_text("") == ""


def test_presentation_mode_strict_matching():
    config = Config()
    matcher = CommandMatcher(config)

    # Allowed exact utterances
    cmd = matcher.match("Next slide.", mode="presentation")
    assert cmd is not None
    assert cmd.id == "next_slide"

    cmd = matcher.match("next", mode="presentation")
    assert cmd is not None
    assert cmd.id == "next_slide"

    cmd = matcher.match("previous slide", mode="presentation")
    assert cmd is not None
    assert cmd.id == "previous_slide"

    cmd = matcher.match("volume up", mode="presentation")
    assert cmd is not None
    assert cmd.id == "volume_up"

    cmd = matcher.match("mute", mode="presentation")
    assert cmd is not None
    assert cmd.id == "mute"


def test_presentation_mode_prevents_accidental_activation():
    config = Config()
    matcher = CommandMatcher(config)

    # Crucial requirement: Accidental utterance should NOT trigger
    unrelated = "And on the next slide we can see the results of our experiment."
    cmd = matcher.match(unrelated, mode="presentation")
    assert cmd is None, "Accidental phrase in sentence must not trigger next_slide in presentation mode"

    unrelated2 = "I think the volume up here is a bit too loud."
    cmd = matcher.match(unrelated2, mode="presentation")
    assert cmd is None, "Accidental phrase in sentence must not trigger volume_up in presentation mode"


def test_normal_mode_matching_and_fillers():
    config = Config()
    matcher = CommandMatcher(config)

    # Conversational natural speech
    cmd = matcher.match("please turn the volume up", mode="normal")
    assert cmd is not None
    assert cmd.id == "volume_up"

    cmd = matcher.match("could you pause the music", mode="normal")
    assert cmd is not None
    assert cmd.id == "pause"

    cmd = matcher.match("next track", mode="normal")
    assert cmd is not None
    assert cmd.id == "next_track"


def test_off_mode():
    config = Config()
    matcher = CommandMatcher(config)

    assert matcher.match("next slide", mode="off") is None
    assert matcher.match("volume up", mode="off") is None
    assert matcher.match("mute", mode="off") is None


def test_wake_word_requirement():
    config = Config()
    config.general.require_wake_word_normal = True
    config.general.wake_word = "computer"
    matcher = CommandMatcher(config)

    # Without wake word: should fail
    assert matcher.match("volume up", mode="normal") is None

    # With wake word: should succeed
    cmd = matcher.match("computer volume up", mode="normal")
    assert cmd is not None
    assert cmd.id == "volume_up"
