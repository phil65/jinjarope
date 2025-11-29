from __future__ import annotations

import datetime
import logging
import pathlib
from typing import TYPE_CHECKING, Any

import upath

from jinjarope import decorators as dec


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    import os

    from jinjarope.utils import AnyPath


logger = logging.getLogger(__name__)


@dec.cache_with_transforms(arg_transformers={0: lambda p: upath.UPath(p).resolve()})
def load_file_cached(path: AnyPath) -> str:
    """Return the text-content of file at given path.

    Call is cached based on resolved file path.
    Also supports fsspec-style URLs and UPaths.

    Args:
        path: The path to get str content from
    """
    from upathtools import to_upath

    return to_upath(path).read_text("utf-8")


_cache: dict[str, str] = {}


def get_output_from_call(
    call: str | Sequence[str],
    cwd: str | os.PathLike[str] | None = None,
    use_cache: bool = False,
) -> str | None:
    """Execute a system call and return its output as a string.

    Args:
        call: The system call to make
        cwd: The working directory for the call
        use_cache: Whether to cache the output of calls
    """
    import subprocess

    if not call:
        return None
    if not isinstance(call, str):
        call = " ".join(call)
    key = pathlib.Path(cwd or ".").resolve().as_posix() + call
    if key in _cache and use_cache:
        return _cache[key]
    logger.info("Executing %r...", call)
    try:
        text = subprocess.getoutput(call)
        _cache[key] = text
        return text  # noqa: TRY300
    except subprocess.CalledProcessError:
        logger.warning("Executing %s failed", call)
        return None


def add(text: str | None, prefix: str = "", suffix: str = "") -> str:
    """Add a pre- or suffix to a value if the value is true-ish.

    Args:
        text: The text to check
        prefix: Prefix to add if text is true-ish
        suffix: Suffix to add if text is true-ish
    """
    return f"{prefix}{text}{suffix}" if text else ""


def ternary[TTrue, TFalse, TNone = None](
    value: Any,
    true_val: TTrue,
    false_val: TFalse,
    none_val: TNone | None = None,
) -> bool | TTrue | TFalse | TNone:
    """Value ? true_val : false_val.

    Args:
        value: The value to check.
        true_val: The value to return if given value is true-ish
        false_val: The value to return if given value is false-ish
        none_val: Optional value to return if given value is None
    """
    if value is None and none_val is not None:
        return none_val
    return true_val if bool(value) else false_val


def match(obj: Any, mapping: dict[str | type, str] | None = None, **kwargs: Any) -> str:
    """A filter trying to imitate a python match-case statement.

    Args:
        obj: match object
        mapping: a mapping for the different cases. If key is type, an isinstance will
                 be performed. If key is a str, check for equality.
        kwargs: Same functionality as mapping, but provided as keyword arguments for
                convenience.

    Examples:
        ``` jinja
        {{ "a" | match(a="hit", b="miss")
        {{ MyClass() | match({MyClass: "hit", OtherClass: "miss"}) }}
        ```
    """
    # kwargs can only contain strs as keys, so we can perform simply getitem.
    if kwargs and obj in kwargs:
        return kwargs[obj]  # type: ignore[no-any-return]

    for k, v in (mapping or {}).items():
        match k:
            case type() if isinstance(obj, k):
                return v
            case _ if k == obj:
                return v
    return ""


def has_internet() -> bool:
    """Return true if machine is connected to internet.

    Checks connection with a HEAD request to the Google DNS server.
    """
    import http.client as httplib

    conn = httplib.HTTPSConnection("8.8.8.8", timeout=2)
    try:
        conn.request("HEAD", "/")
        return True  # noqa: TRY300
    except Exception:  # noqa: BLE001
        return False
    finally:
        conn.close()


def now(tz: datetime.tzinfo | None = None) -> datetime.datetime:
    """Get current Datetime.

    Args:
        tz: timezone for retuned datetime
    """
    return datetime.datetime.now(tz)


def utcnow() -> datetime.datetime:
    """Get UTC datetime."""
    return datetime.datetime.now(datetime.UTC)


ENV_GLOBALS: dict[str, Callable[..., Any]] = {
    "range": range,
    "zip": zip,
    "set": set,
    "tuple": tuple,
    "list": list,
    "int": int,
    "str": str,
}


if __name__ == "__main__":
    output = get_output_from_call("git status")
    print(output)
