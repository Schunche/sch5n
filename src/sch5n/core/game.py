# Copyright (c) 2026 Schunche
"""Experimental software."""

import argparse
import threading
from dataclasses import dataclass
from typing import Any, ClassVar


@dataclass
class Program:
    launch_args: argparse.Namespace

    def __init__(self) -> None:
        pass

    def launch_game(self, args: argparse.Namespace) -> None:

    def process_launch_args(self, args: argparse.Namespace) -> bool:
        is_server = False

        self.launch_args = args

        is_server = self.launch_args.server

PROGRAM = Program()

class Game:

    def __init__(
        self,
        program: Game.Program
    ) -> None:
        pass
