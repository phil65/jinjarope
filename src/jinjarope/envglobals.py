import collections
import datetime as dt
import logging
import os
import pathlib
import threading
from typing import TYPE_CHECKING, Any

import upath


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from jinjarope.utils import AnyPath


logger = logging.getLogger(__name__)


FILE_CACHE_SIZE = 256
"""How many files `load_file_cached` keeps (least recently used ones go first)."""

_file_cache: collections.OrderedDict[tuple[Any, ...], str] = collections.OrderedDict()
_file_cache_lock = threading.Lock()


def _local_file(path: AnyPath) -> str | None:
    """The absolute path of a local file, None for remote / virtual paths."""
    if isinstance(path, str):
        if path.startswith("file://"):
            path = path.removeprefix("file://")
        elif "://" in path:
            return None
    if isinstance(path, str | os.PathLike):
        return os.path.abspath(os.fspath(path))  # noqa: PTH100
    return None  # UPaths of other file systems aren't os.PathLike


def _read_text(path: AnyPath) -> str:
    from upathtools import to_upath

    return to_upath(path).read_text("utf-8")


def load_file_cached(path: AnyPath) -> str:
    """Return the text-content of file at given path.

    Local files are cached by path and modification time (edits are seen); other
    paths (fsspec-style URLs and UPaths) by URL. The cache keeps the last
    `FILE_CACHE_SIZE` files.

    Args:
        path: The path to get str content from
    """
    if (local := _local_file(path)) is not None:
        try:
            stat = os.stat(local)  # noqa: PTH116
        except OSError:
            return _read_text(path)  # raises the file system's error
        key: tuple[Any, ...] = (local, stat.st_mtime_ns, stat.st_size)
    else:
        key = (str(upath.UPath(path)),)
    with _file_cache_lock:
        if (text := _file_cache.get(key)) is not None:
            _file_cache.move_to_end(key)
            return text
    text = _read_text(path)
    with _file_cache_lock:
        _file_cache[key] = text
        while len(_file_cache) > FILE_CACHE_SIZE:
            _file_cache.popitem(last=False)
    return text


def clear_file_cache() -> None:
    """Forget the files `load_file_cached` read."""
    with _file_cache_lock:
        _file_cache.clear()


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


def now(tz: dt.tzinfo | None = None) -> dt.datetime:
    """Get current Datetime.

    Args:
        tz: timezone for retuned datetime
    """
    return dt.datetime.now(tz)


def utcnow() -> dt.datetime:
    """Get UTC datetime."""
    return dt.datetime.now(dt.UTC)


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
