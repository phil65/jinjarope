from __future__ import annotations

import logging
import pathlib
from typing import TYPE_CHECKING

from jinja2.ext import Extension, InternationalizationExtension


try:
    from babel.core import Locale, UnknownLocaleError  # pyright: ignore
    from babel.support import NullTranslations, Translations

    HAS_BABEL = True
except ImportError:  # pragma: no cover
    from string import ascii_letters
    from typing import NamedTuple

    HAS_BABEL = False

    class UnknownLocaleError(Exception):  # type: ignore[no-redef]
        pass

    class Locale(NamedTuple):  # type: ignore[no-redef]
        language: str
        territory: str = ""

        def __str__(self) -> str:
            if self.territory:
                return f"{self.language}_{self.territory}"
            return self.language

        @classmethod
        def parse(cls, identifier: str, sep: str | None) -> Locale:
            if not isinstance(identifier, str):
                msg = f"Unexpected value for identifier: {identifier!r}"
                raise TypeError(msg)
            locale = cls(*identifier.split(sep, 1))
            if not all(x in ascii_letters for x in locale.language):
                msg = f"expected only letters, got {locale.language!r}"
                raise ValueError(msg)
            if len(locale.language) != 2:  # noqa: PLR2004
                msg = f"unknown locale {locale.language!r}"
                raise UnknownLocaleError(msg)
            return locale  # type: ignore[return-value]


if TYPE_CHECKING:
    from collections.abc import Sequence
    import os

    import jinja2


logger = logging.getLogger(__name__)


class NoBabelExtension(InternationalizationExtension):
    def __init__(self, environment: jinja2.Environment) -> None:
        Extension.__init__(self, environment)
        environment.extend(
            install_null_translations=self._install_null,
            newstyle_gettext=False,
        )


def parse_locale(locale: str) -> Locale:
    """Parse a locale string into a Locale object.

    Args:
        locale: The locale string to parse (e.g., 'en_US').

    Returns:
        Locale: The parsed Babel Locale object.

    Raises:
        RuntimeError: If the locale string is invalid.
    """
    try:
        return Locale.parse(locale, sep="_")
    except (ValueError, UnknownLocaleError, TypeError) as e:
        msg = f"Invalid value for locale: {e}"
        raise RuntimeError(msg) from e


def install_translations(
    env: jinja2.Environment, locale: str | Locale, dirs: Sequence[str | os.PathLike[str]]
) -> None:
    """Install translations for the given locale in the Jinja environment.

    Args:
        env: The Jinja2 environment to install translations into.
        locale: The target locale.
        dirs: Sequence of directory paths to search for translations.
              Directories listed first
    """
    if isinstance(locale, str):
        locale = parse_locale(locale)
    if HAS_BABEL:
        env.add_extension("jinja2.ext.i18n")
        translations = _get_merged_translations(dirs, "locales", locale)
        if translations is not None:
            env.install_gettext_translations(translations)  # type: ignore[attr-defined]
        else:
            env.install_null_translations()  # type: ignore[attr-defined]
            if locale.language != "en":
                logger.warning(
                    "Translations couldnt be found for locale %r, defaulting to English",
                    locale,
                )
    else:  # pragma: no cover
        # no babel installed, add dummy support for trans/endtrans blocks
        env.add_extension(NoBabelExtension)
        env.install_null_translations()  # type: ignore[attr-defined]


def _get_merged_translations(
    dirs: Sequence[str | os.PathLike[str]], locales_dir: str, locale: Locale
) -> Translations | None:
    """Merge translations from multiple directories for a given locale.

    Args:
        dirs: Sequence of directory paths to search for translations.
        locales_dir: Name of the directory containing locale files.
        locale: The target locale.

    Returns:
        Merged translations object or None if no translations are found.
    """
    merged_translations: NullTranslations | None = None

    logger.debug("Looking for translations for locale %r", locale)
    locale_str = f"{locale.language}_{locale.territory}" if locale.territory else locale.language
    for theme_dir in reversed(dirs):
        dirname = pathlib.Path(theme_dir) / locales_dir
        translations = Translations.load(dirname, [locale_str])

        if type(translations) is NullTranslations:
            logger.debug("No translations found in: %r", dirname)
            continue
        logger.debug("Translations found in: %r", dirname)
        if merged_translations is None:
            merged_translations = translations
        else:
            merged_translations.merge(translations)  # type: ignore[attr-defined]

    return merged_translations  # type: ignore[return-value]
