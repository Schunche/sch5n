# Copyright (c) 2026 Schunche
"""Experimental software."""

import logging
import time
from typing import ClassVar

logger = logging.getLogger(__name__)


class Color:
    """Utility class for applying ANSI color codes to text."""

    COLOR_CODES: ClassVar[dict[str, str]] = {
        "black": "\033[30m",
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "magenta": "\033[35m",
        "cyan": "\033[36m",
        "white": "\033[37m",
        "reset": "\033[0m",
    }

    @classmethod
    def apply(cls, text: str, color_name: str) -> str:
        """Apply color to the given text.

        Args:
            text (str): The text to colorize.
            color_name (str): The name of the color to apply.

        Returns:
            str: The colorized text.

        """
        color_code = cls.COLOR_CODES.get(color_name, "")
        return f"{color_code}{text}{cls.COLOR_CODES["reset"]}"


def log_message(msg: str) -> None:
    """Log a message with a timestamp in white color.

    Args:
        msg (str): The message to log.

    """
    print(Color.apply(f"{time.asctime()} :> {msg}", "white"))
    logger.debug(msg)


def log_error(msg: str) -> None:
    """Log an error message with a timestamp in red color.

    Args:
        msg (str): The error message to log.

    """
    print(Color.apply(f"{time.asctime()} :> ERROR - {msg}", "red"))
    logger.error(msg)


def log_success(msg: str) -> None:
    """Log a message with a timestamp in green color.

    Args:
        msg (str): The error message to log.

    """
    print(Color.apply(f"{time.asctime()} :> {msg}", "green"))
    logger.warning(msg)
