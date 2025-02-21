# mypy: disable-error-code="attr-defined"
from typing import Any

import pytest

from jinjarope.decorators import cache_with_transforms


def test_basic_caching():
    """Test basic function caching without transformers."""
    call_count = 0

    @cache_with_transforms()
    def add(x: int, y: int) -> int:
        nonlocal call_count
        call_count += 1
        return x + y

    assert add(1, 2) == 3
    assert add(1, 2) == 3
    assert call_count == 1
    assert add.cache_info()["cache_size"] == 1


def test_arg_transformer():
    """Test caching with argument transformers."""

    @cache_with_transforms(arg_transformers={0: lambda x: x.lower()})
    def greet(name: str) -> str:
        return f"Hello, {name}!"

    assert greet("John") == "Hello, John!"
    assert greet("JOHN") == "Hello, John!"  # Should hit cache, previous word cached
    assert greet.cache_info()["cache_size"] == 1


def test_kwarg_transformer():
    """Test caching with keyword argument transformers."""

    @cache_with_transforms(kwarg_transformers={"items": tuple})
    def process_list(*, items: list[int]) -> int:
        return sum(items)

    assert process_list(items=[1, 2, 3]) == 6
    assert process_list(items=[1, 2, 3]) == 6  # Should hit cache
    assert process_list.cache_info()["cache_size"] == 1


def test_unhashable_args():
    """Test caching with unhashable arguments."""

    @cache_with_transforms(arg_transformers={0: tuple})
    def process_list(lst: list[int]) -> int:
        return sum(lst)

    assert process_list([1, 2, 3]) == 6
    assert process_list([1, 2, 3]) == 6  # Should hit cache
    assert process_list.cache_info()["cache_size"] == 1


def test_mixed_args_kwargs():
    """Test caching with both positional and keyword arguments."""

    @cache_with_transforms(
        arg_transformers={0: str.lower}, kwarg_transformers={"items": tuple}
    )
    def process_data(prefix: str, *, items: list[int]) -> str:
        return f"{prefix}: {sum(items)}"

    assert process_data("Sum", items=[1, 2, 3]) == "Sum: 6"
    assert process_data("SUM", items=[1, 2, 3]) == "Sum: 6"  # Should hit cache
    assert process_data.cache_info()["cache_size"] == 1


def test_multiple_calls_different_args():
    """Test caching behavior with different arguments."""
    call_count = 0

    @cache_with_transforms()
    def add(x: int, y: int) -> int:
        nonlocal call_count
        call_count += 1
        return x + y

    assert add(1, 2) == 3
    assert add(2, 3) == 5
    assert add(1, 2) == 3  # Should hit cache
    assert call_count == 2
    assert add.cache_info()["cache_size"] == 2


def test_none_values():
    """Test caching behavior with None values."""

    @cache_with_transforms()
    def process_optional(x: Any) -> str:
        return str(x)

    assert process_optional(None) == "None"
    assert process_optional(None) == "None"  # Should hit cache
    assert process_optional.cache_info()["cache_size"] == 1


def test_empty_transformers():
    """Test that decorator works with empty transformers."""

    @cache_with_transforms(arg_transformers={}, kwarg_transformers={})
    def identity(x: int) -> int:
        return x

    assert identity(1) == 1
    assert identity.cache_info()["cache_size"] == 1


def test_cache_persistence():
    """Test that cache persists between calls."""

    @cache_with_transforms()
    def expensive_operation(x: int) -> int:
        return x**2

    assert expensive_operation(2) == 4
    initial_cache = expensive_operation.cache
    assert expensive_operation(2) == 4
    assert expensive_operation.cache is initial_cache


def test_different_kwarg_orders():
    """Test that different keyword argument orders produce same cache key."""

    @cache_with_transforms()
    def process_kwargs(*, a: int, b: int) -> int:
        return a + b

    assert process_kwargs(a=1, b=2) == 3
    assert process_kwargs(b=2, a=1) == 3  # Should hit cache
    assert process_kwargs.cache_info()["cache_size"] == 1


def test_complex_transformers():
    """Test with more complex transformer functions."""

    def complex_transform(x: list[Any]) -> tuple[Any, ...]:
        return tuple(sorted(x))

    @cache_with_transforms(
        arg_transformers={0: complex_transform},
        kwarg_transformers={"data": complex_transform},
    )
    def process_lists(lst: list[int], *, data: list[int]) -> int:
        return sum(lst) + sum(data)

    assert process_lists([3, 1, 2], data=[6, 4, 5]) == 21
    assert process_lists([2, 3, 1], data=[5, 6, 4]) == 21  # Should hit cache
    assert process_lists.cache_info()["cache_size"] == 1


def test_error_handling():
    """Test that errors in the original function are not cached."""

    @cache_with_transforms()
    def failing_function(x: int) -> int:
        msg = "Error"
        raise ValueError(msg)

    with pytest.raises(ValueError):  # noqa: PT011
        failing_function(1)

    with pytest.raises(ValueError):  # noqa: PT011
        failing_function(1)  # Should not be cached

    assert failing_function.cache_info()["cache_size"] == 0


if __name__ == "__main__":
    pytest.main([__file__])
