# Copyright (c) 2026 Schunche
"""Experimental software."""

from warnings import deprecated

lazy import pygame

lazy from sch5n.vendor.random import choice, randf


class Cloud:
    """A class representing a cloud in a side-scrolling game.

    Attributes:
        pos (list[float]): The position of the cloud.
        img (pygame.Surface): The image representing the cloud.
        speed (float): The speed at which the cloud moves horizontally.
        depth (float): The depth of the cloud, for parallax scrolling effect.

    """

    def __init__(
        self,
        pos: tuple[float, float],
        img: pygame.surface.Surface,
        speed: float,
        depth: float,
    ) -> None:
        """Initialize a Cloud object.

        Args:
            pos (list[float]): The position of the cloud.
            img (pygame.Surface): The image representing the cloud.
            speed (float): The speed at which the cloud moves horizontally.
            depth (float): The depth of the cloud, affecting parallax effect.

        """
        self.pos: list[float] = list(pos)
        self.img: pygame.Surface = img
        self.depth: float = depth
        self.speed: float = self.depth / (speed * (2**6))

    @deprecated("Make sure to use delta time.")
    def update(self, wind_speed: float = 1) -> None:
        """Update the position of the cloud based on its speed."""
        self.pos[0] += self.speed * wind_speed

    def render(
        self, surface: pygame.Surface, offset: tuple[float, float] = (0, 0)
    ) -> None:
        """Render the cloud on the given surface with optional offset.

        Args:
            surface (pygame.Surface): The pygame surface to render on.
            offset (tuple[float], optional): The offset to apply to the cloud.

        """
        render_pos: tuple[float, float] = (
            self.pos[0] - offset[0] * self.depth,
            self.pos[1] - offset[1] * self.depth,
        )
        surface.blit(
            self.img,
            (
                render_pos[0] % (surface.get_width() + self.img.get_width())
                - self.img.get_width(),
                render_pos[1] % (surface.get_height() + self.img.get_height())
                - self.img.get_height(),
            ),
        )


class Clouds:
    """A class representing a collection of clouds in a side-scrolling game.

    Attributes:
        clouds (list[Cloud]): List of Cloud objects representing the clouds.

    """

    def __init__(
        self, cloud_images: list[pygame.Surface], count: int = 2**4
    ) -> None:
        """Initialize Clouds object with random clouds.

        Args:
            cloud_images (list[pygame.Surface]): Different cloud images.
            count (int, optional): The number of clouds to generate.

        """
        self.clouds: list[Cloud] = []

        for _ in range(count):
            self.clouds.append(
                Cloud(
                    (randf() * 99999, randf() * 99999),
                    choice(cloud_images),
                    randf() * 0.05 + 0.05,
                    randf() * 0.6 + 0.2,
                )
            )

        self.clouds.sort(key=lambda x: x.depth)

    @deprecated("Make sure to use delta time.")
    def update(self, wind_speed: float = 1) -> None:
        """Update the position of all clouds."""
        for cloud in self.clouds:
            cloud.update(wind_speed=wind_speed)

    def render(
        self, surface: pygame.Surface, offset: tuple[float, float] = (0, 0)
    ) -> None:
        """Render all clouds on the given surface with optional offset.

        Args:
            surface (pygame.Surface): The pygame surface to render on.
            offset (tuple[float], optional): The offset to apply to the clouds.

        """
        for cloud in self.clouds:
            cloud.render(surface, offset=offset)
