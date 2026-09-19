from sch5n.core.item import Block, Item, SwingTool

ITEM_DATA: dict[int, Item] = {
    0: SwingTool(
        id=0,
        name="Copper Pickaxe",
        use_time=25,
        tool_type={"pickaxe": 25},
        damage=3,
        knockback=2,
    ),
    1: SwingTool(
        id=1,
        name="Copper Axe",
        use_time=40,
        tool_type={"axe": 30},
        damage=4,
        knockback=3,
    ),
    2: Block(id=2, name="Dirt Block"),
    3: Block(id=3, name="Oak Log"),
}
