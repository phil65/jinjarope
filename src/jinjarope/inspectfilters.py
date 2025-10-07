from __future__ import annotations

from collections.abc import Callable, Iterator
import contextlib
import functools
import inspect
import logging
import pathlib
import types
from typing import Any


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
def list_baseclasses[ClassType: type](
    klass: ClassType,
    *,
    recursive: bool = True,
    filter_abstract: bool = False,
    filter_generic: bool = True,
    filter_locals: bool = True,
) -> list[ClassType]:
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


def iter_baseclasses[ClassType: type](
    klass: ClassType,
    *,
    recursive: bool = True,
    filter_abstract: bool = False,
    filter_generic: bool = True,
    filter_locals: bool = True,
) -> Iterator[ClassType]:
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
        obj: Object to get docstrings from
        escape: Whether docstrings should get escaped
        fallback: Fallback in case docstrings dont exist
        from_base_classes: Use base class docstrings if docstrings dont exist
        only_summary: Only return first line of docstrings
        only_description: Only return block after first line
    """
    from jinjarope import mdfilters

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
def get_members(obj: object, predicate: Callable[[Any], bool] | None = None):
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


if __name__ == "__main__":
    doc = get_doc(str)
