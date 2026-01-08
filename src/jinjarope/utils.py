from __future__ import annotations

from collections.abc import Callable, Mapping
import dataclasses
import functools
import importlib

# from importlib.metadata import entry_points as _entry_points  # replaced by epregistry
import logging
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, overload

from upath.types import JoinablePath


if TYPE_CHECKING:
    from dataclasses import Field
    import os


logger = logging.getLogger(__name__)

type AnyPath = str | os.PathLike[str] | JoinablePath


class DataclassInstance(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Field[Any]]]


# delegation for docstrings
def partial[T](fn: Callable[..., T], *args: Any, **kwargs: Any) -> Callable[..., T]:
    """Create new function with partial application of given arguments / keywords.

    Args:
        fn: The function to generate a partial from
        args: patially applied arguments
        kwargs: partially applied keywords
    """
    return functools.partial(fn, *args, **kwargs)


def get_dataclass_nondefault_values(
    instance: DataclassInstance,
) -> dict[str, Any]:
    """Return dictionary with non-default key-value pairs of given dataclass.

    Args:
        instance: dataclass instance
    """
    non_default_fields: dict[str, Any] = {}

    for field in dataclasses.fields(instance):
        value = getattr(instance, field.name)

        # Check if the field has a default value
        if field.default is not dataclasses.MISSING:
            default = field.default
        elif field.default_factory is not dataclasses.MISSING:
            default = field.default_factory()
        else:
            # If there's no default, we consider the current value as non-default
            non_default_fields[field.name] = value
            continue

        # Compare the current value with the default
        if value != default:
            non_default_fields[field.name] = value
    return non_default_fields


def get_repr(_obj: Any, *args: Any, **kwargs: Any) -> str:
    """Get a suitable __repr__ string for an object.

    Args:
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
def fsspec_get(path: str | os.PathLike[str]) -> str:
    """Fetch a file via fsspec and return file content as a string.

    Args:
        path: The path to fetch the file from
    """
    import fsspec  # type: ignore[import-untyped]

    with fsspec.open(path) as file:
        return file.read().decode()  # type: ignore[no-any-return]


@functools.lru_cache(maxsize=1)
def _get_black_formatter() -> Callable[[str, int], str]:
    """Return a formatter.

    If black is available, a callable to format code using black is returned,
    otherwise a noop callable is returned.
    """
    try:
        from black import Mode, format_str
        from black.parsing import InvalidInput
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


def entry_points(group: str) -> Mapping[str, Callable[..., Any]]:
    """Get entry points for a group using epregistry.

    Args:
        group: Entry point group name

    Returns:
        Mapping of entry point names to loaded callables
    """
    from epregistry import EntryPointRegistry

    registry = EntryPointRegistry[Callable[..., Any]](group)
    # load_all() handles exceptions internally and logs warnings for failures
    return registry.load_all()


def get_hash(obj: Any, hash_length: int | None = 7) -> str:
    """Get a Md5 hash for given object.

    Args:
        obj: The object to get a hash for ()
        hash_length: Optional cut-off value to limit length
    """
    import hashlib

    hash_md5 = hashlib.md5(str(obj).encode("utf-8"))
    return hash_md5.hexdigest()[:hash_length]


@overload
def resolve(
    name: str,
    module: str | None = None,
    py_type: None = None,
) -> Any: ...


@overload
def resolve[T](
    name: str,
    module: str | None = None,
    *,
    py_type: type[T],
) -> T: ...


def resolve[T](
    name: str,
    module: str | None = None,
    py_type: type[T] | None = None,
) -> T | Any:
    """Resolve ``name`` to a Python object via imports / attribute lookups.

    If ``module`` is None, ``name`` must be "absolute" (no leading dots).

    If ``module`` is not None, and ``name`` is "relative" (has leading dots),
    the object will be found by navigating relative to ``module``.

    Args:
        name: The name to resolve
        module: Optional base module for relative imports
        py_type: Optional type to validate the resolved object against

    Returns:
        The resolved object

    Raises:
        ValueError: If using a relative name without a base module
        TypeError: If py_type is provided and the resolved object
                  doesn't match that type
    """
    from jinjarope import envtests

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

        found = getattr(builtins, used)
    else:
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

    if py_type is not None and not isinstance(found, py_type):
        msg = f"Expected {py_type.__name__}, but {name} is {type(found).__name__}"
        raise TypeError(msg)

    return found


if __name__ == "__main__":
    doc = resolve("jinjarope.inspectfilters")
