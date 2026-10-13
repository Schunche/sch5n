# Copyright (c) 2026 Schunche
"""Experimental software."""

from typing import TYPE_CHECKING

from sch5n.math.vector import FloatTuple2

if TYPE_CHECKING:
    import pygame

    from sch5n.deprecated.animation import Animation


class Particle:
    """A class representing a particle in a game.

    Attributes:
        species (str): The species of the particle.
        pos (list[float]): The position of the particle.
        velocity (list[float]): The velocity of the particle.
        frame (int): The current frame of the particle's animation.
        animation (Animation): The animation object representing the particle.

    """

    def __init__(
        self,
        assets: dict[str, Animation],
        species: str,
        pos: FloatTuple2,
        velocity: FloatTuple2 | None = None,
        frame: int = 0,
    ) -> None:
        """Initialize a Particle object.

        Args:
            assets (dict[str, Animation]): A dictionary mapping to animations.
            species (str): The species of the particle.
            pos (FloatTuple2): The initial position of the particle.
            velocity (FloatTuple2, optional): Initial velocity.
            frame (int, optional): Initial frame of the animation.

        """
        if velocity is None:
            velocity = FloatTuple2(0, 0)

        self.species: str = species
        self.pos: FloatTuple2 = pos
        self.velocity: FloatTuple2 = velocity
        self.frame: int = frame

        self.animation: Animation = assets[species].copy()
        self.animation.frame = frame

    def update(self) -> bool:
        """Update the particle's position and animation.

        Returns:
            bool: True if the particle is to be removed, False otherwise.

        """
        kill: bool = False
        if self.animation.done:
            kill = True

        self.pos = FloatTuple2(
            self.pos[0] + self.velocity[0],
            self.pos[1] + self.velocity[1],
        )

        self.animation.update()

        return kill

    def render(
        self, surface: pygame.Surface, offset: FloatTuple2 | None = None
    ) -> None:
        """Render the particle on the given surface with an optional offset.

        Args:
            surface (pygame.Surface): The surface to render the particle on.
            offset (list[int], optional): The offset to apply to the particle.

        """
        if offset is None:
            offset = FloatTuple2(0, 0)

        image: pygame.Surface = self.animation.img()
        surface.blit(
            image,
            (
                self.pos[0] - offset[0] - image.get_width() // 2,
                self.pos[1] - offset[1] - image.get_height() // 2,
            ),
        )
