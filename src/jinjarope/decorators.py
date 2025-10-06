from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from collections.abc import Callable


def cache_with_transforms[**P, R](
    *,
    arg_transformers: dict[int, Callable[[Any], Any]] | None = None,
    kwarg_transformers: dict[str, Callable[[Any], Any]] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """A caching decorator with transformation functions for args and kwargs.

    Can be used to make specific args / kwargs hashable.
    Also adds cache and cache_info objects to the decorated function.

    Args:
        arg_transformers: Dict mapping positional args indices to transformer functions
        kwarg_transformers: Dict mapping kwargs names to transformer functions

    Returns:
        A decorator function that caches results based on transformed arguments
    """
    arg_transformers = arg_transformers or {}
    kwarg_transformers = kwarg_transformers or {}

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        cache: dict[tuple[Any, ...], R] = {}

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Transform positional arguments
            transformed_args = tuple(
                arg_transformers.get(i, lambda x: x)(arg) for i, arg in enumerate(args)
            )

            # Transform keyword arguments
            transformed_kwargs = {
                key: kwarg_transformers.get(key, lambda x: x)(value)
                for key, value in sorted(kwargs.items())
            }

            # Create cache key from transformed arguments
            cache_key = (transformed_args, tuple(transformed_kwargs.items()))

            if cache_key not in cache:
                cache[cache_key] = func(*args, **kwargs)
            return cache[cache_key]

        def cache_info() -> dict[str, int]:
            """Return information about cache hits and size."""
            return {"cache_size": len(cache)}

        wrapper.cache_info = cache_info  # type: ignore
        wrapper.cache = cache  # type: ignore

        return wrapper

    return decorator


if __name__ == "__main__":
    import upath

    @cache_with_transforms(arg_transformers={0: lambda p: upath.UPath(p).resolve()})
    def read_file_content(filepath: str | upath.UPath) -> str:
        """Read and return the content of a file."""
        with upath.UPath(filepath).open() as f:
            return f.read()

    # These calls will use the same cache entry
    content1 = read_file_content("pyproject.toml")
    content1 = read_file_content("mkdocs.yml")
    content2 = read_file_content(upath.UPath("pyproject.toml"))
    content3 = read_file_content(upath.UPath("./pyproject.toml").absolute())

    # Check cache statistics
    print(read_file_content.cache_info())  # type: ignore
