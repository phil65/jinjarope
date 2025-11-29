from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import jinja2

from jinjarope import loaders as loaders_, utils


if TYPE_CHECKING:
    from collections.abc import Callable


class RewriteLoader(loaders_.LoaderMixin, jinja2.BaseLoader):
    """A loader which modifies templates based on a callable.

    Can get chained like a PrefixLoader.
    The path passed to the callable can be used to check whether given template
    should be modified.
    """

    ID = "rewrite"

    def __init__(self, loader: jinja2.BaseLoader, rewrite_fn: Callable[[str, str], str]) -> None:
        """Instanciate the RewriteLoader.

        Args:
            loader: The loader to rewrite / modify the templates from
            rewrite_fn: Callable to modify templates.
                        It gets called with two arguments (path and template text)
                        and should return a (possibly modified) template text
        """
        self.loader = loader
        self.rewrite_fn = rewrite_fn

    def __repr__(self) -> str:
        return utils.get_repr(self, self.loader, self.rewrite_fn)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RewriteLoader):
            return NotImplemented
        return self.loader == other.loader and self.rewrite_fn == other.rewrite_fn

    def __hash__(self) -> int:
        return hash(self.loader) + hash(self.rewrite_fn)

    def get_source(
        self,
        environment: jinja2.Environment,
        template: str,
    ) -> tuple[str, str, Callable[[], bool] | None]:
        src: str | None
        src, filename, uptodate = self.loader.get_source(environment, template)
        old_src = src
        assert filename is not None
        path = pathlib.Path(filename).as_posix()
        src = self.rewrite_fn(path, src)
        return src or old_src, filename, uptodate


if __name__ == "__main__":
    import jinjarope

    loader = jinjarope.FsSpecProtocolPathLoader()
    rewrite_loader = RewriteLoader(loader, lambda path, x: x.replace("a", "XX"))
    env = jinjarope.Environment()
    env.loader = rewrite_loader
    result = env.render_template("github://phil65:mknodes@main/README.md")
    print(result)
