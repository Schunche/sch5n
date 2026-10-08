# Copyright (c) 2026 Schunche
"""Experimental software."""

import argparse
from dataclasses import dataclass


@dataclass
class Program:
    launch_args: argparse.Namespace

    def __init__(self) -> None:
        pass

    def launch_game(self, args: argparse.Namespace) -> None:
        pass

    def process_launch_args(self, args: argparse.Namespace) -> bool:
        self.launch_args = args

        is_server = self.launch_args.server


PROGRAM = Program()


class Game:
    def __init__(self, program: Game.Program) -> None:
        pass
