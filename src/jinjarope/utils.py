from __future__ import annotations

import functools
import importlib
from importlib.metadata import entry_points
import logging
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, TypeVar

from jinjarope import envtests


if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from dataclasses import Field
    import types


logger = logging.getLogger(__name__)

ClassType = TypeVar("ClassType", bound=type)


class DataclassInstance(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Field[Any]]]


def partial(fn: Callable, *args: Any, **kwargs: Any):
    """Create new function with partial application of given arguments / keywords.

    Arguments:
        fn: The function to generate a partial from
        args: patially applied arguments
        kwargs: partially applied keywords
    """
    return functools.partial(fn, *args, **kwargs)


def get_dataclass_nondefault_values(instance: DataclassInstance) -> dict[str, Any]:
    """Return dictionary with non-default key-value pairs of given dataclass.

    Arguments:
        instance: dataclass instance
    """
    import dataclasses
    from operator import attrgetter

    vals = []
    for f in dataclasses.fields(instance):
        no_default = isinstance(f.default, dataclasses._MISSING_TYPE)
        no_default_factory = isinstance(f.default_factory, dataclasses._MISSING_TYPE)
        if not no_default:
            val = attrgetter(f.name)(instance)
            if val != f.default:
                vals.append((f.name, val))
        if not no_default_factory:
            val = attrgetter(f.name)(instance)
            if val != f.default_factory():
                vals.append((f.name, val))
        if no_default and no_default_factory:
            val = attrgetter(f.name)(instance)
            vals.append((f.name, val))
    return dict(vals)


def get_repr(_obj: Any, *args: Any, **kwargs: Any) -> str:
    """Get a suitable __repr__ string for an object.

    Arguments:
        _obj: The object to get a repr for.
        args: Arguments for the repr
        kwargs: Keyword arguments for the repr
    """
    classname = type(_obj).__name__
    parts = [repr(v) for v in args]
    kw_parts = [f"{k}={v!r}" for k, v in kwargs.items()]
    sig = ", ".join(parts + kw_parts)
    return f"{classname}({sig})"


@functools.cache
def fsspec_get(path: str) -> str:
    """Fetch a file via fsspec and return file content as a string.

    Arguments:
        path: The path to fetch the file from
    """
    import fsspec

    with fsspec.open(path) as file:
        return file.read().decode()


T = TypeVar("T")


@functools.lru_cache(maxsize=1)
def _get_black_formatter() -> Callable[[str, int], str]:
    """Return a formatter.

    If black is available, a callable to format code using black is returned,
    otherwise a noop callable is returned.
    """
    try:
        from black import InvalidInput, Mode, format_str
    except ModuleNotFoundError:
        logger.info("Formatting signatures requires Black to be installed.")
        return lambda text, _: text

    def formatter(code: str, line_length: int) -> str:
        mode = Mode(line_length=line_length)
        try:
            return format_str(code, mode=mode)
        except InvalidInput:
            return code

    return formatter


@functools.lru_cache
def _entry_points(group: str) -> Mapping[str, Callable]:
    eps = {ep.name: ep.load() for ep in entry_points(group=group)}
    logger.debug("Available %r entry points: %s", group, sorted(eps))
    return eps


def get_hash(obj: Any, hash_length: int | None = 7) -> str:
    """Get a Md5 hash for given object.

    Arguments:
        obj: The object to get a hash for ()
        hash_length: Optional cut-off value to limit length
    """
    import hashlib

    hash_md5 = hashlib.md5(str(obj).encode("utf-8"))
    return hash_md5.hexdigest()[:hash_length]


@functools.cache
def resolve(name: str, module: str | None = None) -> types.ModuleType | Callable:
    """Resolve ``name`` to a Python object via imports / attribute lookups.

    If ``module`` is None, ``name`` must be "absolute" (no leading dots).

    If ``module`` is not None, and ``name`` is "relative" (has leading dots),
    the object will be found by navigating relative to ``module``.

    Returns the object, if found.  If not, propagates the error.
    """
    names = name.split(".")
    if not names[0]:
        if module is None:
            msg = "relative name without base module"
            raise ValueError(msg)
        modules = module.split(".")
        names.pop(0)
        while not name[0]:
            modules.pop()
            names.pop(0)
        names = modules + names

    used = names.pop(0)
    if envtests.is_python_builtin(used):
        import builtins

        return getattr(builtins, used)
    found = importlib.import_module(used)
    for n in names:
        used += "." + n
        try:
            found = getattr(found, n)
        except AttributeError:
            try:
                importlib.import_module(used)
                found = getattr(found, n)
            except ModuleNotFoundError:
                mod = ".".join(used.split(".")[:-1])
                importlib.import_module(mod)
                found = getattr(found, n)
    return found


if __name__ == "__main__":
    doc = resolve("jinjarope.inspectfilters")
