"""Engine-independent part of the jinjarope environments (all backends)."""

import ast
import contextlib
import io
import logging
import os
import pathlib
import time
from typing import TYPE_CHECKING, Any

import jinja2

import jinjarope
from jinjarope import envglobals, jinjafile, loaders, utils


if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from jinjarope import envconfig


logger = logging.getLogger(__name__)

RESOURCES = pathlib.Path(__file__).parent / "resources"
DEFAULT_JINJA_FILES = (
    "filters.toml",
    "tests.toml",
    "functions.toml",
    "humanize_filters.toml",
    "llm_filters.toml",
)


class EnvironmentBase:
    """Methods shared by the environments of all backends (see `jinjarope.engine`).

    Subclasses provide `filters`, `tests`, `globals`, `loader` and the render methods.
    """

    filters: dict[str, Callable[..., Any]]
    tests: dict[str, Callable[..., bool]]
    globals: dict[str, Any]
    loader: jinja2.BaseLoader | None
    _extra_files: set[str]
    _extra_paths: set[str]

    def render_string(
        self,
        string: str,
        variables: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        raise NotImplementedError

    def render_template(
        self,
        template_name: str,
        variables: dict[str, Any] | None = None,
        block_name: str | None = None,
        parent_template: str | None = None,
        **kwargs: Any,
    ) -> str:
        raise NotImplementedError

    def __contains__(self, template: str | os.PathLike[str]) -> bool:
        raise NotImplementedError

    def _apply_envconfig(self, cfg: envconfig.EnvConfig) -> None:
        """Apply the syntax / whitespace settings (and extensions) of a JinjaFile."""
        raise NotImplementedError

    def _install_defaults(self) -> None:
        """Add jinjarope's filters / tests / functions and the plugins' additions."""
        for name in DEFAULT_JINJA_FILES:
            self.load_jinja_file(RESOURCES / name)
        self.globals.update(envglobals.ENV_GLOBALS)
        for name, fn in utils.entry_points(group="jinjarope.environment").items():
            # A broken plugin (e.g. an incompatible dependency of another package)
            # must not break every environment: skip it with a warning.
            try:
                fn(self)
            except Exception:
                logger.warning("jinjarope.environment plugin %r failed", name, exc_info=True)
        self.filters["render_template"] = self.render_template
        self.filters["render_string"] = self.render_string
        self.filters["render_file"] = self.render_file
        self.filters["evaluate"] = self.evaluate
        self.globals["filters"] = self.filters
        self.globals["tests"] = self.tests
        self.tests["template"] = lambda template_name: template_name in self

    def get_source(self, template_name: str) -> str:
        """Return the source of a template of the loader.

        Args:
            template_name: The template name

        Raises:
            jinja2.TemplateNotFound: The loader doesn't know the template (or there is none)
        """
        if self.loader is None:
            raise jinja2.TemplateNotFound(template_name)
        return self.loader.get_source(None, template_name)[0]  # ty: ignore[invalid-argument-type]

    def load_jinja_file(
        self,
        path: str | os.PathLike[str],
        scope_prefix: str = "",
        load_filters: bool = True,
        load_tests: bool = True,
        load_functions: bool = True,
        load_config: bool = True,
        load_loader: bool = True,
    ) -> None:
        """Load the content of a JinjaFile and add it to the environment.

        This function reads a JinjaFile and adds its filters, tests,
        functions, and configuration to the current environment.

        Args:
            path: The path to the JinjaFile
            scope_prefix: Optional prefix to add to all tests / filters / functions
            load_filters: Whether to load filters from the JinjaFile
            load_tests: Whether to load tests from the JinjaFile
            load_functions: Whether to load functions from the JinjaFile
            load_config: Whether to load the environment config from the JinjaFile
            load_loader: Whether to load the Loader from the JinjaFile
        """
        file = jinjafile.JinjaFile(path)
        filters, tests, functions = jinjafile.load_items(path)
        if load_filters:
            self.filters.update({f"{scope_prefix}{k}": v for k, v in filters.items()})
        if load_tests:
            self.tests.update({f"{scope_prefix}{k}": v for k, v in tests.items()})
        if load_functions:
            self.globals.update({f"{scope_prefix}{k}": v for k, v in functions.items()})
        if load_config:
            self._apply_envconfig(file.envconfig)
        if load_loader and (loader := file.loader):
            self._add_loader(loader)

    def add_template(self, file: str | os.PathLike[str]) -> None:
        """Add a new template during runtime.

        This function adds a new template to the environment during
        runtime by creating a new DictLoader and injecting it into the
        existing loaders. This allows rendering templates that were not
        defined when the environment was initialized.

        !!! info "Use case"
            This function is particularly useful for situations where a
            template needs to be rendered dynamically, such as when
            rendering templates within other templates.

        Args:
            file: File to add as a template
        """
        # we keep track of already added extra files to not add things multiple times.
        file = str(file)
        if file in self._extra_files:
            return
        self._extra_files.add(file)
        content = envglobals.load_file_cached(file)
        new_loader = loaders.DictLoader({file: content})
        self._add_loader(new_loader)

    def add_template_path(self, *path: str | os.PathLike[str]) -> None:
        """Add a new template path during runtime.

        This function adds a new template path to the environment
        during runtime by appending a new FileSystemLoader to the
        existing loaders. This allows the environment to find templates
        in additional locations.

        Args:
            path: Template search path(s) to add
        """
        for p in path:
            if p in self._extra_paths:
                return
            self._extra_paths.add(str(p))
            new_loader = loaders.FileSystemLoader(p)
            self._add_loader(new_loader)

    def _add_loader(
        self,
        new_loader: jinja2.BaseLoader | dict[str, str] | str | os.PathLike[str],
    ) -> None:
        """Add a new loader to the current environment."""
        match new_loader:
            case dict():
                new_loader = loaders.DictLoader(new_loader)
            case str() | os.PathLike():
                new_loader = loaders.FileSystemLoader(new_loader)
        match self.loader:
            case jinja2.ChoiceLoader():
                self.loader.loaders = [new_loader, *self.loader.loaders]
            case None:
                self.loader = new_loader
            case _:
                self.loader = loaders.ChoiceLoader(loaders=[new_loader, self.loader])

    def render_condition(
        self,
        string: str,
        variables: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> bool:
        """Render a template condition.

        This function renders a template string and evaluates its
        result as a boolean. It returns True if the result is truthy
        (not None, False, or an empty string), otherwise False.

        Args:
            string: String to evaluate for True-ishness
            variables: Extra variables for the rendering
            kwargs: Further extra variables for rendering

        Returns:
            True if the rendered string is truthy, False otherwise.
        """
        result = self.render_string(string=string, variables=variables, **kwargs)
        return result not in ["None", "False", ""]

    def render_file(
        self,
        file: str | os.PathLike[str],
        variables: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        """Helper to directly render a template from filesystem.

        This function renders a template file directly from the
        filesystem using the current environment's configuration and
        globals.

        !!! info
            The file content is cached, which is generally acceptable
            for common use cases.

        Args:
            file: Template file to load
            variables: Extra variables for the rendering
            kwargs: Further extra variables for rendering

        Returns:
            The rendered string.
        """
        content = envglobals.load_file_cached(str(file))
        return self.render_string(content, variables, **kwargs)

    @contextlib.contextmanager
    def with_globals(self, **kwargs: Any) -> Generator[None]:
        """Context manager to temporarily set globals for the environment.

        This context manager allows temporarily overriding the environment's
        globals with the provided values. The previous values are restored on exit,
        also when the block raises.

        The globals dict is changed in place (templates loaded before see the
        values too), so this is not safe while other threads or tasks render with
        the same environment: pass render variables there instead.

        Args:
            kwargs: Globals to set
        """
        missing = object()
        previous = {k: self.globals.get(k, missing) for k in kwargs}
        self.globals.update(kwargs)
        try:
            yield
        finally:
            for k, v in previous.items():
                if v is missing:
                    self.globals.pop(k, None)
                else:
                    self.globals[k] = v

    def setup_loader(
        self,
        dir_paths: list[str] | None = None,
        module_paths: list[str] | None = None,
        static: dict[str, str] | None = None,
        fsspec_paths: bool = True,
    ) -> None:
        """Set the loader for the environment.

        This function sets the loader for the environment based on
        the provided parameters. It uses the ``jinjarope.get_loader``
        function to create a suitable loader.

        Args:
            dir_paths: List of directory paths to search for templates
            module_paths: List of module paths to search for templates
            static: Dictionary of static files to include in the loader
            fsspec_paths: Whether to add a loader taking any local path or fsspec URL
                as template name. With it, templates can include any file or URL,
                outside of ``dir_paths``: only use it for trusted templates.
        """
        self.loader = jinjarope.get_loader(
            dir_paths=dir_paths,
            module_paths=module_paths,
            static=static,
            fsspec_paths=fsspec_paths,
        )

    def evaluate(
        self,
        code: str,
        context: dict[str, Any] | None = None,
    ) -> Any:
        """Evaluate python code and return the caught stdout + return value of last line.

        The code runs in a copy of the environment's globals (updated with
        ``context``), so its assignments don't leak into the environment.
        Output of ``print()`` calls is captured without swapping ``sys.stdout``
        (writes to ``sys.stdout`` itself are not captured).

        Args:
            code: The code to execute
            context: Additional globals for the execution

        Returns:
            The value of the last line if nothing was printed (``""`` for ``None``),
            otherwise the printed output followed by that value.
        """
        now = time.time()
        logger.debug("Evaluating code:\n%s", code)
        tree = ast.parse(code)
        last = tree.body[-1] if tree.body else None
        eval_expr = ast.Expression(last.value) if isinstance(last, ast.Expr) else None
        exec_expr = ast.Module(body=tree.body[:-1] if eval_expr else tree.body, type_ignores=[])
        buffer = io.StringIO()

        def _print(*args: Any, file: Any = None, **kwargs: Any) -> None:
            print(*args, file=buffer if file is None else file, **kwargs)

        namespace: dict[str, Any] = {**self.globals, **(context or {}), "print": _print}
        exec(compile(exec_expr, "file", "exec"), namespace)
        val = eval(compile(eval_expr, "file", "eval"), namespace) if eval_expr else None
        logger.debug("Code evaluation took %s seconds.", time.time() - now)
        if output := buffer.getvalue():
            return output if val is None else f"{output}{val}"
        return "" if val is None else val
