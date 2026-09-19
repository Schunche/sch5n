from sch5n.core.loader import (
    SETTINGS,
    load_icon,
    load_image,
    load_image_resized,
)

ITEM_ICON: dict = {
    0: load_icon("tool/copperPickaxe"),
    1: load_icon("tool/copperAxe"),
    2: load_icon("tile/dirt/0"),
    3: load_icon("tile/oakLog/0"),
}

ITEM_IMAGE: dict = {
    0: load_image("tool/copperPickaxe"),
    1: load_image("tool/copperAxe"),
    2: load_image_resized(
        "tile/dirt/0",
        (int(SETTINGS["tile_size"] * 0.5), int(SETTINGS["tile_size"] * 0.5)),
    ),
    3: load_image_resized(
        "tile/oakLog/0",
        (int(SETTINGS["tile_size"] * 0.5), int(SETTINGS["tile_size"] * 0.5)),
    ),
}
