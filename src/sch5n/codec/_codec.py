# Copyright (c) 2026 Schunche
"""Experimental software."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from _typeshed import SupportsRead, SupportsWrite


class Decoder[T](ABC):
    """Base decoder class."""

    @classmethod
    @abstractmethod
    def loads(
        cls, s: str | bytes | bytearray, *args: Any, **kwargs: Any) -> T:  # ruff: ignore[any-type]
        """Load desired string.

        Args:
            s (str | bytes): String to load from.
            args (Any): ...
            kwargs (Any): ...

        Returns:
            T: Desired loaded content.

        """

    @classmethod
    @abstractmethod
    def load(
        cls, fp: SupportsRead[str | bytes], *args: Any, **kwargs: Any) -> T:  # ruff: ignore[any-type]
        """Load desired file.

        Args:
            fp (SupportsRead[str  |  bytes]): File to load from.
            args (Any): ...
            kwargs (Any): ...

        Returns:
            T: Desired loaded content.

        """


class Encoder[T](ABC):
    """Base encoder class."""

    @classmethod
    @abstractmethod
    def dumps(cls, obj: T, *args: Any, **kwargs: Any) -> str:  # ruff: ignore[any-type]
        """Save desired obj to string.

        Args:
            obj (T): Desired obj to save.
            args (Any): ...
            kwargs (Any): ...

        Returns:
            str: Desired encoded string.

        """

    @classmethod
    @abstractmethod
    def dump(
        cls,
        obj: T,
        fp: SupportsWrite[str], *args: Any, **kwargs: Any) -> None:  # ruff: ignore[any-type]
        """Save desired obj to desired file.

        Args:
            obj (T): Desired obj to save.
            fp (SupportsWrite[str]): Desired file to save to.
            args (Any): ...
            kwargs (Any): ...

        """


class Codec[T](Decoder[T], Encoder[T], ABC):  # pyright: ignore[reportUnusedClass]
    """Base codec class."""
