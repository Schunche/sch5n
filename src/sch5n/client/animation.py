# Copyright (c) 2026 Schunche
"""Playing a mob's animations, with transition clips between them."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from sch5n.client.assets import Animation
    from sch5n.client.render.atlas import Region
    from sch5n.game.config import Transition


class Animator:
    """Follows a mob's action and decides which frame to show.

    When the action changes and a transition is defined between the old
    and the new action, the transition clip plays once first; then the
    new action's clip starts. Another change of action interrupts a
    transition at once.
    """

    def __init__(
        self,
        clips: Mapping[str, Animation],
        transitions: Iterable[Transition],
        action: str,
    ) -> None:
        """Start showing `action`."""
        self.clips = clips
        self._bridges: dict[tuple[str, str], str] = {
            (source, target): transition.play
            for transition in transitions
            for source in transition.from_
            for target in transition.to
        }
        self.action = action
        """The mob's action, what plays once any transition is over."""
        self.clip = action
        """The clip playing now: `action`, or a transition into it."""
        self.age = 0
        """Ticks since `clip` started."""

    @property
    def in_transition(self) -> bool:
        """Whether a transition clip is playing."""
        return self.clip != self.action

    def update(self, action: str) -> None:
        """Advance one tick, following the mob's current action."""
        if action != self.action:
            bridge = self._bridges.get((self.action, action))
            self.action = action
            self.clip = bridge if bridge is not None else action
            self.age = 0
            return

        self.age += 1
        if self.in_transition and self.age >= self.clips[self.clip].duration:
            self.clip = self.action
            self.age = 0

    @property
    def frame(self) -> Region:
        """The frame to draw now."""
        return self.clips[self.clip].frame(self.age)
