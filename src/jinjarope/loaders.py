from __future__ import annotations

import os
import pathlib
import types
from typing import TYPE_CHECKING, Any

import jinja2

from jinjarope import inspectfilters, utils


if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from fsspec.utils import Iterator  # type: ignore[import-untyped]
    from jinja2 import BaseLoader


class LoaderMixin:
    """Loader mixin which allows to OR loaders into a choice loader."""

    ID: str
    loader: jinja2.BaseLoader
    list_templates: Callable[..., Any]
    get_source: Callable[..., Any]
    load: Callable[..., jinja2.Template]

    def __or__(self, other: jinja2.BaseLoader) -> ChoiceLoader:
        own = self.loaders if isinstance(self, jinja2.ChoiceLoader) else [self]  # type: ignore[list-item]
        others = other.loaders if isinstance(other, jinja2.ChoiceLoader) else [other]
        return ChoiceLoader([*own, *others])  # pyright: ignore[reportArgumentType]

    def __getitem__(self, val: str) -> jinja2.Template:
        """Return the template object for given template path."""
        return self.load(None, val)

    def __contains__(self, path: str) -> bool:
        """Check whether given path is loadable by this loader."""
        import upath

        return upath.UPath(path).as_posix() in self.list_templates()

    def __rtruediv__(self, path: str) -> PrefixLoader:
        return self.prefixed_with(path)

    def prefixed_with(self, prefix: str) -> PrefixLoader:
        """Return loader wrapped in a PrefixLoader instance with given prefix.

        Args:
            prefix: The prefix to use
        """
        return PrefixLoader({prefix: self})  # type: ignore[dict-item]

    def get_template_source(self, template_path: str) -> str:
        """Return the source for given template path."""
        return self.get_source(None, template_path)[0]  # type: ignore[no-any-return]


class PrefixLoader(LoaderMixin, jinja2.PrefixLoader):
    """A loader for prefixing other loaders."""

    ID = "prefix"

    def __repr__(self) -> str:
        return utils.get_repr(self, self.mapping)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PrefixLoader):
            return NotImplemented
        return self.mapping == other.mapping

    def __hash__(self) -> int:
        return hash(tuple(sorted(self.mapping.items())))

    def __bool__(self) -> bool:
        return bool(self.mapping)

    def __iter__(self) -> Iterator[Mapping[str, BaseLoader]]:
        return iter(self.mapping)


class ModuleLoader(LoaderMixin, jinja2.ModuleLoader):
    """This loader loads templates from precompiled templates.

    Templates can be precompiled with :meth:`Environment.compile_templates`.
    """

    ID = "module"

    def __repr__(self) -> str:
        return utils.get_repr(self, path=self.module.__path__)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ModuleLoader):
            return NotImplemented
        return self.package_name == other.package_name and self.module == other.module

    def __hash__(self) -> int:
        return hash(self.package_name) + hash(self.module)


class FunctionLoader(LoaderMixin, jinja2.FunctionLoader):
    """A loader for loading templates from a function.

    The function takes a template path as parameter and either returns
    a (text, None, uptodate_fn) tuple or just the text as str.
    """

    ID = "function"

    def __repr__(self) -> str:
        return utils.get_repr(self, self.load_func)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FunctionLoader):
            return NotImplemented
        return self.load_func == other.load_func

    def __hash__(self) -> int:
        return hash(self.load_func)


class PackageLoader(LoaderMixin, jinja2.PackageLoader):
    """A loader for loading templates from a package."""

    ID = "package"

    def __init__(
        self,
        package: str | types.ModuleType,
        package_path: str | None = None,
        encoding: str = "utf-8",
    ) -> None:
        """Instanciate a PackageLoader.

        Compared to the jinja2 equivalent, this loader also supports
        `ModuleType`s and dotted module paths for the `package` argument.

        Args:
            package: The python package to create a loader for
            package_path: If given, use the given path as the root.
            encoding: The encoding to use for loading templates
        """
        if isinstance(package, types.ModuleType):
            package = package.__name__
        parts = package.split(".")
        path = "/".join(parts[1:])
        if package_path:
            path = (pathlib.Path(path) / package_path).as_posix()
        super().__init__(parts[0], path, encoding)

    def __repr__(self) -> str:
        return utils.get_repr(
            self,
            package_name=self.package_name,
            package_path=self.package_path,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PackageLoader):
            return NotImplemented
        return self.package_name == other.package_name and self.package_path == other.package_path

    def __hash__(self) -> int:
        return hash(self.package_name) + hash(self.package_path)


