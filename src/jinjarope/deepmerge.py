"""Module for deep merging of data structures with customizable merge strategies."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from collections.abc import Callable, Mapping


def merge_dict(
    merger: DeepMerger, source: Mapping[Any, Any], target: Mapping[Any, Any]
) -> Mapping[Any, Any]:
    """Merge two mappings recursively.

    Args:
        merger: The DeepMerger instance handling the merge operation
        source: The source mapping whose values take precedence
        target: The target mapping to merge into

    Returns:
        A new dictionary containing the merged key-value pairs

    Example:
        ```python
        merger = DeepMerger()
        source = {"a": {"b": 1}}
        target = {"a": {"c": 2}}
        merge_dict(merger, source, target)
        # {'a': {'b': 1, 'c': 2}}
        ```
    """
    result = dict(target)
    for key, source_value in source.items():
        target_value = result.get(key, type(source_value)())
        try:
            value = merger.merge(source_value, target_value)
        except TypeError:
            # If values can't be merged, use source value
            value = source_value
        result[key] = value
    return result


def merge_list(merger: DeepMerger, source: list[Any], target: list[Any]) -> list[Any]:
    """Concatenate two lists.

    Args:
        merger: The DeepMerger instance handling the merge operation
        source: The source list to append
        target: The target list to merge into

    Returns:
        A new list containing all elements from both lists

    Example:
        ```python
        merger = DeepMerger()
        merge_list(merger, [3, 4], [1, 2])
        # [1, 2, 3, 4]
        ```
    """
    return target + source


DEFAULT_MERGERS: dict[type, Callable[..., Any]] = {dict: merge_dict, list: merge_list}


class DeepMerger:
    """A class that handles deep merging of data structures.

    The merger can be customized by providing different merge strategies
    for different types.

    Attributes:
        mergers: A dictionary mapping types to their corresponding merge functions

    Example:
        ```python
        merger = DeepMerger()
        source = {"a": {"b": 1}}
        target = {"a": {"c": 2}}
        merger.merge(source, target)
        # {'a': {'b': 1, 'c': 2}}
        ```
    """

    mergers: dict[type[Any], Callable[..., Any]] = DEFAULT_MERGERS

    def __init__(self, mergers: dict[type[Any], Callable[..., Any]] | None = None) -> None:
        """Initialize the DeepMerger with custom merge strategies.

        Args:
            mergers: Optional dictionary of type-specific merge functions
        """
        if mergers is not None:
            self.mergers = mergers

    def merge[T](self, source: T, target: T) -> T:
        """Merge two objects of the same type.

        Args:
            source: The source object whose values take precedence
            target: The target object to merge into

        Returns:
            The merged object

        Raises:
            TypeError: If the types cannot be merged
        """
        source_type = type(source)
        target_type = type(target)
        merger = self.mergers.get(target_type)
        if source_type is not target_type or merger is None:
            msg = f"Cannot merge {source_type} with {target_type}"
            raise TypeError(msg)
        return merger(self, source, target)  # type: ignore[no-any-return]


if __name__ == "__main__":
    merger = DeepMerger()
    source = {"a": {"b": 1}}
    target = {"a": {"c": 2}}
    result = merger.merge(source, target)
    print(result)
    assert result == {"a": {"b": 1, "c": 2}}
