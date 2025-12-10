from __future__ import annotations

from collections.abc import Callable, Iterator
import contextlib
import functools
import importlib
import inspect
import logging
import pathlib
import types
from typing import Annotated, Any, Union, get_args, get_origin


logger = logging.getLogger(__name__)


HasCodeType = (
    types.ModuleType
    | type
    | types.MethodType
    | types.FunctionType
    | types.TracebackType
    | types.FrameType
    | types.CodeType
    | Callable[..., Any]
)


@functools.cache
def list_subclasses[ClassType: type](
    klass: ClassType,
    *,
    recursive: bool = True,
    filter_abstract: bool = False,
    filter_generic: bool = True,
    filter_locals: bool = True,
) -> list[ClassType]:
    """Return list of all subclasses of given klass.

    Note: This call is cached. Consider iter_subclasses for uncached iterating.

    Args:
        klass: class to get subclasses from
        filter_abstract: whether abstract base classes should be included.
        filter_generic: whether generic base classes should be included.
        filter_locals: whether local base classes should be included.
        recursive: whether to also get subclasses of subclasses.
    """
    return list(
        iter_subclasses(
            klass,
            recursive=recursive,
            filter_abstract=filter_abstract,
            filter_generic=filter_generic,
            filter_locals=filter_locals,
        ),
    )


def iter_subclasses[ClassType: type](
    klass: ClassType,
    *,
    recursive: bool = True,
    filter_abstract: bool = False,
    filter_generic: bool = True,
    filter_locals: bool = True,
) -> Iterator[ClassType]:
    """(Recursively) iterate all subclasses of given klass.

    Args:
        klass: class to get subclasses from
        filter_abstract: whether abstract base classes should be included.
        filter_generic: whether generic base classes should be included.
        filter_locals: whether local base classes should be included.
        recursive: whether to also get subclasses of subclasses.
    """
    if getattr(klass.__subclasses__, "__self__", None) is None:
        return
    for kls in klass.__subclasses__():
        if recursive:
            yield from iter_subclasses(
                kls,
                filter_abstract=filter_abstract,
                filter_generic=filter_generic,
                filter_locals=filter_locals,
            )
        if filter_abstract and inspect.isabstract(kls):
            continue
        if filter_generic and kls.__qualname__.endswith("]"):
            continue
        if filter_locals and "<locals>" in kls.__qualname__:
            continue
        yield kls


@functools.cache
def list_baseclasses(
    klass: type,
    *,
    recursive: bool = True,
    filter_abstract: bool = False,
    filter_generic: bool = True,
    filter_locals: bool = True,
) -> list[type]:
    """Return list of all baseclasses of given klass.

    Args:
        klass: class to get subclasses from
        filter_abstract: whether abstract base classes should be included.
        filter_generic: whether generic base classes should be included.
        filter_locals: whether local base classes should be included.
        recursive: whether to also get baseclasses of baseclasses.
    """
    return list(
        iter_baseclasses(
            klass,
            recursive=recursive,
            filter_abstract=filter_abstract,
            filter_generic=filter_generic,
            filter_locals=filter_locals,
        ),
    )


def iter_baseclasses(
    klass: type,
    *,
    recursive: bool = True,
    filter_abstract: bool = False,
    filter_generic: bool = True,
    filter_locals: bool = True,
) -> Iterator[type]:
    """(Recursively) iterate all baseclasses of given klass.

    Args:
        klass: class to get subclasses from
        filter_abstract: whether abstract base classes should be included.
        filter_generic: whether generic base classes should be included.
        filter_locals: whether local base classes should be included.
        recursive: whether to also get baseclasses of baseclasses.
    """
    for kls in klass.__bases__:
        if recursive:
            yield from iter_baseclasses(
                kls,
                recursive=recursive,
                filter_abstract=filter_abstract,
                filter_generic=filter_generic,
                filter_locals=filter_locals,
            )
        if filter_abstract and inspect.isabstract(kls):
            continue
        if filter_generic and kls.__qualname__.endswith("]"):
            continue
        if filter_locals and "<locals>" in kls.__qualname__:
            continue
        yield kls


@functools.cache
def get_doc(
    obj: Any,
    *,
    escape: bool = False,
    fallback: str = "",
    from_base_classes: bool = False,
    only_summary: bool = False,
    only_description: bool = False,
) -> str:
    """Get __doc__ for given object.

    Args:
        obj: Object to get docstrings from, or import path string
            (supports both "module.path:object" and "module.path.object")
        escape: Whether docstrings should get escaped
        fallback: Fallback in case docstrings dont exist
        from_base_classes: Use base class docstrings if docstrings dont exist
        only_summary: Only return first line of docstrings
        only_description: Only return block after first line
    """
    from jinjarope import mdfilters

    # Handle string import paths
    if isinstance(obj, str):
        # Try colon notation first (module.path:object)
        if ":" in obj:
            module_path, obj_name = obj.rsplit(":", 1)
            try:
                module = importlib.import_module(module_path)
                obj = getattr(module, obj_name)
            except (ImportError, AttributeError) as e:
                logger.debug(f"Failed to import {obj}: {e}")  # noqa: G004
                return fallback
        else:
            # Try dot notation (module.path.object)
            parts = obj.rsplit(".", 1)
            if len(parts) == 2:  # noqa: PLR2004
                module_path, obj_name = parts
                try:
                    module = importlib.import_module(module_path)
                    obj = getattr(module, obj_name)
                except (ImportError, AttributeError):
                    # Maybe the whole thing is a module?
                    try:
                        obj = importlib.import_module(obj)
                    except ImportError as e:
                        logger.debug(f"Failed to import {obj}: {e}")  # noqa: G004
                        return fallback
            else:
                # Just a module name
                try:
                    obj = importlib.import_module(obj)
                except ImportError as e:
                    logger.debug(f"Failed to import {obj}: {e}")  # noqa: G004
                    return fallback

    match obj:
        case _ if from_base_classes:
            doc = inspect.getdoc(obj)
        case _ if obj.__doc__:
            doc = inspect.cleandoc(obj.__doc__)
        case _:
            doc = None
    if not doc:
        return fallback
    if only_summary:
        doc = doc.split("\n")[0]
    if only_description:
        doc = "\n".join(doc.split("\n")[1:])
    return mdfilters.md_escape(doc) if doc and escape else doc