class FileSystemLoader(LoaderMixin, jinja2.FileSystemLoader):
    """A loader to load templates from the file system."""

    ID = "filesystem"

    def __repr__(self) -> str:
        return utils.get_repr(self, searchpath=self.searchpath)

    def __add__(self, other: FileSystemLoader | str | os.PathLike[str]) -> FileSystemLoader:
        ls = [other] if isinstance(other, str | os.PathLike) else other.searchpath
        return FileSystemLoader([*self.searchpath, *ls])  # pyright: ignore

    def __bool__(self) -> bool:
        return len(self.searchpath) > 0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FileSystemLoader):
            return NotImplemented
        return self.searchpath == other.searchpath

    def __hash__(self) -> int:
        return hash(tuple(self.searchpath))


class ChoiceLoader(LoaderMixin, jinja2.ChoiceLoader):
    """A loader which combines multiple other loaders."""

    ID = "choice"

    def __repr__(self) -> str:
        return utils.get_repr(self, loaders=self.loaders)

    def __bool__(self) -> bool:
        return len(self.loaders) > 0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ChoiceLoader):
            return NotImplemented
        return self.loaders == other.loaders

    def __hash__(self) -> int:
        return hash(tuple(self.loaders))

    def __iter__(self) -> Iterator[jinja2.BaseLoader]:
        return iter(self.loaders)


class DictLoader(LoaderMixin, jinja2.DictLoader):
    """A loader to load static content from a path->template-str mapping."""

    ID = "dict"

    def __repr__(self) -> str:
        return utils.get_repr(self, mapping=self.mapping)

    def __add__(self, other: dict[str, str] | jinja2.DictLoader) -> DictLoader:
        if isinstance(other, jinja2.DictLoader):
            mapping = {**self.mapping, **other.mapping}
        else:
            mapping = {**self.mapping, **other}
        return DictLoader(mapping)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DictLoader):
            return NotImplemented
        return self.mapping == other.mapping

    def __hash__(self) -> int:
        return hash(tuple(sorted(self.mapping.items())))


def from_json(
    dct_or_list: dict[str, Any] | list[Any] | None | jinja2.BaseLoader,
) -> jinja2.BaseLoader | None:
    """Create a loader based on a json representation.

    Args:
        dct_or_list: A dictionary or list describing loaders.
    """
    from jinjarope import fsspecloaders

    if not dct_or_list:
        return None
    loaders = []
    ls = dct_or_list if isinstance(dct_or_list, list) else [dct_or_list]
    for item in ls:
        match item:
            case jinja2.BaseLoader():
                loader = item
            case str() if "://" in item:
                loader = fsspecloaders.FsSpecFileSystemLoader(item)
            case str():
                loader = FileSystemLoader(item)
            case types.ModuleType():
                loader = PackageLoader(item)
            case dict():
                dct_copy = item.copy()
                typ = dct_copy.pop("type")
                mapping = dct_copy.pop("mapping", None)
                prefix = dct_copy.pop("prefix", None)
                kls = next(
                    kls
                    for kls in inspectfilters.list_subclasses(jinja2.BaseLoader)
                    if getattr(kls, "ID", None) == typ
                )
                if kls.ID == "prefix":
                    mapping = {k: from_json(v) for k, v in mapping.items()}
                    loader = kls(mapping)
                elif prefix:
                    loader = prefix / kls(**dct_copy)
                else:
                    loader = kls(**dct_copy)
            case _:
                raise TypeError(item)
        loaders.append(loader)
    match len(loaders):
        case 1:
            return loaders[0]
        case 0:
            return None
        case _:
            return ChoiceLoader(loaders)


if __name__ == "__main__":
    from jinjarope import Environment

    env = Environment()
    env.loader = FileSystemLoader("")
    text = env.render_template(".pre-commit-config.yaml")
