# Copyright (c) 2026 Schunche
"""Transitions between animations."""

from __future__ import annotations

import pydantic
import pytest

from sch5n.client.animation import Animator
from sch5n.client.assets import Animation
from sch5n.client.render.atlas import Region
from sch5n.game.config import AnimationClip, AnimationsConfig, Transition
from sch5n.game.content import load_animations
from sch5n.utility import path

TICKS = 4
"""Ticks per frame of the test clips."""


def clip(frames: int, *, loop: bool) -> Animation:
    """Create a clip whose frames are distinguishable by width.

    Returns:
        Animation: Frames 1, 2, ... pixels wide.

    """
    regions = tuple(Region(0, 0, 1, 1, i + 1, 1) for i in range(frames))
    return Animation(
        AnimationClip(path="x", frame_ticks=TICKS, loop=loop), regions
    )


CLIPS = {
    "idle": clip(2, loop=True),
    "run": clip(3, loop=True),
    "fall": clip(1, loop=True),
    "land": clip(2, loop=False),
    "jump": clip(1, loop=False),
}
LAND = Transition.model_validate({
    "from": ["fall"],
    "to": ["idle", "run"],
    "play": "land",
})


def animator(action: str) -> Animator:
    """Create an animator with a landing transition.

    Returns:
        Animator: Showing `action`.

    """
    return Animator(CLIPS, [LAND], action)


def test_transition_plays_once_then_target() -> None:
    """Landing plays the landing clip, then idles."""
    anim = animator("fall")
    anim.update("idle")
    assert anim.in_transition
    assert anim.clip == "land"
    assert anim.frame is CLIPS["land"].frames[0]
    for _ in range(CLIPS["land"].duration - 1):
        anim.update("idle")
    assert anim.clip == "land"
    anim.update("idle")
    assert anim.clip == "idle"
    assert anim.age == 0
    assert anim.frame is CLIPS["idle"].frames[0]


def test_no_transition_switches_directly() -> None:
    """Changes without a defined transition start the new clip at once."""
    anim = animator("idle")
    for _ in range(10):
        anim.update("idle")
    anim.update("jump")
    assert anim.clip == "jump"
    assert anim.age == 0
    assert not anim.in_transition


def test_transition_can_be_interrupted() -> None:
    """Jumping during the landing crouch does not wait for it."""
    anim = animator("fall")
    anim.update("run")
    anim.update("run")
    assert anim.clip == "land"
    anim.update("jump")
    assert anim.clip == "jump"
    assert anim.action == "jump"


def test_same_action_keeps_playing() -> None:
    """Staying in an action advances its frames."""
    anim = animator("run")
    frames = []
    for _ in range(3 * TICKS):
        frames.append(anim.frame.width)
        anim.update("run")
    assert frames == [1] * TICKS + [2] * TICKS + [3] * TICKS


def test_bundled_transitions_are_valid() -> None:
    """The game's animations define player transitions that load."""
    config = load_animations(path.DATA_DIR)
    transitions = config.transitions["player"]
    assert {t.play for t in transitions} <= set(config.mobs["player"])


@pytest.mark.parametrize(
    ("play", "message"), [("nope", "unknown clips"), ("idle", "loops")]
)
def test_invalid_transitions_are_rejected(play: str, message: str) -> None:
    """Transitions must use existing, non looping clips."""
    data = load_animations(path.DATA_DIR).model_dump(by_alias=True)
    data["transitions"] = {
        "player": [{"from": ["run"], "to": ["idle"], "play": play}]
    }
    with pytest.raises(pydantic.ValidationError, match=message):
        AnimationsConfig.model_validate(data)
