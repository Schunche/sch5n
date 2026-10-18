# Copyright (c) 2026 Schunche
"""Experimental software."""

lazy from sch5n.deprecated.__main__ import main as main_old


# def main(argv: list[str] | None = None) -> None:
def main() -> None:
    # parser = argparse.ArgumentParser(prog="sch5n client")

    # parser.add_argument("--width", type=int, default=1280)
    # parser.add_argument("--height", type=int, default=720)
    # parser.add_argument("--fullscreen", action="store_true")

    # args = parser.parse_args(argv)

    # print(args)
    main_old()


if __name__ == "__main__":
    main()
