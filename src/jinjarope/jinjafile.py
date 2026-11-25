from __future__ import annotations

import dataclasses
import functools
import logging
import os
import tomllib
from typing import TYPE_CHECKING, Any, Literal, Self

import jinjarope
from jinjarope import envconfig, envglobals, envtests, loaders, utils


logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from collections.abc import Callable

    import jinja2


@functools.cache
def _load(txt: str) -> dict[str, Any]:
    """Some dumb caching since this might be invoked on each env instanciation."""
    return tomllib.loads(txt)


class JinjaFile(dict[str, Any]):
    """A file defining filters / tests."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        """Instanciate the file.

        Args:
            path: Path to the jinja file
        """
        super().__init__()
        text = envglobals.load_file_cached(os.fspath(path))
        data = _load(text)
        self.update(data)

    @property
    def filters(self) -> list[JinjaItem]:
        """Return list of filters defined in the file."""
        return [
            JinjaItem(filter_name, typ="filter", **dct)
            for filter_name, dct in self.get("filters", {}).items()
            if all(envtests.is_installed(i) for i in dct.get("required_packages", []))
        ]

    @property
    def tests(self) -> list[JinjaItem]:
        """Return list of tests defined in the file."""
        return [
            JinjaItem(filter_name, typ="test", **dct)
            for filter_name, dct in self.get("tests", {}).items()
            if all(envtests.is_installed(i) for i in dct.get("required_packages", []))
        ]

    @property
    def functions(self) -> list[JinjaItem]:
        """Return list of functions defined in the file."""
        return [
            JinjaItem(filter_name, typ="function", **dct)
            for filter_name, dct in self.get("functions", {}).items()
            if all(envtests.is_installed(i) for i in dct.get("required_packages", []))
        ]

    @property
    def filters_dict(self) -> dict[str, Callable[..., Any]]:
        """Return a dictionary with all filters.

        Can directly get merged into env filters.
        """
        return _collect(self.filters)

    @property
    def tests_dict(self) -> dict[str, Callable[..., bool]]:
        """Return a dictionary with all filters.

        Can directly get merged into env filters.
        """
        return _collect(self.tests)

    @property
    def functions_dict(self) -> dict[str, Callable[..., Any]]:
        """Return a dictionary with all filters.

        Can directly get merged into env filters.
        """
        return _collect(self.functions)

    @property
    def envconfig(self) -> envconfig.EnvConfig:  # ty: ignore[missing-attribute]
        """Return the config object defined in this Jinja file."""
        cfg = self.get("config", {})
        return envconfig.EnvConfig(**cfg, loader=self.loader)

    @property
    def loader(self) -> jinja2.BaseLoader | None:
        """Return a (composed Choice-) loader defined in this Jinja file."""
        return loaders.from_json(self.get("loaders", []))


type ItemDicts = tuple[dict[str, Any], dict[str, Any], dict[str, Any]]


def load_items(path: str | os.PathLike[str]) -> ItemDicts:
    """Return (filters, tests, functions) of given Jinja file, cached per file version.

    Environments get created often (one per node in MkNodes); parsing the TOML and
    checking `required_packages` again for each of them is wasted work.
    """
    resolved = os.path.abspath(os.fspath(path))  # noqa: PTH100
    try:
        mtime = os.stat(resolved).st_mtime_ns  # noqa: PTH116
    except OSError:  # remote / virtual paths: no caching
        file = JinjaFile(path)
        return file.filters_dict, file.tests_dict, file.functions_dict
    return _load_items_cached(resolved, mtime)


@functools.cache
def _load_items_cached(
    path: str, mtime: int
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    file = JinjaFile(path)
    return file.filters_dict, file.tests_dict, file.functions_dict


def _collect(items: list[JinjaItem]) -> dict[str, Callable[..., Any]]:
    """Map identifiers and aliases to callables.

    The callables are lazy: the target gets imported on first use. Creating an
    environment therefore doesn't import every library a filter file refers to
    (e.g. the LLM filters import agentpool, which takes seconds). Items with missing
    ``required_packages`` are left out; a target that fails to import raises on use.
    """
    dct: dict[str, Callable[..., Any]] = {}
    for item in items:
        fn = item.lazy_fn
        dct[item.identifier] = fn
        for alias in item.aliases:
            dct[alias] = fn
    return dct


class LazyCallable:
    """Callable proxy importing the target of a `JinjaItem` on first use.

    Attribute access is forwarded to the target, so Jinja sees `jinja_pass_arg`
    (`@pass_context` & co.) and `inspect` sees the signature (via `__wrapped__`).
    """

    __slots__ = ("_item", "_target")

    def __init__(self, item: JinjaItem) -> None:
        self._item = item
        self._target: Callable[..., Any] | None = None

    @property
    def __wrapped__(self) -> Callable[..., Any]:
        if self._target is None:
            self._target = self._item.filter_fn
        return self._target

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.__wrapped__(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.__wrapped__, name)

    def __repr__(self) -> str:
        state = "resolved" if self._target is not None else "lazy"
        return f"{type(self).__name__}({self._item.fn!r}, {state})"


@dataclasses.dataclass(frozen=True)
class JinjaItem:
    """An item representing a filter / test."""

    identifier: str
    typ: Literal["filter", "test", "function"]
    fn: str
    group: str
    icon: str | None = None
    examples: dict[str, dict[str, str]] = dataclasses.field(default_factory=dict)
    description: str | None = None
    aliases: list[str] = dataclasses.field(default_factory=list)
    required_packages: list[str] = dataclasses.field(default_factory=list)

    def __repr__(self) -> str:
        return utils.get_repr(self, self.identifier)

    @property
    def filter_fn(self) -> Callable[..., Any]:
        """Return the callable to use as filter / test / function (imported now)."""
        try:
            obj = utils.resolve(self.fn)
        except AttributeError:
            msg = f"Could not import jinja item {self.identifier!r} from {self.fn!r}"
            raise ImportError(msg) from AttributeError
        if not callable(obj):
            msg = "Filter needs correct, importable Path for callable"
            raise TypeError(msg)
        return obj  # type: ignore[no-any-return]

    @functools.cached_property
    def lazy_fn(self) -> LazyCallable:
        """Return a callable which imports the filter / test / function on first use."""
        return LazyCallable(self)

    @classmethod
    def for_function(
        cls,
        fn: Callable[..., Any],
        typ: Literal["filter", "test", "function"],
        group: str = "imported",
        **kwargs: Any,
    ) -> Self:
        """Alternative ctor to construct a JinjaItem based on a callable.

        Args:
            fn: Callable to get a JinjaItem for
            typ: The item type
            group: Group for metadata
            kwargs: Additional keyword arguments for JinjaItem ctor
        """
        return cls(
            fn.__name__,  # ty: ignore[missing-attribute]
            typ=typ,
            fn=f"{fn.__module__}.{fn.__name__}",  # ty: ignore[missing-attribute]
            group=group,
            **kwargs,
        )

    def apply(self, *args: Any, **kwargs: Any) -> Any:
        """Apply the filter function using given arguments and keywords.

        Args:
            args: The arguments for the call
            kwargs: They keyword arguments for the call
        """
        return self.filter_fn(*args, **kwargs)

    def resolve_example(self, example_name: str) -> str:
        """Render example with given name and return the result.

        Args:
            example_name: The example identifier
        """
        example = self.examples[example_name]
        loader = jinjarope.FileSystemLoader("")
        env = jinjarope.Environment(loader=loader)
        return env.render_string(example["template"])


if __name__ == "__main__":
    file = JinjaFile("src/jinjarope/resources/filters.toml")
    print(file.filters[5].resolve_example("basic"))
