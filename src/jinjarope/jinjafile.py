from __future__ import annotations

from collections.abc import Callable
import dataclasses
import os
import tomllib

import jinjarope

from jinjarope import envconfig, envglobals, envtests, utils


class JinjaFile(dict):
    """A file defining filters / tests."""

    def __init__(self, path: str | os.PathLike):
        """Instanciate the file.

        Arguments:
            path: Path to the jinja file
        """
        super().__init__()
        text = envglobals.load_file_cached(os.fspath(path))
        data = tomllib.loads(text)
        self.update(data)

    @property
    def filters(self) -> list[JinjaItem]:
        """Return list of filters defined in the file."""
        return [
            JinjaItem(filter_name, **dct)
            for filter_name, dct in self.get("filters", {}).items()
            if all(envtests.is_installed(i) for i in dct.get("required_packages", []))
        ]

    @property
    def tests(self) -> list[JinjaItem]:
        """Return list of tests defined in the file."""
        return [
            JinjaItem(filter_name, **dct)
            for filter_name, dct in self.get("tests", {}).items()
            if all(envtests.is_installed(i) for i in dct.get("required_packages", []))
        ]

    @property
    def functions(self) -> list[JinjaItem]:
        """Return list of functions defined in the file."""
        return [
            JinjaItem(filter_name, **dct)
            for filter_name, dct in self.get("functions", {}).items()
            if all(envtests.is_installed(i) for i in dct.get("required_packages", []))
        ]

    @property
    def filters_dict(self) -> dict[str, Callable]:
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
    def tests_dict(self) -> dict[str, Callable]:
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
    def functions_dict(self) -> dict[str, Callable]:
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
    def envconfig(self):
        cfg = self.get("config", {})
        return envconfig.EnvConfig(**cfg)


@dataclasses.dataclass(frozen=True)
class JinjaItem:
    """An item representing a filter / test."""

    identifier: str
    fn: str
    group: str
    examples: dict = dataclasses.field(default_factory=dict)
    description: str | None = None
    aliases: list[str] = dataclasses.field(default_factory=list)
    required_packages: list[str] = dataclasses.field(default_factory=list)

    @property
    def filter_fn(self):
        obj = utils.resolve(self.fn)
        if not callable(obj):
            msg = "Filter needs correct, importable Path for callable"
            raise TypeError(msg)
        return obj

    def apply(self, *args, **kwargs):
        self.filter_fn(*args, **kwargs)

    def resolve_example(self, example_name):
        example = self.examples[example_name]
        env = jinjarope.Environment()
        return env.render_string(example["template"])


if __name__ == "__main__":
    file = JinjaFile("src/jinjarope/filters.toml")
    print(file.filters[5].resolve_example("basic"))
    import json

    json.loads("'test'")
