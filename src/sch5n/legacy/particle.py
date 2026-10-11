# Copyright (c) 2026 Schunche
"""Experimental software."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pygame

    from sch5n.legacy.animation import Animation


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
        pos: tuple[float, float],
        velocity: tuple[float, float] = (0, 0),
        frame: int = 0,
    ) -> None:
        """Initialize a Particle object.

        Args:
            assets (dict[str, Animation]): A dictionary mapping to animations.
            species (str): The species of the particle.
            pos (list[float]): The initial position of the particle.
            velocity (list[float], optional): Initial velocity.
            frame (int, optional): Initial frame of the animation.

        """
        self.species: str = species
        self.pos: tuple[float, float] = pos
        self.velocity: tuple[float, float] = velocity
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

        self.pos = (
            self.pos[0] + self.velocity[0],
            self.pos[1] + self.velocity[1],
        )

        self.animation.update()

        return kill

    def render(
        self, surface: pygame.Surface, offset: tuple[float, float] = (0, 0)
    ) -> None:
        """Render the particle on the given surface with an optional offset.

        Args:
            surface (pygame.Surface): The surface to render the particle on.
            offset (list[int], optional): The offset to apply to the particle.

        """
        image: pygame.Surface = self.animation.img()
        surface.blit(
            image,
            (
                self.pos[0] - offset[0] - image.get_width() // 2,
                self.pos[1] - offset[1] - image.get_height() // 2,
            ),
        )