def get_argspec(obj: Any, remove_self: bool = True) -> inspect.FullArgSpec:
    """Return a cleaned-up FullArgSpec for given callable.

    ArgSpec is cleaned up by removing `self` from method callables.

    Args:
        obj: A callable python object
        remove_self: Whether to remove "self" argument from method argspecs
    """
    if inspect.isfunction(obj):
        argspec = inspect.getfullargspec(obj)
    elif inspect.ismethod(obj):
        argspec = inspect.getfullargspec(obj)
        if remove_self:
            del argspec.args[0]
    elif inspect.isclass(obj):
        if obj.__init__ is object.__init__:  # to avoid an error
            argspec = inspect.getfullargspec(lambda self: None)
        else:
            argspec = inspect.getfullargspec(obj.__init__)
        if remove_self:
            del argspec.args[0]
    elif callable(obj):
        argspec = inspect.getfullargspec(obj.__call__)
        if remove_self:
            del argspec.args[0]
    else:
        msg = f"{obj} is not callable"
        raise TypeError(msg)
    return argspec


def get_deprecated_message(obj: Any) -> str | None:
    """Return deprecated message (created by deprecated decorator).

    Args:
        obj: Object to check
    """
    return obj.__deprecated__ if hasattr(obj, "__deprecated__") else None


@functools.cache
def get_source(obj: HasCodeType) -> str:
    """Cached wrapper for inspect.getsource.

    Args:
        obj: Object to return source for.
    """
    return inspect.getsource(obj)


@functools.cache
def get_source_lines(obj: HasCodeType) -> tuple[list[str], int]:
    """Cached wrapper for inspect.getsourcelines.

    Args:
        obj: Object to return source lines for.
    """
    return inspect.getsourcelines(obj)


@functools.cache
def get_signature(obj: Callable[..., Any]) -> inspect.Signature:
    """Cached wrapper for inspect.signature.

    Args:
        obj: Callable to get a signature for.
    """
    return inspect.signature(obj)


@functools.cache
def get_members(
    obj: object, predicate: Callable[[Any], bool] | None = None
) -> list[tuple[str, Any]]:
    """Cached version of inspect.getmembers.

    Args:
        obj: Object to get members for
        predicate: Optional predicate for the members
    """
    return inspect.getmembers(obj, predicate)


@functools.cache
def get_file(obj: HasCodeType) -> pathlib.Path | None:
    """Cached wrapper for inspect.getfile.

    Args:
        obj: Object to get file for
    """
    with contextlib.suppress(TypeError):
        return pathlib.Path(inspect.getfile(obj))
    return None


def iter_union_types(
    union_type: Any,
    *,
    filter_none: bool = True,
) -> Iterator[type]:
    """Iterate through all types in a Union.

    Handles unwrapping of Annotated types automatically.

    Args:
        union_type: A Union type (e.g., Union[A, B, C] or A | B | C)
        filter_none: Whether to filter out NoneType from the results

    Yields:
        Each type found in the union

    Example:
        >>> from typing import Union
        >>> for typ in iter_union_types(Union[str, int, None]):
        ...     print(typ)
        <class 'str'>
        <class 'int'>
    """
    # Unwrap Annotated if needed
    origin = get_origin(union_type)
    if origin is Annotated:
        # Get the actual type from Annotated[Union[...], ...]
        union_type = get_args(union_type)[0]
        origin = get_origin(union_type)

    # Check if it's a Union type
    if origin not in (Union, types.UnionType):
        msg = f"Expected Union type, got: {union_type}"
        raise TypeError(msg)

    # Get all types in the union
    union_args = get_args(union_type)

    for arg in union_args:
        if filter_none and arg is type(None):
            continue
        yield arg


if __name__ == "__main__":
    doc = get_doc(str)

    # Test iter_union_types
    from typing import Annotated

    print("\n--- Testing iter_union_types ---")

    # Basic union
    union_type = str | int | float
    print("\nUnion: str | int | float")
    for typ in iter_union_types(union_type):
        print(f"  - {typ}")

    # Union with None (filtered by default)
    union_with_none = str | int | None
    print("\nUnion with None (filtered): str | int | None")
    for typ in iter_union_types(union_with_none):
        print(f"  - {typ}")

    # Union with None (not filtered)
    print("\nUnion with None (not filtered): str | int | None")
    for typ in iter_union_types(union_with_none, filter_none=False):
        print(f"  - {typ}")

    # Annotated union
    annotated_union = Annotated[str | int, "some metadata"]
    print("\nAnnotated Union: Annotated[str | int, 'metadata']")
    for typ in iter_union_types(annotated_union):
        print(f"  - {typ}")
