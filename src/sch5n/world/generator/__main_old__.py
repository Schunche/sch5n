# Copyright (c) 2026 Schunche
"""Experimental software."""

import json
import math
import pathlib
from warnings import deprecated

from sch5n.vendor.random import choice, randbelow, randf, randint
lazy from sch5n.log.logger import LOGGER


def _save_map(tilemap: dict[str, dict[str, str | int]], alias: str) -> None:
    with pathlib.Path(f"src/map/{alias}/tilemap.json").open(
        mode="w", encoding="utf-8"
    ) as file:
        json.dump(tilemap, file, indent=4)


def _round_up(num: float) -> int:
    if float.is_integer(num):
        return int(num)
    return int(num) + 1


def _diff25(num: float) -> float:
    return abs(num * (1 + math.sin(randf() * 2 * math.pi) / 4))


def _temp_func(num: float) -> float:
    return 2 ** (5 * (2 * num - 1))


def _temp_func_2(num: float) -> float:
    return 8 * ((1 - num) ** 3)


def _random_signed(num: float) -> float:
    return ((randbelow(1) * 2) - 1) * num


@deprecated("Create substitute")
def _generate_map(
    x_left: int = 0, x_right: int = 100, y_top: int = 0, y_bottom: int = 100
) -> dict[str, dict[str, str | int]]:
    tilemap: dict[str, dict[str, str | int]] = {}
    # Top half is filles with dirt
    # Bottom half with stone

    until_dirt_y: int = int((y_top + y_bottom) / 2)
    LOGGER.info("Dirt is generated until: y = %s", until_dirt_y)
    for x in range(x_left, x_right):
        # Dirt
        for y in range(y_top, until_dirt_y):
            tilemap[f"{x};{y}"] = {"block": "dirt", "variant": 0}

        # Stone
        for y in range(until_dirt_y, y_bottom):
            tilemap[f"{x};{y}"] = {"block": "stone", "variant": 0}

    # Draw strokes of dirt/stone
    def draw_patch_stroke(
        point: tuple[int, int],
        block: str,
        count: int = 0,
        radius: float | None = None,
        patches_in_stroke: int = 1,
    ) -> None:
        if radius is None:
            radius = int(randint(9, 50) / randint(9, 12))

        if count == 0:
            if block == "stone":
                patches_in_stroke = int(
                    _diff25(
                        _temp_func((point[1] - y_top) / (until_dirt_y - y_top))
                    )
                )
            elif block == "dirt":
                patches_in_stroke = int(
                    _diff25(
                        _temp_func_2(
                            (point[1] - until_dirt_y)
                            / (y_bottom - until_dirt_y)
                        )
                    )
                )
            patches_in_stroke = min(
                max(patches_in_stroke, 0), 32
            )  # Capped between 0 and 32

        if patches_in_stroke != 0:
            # Go thru the circle and draw it
            for x in range(int(point[0] - radius), int(point[0] + radius) + 1):
                for y in range(
                    int(point[1] - radius), int(point[1] + radius) + 1
                ):
                    # If not inside grid, go to next point
                    if not (x_left <= x < x_right and y_top <= y < y_bottom):
                        continue

                    # Place the block if inside the circle
                    if (x - point[0]) ** 2 + (y - point[1]) ** 2 <= _round_up(
                        radius**2
                    ):
                        tilemap[f"{x};{y}"] = {"block": block, "variant": 0}

        if count < patches_in_stroke:
            shift_direction: float = math.pi * (1 + randf())
            next_point: tuple[int, int] = (
                int(
                    point[0]
                    + _random_signed(radius / 2 * math.cos(shift_direction))
                ),
                int(point[1] + radius / 2 * math.sin(shift_direction)),
            )
            # Change previous radious with a max of 25 %
            next_radius: float = min(
                max(_diff25(radius), 1), 5
            )  # Capped between 1 and 5

            draw_patch_stroke(
                next_point,
                block,
                count=count + 1,
                radius=next_radius,
                patches_in_stroke=patches_in_stroke,
            )

    # Stone patches in dirt
    num_of_patches: int = int(
        _diff25((x_right - x_left) * (until_dirt_y - y_top) * 0.003)
    )
    LOGGER.info("Stone strokes in dirt: %s", num_of_patches)
    for _ in range(num_of_patches):
        point: tuple[int, int] = (
            x_left + int(randf() * (x_right - x_left)),
            y_top + int(randf() * (until_dirt_y - y_top)),
        )
        draw_patch_stroke(point, "stone")

    # Dirt patches in stone
    num_of_patches = int(
        _diff25((x_right - x_left) * (y_bottom - until_dirt_y) * 0.004)
    )
    LOGGER.info("Dirt strokes in stone: %s", num_of_patches)
    for _ in range(num_of_patches):
        point = (
            x_left + int(randf() * (x_right - x_left)),
            until_dirt_y + int(randf() * (y_bottom - until_dirt_y)),
        )
        draw_patch_stroke(point, "dirt")

    ores: list[str] = [
        "copper",
        "tin",
        "iron",
        "lead",
        "silver",
        "tungsten",
        "gold",
        "platinum",
    ]

    world_ores: list[str] = [
        choice(ores[(2 * _) : ((_ + 1) * 2)])
        for _ in range(int(len(ores) / 2))
    ]

    LOGGER.info("This world contains the ores: %s", ", ".join(world_ores))

    return tilemap


@deprecated("Create substitute")
def main(filename: str = "procedural") -> None:
    LOGGER.info("Started making it")
    # X grows left to right
    # Y grows top to bottom

    # Advised size: the bigger the better
    # Don't go below 50 please
    map_left: int = 0
    map_right: int = 300
    map_top: int = 0
    map_bottom: int = 160
    LOGGER.info(
        "In range: x = (%s; %s), y = (%s; %s)",
        map_left,
        map_right,
        map_top,
        map_bottom,
    )

    generated_map = _generate_map(
        x_left=map_left, x_right=map_right, y_top=map_top, y_bottom=map_bottom
    )

    _save_map(generated_map, filename)
    LOGGER.info("Map saved to '%s'", filename)


if __name__ == "__main__":
    main()
