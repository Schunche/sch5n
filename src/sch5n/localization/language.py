# Copyright (c) 2026 Schunche
"""Experimental software."""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar, cast

type Language = str


class _FileFormatError(Exception):
    """Wrong file format."""


class _UnknownLanguageError(Exception):
    """Tried to target unknown language."""


class _MissingLocalizationError(Exception):
    """Source folder does not exist."""


class _LanguageDictionary:
    """Dictionary to translate every string."""

    _LOCALIZATON_DIR: ClassVar[Path] = Path.cwd() / "assets" / "localization"

    _DEFAULT_LANGUAGE: ClassVar[Language] = "en"
    _FALLBACK_LANGUAGE: ClassVar[Language] = _DEFAULT_LANGUAGE

    _DICTIONARY: ClassVar[dict[Language, dict[str, str]]] = {
        _DEFAULT_LANGUAGE: {}
    }

    _language: ClassVar[Language] = _DEFAULT_LANGUAGE

    @classmethod
    def add_language(cls, lang: Language) -> None:
        """Add a new language to the dictionary."""
        cls._DICTIONARY.update({lang: {}})

    @classmethod
    def set_target_language(
        cls,
        lang: Language,
        *,
        check: bool = False
    ) -> None:
        """Set target language for translation.

        Raises:
            _UnknownLanguageError: Tried to target unknown language.

        """
        if check and (lang not in cls._DICTIONARY):
            msg = "Tried to target unknown language."
            raise _UnknownLanguageError(msg)

        cls._language = lang

    @classmethod
    def get_target_language(cls) -> Language:
        """Get target language for translation.

        Returns:
            Language: Target language.

        """
        return cls._language

    @classmethod
    def _parse_file(cls, path: Path) -> None:
        """Parse a localization file.

        Raises:
            _FileFormatError: Wrong file format.
            TypeError: File contents corrupted.

        """
        if (not path.is_file()) or (not path.name.endswith(".json")):
            msg = "Wrong file format."
            raise _FileFormatError(msg)

        data = json.load(path.open(encoding="utf-8"))

        if not isinstance(data, dict):
            raise TypeError

        for value in data.values():  # pyright: ignore[reportUnknownVariableType]
            if not isinstance(value, str):
                raise TypeError

        language: Language = path.name.removesuffix(".json")

        cls.add_language(language)
        cls._DICTIONARY[language].update(cast("dict[str, str]", data))

    @classmethod
    def translate(cls, key: str) -> str:
        """Translate given key.

        Returns:
            str: Translation.

        Raises:
            KeyError: Localization key not found.

        """
        localization = cls._DICTIONARY.get(cls._language, {})
        if key in localization:
            return localization[key]

        # TODO: Log missing localization key  # ruff: ignore[line-contains-todo]

        fallback = cls._DICTIONARY.get(cls._FALLBACK_LANGUAGE, {})
        if key in fallback:
            return fallback[key]

        msg = f"Localization key not found: {key}"
        raise KeyError(msg)

    @classmethod
    def read_localization(cls) -> int:
        """Read localization from source files.

        Returns:
            int: Number of found languages.

        Raises:
            _MissingLocalizationError: Source folder is missing, or corrupted.

        """
        if not cls._LOCALIZATON_DIR.exists():
            msg = "Source folder does not exist."
            raise _MissingLocalizationError(msg)

        count = 0

        for path in cls._LOCALIZATON_DIR.iterdir():
            if not path.is_file():
                continue

            try:
                cls._parse_file(path)
                count += 1
            except _FileFormatError:
                path.unlink()

        if not cls._DICTIONARY:
            msg = "No localization found at all..."
            raise _MissingLocalizationError(msg)

        if cls._FALLBACK_LANGUAGE not in cls._DICTIONARY:
            msg = "No fallback localization found."
            raise _MissingLocalizationError(msg)

        return count


_initialized: bool = False


def _init() -> None:
    """Initialize translation tools."""
    global _initialized  # ruff: ignore[global-statement]

    if not _initialized:
        _LanguageDictionary.read_localization()
        _initialized = True


def set_language(lang: Language) -> None:
    """Set target language for translation."""
    if not _initialized:
        _init()

    _LanguageDictionary.set_target_language(lang, check=True)


def get_language() -> Language:
    """Get target language for translation.

    Returns:
        Language: Target language.

    """
    if not _initialized:
        _init()

    return _LanguageDictionary.get_target_language()


def translate(key: str) -> str:
    """Translate given key.

    Returns:
        str: Translation.

    """
    if not _initialized:
        _init()

    return _LanguageDictionary.translate(key)
