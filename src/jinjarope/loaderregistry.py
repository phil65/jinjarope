from __future__ import annotations

import pathlib
import types
from typing import TYPE_CHECKING, Any

from jinjarope import fsspecloaders, iterfilters, loaders


if TYPE_CHECKING:
    from collections.abc import Callable
    import os

    import jinja2


class LoaderRegistry:
    """Registry which caches and builds jinja loaders."""

    def __init__(self) -> None:
        self.fs_loaders: dict[str, loaders.FileSystemLoader] = {}
        self.fsspec_loaders: dict[str, fsspecloaders.FsSpecFileSystemLoader] = {}
        self.package_loaders: dict[str, loaders.PackageLoader] = {}

    def by_path(
        self,
        path: str | os.PathLike[str],
    ) -> loaders.FileSystemLoader | fsspecloaders.FsSpecFileSystemLoader:
        """Convenience method to get a suiting loader for given path.

        Return a FsSpec loader for protocol-like paths or else a FileSystem loader.

        Args:
            path: The path to get a loader for
        """
        if "://" in str(path):
            return self.get_fsspec_loader(str(path))
        return self.get_filesystem_loader(path)

    def get_fsspec_loader(self, path: str) -> fsspecloaders.FsSpecFileSystemLoader:
        """Return a FsSpec loader for given path from registry.

        If the loader does not exist yet, create and cache it.

        Args:
            path: The path to get a loader for
        """
        if path in self.fsspec_loaders:
            return self.fsspec_loaders[path]
        loader = fsspecloaders.FsSpecFileSystemLoader(path)
        self.fsspec_loaders[path] = loader
        return loader

    def get_filesystem_loader(
        self,
        path: str | os.PathLike[str],
    ) -> loaders.FileSystemLoader:
        """Return a FileSystem loader for given path from registry.

        If the loader does not exist yet, create and cache it.

        Args:
            path: The path to get a loader for
        """
        path = pathlib.Path(path).as_posix()
        if path in self.fs_loaders:
            return self.fs_loaders[path]
        loader = loaders.FileSystemLoader(path)
        self.fs_loaders[path] = loader
        return loader

    def get_package_loader(self, package: str) -> loaders.PackageLoader:
        """Return a Package loader for given (dotted) package path from registry.

        If the loader does not exist yet, create and cache it.

        Args:
            package: The package to get a loader for
        """
        if package in self.package_loaders:
            return self.package_loaders[package]
        loader = loaders.PackageLoader(package)
        self.package_loaders[package] = loader
        return loader

    def get_loader(
        self,
        *args: str | types.ModuleType,
        dir_paths: list[str] | None = None,
        module_paths: list[str] | None = None,
        functions: list[Callable[..., Any]] | None = None,
        static: dict[str, str] | None = None,
        fsspec_paths: bool = True,
    ) -> jinja2.BaseLoader:
        """Construct a Loader.

        If given a positional argument, return a loader for given argument,
        otherwise return a ChoiceLoader based on given keyword arguments.
        Loader is constructed from cached sub-loaders if existing, otherwise they are
        created (and cached).

        Args:
            args: What to get a loader for (can be path or module)
            dir_paths: Directory paths (either FsSpec-protocol URLs to a folder or
                       filesystem paths)
            module_paths: (dotted) package paths
            functions: A list of callables
            static: A dictionary containing a path-> template mapping
            fsspec_paths: Whether a loader for FsSpec protcol paths should be added
        """
        match args:
            case (str() as path,):
                return self.by_path(path)
            case (types.ModuleType() as mod,):
                return loaders.PackageLoader(mod)
            case (fn,) if callable(fn):
                return loaders.FunctionLoader(fn)
        m_paths = iterfilters.reduce_list(module_paths or [])
        loader = loaders.ChoiceLoader([self.get_package_loader(p) for p in m_paths])
        for file in iterfilters.reduce_list(dir_paths or []):
            if "://" in file:
                loader |= self.get_fsspec_loader(file)
            else:
                loader |= self.get_filesystem_loader(file)
        for function in functions or []:
            loader |= loaders.FunctionLoader(function)
        if static:
            loader |= loaders.DictLoader(static)
        if fsspec_paths:
            loader |= fsspecloaders.FsSpecProtocolPathLoader()
        return loader


registry = LoaderRegistry()


if __name__ == "__main__":
    pass
