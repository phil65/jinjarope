from __future__ import annotations

import dataclasses
import functools
import os
import tomllib
from typing import TYPE_CHECKING, Any, Literal, Self

import jinjarope
from jinjarope import envconfig, envglobals, envtests, loaders, utils


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
        dct = {}
        for f in self.filters:
            dct[f.identifier] = f.filter_fn
            for alias in f.aliases:
                dct[alias] = f.filter_fn
        return dct

    @property
    def tests_dict(self) -> dict[str, Callable[..., bool]]:
        """Return a dictionary with all filters.

        Can directly get merged into env filters.
        """
        dct = {}
        for f in self.tests:
            dct[f.identifier] = f.filter_fn
            for alias in f.aliases:
                dct[alias] = f.filter_fn
        return dct

    @property
    def functions_dict(self) -> dict[str, Callable[..., Any]]:
        """Return a dictionary with all filters.

        Can directly get merged into env filters.
        """
        dct = {}
        for f in self.functions:
            dct[f.identifier] = f.filter_fn
            for alias in f.aliases:
                dct[alias] = f.filter_fn
        return dct

    @property
    def envconfig(self) -> envconfig.EnvConfig:
        """Return the config object defined in this Jinja file."""
        cfg = self.get("config", {})
        return envconfig.EnvConfig(**cfg, loader=self.loader)

    @property
    def loader(self) -> jinja2.BaseLoader | None:
        """Return a (composed Choice-) loader defined in this Jinja file."""
        return loaders.from_json(self.get("loaders", []))


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
        """Return the callable to use as filter / test / function."""
        try:
            obj = utils.resolve(self.fn)
        except AttributeError:
            msg = f"Could not import jinja item {self.identifier!r} from {self.fn!r}"
            raise ImportError(msg) from AttributeError
        if not callable(obj):
            msg = "Filter needs correct, importable Path for callable"
            raise TypeError(msg)
        return obj  # type: ignore[no-any-return]

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
            fn.__name__,
            typ=typ,
            fn=f"{fn.__module__}.{fn.__name__}",
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
