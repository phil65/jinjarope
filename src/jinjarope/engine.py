"""Template engine protocol: what users of jinjarope need from a template engine.

Two backends implement it:

- `jinjarope.Environment`: Jinja2 (the default, all features)
- `jinjarope.MiniJinjaEnvironment`: [minijinja](https://github.com/mitsuhiko/minijinja)
  (Rust, optional extra `minijinja`; differences: `docs/engines.md`)

Both take the same filters / tests / globals (plain Python callables, also the ones
using Jinja2's `pass_context` / `pass_environment` markers), the same loaders (the
jinjarope / Jinja2 loader classes) and raise the same errors (below), so code written
against `TemplateEngine` works with either of them. Pick a backend by name with
`get_engine_class()`.
"""

from typing import TYPE_CHECKING, Any, ClassVar, Literal, Protocol, runtime_checkable


if TYPE_CHECKING:
    from collections.abc import Callable
    import contextlib
    import os

    import jinja2

    from jinjarope import undefined as undefined_


type EngineName = Literal["jinja2", "minijinja"]
"""Names of the template engine backends."""

ENGINES: tuple[EngineName, ...] = ("jinja2", "minijinja")
DEFAULT_ENGINE: EngineName = "jinja2"


class TemplateError(Exception):
    """Base class of the errors raised by template engines (all backends)."""


class TemplateSyntaxError(TemplateError, SyntaxError):
    """A template could not be parsed (also a `SyntaxError`)."""


class TemplateRenderError(TemplateError, RuntimeError):
    """Rendering a template string failed (also a `RuntimeError`).

    The original exception (an undefined variable, an exception raised by a filter, ...)
    is the `__cause__`.
    """


class TemplateNotFoundError(TemplateError, LookupError):
    """A template name could not be resolved by the loader (also a `LookupError`)."""

    def __init__(self, name: str, message: str | None = None) -> None:
        self.name = name
        super().__init__(message or f"Template {name!r} not found")


@runtime_checkable
class TemplateEngine(Protocol):
    """The engine surface: render strings / templates, register filters / tests / globals.

    Filters, tests and globals are plain dicts: add or replace entries at any time,
    the next render sees them. Templates are found by `loader` (a Jinja2 /
    jinjarope loader; other backends adapt it).

    Errors: `render_string` raises `TemplateSyntaxError` / `TemplateRenderError`
    (original exception as `__cause__`). Template lookups by name raise
    `TemplateNotFoundError` (minijinja) or `jinja2.TemplateNotFound` (Jinja2, both
    are `LookupError`s); other errors of `render_template` are the backend's own
    (Jinja2: `jinja2.TemplateError` subclasses, minijinja: `minijinja.TemplateError`)
    or the exception raised by a filter / global.
    """

    engine_name: ClassVar[str]
    """Name of the backend (`"jinja2"`, `"minijinja"`)."""
    filters: dict[str, Callable[..., Any]]
    """Filters by name (`{{ x | name }}`)."""
    tests: dict[str, Callable[..., bool]]
    """Tests by name (`{% if x is name %}`)."""
    globals: dict[str, Any]
    """Global variables / functions of all templates."""
    loader: jinja2.BaseLoader | None
    """The template loader (`None`: only template strings can be rendered)."""

    def render_string(
        self,
        string: str,
        variables: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        """Render a template string with given variables."""
        ...

    def render_template(
        self,
        template_name: str,
        variables: dict[str, Any] | None = None,
        block_name: str | None = None,
        parent_template: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Render a template of the loader (or only one block of it)."""
        ...

    def render_condition(
        self,
        string: str,
        variables: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> bool:
        """Render a template string and return whether the result is truthy."""
        ...

    def render_file(
        self,
        file: str | os.PathLike[str],
        variables: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        """Render a file (local path or fsspec URL) as template string."""
        ...

    def get_source(self, template_name: str) -> str:
        """Return the source of a template of the loader."""
        ...

    def set_undefined(self, value: undefined_.UndefinedStr) -> None:
        """Set the behaviour for undefined variables (`strict`, `silent`, ...)."""
        ...

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
        """Add the filters / tests / functions (and config, loader) of a JinjaFile."""
        ...

    def add_template(self, file: str | os.PathLike[str]) -> None:
        """Make a file available as template (its path is the template name)."""
        ...

    def add_template_path(self, *path: str | os.PathLike[str]) -> None:
        """Add folders to search templates in."""
        ...

    def with_globals(self, **kwargs: Any) -> contextlib.AbstractContextManager[None]:
        """Set globals temporarily (not thread-safe: changes the shared dict)."""
        ...

    def __contains__(self, template: str | os.PathLike[str]) -> bool:
        """Whether the loader knows given template."""
        ...


def get_engine_class(name: EngineName | str | None = None) -> type[TemplateEngine]:
    """Return the environment class of given backend (default: Jinja2).

    Args:
        name: `"jinja2"` or `"minijinja"` (`None`: the default, Jinja2)

    Raises:
        ValueError: Unknown backend name
        ImportError: The backend needs a package which is not installed
            (minijinja: `pip install jinjarope[minijinja]`)
    """
    match name or DEFAULT_ENGINE:
        case "jinja2":
            from jinjarope.environment import Environment

            return Environment
        case "minijinja":
            from jinjarope.minijinjaenv import MiniJinjaEnvironment

            return MiniJinjaEnvironment
        case _:
            msg = f"Unknown template engine {name!r} (one of {', '.join(ENGINES)})"
            raise ValueError(msg)


def create_environment(name: EngineName | str | None = None, **kwargs: Any) -> TemplateEngine:
    """Create an environment of given backend (keyword arguments: see `Environment`)."""
    return get_engine_class(name)(**kwargs)
