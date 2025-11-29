"""Filesystem implementation for jinja environment templates."""

from __future__ import annotations

import logging
from typing import Any, Literal, override

import fsspec  # type: ignore[import-untyped]
from fsspec.implementations import memory  # type: ignore[import-untyped]
import jinja2


logger = logging.getLogger(__name__)


class JinjaLoaderFileSystem(fsspec.AbstractFileSystem):  # type: ignore[misc]
    """A FsSpec Filesystem implementation for jinja environment templates."""

    protocol = "jinja"
    async_impl = True

    def __init__(self, env: jinja2.Environment) -> None:
        """Initialize a JinjaLoader filesystem.

        Args:
            env: The environment of the loaders to get a filesystem for.
        """
        super().__init__()
        self.env = env

    @override
    def isdir(self, path: str) -> bool:
        """Check if path is a directory.

        Args:
            path: Path to check

        Returns:
            True if path is a directory
        """
        from upath import UPath

        if not self.env.loader:
            return False

        clean_path = UPath(path).as_posix().strip("/")
        if clean_path in {"", "/", "."}:
            return True

        templates = self.env.loader.list_templates()
        return any(template.startswith(f"{clean_path}/") for template in templates)

    @override
    def isfile(self, path: str) -> bool:
        """Check if path is a file.

        Args:
            path: Path to check

        Returns:
            True if path is a file
        """
        if not self.env.loader:
            return False

        try:
            self.env.loader.get_source(self.env, path)
        except jinja2.TemplateNotFound:
            return False
        else:
            return True

    @override
    def cat_file(self, path: str, **kwargs: Any) -> bytes:
        """Get contents of file as bytes.

        Args:
            path: Path to file
            **kwargs: Additional arguments (unused)

        Returns:
            File contents as bytes

        Raises:
            FileNotFoundError: If template not found or env has no loader
        """
        if not self.env.loader:
            msg = "Environment has no loader"
            raise FileNotFoundError(msg)

        try:
            source, _, _ = self.env.loader.get_source(self.env, path)
            return source.encode()
        except jinja2.TemplateNotFound as exc:
            msg = f"Template not found: {path}"
            raise FileNotFoundError(msg) from exc

    @override
    def cat(self, path: str | list[str], **kwargs: Any) -> bytes | dict[str, bytes]:
        """Get contents of file(s).

        Args:
            path: Path or list of paths
            **kwargs: Additional arguments

        Returns:
            File contents as bytes or dict of path -> contents
        """
        if isinstance(path, str):
            return self.cat_file(path, **kwargs)

        return {p: self.cat_file(p, **kwargs) for p in path}

    async def _cat_file(self, path: str, **kwargs: Any) -> bytes:
        """Async implementation of cat_file.

        Args:
            path: Path to file
            **kwargs: Additional arguments

        Returns:
            File contents as bytes
        """
        return self.cat_file(path, **kwargs)

    @override
    def ls(self, path: str, detail: bool = True, **kwargs: Any) -> list[dict[str, str]] | list[str]:
        """List contents of path.

        Args:
            path: The path to list
            detail: If True, return a list of dictionaries, else return a list of paths
            **kwargs: Additional arguments (unused)

        Returns:
            List of paths or file details

        Raises:
            FileNotFoundError: If path doesn't exist or env has no loader
        """
        from upath import UPath

        if not self.env.loader:
            msg = "Environment has no loader"
            raise FileNotFoundError(msg)

        templates = self.env.loader.list_templates()
        clean_path = UPath(path).as_posix().strip("/")

        if clean_path in {"", "/", "."}:
            return self._list_root(templates, detail)
        return self._list_subdirectory(templates, clean_path, detail)

    def _list_root(self, templates: list[str], detail: bool) -> list[dict[str, str]] | list[str]:
        """List contents of root directory."""
        root_files = [path for path in templates if "/" not in path]
        root_dirs = {
            path.split("/")[0] for path in templates if "/" in path and path not in root_files
        }

        if detail:
            file_entries = [{"name": path, "type": "file"} for path in root_files]
            dir_entries = [{"name": path, "type": "directory"} for path in root_dirs]
            return dir_entries + file_entries
        return list(root_dirs) + root_files

    def _list_subdirectory(
        self, templates: list[str], path: str, detail: bool
    ) -> list[dict[str, str]] | list[str]:
        """List contents of a subdirectory."""
        # Get all templates that start with the path
        relevant_templates = [template for template in templates if template.startswith(f"{path}/")]

        if not relevant_templates:
            msg = f"Directory not found: {path}"
            raise FileNotFoundError(msg)

        # Get immediate children only
        items: set[str] = set()
        for template in relevant_templates:
            # Remove the path prefix and split the remaining path
            relative_path = template[len(f"{path}/") :].split("/", 1)[0]
            items.add(relative_path)

        # Sort for consistent ordering
        sorted_items = sorted(items)

        if detail:
            return [
                {
                    "name": item,
                    # If there's no extension or if it appears in the full paths
                    # with something after it, it's a directory
                    "type": "directory"
                    if ("." not in item or any(t.startswith(f"{path}/{item}/") for t in templates))
                    else "file",
                }
                for item in sorted_items
            ]
        return list(sorted_items)

    async def _ls(
        self, path: str, detail: bool = True, **kwargs: Any
    ) -> list[dict[str, str]] | list[str]:
        """Async implementation of ls."""
        return self.ls(path, detail=detail, **kwargs)

    @override
    def _open(
        self,
        path: str,
        mode: Literal["rb", "wb", "ab"] = "rb",
        block_size: int | None = None,
        autocommit: bool = True,
        cache_options: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> memory.MemoryFile:
        """Open a file."""
        if not self.env.loader:
            msg = "Environment has no loader"
            raise FileNotFoundError(msg)

        try:
            source, _, _ = self.env.loader.get_source(self.env, path)
            return memory.MemoryFile(fs=self, path=path, data=source.encode())
        except jinja2.TemplateNotFound as exc:
            msg = f"Template not found: {path}"
            raise FileNotFoundError(msg) from exc

    async def _open_async(
        self,
        path: str,
        mode: Literal["rb", "wb", "ab"] = "rb",
        block_size: int | None = None,
        autocommit: bool = True,
        cache_options: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> memory.MemoryFile:
        """Async implementation of _open."""
        return self._open(
            path,
            mode=mode,
            block_size=block_size,
            autocommit=autocommit,
            cache_options=cache_options,
            **kwargs,
        )

    @override
    def exists(self, path: str, **_kwargs: Any) -> bool:
        """Check if path exists.

        Args:
            path: Path to check

        Returns:
            True if path exists as a file or directory
        """
        return self.isfile(path) or self.isdir(path)

    @override
    def info(self, path: str, **kwargs: Any) -> dict[str, Any]:
        """Get info about a path.

        Args:
            path: Path to get info for
            **kwargs: Additional arguments (unused)

        Returns:
            Dictionary of path information

        Raises:
            FileNotFoundError: If path doesn't exist
        """
        if self.isfile(path):
            content = self.cat_file(path)
            return {
                "name": path,
                "size": len(content),
                "type": "file",
                "created": None,  # Jinja doesn't track these
                "modified": None,
            }
        if self.isdir(path):
            return {
                "name": path,
                "size": 0,
                "type": "directory",
                "created": None,
                "modified": None,
            }

        msg = f"Path not found: {path}"
        raise FileNotFoundError(msg)


if __name__ == "__main__":
    from jinjarope import loaders

    fsspec.register_implementation("jinja", JinjaLoaderFileSystem)
    template_env = jinja2.Environment(loader=loaders.PackageLoader("jinjarope"))
    filesystem = fsspec.filesystem("jinja", env=template_env)
    print(filesystem.ls(""))
