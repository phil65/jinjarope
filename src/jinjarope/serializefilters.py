from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, overload

from jinjarope import deepmerge


if TYPE_CHECKING:
    from collections.abc import Callable


SerializeFormatStr = Literal["yaml", "json", "ini", "toml"]


def serialize(data: Any, fmt: SerializeFormatStr, **kwargs: Any) -> str:
    """Serialize given json-like object to given format.

    Args:
        data: The data to serialize
        fmt: The serialization format
        kwargs: Keyword arguments passed to the dumper function
    """
    from yamling import dump_universal

    return dump_universal.dump(data, mode=fmt, **kwargs)


def deserialize(data: str, fmt: SerializeFormatStr, **kwargs: Any) -> Any:
    """Serialize given json-like object to given format.

    Args:
        data: The data to deserialize
        fmt: The serialization format
        kwargs: Keyword arguments passed to the loader function
    """
    from yamling import load_universal

    return load_universal.load(data, mode=fmt, **kwargs)


def dig(
    data: dict[str, Any] | list[Any] | str,
    *sections: str,
    keep_path: bool = False,
    dig_yaml_lists: bool = True,
) -> Any:
    """Try to get data with given section path from a dict-list structure.

    If a list is encountered and dig_yaml_lists is true, treat it like a list of
    {"identifier", {subdict}} items, as used in MkDocs config for
    plugins & extensions.
    If Key path does not exist, return None.

    Args:
        data: The data to dig into
        sections: Sections to dig into
        keep_path: Return result with original nesting
        dig_yaml_lists: Also dig into single-key->value pairs, as often found in yaml.
    """
    for i in sections:
        if isinstance(data, dict):
            if child := data.get(i):
                data = child
            else:
                return None
        elif dig_yaml_lists and isinstance(data, list):
            # this part is for yaml-style listitems
            for idx in data:
                if i in idx and isinstance(idx, dict):
                    data = idx[i]
                    break
                if isinstance(idx, str) and idx == i:
                    data = idx
                    break
            else:
                return None
    if not keep_path:
        return data
    result: dict[str, Any] = {}
    new = result
    for sect in sections:
        result[sect] = data if sect == sections[-1] else {}
        result = result[sect]
    return new


@overload
def merge(
    target: dict[str, Any],
    *source: dict[str, Any],
    deepcopy: bool = False,
    mergers: dict[type, Callable[[Any, Any, Any], Any]] | None = None,
) -> dict[str, Any]: ...


@overload
def merge(
    target: list[Any],
    *source: list[Any],
    deepcopy: bool = False,
    mergers: dict[type, Callable[[Any, Any, Any], Any]] | None = None,
) -> list[Any]: ...


def merge(
    target: list[Any] | dict[str, Any],
    *source: list[Any] | dict[str, Any],
    deepcopy: bool = False,
    mergers: dict[type, Callable[[Any, Any, Any], Any]] | None = None,
) -> list[Any] | dict[str, Any]:
    """Merge given data structures using mergers provided.

    Args:
        target: Data structure to merge into
        source:  Data structures to merge into target
        deepcopy: Whether to deepcopy the target
        mergers: Mergers with strategies for each type (default: additive)
    """
    import copy

    if deepcopy:
        target = copy.deepcopy(target)
    context = deepmerge.DeepMerger(mergers)
    for s in source:
        target = context.merge(s, target)
    return target
