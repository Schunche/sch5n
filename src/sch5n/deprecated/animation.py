# Copyright (c) 2026 Schunche
"""Experimental software."""

from __future__ import annotations

from warnings import deprecated
lazy from typing import Self

lazy import pygame


@deprecated("Create replacement")
class Animation:
    """A class to represent an animation consisting of a sequence of images."""

    def __init__(
        self,
        images: list[pygame.Surface],
        image_duration: int = 5,
        *,
        do_loop: bool = False,
    ) -> None:
        """Initialize the Animation object.

        Args:
            images: List of pygame Surface objects.
            image_duration: Duration (in frames) each image.
            do_loop: Determines if the animation should loop.

        """
        self.images = images
        self.image_duration: int = image_duration
        self.do_loop: bool = do_loop

        self.done: bool = False
        self.frame: int = 0

    def copy(self) -> Self:
        """Create a copy of the Animation object.

        Returns:
            Animation: A new Animation object with the same attributes.

        """
        return type(self)(
            self.images, self.image_duration, do_loop=self.do_loop
        )

    def update(self) -> None:
        """Update the animation frame.

        If do_loop is True, the animation loops continously.
        If do_loop is False, the animation stops upon reaching the last frame.
        """
        if self.do_loop:
            self.frame = (self.frame + 1) % (
                self.image_duration * len(self.images)
            )
        else:
            self.frame = min(
                self.frame + 1, self.image_duration * len(self.images) - 1
            )
            if self.frame >= self.image_duration * len(self.images) - 1:
                self.done = True

    def img(self) -> pygame.Surface:
        """Get the current frame of the animation.

        Returns:
            pygame.Surface: The pygame Surface representing the current frame.

        """
        return self.images[int(self.frame / self.image_duration)]
