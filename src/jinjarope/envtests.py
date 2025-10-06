from __future__ import annotations

import builtins
import datetime
import inspect
import math
import os
import re
import sys
from typing import TYPE_CHECKING, Any

from jinjarope import utils


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


_RFC_3986_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+\-+.]*://")


def is_number(value: Any) -> bool:
    """Try to convert value to a float."""
    try:
        fvalue = float(value)
    except (ValueError, TypeError):
        return False
    return math.isfinite(fvalue)


def _is_type(value: Any) -> bool:
    """Return whether a value is a type."""
    return isinstance(value, type)


def _is_list(value: Any) -> bool:
    """Return whether a value is a list."""
    return isinstance(value, list)


def _is_set(value: Any) -> bool:
    """Return whether a value is a set."""
    return isinstance(value, set)


def _is_tuple(value: Any) -> bool:
    """Return whether a value is a tuple."""
    return isinstance(value, tuple)


def _is_dict(value: Any) -> bool:
    """Return whether a value is a tuple."""
    return isinstance(value, dict)


def _to_set(value: Any) -> set[Any]:
    """Convert value to set."""
    return set(value)


def _to_tuple[T](value: Sequence[T]) -> tuple[T, ...]:
    """Convert value to tuple."""
    return tuple(value)


def is_instance(obj: object, typ: str | type) -> bool:
    """Like the isinstance builtin, but also accepts strs as type.

    Args:
        obj: The object to check
        typ: A type (name)
    """
    kls = utils.resolve(typ) if isinstance(typ, str) else typ
    if not isinstance(kls, type):
        raise TypeError(kls)
    return isinstance(obj, kls)


def is_subclass(obj: type, typ: str | type) -> bool:
    """Like the issubclass builtin, but also accepts strs as type.

    Args:
        obj: The class to check
        typ: A type (name)
    """
    kls = utils.resolve(typ) if isinstance(typ, str) else typ
    if not isinstance(kls, type):
        raise TypeError(kls)
    return issubclass(obj, kls)


def _is_datetime(value: Any) -> bool:
    """Return whether a value is a datetime."""
    return isinstance(value, datetime.datetime)


def _is_string_like(value: Any) -> bool:
    """Return whether a value is a string or string like object."""
    return isinstance(value, str | bytes | bytearray)


def is_http_url(string: str) -> bool:
    """Return true when given string represents a HTTP url.

    Args:
        string: The string to check
    """
    return string.startswith(("http://", "https://", "www.")) and "\n" not in string


def is_protocol_url(string: str) -> bool:
    """Return true when given string represents any type of URL.

    Args:
        string: The string to check
    """
    return "://" in string and "\n" not in string


def is_python_keyword(string: str) -> bool:
    """Return true when given string represents a python keyword.

    Args:
        string: The string to check
    """
    import keyword

    return keyword.iskeyword(string)


def is_python_builtin(fn: str | Callable[..., Any]) -> bool:
    """Return true when given fn / string represents a python builtin.

    Args:
        fn: (Name of) function to check
    """
    return fn in dir(builtins) if isinstance(fn, str) else inspect.isbuiltin(fn)


def is_in_std_library(fn: str | Callable[..., Any]) -> bool:
    """Return true when given fn / string is part of the std library.

    Args:
        fn: (Name of) function to check
    """
    name = fn if isinstance(fn, str) else fn.__module__
    return name.split(".")[0] in sys.stdlib_module_names


def is_fsspec_url(string: str | os.PathLike[str]) -> bool:
    """Returns true if the given URL looks like an fsspec protocol, except http/https.

    Args:
        string: The URL to check
    """
    return (
        isinstance(string, str)
        and bool(_RFC_3986_PATTERN.match(string))
        and not string.startswith(("http://", "https://"))
    )


def contains_files(directory: str | os.PathLike[str]) -> bool:
    """Check if given directory exists and contains any files.

    Supports regular file paths and fsspec URLs.

    Args:
        directory: The directoy to check
    """
    from upathtools import to_upath

    path = to_upath(directory)
    return path.exists() and any(path.iterdir())


def is_installed(package_name: str) -> bool:
    """Returns true if a package with given name is found.

    Args:
        package_name: The package name to check
    """
    import importlib.util

    return bool(importlib.util.find_spec(package_name))


def is_env_var(env_var: str) -> bool:
    """Returns true if an environment variable with given name has a value.

    Args:
        env_var: The environment variable name to check
    """
    return bool(os.getenv(env_var))


def is_indented(text: str, indentation: str = "    ") -> bool:
    """Check whether all lines of given text are indented.

    Args:
        text: The text to check
        indentation: The indent each line must start with
    """
    return all(i.startswith(indentation) for i in text.split("\n"))


if __name__ == "__main__":
    result = is_in_std_library(inspect.getsource)
    print(result)
