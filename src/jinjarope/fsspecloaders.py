from __future__ import annotations

import functools
import pathlib
from typing import TYPE_CHECKING, Any

import jinja2
import upathtools

from jinjarope import envglobals, loaders as loaders_, utils


if TYPE_CHECKING:
    from collections.abc import Callable

    import fsspec  # type: ignore[import-untyped]


@functools.cache
async def get_template(path: str) -> str:
    return await upathtools.read_path(path)


class FsSpecProtocolPathLoader(loaders_.LoaderMixin, jinja2.BaseLoader):
    """A jinja loader for fsspec filesystems.

    This loader allows to access templates from an fsspec protocol path,
    like "github://phil65:mknodes@main/README.md"

    Examples:
        ``` py
        loader = FsSpecProtocolPathLoader()
        env = Environment(loader=loader)
        env.get_template("github://phil65:mknodes@main/docs/icons.jinja").render()
        ```
    """

    ID = "fsspec_protocol_path"

    def __eq__(self, other: object) -> bool:
        return type(self) is type(other)

    def __hash__(self) -> int:
        return hash(type(self))

    def get_source(
        self,
        environment: jinja2.Environment | None,
        template: str,
    ) -> tuple[str, str, Callable[[], bool] | None]:
        try:
            src = envglobals.load_file_cached(template)
        except FileNotFoundError as e:
            raise jinja2.TemplateNotFound(template) from e
        path = pathlib.Path(template).as_posix()
        return src, path, lambda: True

    async def get_source_async(
        self,
        environment: jinja2.Environment | None,
        template: str,
    ) -> tuple[str, str, Callable[[], bool] | None]:
        try:
            src = await get_template(template)
        except FileNotFoundError as e:
            raise jinja2.TemplateNotFound(template) from e
        path = pathlib.Path(template).as_posix()
        return src, path, lambda: True

    def list_templates(self) -> list[str]:
        return []

    def __contains__(self, path: str) -> bool:
        try:
            self.get_source(None, path)
        except jinja2.TemplateNotFound:
            return False
        else:
            return True

    def __repr__(self) -> str:
        return utils.get_repr(self)


class FsSpecFileSystemLoader(loaders_.LoaderMixin, jinja2.BaseLoader):
    """A jinja loader for fsspec filesystems.

    This loader allows to access templates from an fsspec filesystem.

    Template paths must be relative to the filesystem root.
    In order to access templates via protocol path, see `FsSpecProtocolPathLoader`.

    Examples:
        ``` py
        # protocol path
        loader = FsSpecFileSystemLoader("dir::github://phil65:mknodes@main/docs")
        env = Environment(loader=loader)
        env.get_template("icons.jinja").render()

        # protocol and storage options
        loader = FsSpecFileSystemLoader("github", org="phil65", repo="mknodes")
        env = Environment(loader=loader)
        env.get_template("docs/icons.jinja").render()

        # fsspec filesystem
        fs = fsspec.filesystem("github", org="phil65", repo="mknodes")
        loader = FsSpecFileSystemLoader(fs)
        env = Environment(loader=loader)
        env.get_template("docs/icons.jinja").render()
        ```

    """

    ID = "fsspec"

    def __init__(self, fs: fsspec.AbstractFileSystem | str, **kwargs: Any) -> None:
        """Constructor.

        Args:
            fs: Either a protocol path string or an fsspec filesystem instance.
                Also supports "::dir" prefix to set the root path.
            kwargs: Optional storage options for the filesystem.
        """
        import fsspec
        import fsspec.core  # type: ignore[import-untyped]

        super().__init__()
        match fs:
            case str() if "://" in fs:
                self.fs, self.path = fsspec.core.url_to_fs(fs, **kwargs)
            case str():
                self.fs, self.path = fsspec.filesystem(fs, **kwargs), ""
            case _:
                self.fs, self.path = fs, ""
        self.storage_options = kwargs

    def __repr__(self) -> str:
        return utils.get_repr(self, fs=self.fs)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FsSpecFileSystemLoader):
            return NotImplemented
        return (
            self.storage_options == other.storage_options
            and self.fs == other.fs
            and self.path == other.path
        )

    def __hash__(self) -> int:
        return hash(tuple(sorted(self.storage_options.items()))) + hash(self.fs) + hash(self.path)

    def list_templates(self) -> list[str]:
        return [
            f"{path}{self.fs.sep}{f}" if path else f
            for path, _dirs, files in self.fs.walk(self.fs.root_marker)
            for f in files
        ]

    def get_source(
        self,
        environment: jinja2.Environment,
        template: str,
    ) -> tuple[str, str, Callable[[], bool] | None]:
        try:
            with self.fs.open(template) as file:
                src = file.read().decode()  # pyright: ignore
        except FileNotFoundError as e:
            raise jinja2.TemplateNotFound(template) from e
        path = pathlib.Path(template).as_posix()
        return src, path, lambda: True

    async def get_source_async(
        self,
        environment: jinja2.Environment,
        template: str,
    ) -> tuple[str, str, Callable[[], bool] | None]:
        from upathtools.async_ops import get_async_fs

        fs = await get_async_fs(self.fs)
        try:
            file = await fs.open_async(template)
            async with file:
                src = await file.read().decode()  # pyright: ignore
        except FileNotFoundError as e:
            raise jinja2.TemplateNotFound(template) from e
        path = pathlib.Path(template).as_posix()
        return src, path, lambda: True


if __name__ == "__main__":
    from jinjarope import Environment

    loader = FsSpecFileSystemLoader("dir::github://phil65:mknodes@main/docs")
    env = Environment()
    env.loader = loader
    # template = env.get_template("icons.jinja")
    print(env.list_templates())
    # loader = FsSpecProtocolPathLoader()
    # result = loader.get_source(env, "github://phil65:mknodes@main/READMdE.md")
    # print(repr(loader))
