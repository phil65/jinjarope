"""minijinja backend of the template engine protocol (`jinjarope.engine`).

`MiniJinjaEnvironment` renders with [minijinja](https://github.com/mitsuhiko/minijinja)
(Rust) and offers the same API as `jinjarope.Environment` where `jinjarope.engine`
needs it: same filters / tests / globals (also Jinja2 `pass_context` & co. callables),
same loaders, same errors. Differences: `docs/engines.md`.

Needs the `minijinja` extra (`pip install jinjarope[minijinja]`).
"""

import enum
import logging
import pathlib
import re
import threading
import types
from typing import TYPE_CHECKING, Any, ClassVar, Literal

import jinja2
import jinja2.defaults
import minijinja

from jinjarope import engine, envbase, envconfig, loaders, undefined as undefined_, utils


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    import os

    from jinja2.ext import Extension


logger = logging.getLogger(__name__)

type MiniJinjaUndefined = Literal["strict", "lenient", "chainable"]

UNDEFINED_BEHAVIOR: dict[str, MiniJinjaUndefined] = {
    "strict": "strict",
    "silent": "lenient",
    # lax renders anything undefined (also attributes of undefined values) as blank.
    "lax": "chainable",
}
"""jinjarope's undefined names -> minijinja's undefined behaviour (`keep` has none)."""

_UNDEFINED_CLASSES: dict[type[jinja2.Undefined], MiniJinjaUndefined] = {
    jinja2.StrictUndefined: "strict",
    jinja2.Undefined: "lenient",
    jinja2.ChainableUndefined: "chainable",
    undefined_.LaxUndefined: "chainable",
}

# Extensions whose syntax minijinja has built in (`{% break %}` / `{% continue %}`).
_BUILTIN_EXTENSIONS = {"jinja2.ext.loopcontrols", "jinja2.ext.LoopControlExtension"}

_SYNTAX_ATTRS = (
    "block_start_string",
    "block_end_string",
    "variable_start_string",
    "variable_end_string",
    "comment_start_string",
    "comment_end_string",
    "line_statement_prefix",
    "line_comment_prefix",
    "trim_blocks",
    "lstrip_blocks",
    "keep_trailing_newline",
)

_PLAIN_CALLABLES = (
    types.FunctionType,
    types.BuiltinFunctionType,
    types.MethodType,
    types.BuiltinMethodType,
)

# Jinja2 built-ins minijinja lacks, or has with other arguments (Jinja2's implementation
# gets registered, so templates work the same with both backends).
JINJA2_COMPAT_FILTERS: dict[str, Callable[..., Any]] = {
    name: jinja2.defaults.DEFAULT_FILTERS[name]
    for name in (
        # missing in minijinja
        "center",
        "forceescape",
        "random",
        "urlize",
        "wordcount",
        "xmlattr",
        # different arguments in minijinja
        "batch",
        "filesizeformat",
        "truncate",
        "wordwrap",
    )
}
JINJA2_COMPAT_TESTS: dict[str, Callable[..., bool]] = {
    "callable": jinja2.defaults.DEFAULT_TESTS["callable"],
}
JINJA2_COMPAT_GLOBALS: dict[str, Any] = {
    name: jinja2.defaults.DEFAULT_NAMESPACE[name] for name in ("lipsum", "cycler", "joiner")
}

# The name minijinja gives template strings (Jinja2: `None`).
_STRING_NAME = "<string>"


class _PassArg(enum.Enum):
    NONE = enum.auto()
    CONTEXT = enum.auto()
    EVAL_CONTEXT = enum.auto()
    ENVIRONMENT = enum.auto()


def _get_pass_arg(fn: Any) -> _PassArg:
    """Return which Jinja2 pass argument (`pass_context` & co.) a callable wants."""
    match getattr(fn, "jinja_pass_arg", None):
        case None:
            return _PassArg.NONE
        case arg:
            return _PassArg[arg.name.upper()]


