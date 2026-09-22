# Copyright (c) 2026 Schunche
"""Experimental software."""

from typing import TYPE_CHECKING, Any

from sch5n.codec._codec import Codec, Decoder, Encoder

if TYPE_CHECKING:
    from _typeshed import SupportsRead, SupportsWrite

import json

type _Json = Any


class JsonEncoder(Encoder[_Json]):
    """_Json encoder class."""

    @classmethod
    def dump(cls, obj: _Json, fp: SupportsWrite[str]) -> None:
        """Save json to desired file.

        Args:
            obj (_Json): Json to save.
            fp (SupportsWrite[str]): Desired file to save to.

        """
        return json.dump(obj, fp)

    @classmethod
    def dumps(cls, obj: _Json) -> str:
        """Save json to string.

        Args:
            obj (_Json): Json to save.

        Returns:
            str: Desired encoded string.

        """
        return json.dumps(obj)


class JsonDecoder(Decoder[_Json]):
    """Json decoder class."""

    @classmethod
    def load(cls, fp: SupportsRead[str | bytes]) -> _Json:
        """Load desired file.

        Args:
            fp (SupportsRead[str  |  bytes]): File to load from.

        Returns:
            _Json: Desired loaded content.

        """
        return json.load(fp)

    @classmethod
    def loads(cls, s: str | bytes | bytearray) -> _Json:
        """Load desired string.

        Args:
            s (str | bytes): String to load from.

        Returns:
            _Json: Desired loaded content.

        """
        return json.loads(s)


class JsonCodec(JsonEncoder, JsonDecoder, Codec[_Json]):
    """Json codec class."""
