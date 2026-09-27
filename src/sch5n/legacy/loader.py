import json
import os
import pathlib
from typing import Any

import pygame

from sch5n.core.log import log_error, log_message

pygame.init()


def load_json(path: str) -> Any:
    """Load json file.

    Arguments:
        path (str): directory path from 'src/' to '.json' WITHOUT the said

    Returns:
        Any: the json file

    """
    try:
        with pathlib.Path(f"src/{path}.json").open(encoding="utf-8") as file:
            return_file = json.load(file)
            log_message(f"'src/{path}.json' found and loaded")
            return return_file

    except FileNotFoundError as e:
        log_error(f"'src/{path}.json' not found: {e}")
        return None

    except UnicodeDecodeError as e:
        log_error(f"'src/{path}.json' is not a valid JSON file: {e}")
        return None

    except Exception as e:
        log_error(f"'src/{path}.json' failed to load: {e}")
        return None


SETTINGS = load_json("data/settings")
FIX_SETTINGS: dict[str,
    int | float | str | dict[str,
    int | float | str | dict[str, int]]] = load_json("fixData/fixSettings")

NAME_SPACE = load_json("fixData/nameSpace")
TRANSPARENT_COLOR: list[int] = NAME_SPACE["color"]["toBeTransparent"]


def load_image(path: str) -> pygame.Surface:
    """Load a '.png' image from a file.

    Args:
        path (str): The path to the image file: from 'src/img/' to '.png'

    Returns:
        pygame.Surface: The loaded image.

    """
    try:
        img: pygame.Surface = pygame.image.load(f"src/img/{path}.png")
        img.set_colorkey(TRANSPARENT_COLOR)
        return img

    except FileNotFoundError as e:
        log_error(f"'src/img/{path}.png' not found: {e}")
        return load_image("icon/_")

    except Exception as e:
        log_error(f"'src/img/{path}.png' failed to load: {e}")
        return load_image("icon/_")


def load_image_resized(path: str, size: tuple[int, int]) -> pygame.Surface:
    """Load an image from a file, and resizes it.

    Args:
        path (str): The path to the image file.
        size (tuple[int, int]): The new size of the image file.

    Returns:
        pygame.Surface: The resized image.

    Raises:
        ValueError: invalid size

    """
    if size[0] < 0:
        msg = "The new width must be an integer greater than 0"
        raise ValueError(msg)
    if size[1] < 0:
        msg = "The new height must be an integer greater than 0"
        raise ValueError(msg)

    img: pygame.Surface = load_image(path)
    return_image: pygame.Surface = pygame.transform.scale(
        img, (size[0], size[1])
    )
    return_image.set_colorkey(TRANSPARENT_COLOR)
    return return_image


def load_dir(path: str) -> dict[str, pygame.Surface]:
    """Load images from a directory.

    Args:
        path (str): The path to the directory containing images.

    Returns:
        dict[str, pygame.Surface]: A dictionary containing images to surfaces.

    """
    images: dict[str, pygame.Surface] = {}
    for image_name in os.listdir(f"src/img/{path}"):
        images[image_name[: image_name.index(".")]] = load_image(
            f"{path}/{image_name[: image_name.index(".")]}"
        )
    return images


def load_images_as_list(path: str) -> list[pygame.Surface]:
    """Load images from a directory into a list of pygame Surface objects.

    Args:
        path (str): The directory path containing the images.

    Returns:
        list[pygame.Surface]: A list of pygame Surface objects representing the loaded images.

    """
    images: list[pygame.Surface] = []
    for image_name in sorted(os.listdir(f"src/img/{path}")):
        images.append(load_image(f"{path}/{image_name[: image_name.index(".")]}"))
    return images


def load_tiles(path: str) -> dict[str, dict[int, pygame.surface.Surface]]:
    """Load tiles from a directory structure into a dictionary of Surface.

    Args:
        path (str): Path containing the tile images by block and variant.

    Returns:
        dict[str, dict[int, pygame.Surface]]: A dictionary mapping Surfaces.

    """
    tiles: dict[str, dict[int, pygame.surface.Surface]] = {}
    for block in os.listdir(f"src/img/{path}"):
        if block not in tiles:
            tiles[block] = {}
        for variant in os.listdir(f"src/img/{path}/{block}"):
            tiles[block][int(variant[: variant.index(".")])] = (
                load_image_resized(
                    f"{path}/{block}/{variant[: variant.index(".")]}",
                    (SETTINGS["tile_size"], SETTINGS["tile_size"]),
                )
            )

    return tiles


def get_bit(block: str = "_") -> str:
    # key <- value
    if block == "_":
        return "_"
    for key, value in NAME_SPACE["bitForm"].items():
        if block in value:
            return key
    return "_"


def load_sys_font(
    name: str, size: int = 16, bold: bool = False, italic: bool = False
) -> pygame.font.Font:
    return pygame.font.SysFont(name=name, size=size, bold=bold, italic=italic)


def load_icon(path: str) -> pygame.Surface:
    """Load an icon from a file.
    """
    return load_image_resized(path, (SETTINGS["gui_size"], SETTINGS["gui_size"]))


def resize_image(image: pygame.Surface, size: tuple[int, int]) -> pygame.Surface:
    """Resize an image.
    """
    return pygame.transform.scale(image, size)