class StateContext:
    """What a Jinja2 `pass_context` callable gets under minijinja.

    A subset of `jinja2.runtime.Context`: `name`, `environment`, `get()`, `[]`, `in`.
    Lookups see template variables, render variables and globals.
    """

    __slots__ = ("_state", "environment")

    def __init__(self, state: Any, environment: MiniJinjaEnvironment) -> None:
        self._state = state
        self.environment = environment

    def __repr__(self) -> str:
        return "Context()"

    @property
    def name(self) -> str | None:
        """Name of the rendered template (`None` for template strings)."""
        name = self._state.name
        return None if name == _STRING_NAME else name

    @property
    def eval_ctx(self) -> EvalContext:
        return EvalContext(self.environment)

    def get(self, key: str, default: Any = None) -> Any:
        value = self._state.lookup(key)
        return default if value is None else value

    def resolve(self, key: str) -> Any:
        return self._state.lookup(key)

    def __getitem__(self, key: str) -> Any:
        value = self._state.lookup(key)
        if value is None:
            raise KeyError(key)
        return value

    def __contains__(self, key: str) -> bool:
        return self._state.lookup(key) is not None


class EvalContext:
    """What a Jinja2 `pass_eval_context` callable gets under minijinja."""

    __slots__ = ("environment",)
    autoescape = False
    volatile = False

    def __init__(self, environment: MiniJinjaEnvironment) -> None:
        self.environment = environment


class _PassArgAdapter:
    """Callable for minijinja which passes Jinja2's pass argument to the wrapped callable.

    The kind of pass argument is looked up on the first call, so lazy filters
    (`jinjafile.LazyCallable`) don't get imported when they are registered.
    """

    __slots__ = ("_env", "_kind", "fn")
    __minijinja_pass_state__ = True

    def __init__(self, fn: Callable[..., Any], env: MiniJinjaEnvironment) -> None:
        self.fn = fn
        self._env = env
        self._kind: _PassArg | None = None

    def __call__(self, state: Any, /, *args: Any, **kwargs: Any) -> Any:
        if (kind := self._kind) is None:
            kind = self._kind = _get_pass_arg(self.fn)
        match kind:
            case _PassArg.NONE:
                return self.fn(*args, **kwargs)
            case _PassArg.ENVIRONMENT:
                return self.fn(self._env, *args, **kwargs)
            case _PassArg.CONTEXT:
                return self.fn(StateContext(state, self._env), *args, **kwargs)
            case _PassArg.EVAL_CONTEXT:
                return self.fn(EvalContext(self._env), *args, **kwargs)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.fn!r})"


class _Registry:
    """Pushes one namespace (filters, tests or globals) to the minijinja environment.

    The Python dict is the source of truth; before a render, changed entries get
    (re-)registered and removed ones unregistered (compared by identity).
    """

    __slots__ = ("_adapt", "_add", "_pushed", "_remove", "callables")

    def __init__(
        self,
        add: Callable[[str, Any], None],
        remove: Callable[[str], None],
        adapt: Callable[[Any], Any],
    ) -> None:
        self._add = add
        self._remove = remove
        self._adapt = adapt
        self._pushed: dict[str, Any] = {}
        self.callables: dict[str, Any] = {}
        """Registered callables by name (what minijinja got: adapted if needed)."""

    def sync(self, current: dict[str, Any]) -> bool:
        """Push changes, return whether there were any."""
        pushed = self._pushed
        changed = False
        for name, value in current.items():
            if pushed.get(name, pushed) is not value:
                adapted = self._adapt(value)
                self._add(name, adapted)
                pushed[name] = value
                if callable(value):
                    self.callables[name] = adapted
                else:
                    self.callables.pop(name, None)
                changed = True
        if len(pushed) > len(current):
            for name in [k for k in pushed if k not in current]:
                self._remove(name)
                del pushed[name]
                self.callables.pop(name, None)
            changed = True
        return changed


