from __future__ import annotations

import ast
import contextlib
import io
import logging
import os
import pathlib
import time
from typing import TYPE_CHECKING, Any, Literal, overload
import weakref

import jinja2
from jinja2.defaults import (
    BLOCK_END_STRING,
    BLOCK_START_STRING,
    COMMENT_END_STRING,
    COMMENT_START_STRING,
    KEEP_TRAILING_NEWLINE,
    LINE_COMMENT_PREFIX,
    LINE_STATEMENT_PREFIX,
    LSTRIP_BLOCKS,
    NEWLINE_SEQUENCE,
    VARIABLE_END_STRING,
    VARIABLE_START_STRING,
)
from jinja2.exceptions import TemplateSyntaxError
import jinja2.nodes

import jinjarope
from jinjarope import (
    envconfig,
    envglobals,
    jinjafile,
    loaders,
    undefined as undefined_,
    utils,
)


if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, MutableMapping, Sequence
    from types import CodeType

    from jinja2.ext import Extension


logger = logging.getLogger(__name__)


class Context(jinja2.runtime.Context):
    def __repr__(self) -> str:
        return "Context()"


class Environment(jinja2.Environment):
    """An enhanced Jinja environment.

    This class extends the Jinja2 environment with functionality for
    loading Jinja files, managing undefined variables, and providing
    helper functions for rendering templates.
    """

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
        block_start_string: str = BLOCK_START_STRING,
        block_end_string: str = BLOCK_END_STRING,
        variable_start_string: str = VARIABLE_START_STRING,
        variable_end_string: str = VARIABLE_END_STRING,
        comment_start_string: str = COMMENT_START_STRING,
        comment_end_string: str = COMMENT_END_STRING,
        line_statement_prefix: str | None = LINE_STATEMENT_PREFIX,
        line_comment_prefix: str | None = LINE_COMMENT_PREFIX,
        lstrip_blocks: bool = LSTRIP_BLOCKS,
        newline_sequence: Literal["\n", "\r\n", "\r"] = NEWLINE_SEQUENCE,
        keep_trailing_newline: bool = KEEP_TRAILING_NEWLINE,
        extensions: Sequence[str | type[Extension]] = (),
        optimized: bool = True,
        finalize: Callable[..., Any] | None = None,
        autoescape: bool | Callable[[str | None], bool] = False,
        bytecode_cache: jinja2.BytecodeCache | None = None,
        enable_async: bool = False,
    ) -> None:
        """Initialize an enhanced Jinja environment with custom settings.

        Args:
            undefined: How undefined variables are handled ("strict", "lenient", etc.)
            trim_blocks: Strip first newline after a block
            cache_size: Size of the template cache (-1 for no limit)
            auto_reload: Automatically reload changed templates
            loader: Template loader or configuration
            block_start_string: String denoting start of block
            block_end_string: String denoting end of block
            variable_start_string: String denoting start of variable
            variable_end_string: String denoting end of variable
            comment_start_string: String denoting start of comment
            comment_end_string: String denoting end of comment
            line_statement_prefix: Prefix for line statements
            line_comment_prefix: Prefix for line comments
            lstrip_blocks: Strip whitespace before blocks
            newline_sequence: Sequence to use for newlines
            keep_trailing_newline: Preserve trailing newline when rendering
            extensions: Jinja2 extensions to load
            optimized: Enable template optimization
            finalize: Function to post-process variables
            autoescape: Auto-escaping behavior
            bytecode_cache: Cache for the bytecode
            enable_async: Enable async template execution

        Note:
            This environment differs from standard Jinja2 by:
            - Using strict undefined behavior by default
            - Setting trim_blocks to True by default
            - Disabling automatic cache cleanup (cache_size = -1)
            - Adding additional filters and functions
            - Enabling loop controls and do extension by default
        """
        self.cache_code = True
        self.context_class = Context

        if isinstance(undefined, str):
            undefined = undefined_.UNDEFINED_BEHAVIOR[undefined]

        if isinstance(loader, dict | list):
            loader = loaders.from_json(loader)

        self._extra_files: set[str] = set()
        self._extra_paths: set[str] = set()

        super().__init__(
            undefined=undefined,
            trim_blocks=trim_blocks,
            cache_size=cache_size,
            auto_reload=auto_reload,
            loader=loader,
            block_start_string=block_start_string,
            block_end_string=block_end_string,
            variable_start_string=variable_start_string,
            variable_end_string=variable_end_string,
            comment_start_string=comment_start_string,
            comment_end_string=comment_end_string,
            line_statement_prefix=line_statement_prefix,
            line_comment_prefix=line_comment_prefix,
            lstrip_blocks=lstrip_blocks,
            newline_sequence=newline_sequence,
            keep_trailing_newline=keep_trailing_newline,
            extensions=extensions,
            optimized=optimized,
            finalize=finalize,
            autoescape=autoescape,
            bytecode_cache=bytecode_cache,
            enable_async=enable_async,
        )
        # Update namespaces
        folder = pathlib.Path(__file__).parent / "resources"
        self.load_jinja_file(folder / "filters.toml")
        self.load_jinja_file(folder / "tests.toml")
        self.load_jinja_file(folder / "functions.toml")
        self.load_jinja_file(folder / "humanize_filters.toml")
        self.load_jinja_file(folder / "llm_filters.toml")
        self.globals.update(envglobals.ENV_GLOBALS)
        for fn in utils.entry_points(group="jinjarope.environment").values():
            fn(self)
        self.filters["render_template"] = self.render_template
        self.filters["render_string"] = self.render_string
        self.filters["render_file"] = self.render_file
        self.filters["evaluate"] = self.evaluate
        self.globals["filters"] = self.filters
        self.globals["tests"] = self.tests
        self.tests["template"] = lambda template_name: template_name in self
        self.template_cache: weakref.WeakValueDictionary[
            str | jinja2.nodes.Template,
            CodeType | str | None,
        ] = weakref.WeakValueDictionary()
        self.add_extension("jinja2.ext.loopcontrols")
        self.add_extension("jinja2.ext.do")

    def __repr__(self) -> str:
        cfg = self.get_config()
        return utils.get_repr(self, **utils.get_dataclass_nondefault_values(cfg))

    def __contains__(self, template: str | os.PathLike[str]) -> bool:
        """Check whether given template path exists.

        Args:
            template: The template path to check

        Returns:
            True if the template exists, False otherwise.
        """
        return pathlib.Path(template).as_posix() in self.list_templates()

    def __getitem__(self, val: str) -> jinja2.Template:
        """Return a template by path.

        Args:
            val: The template path

        Returns:
            The template object for the given path.
        """
        return self.get_template(val)

    def install_translations(self, locale: str, dirs: Sequence[str | os.PathLike[str]]) -> None:
        """Install translations for the environment.

        This function installs translations for the given locale
        using the provided directory paths. It uses the
        `jinjarope.localization` module to manage translations.

        Args:
            locale: The locale to install translations for
            dirs: A sequence of directory paths containing translation files
        """
        from jinjarope import localization

        localization.install_translations(self, locale, dirs)

    def set_undefined(self, value: undefined_.UndefinedStr | type[jinja2.Undefined]) -> None:
        """Set the undefined behaviour for the environment.

        Args:
            value: The new undefined behaviour
        """
        new = undefined_.UNDEFINED_BEHAVIOR[value] if isinstance(value, str) else value
        self.undefined = new

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
        if load_filters:
            dct = {f"{scope_prefix}{k}": v for k, v in file.filters_dict.items()}
            self.filters.update(dct)
        if load_tests:
            dct = {f"{scope_prefix}{k}": v for k, v in file.tests_dict.items()}
            self.tests.update(dct)
        if load_functions:
            dct = {f"{scope_prefix}{k}": v for k, v in file.functions_dict.items()}
            self.globals.update(dct)
        if load_config:
            self.block_start_string = file.envconfig.block_start_string
            self.block_end_string = file.envconfig.block_end_string
            self.variable_start_string = file.envconfig.variable_start_string
            self.variable_end_string = file.envconfig.variable_end_string
            self.comment_start_string = file.envconfig.comment_start_string
            self.comment_end_string = file.envconfig.comment_end_string
            self.line_statement_prefix = file.envconfig.line_statement_prefix
            self.line_comment_prefix = file.envconfig.line_comment_prefix
            self.trim_blocks = file.envconfig.trim_blocks
            self.lstrip_blocks = file.envconfig.lstrip_blocks
            self.newline_sequence = file.envconfig.newline_sequence
            self.keep_trailing_newline = file.envconfig.keep_trailing_newline
            for ext in file.envconfig.extensions or []:
                self.add_extension(ext)
        if load_loader and (loader := file.loader):
            self._add_loader(loader)

    @overload
    def compile(
        self,
        source: str | jinja2.nodes.Template,
        name: str | None = None,
        filename: str | None = None,
        raw: Literal[False] = False,
        defer_init: bool = False,
    ) -> CodeType: ...

    @overload
    def compile(
        self,
        source: str | jinja2.nodes.Template,
        name: str | None = None,
        filename: str | None = None,
        raw: Literal[True] = ...,
        defer_init: bool = False,
    ) -> str: ...

    def compile(
        self,
        source: str | jinja2.nodes.Template,
        name: str | None = None,
        filename: str | None = None,
        raw: bool = False,
        defer_init: bool = False,
    ) -> CodeType | str:
        """Compile the template.

        This function compiles the given template source. If any of the
        keyword arguments are set to a non-default value, the compiled code
        is not cached. Otherwise, the compilation result is cached using the
        ``source`` as key. This behavior can be overwritten by setting
        ``self.cache_code`` to ``False``.

        !!! info "Changes from Jinja2"
            The default behavior of the ``compile`` method has been modified
            to cache the compiled code unless any keyword arguments are
            provided.

        Args:
            source: The template source
            name: The name of the template
            filename: The filename of the template
            raw: Whether to compile the template as raw
            defer_init: Whether to defer initialization

        Returns:
            The compiled template code.
        """
        if (
            not self.cache_code
            or name is not None
            or filename is not None
            or raw is not False
            or defer_init is not False
        ):
            # If there are any non-default keywords args, we do
            # not cache.
            return super().compile(  # type: ignore[no-any-return,call-overload]
                source,
                name,
                filename,
                raw,
                defer_init,
            )

        if (cached := self.template_cache.get(source)) is None:
            cached = self.template_cache[source] = super().compile(source)

        return cached

    def inherit_from(self, env: jinja2.Environment) -> None:
        """Inherit complete configuration from another environment.

        This function copies all settings and configuration from another
        environment to the current one. This effectively allows
        inheritance of environment settings.

        Args:
            env: The environment to inherit settings from
        """
        self.__dict__.update(env.__dict__)
        self.linked_to = env
        self.overlayed = True

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

    async def render_condition_async(
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
        result = await self.render_string_async(string=string, variables=variables, **kwargs)
        return result not in ["None", "False", ""]

    def render_string(
        self,
        string: str,
        variables: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        """Render a template string.

        This function renders the given template string using the
        current environment's configuration and globals.

        Args:
            string: String to render
            variables: Extra variables for the rendering
            kwargs: Further extra variables for rendering

        Returns:
            The rendered string.
        """
        variables = (variables or {}) | kwargs
        cls = self.template_class
        try:
            template = cls.from_code(self, self.compile(string), self.globals, None)
        except TemplateSyntaxError as e:
            msg = f"Error when evaluating \n{string}\n (extra globals: {variables})"
            raise SyntaxError(msg) from e
        try:
            return template.render(**variables)
        except Exception as e:
            msg = f"Error when rendering \n{string}\n (extra globals: {variables})"
            raise RuntimeError(msg) from e

    async def render_string_async(
        self,
        string: str,
        variables: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        """Render a template string.

        This function renders the given template string using the
        current environment's configuration and globals.

        Args:
            string: String to render
            variables: Extra variables for the rendering
            kwargs: Further extra variables for rendering

        Returns:
            The rendered string.
        """
        variables = (variables or {}) | kwargs
        cls = self.template_class
        try:
            template = cls.from_code(self, self.compile(string), self.globals, None)
        except TemplateSyntaxError as e:
            msg = f"Error when evaluating \n{string}\n (extra globals: {variables})"
            raise SyntaxError(msg) from e
        try:
            return await template.render_async(**variables)
        except Exception as e:
            msg = f"Error when rendering \n{string}\n (extra globals: {variables})"
            raise RuntimeError(msg) from e

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

    async def render_file_async(
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
        return await self.render_string_async(content, variables, **kwargs)

    def render_template(
        self,
        template_name: str,
        variables: dict[str, Any] | None = None,
        block_name: str | None = None,
        parent_template: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Render a loaded template (or a block of a template).

        This function renders a loaded template or a specific block from
        a template. It allows for the inclusion of parent templates and
        provides the flexibility to render individual blocks.

        Args:
            template_name: Template name
            variables: Extra variables for rendering
            block_name: Render specific block from the template
            parent_template: The name of the parent template importing this template
            kwargs: Further extra variables for rendering

        Returns:
            The rendered string.

        Raises:
            BlockNotFoundError: If the specified block is not found in the
            template.
        """
        variables = (variables or {}) | kwargs
        template = self.get_template(template_name, parent=parent_template)
        if not block_name:
            return template.render(**variables)
        try:
            block_render_func = template.blocks[block_name]
        except KeyError:
            raise BlockNotFoundError(block_name, template_name) from KeyError

        ctx = template.new_context(variables)
        return self.concat(block_render_func(ctx))
        # except Exception:
        #     self.handle_exception()

    async def render_template_async(
        self,
        template_name: str,
        variables: dict[str, Any] | None = None,
        block_name: str | None = None,
        parent_template: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Render a loaded template (or a block of a template).

        This function renders a loaded template or a specific block from
        a template. It allows for the inclusion of parent templates and
        provides the flexibility to render individual blocks.

        Args:
            template_name: Template name
            variables: Extra variables for rendering
            block_name: Render specific block from the template
            parent_template: The name of the parent template importing this template
            kwargs: Further extra variables for rendering

        Returns:
            The rendered string.

        Raises:
            BlockNotFoundError: If the specified block is not found in the
            template.
        """
        variables = (variables or {}) | kwargs
        template = self.get_template(template_name, parent=parent_template)
        if not block_name:
            return await template.render_async(**variables)
        try:
            block_render_func = template.blocks[block_name]
        except KeyError:
            raise BlockNotFoundError(block_name, template_name) from KeyError

        ctx = template.new_context(variables)
        return self.concat(
            [n async for n in block_render_func(ctx)]  # type: ignore
        )
        # return self.concat(block_render_func(ctx))

    @contextlib.contextmanager
    def with_globals(self, **kwargs: Any) -> Iterator[None]:
        """Context manager to temporarily set globals for the environment.

        This context manager allows temporarily overriding the environment's
        globals with the provided values. Any changes made within the context
        manager are reverted upon exiting the context.

        Args:
            kwargs: Globals to set
        """
        temp = self.globals.copy()
        self.globals.update(kwargs)
        yield
        self.globals = temp

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
            fsspec_paths: Whether to use fsspec paths for loading
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
    ) -> str:
        """Evaluate python code and return the caught stdout + return value of last line.

        This function executes Python code within the environment's
        globals. It captures the standard output generated during
        execution and returns the combined result as a string.

        Args:
            code: The code to execute
            context: Globals for the execution environment

        Returns:
            The combined standard output and return value of the last
            line of code.
        """
        now = time.time()
        logger.debug("Evaluating code:\n%s", code)
        tree = ast.parse(code)
        eval_expr = ast.Expression(tree.body[-1].value)  # type: ignore
        # exec_expr = ast.Module(tree.body[:-1])  # type: ignore
        exec_expr = ast.parse("")
        exec_expr.body = tree.body[:-1]
        compiled = compile(exec_expr, "file", "exec")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exec(compiled, self.globals)
            val = eval(compile(eval_expr, "file", "eval"), self.globals)
        logger.debug("Code evaluation took %s seconds.", time.time() - now)
        # result = mk.MkContainer([buffer.getvalue(), val])
        return val or ""

    def get_config(self) -> envconfig.EnvConfig:
        """All environment settings as a dict (not included: undefined and loaders).

        This function returns a dictionary representation of all
        environment settings, excluding undefined and loaders.

        Returns:
            A dictionary containing the environment configuration.
        """
        exts = [
            k
            for k in self.extensions
            if k not in ["jinja2.ext.LoopControlExtension", "jinja2.ext.ExprStmtExtension"]
        ]
        return envconfig.EnvConfig(
            block_start_string=self.block_start_string,
            block_end_string=self.block_end_string,
            variable_start_string=self.variable_start_string,
            variable_end_string=self.variable_end_string,
            comment_start_string=self.comment_start_string,
            comment_end_string=self.comment_end_string,
            line_statement_prefix=self.line_statement_prefix,
            line_comment_prefix=self.line_comment_prefix,
            trim_blocks=self.trim_blocks,
            lstrip_blocks=self.lstrip_blocks,
            newline_sequence=self.newline_sequence,  # pyright: ignore[reportArgumentType]
            keep_trailing_newline=self.keep_trailing_newline,
            loader=self.loader,
            undefined=self.undefined,
            extensions=exts,
        )

    def make_globals(
        self,
        d: MutableMapping[str, Any] | None,
    ) -> MutableMapping[str, Any]:
        """Make the globals map for a template.

        This function creates a globals map for a template, where
        template-specific globals overlay the environment's global
        variables.

        !!! info
            Avoid modifying any globals after a template is loaded.

        Args:
            d: Dict of template-specific globals

        Returns:
            A ChainMap containing the template globals.
        """
        if d is None:
            d = {}

        import collections

        class GlobalsMap(collections.ChainMap[Any, Any]):
            def __repr__(self) -> str:
                return f"GlobalsMap<{len(self)} keys>"

        return GlobalsMap(d, self.globals)


class BlockNotFoundError(Exception):
    """Exception for not-found template blocks."""

    def __init__(
        self,
        block_name: str,
        template_name: str,
        message: str | None = None,
    ) -> None:
        """Initialize the exception."""
        self.block_name = block_name
        self.template_name = template_name
        super().__init__(
            message or f"Block {self.block_name!r} not found in template {self.template_name!r}",
        )


if __name__ == "__main__":
    env = Environment()
    txt = """{% filter indent %}
    test
    {% endfilter %}
    """
    print(env.render_string(txt))