class MiniJinjaEnvironment(envbase.EnvironmentBase):
    """A jinjarope environment rendering with minijinja.

    Takes the keyword arguments of `jinjarope.Environment`; Jinja2-only options
    (`cache_size`, `optimized`, `bytecode_cache`) are ignored, unsupported ones
    (`enable_async`, extensions other than loop controls, a `newline_sequence` other
    than a line feed, the `keep` undefined) raise `ValueError`.
    """

    engine_name: ClassVar[str] = "minijinja"

    def __init__(
        self,
        *,
        undefined: undefined_.UndefinedStr | type[jinja2.Undefined] = "strict",
        trim_blocks: bool = True,
        cache_size: int = -1,
        auto_reload: bool = False,
        loader: (
            jinja2.BaseLoader
            | list[jinja2.BaseLoader]
            | dict[str, Any]
            | list[dict[str, Any]]
            | None
        ) = None,
        block_start_string: str = "{%",
        block_end_string: str = "%}",
        variable_start_string: str = "{{",
        variable_end_string: str = "}}",
        comment_start_string: str = "{#",
        comment_end_string: str = "#}",
        line_statement_prefix: str | None = None,
        line_comment_prefix: str | None = None,
        lstrip_blocks: bool = False,
        newline_sequence: Literal["\n", "\r\n", "\r"] = "\n",
        keep_trailing_newline: bool = False,
        extensions: Sequence[str | type[Extension]] = (),
        optimized: bool = True,
        finalize: Callable[..., Any] | None = None,
        autoescape: bool | Callable[[str | None], bool] = False,
        bytecode_cache: jinja2.BytecodeCache | None = None,
        enable_async: bool = False,
    ) -> None:
        """Create the environment (arguments: see `jinjarope.Environment`)."""
        if enable_async:
            msg = "minijinja renders synchronously only (enable_async=True)"
            raise ValueError(msg)
        if isinstance(loader, dict | list):
            loader = loaders.from_json(loader)
        self.filters: dict[str, Callable[..., Any]] = dict(JINJA2_COMPAT_FILTERS)
        self.tests: dict[str, Callable[..., bool]] = dict(JINJA2_COMPAT_TESTS)
        self.globals: dict[str, Any] = dict(JINJA2_COMPAT_GLOBALS)
        # read by some of Jinja2's filters (`truncate`, `urlize`, ...)
        self.policies: dict[str, Any] = dict(jinja2.defaults.DEFAULT_POLICIES)
        self._extra_files: set[str] = set()
        self._extra_paths: set[str] = set()
        self._lock = threading.Lock()
        self._native = minijinja.Environment(
            trim_blocks=trim_blocks,
            lstrip_blocks=lstrip_blocks,
            keep_trailing_newline=keep_trailing_newline,
            block_start_string=block_start_string,
            block_end_string=block_end_string,
            variable_start_string=variable_start_string,
            variable_end_string=variable_end_string,
            comment_start_string=comment_start_string,
            comment_end_string=comment_end_string,
            line_statement_prefix=line_statement_prefix,
            line_comment_prefix=line_comment_prefix,
            reload_before_render=auto_reload,
        )
        self._native.loader = self._load_source
        if finalize is not None:
            self._native.finalizer = finalize
        if autoescape:
            self._native.auto_escape_callback = (
                autoescape if callable(autoescape) else (lambda _name: True)
            )
        self.newline_sequence = newline_sequence
        self._check_newline_sequence(newline_sequence)
        for ext in extensions:
            self.add_extension(ext)
        self._loader: jinja2.BaseLoader | None = loader
        native = self._native
        self._registries = (
            (self.filters, _Registry(native.add_filter, native.remove_filter, self._adapt)),
            (self.tests, _Registry(native.add_test, native.remove_test, self._adapt)),
            (self.globals, _Registry(native.add_global, native.remove_global, self._adapt)),
        )
        self.set_undefined(undefined)
        self._install_defaults()

    def __repr__(self) -> str:
        cfg = self.get_config()
        values = utils.get_dataclass_nondefault_values(cfg)
        values.pop("engine", None)
        return utils.get_repr(self, **values)

    def __getattr__(self, name: str) -> Any:
        # syntax / whitespace settings live on the minijinja environment
        if name in _SYNTAX_ATTRS:
            return getattr(self._native, name)
        msg = f"{type(self).__name__!r} object has no attribute {name!r}"
        raise AttributeError(msg)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in _SYNTAX_ATTRS:
            setattr(self._native, name, value)
        else:
            super().__setattr__(name, value)

    def __contains__(self, template: str | os.PathLike[str]) -> bool:
        """Check whether the loader knows given template."""
        if self.loader is None:
            return False
        return pathlib.Path(template).as_posix() in self.loader.list_templates()

    @property
    def loader(self) -> jinja2.BaseLoader | None:
        """The template loader (a Jinja2 / jinjarope loader)."""
        return self._loader

    @loader.setter
    def loader(self, value: jinja2.BaseLoader | None) -> None:
        self._loader = value
        # minijinja caches loaded templates: a new loader may resolve names differently
        self._native.clear_templates()

    @property
    def undefined_behavior(self) -> MiniJinjaUndefined:
        """The undefined behaviour of minijinja (`strict`, `lenient`, `chainable`)."""
        return self._native.undefined_behavior  # type: ignore[return-value]

    def set_undefined(self, value: undefined_.UndefinedStr | type[jinja2.Undefined]) -> None:
        """Set the undefined behaviour for the environment.

        Args:
            value: `strict`, `silent` (minijinja: lenient) or `lax` (chainable), or the
                matching Jinja2 Undefined class

        Raises:
            ValueError: No minijinja equivalent (`keep` / `jinja2.DebugUndefined`, custom
                Undefined classes)
        """
        behavior = (
            UNDEFINED_BEHAVIOR.get(value)
            if isinstance(value, str)
            else _UNDEFINED_CLASSES.get(value)
        )
        if behavior is None:
            msg = f"Undefined behaviour {value!r} is not supported by minijinja"
            raise ValueError(msg)
        self._native.undefined_behavior = behavior

    def add_extension(self, extension: str | type[Extension]) -> None:
        """Accept the Jinja2 extensions minijinja has built in (loop controls).

        Raises:
            ValueError: Any other extension (minijinja has no extension API)
        """
        name = (
            extension
            if isinstance(extension, str)
            else f"{extension.__module__}.{extension.__qualname__}"
        )
        if name not in _BUILTIN_EXTENSIONS:
            msg = f"Jinja2 extension {name!r} is not supported by minijinja"
            raise ValueError(msg)

    def _check_newline_sequence(self, value: str) -> None:
        if value != "\n":
            msg = f"newline_sequence {value!r} is not supported by minijinja (only '\\n')"
            raise ValueError(msg)

    def _apply_envconfig(self, cfg: envconfig.EnvConfig) -> None:
        for attr in _SYNTAX_ATTRS:
            setattr(self._native, attr, getattr(cfg, attr))
        self._check_newline_sequence(cfg.newline_sequence)
        for ext in cfg.extensions or []:
            self.add_extension(ext)

    def _adapt(self, value: Any) -> Any:
        """Return what minijinja gets registered for a filter / test / global."""
        if isinstance(value, _PLAIN_CALLABLES):
            # cheap and safe to inspect now
            if getattr(value, "jinja_pass_arg", None) is None:
                return value
            return _PassArgAdapter(value, self)
        if callable(value) and not isinstance(value, type):
            # Other callables (lazy filters, proxies of plugins, partials) may import
            # their target on attribute access: look at them on the first call.
            return _PassArgAdapter(value, self)
        return value

    def _load_source(self, name: str) -> str | None:
        """Minijinja loader callback: ask the Jinja2 / jinjarope loader."""
        if self._loader is None:
            return None
        try:
            return self._loader.get_source(None, name)[0]  # ty: ignore[invalid-argument-type]
        except jinja2.TemplateNotFound:
            return None

    def _sync(self) -> dict[str, Any]:
        """Push changed filters / tests / globals to minijinja (before each render).

        Returns the render context for the globals: minijinja turns callable globals into
        functions which can be called, but are no values (`{{ zip | list_baseclasses }}`
        would get a string), so they get passed as render variables as well.
        """
        with self._lock:
            for current, registry in self._registries:
                registry.sync(current)
            return self._registries[2][1].callables

    def render_string(
        self,
        string: str,
        variables: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        """Render a template string.

        Args:
            string: String to render
            variables: Extra variables for the rendering
            kwargs: Further extra variables for rendering

        Raises:
            TemplateSyntaxError: The string is no valid template
            TemplateRenderError: Rendering failed (the original error is the `__cause__`)
        """
        variables = (variables or {}) | kwargs
        context = self._sync() | variables
        try:
            return self._native.render_str(string, **context)
        except minijinja.TemplateError as e:
            if e.kind == "SyntaxError":
                msg = f"Error when evaluating \n{string}\n (extra globals: {variables})"
                raise engine.TemplateSyntaxError(msg) from e
            msg = f"Error when rendering \n{string}\n (extra globals: {variables})"
            raise engine.TemplateRenderError(msg) from e
        except Exception as e:
            msg = f"Error when rendering \n{string}\n (extra globals: {variables})"
            raise engine.TemplateRenderError(msg) from e

    def render_template(
        self,
        template_name: str,
        variables: dict[str, Any] | None = None,
        block_name: str | None = None,
        parent_template: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Render a template of the loader (or a block of it).

        Args:
            template_name: Template name
            variables: Extra variables for rendering
            block_name: Render only this block of the template (its own source: blocks
                inherited from a parent template can't be rendered alone)
            parent_template: Ignored (names are not relative to the including template,
                like in Jinja2 by default)
            kwargs: Further extra variables for rendering

        Raises:
            TemplateNotFoundError: The loader doesn't know the template
            BlockNotFoundError: The template has no block with given name
        """
        variables = (variables or {}) | kwargs
        context = self._sync() | variables
        if block_name:
            source = self.get_source(template_name)
            block = extract_block(source, block_name, self._native.block_start_string)
            if block is None:
                from jinjarope.environment import BlockNotFoundError

                raise BlockNotFoundError(block_name, template_name)
            return self._native.render_str(block, template_name, **context)
        try:
            return self._native.render_template(template_name, **context)
        except minijinja.TemplateError as e:
            if e.kind == "TemplateNotFound" and e.name is None:
                raise engine.TemplateNotFoundError(template_name, str(e)) from e
            raise

    def get_source(self, template_name: str) -> str:
        """Return the source of a template of the loader.

        Raises:
            TemplateNotFoundError: The loader doesn't know the template
        """
        if (source := self._load_source(template_name)) is None:
            raise engine.TemplateNotFoundError(template_name)
        return source

    def get_config(self) -> envconfig.EnvConfig:
        """All environment settings (not included: undefined and loaders)."""
        return envconfig.EnvConfig(
            **{attr: getattr(self._native, attr) for attr in _SYNTAX_ATTRS},
            newline_sequence=self.newline_sequence,
            loader=self.loader,
            engine="minijinja",
        )


def extract_block(source: str, block_name: str, block_start: str = "{%") -> str | None:
    """Return the source inside `{% block <block_name> %}` ... `{% endblock %}`.

    Nested blocks count (the matching `endblock` is found). `None` if there is no such
    block. minijinja's Python API can't render a single block, so `render_template`
    renders this source instead.
    """
    start = re.escape(block_start)
    tag = re.compile(rf"{start}[-+]?\s*(block\s+(\w+)|endblock)\b[^%]*?[-+]?%}}")
    depth = 0
    begin: int | None = None
    for match in tag.finditer(source):
        if match.group(2) is not None:
            if begin is None and match.group(2) == block_name:
                begin = match.end()
                depth = 0
            elif begin is not None:
                depth += 1
        elif begin is not None:
            if depth == 0:
                return source[begin : match.start()]
            depth -= 1
    return None
