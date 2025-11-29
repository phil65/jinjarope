"""Jinja2 template tag extensions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Literal

from jinja2 import nodes
from jinja2.ext import Extension
from jinja2.lexer import describe_token


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from jinja2.environment import Environment
    from jinja2.parser import Parser
    from jinja2.runtime import Context


__all__ = ["ContainerTag", "InclusionTag", "StandaloneTag"]
__version__ = "0.6.1"


class BaseTemplateTag(Extension):
    """Base class for template tag extensions providing common functionality."""

    def __init__(self, environment: Environment) -> None:
        super().__init__(environment)
        self.context: Context | None = None
        self.template: str | None = None
        self.lineno: int | None = None
        self.tag_name: str | None = None

    def parse(self, parser: Parser) -> nodes.Node:
        """Parse the tag definition and return a Node."""
        lineno = parser.stream.current.lineno
        tag_name = parser.stream.current.value
        meta_kwargs = [
            nodes.Keyword("_context", nodes.ContextReference()),
            nodes.Keyword("_template", nodes.Const(parser.name)),
            nodes.Keyword("_lineno", nodes.Const(lineno)),
            nodes.Keyword("_tag_name", nodes.Const(tag_name)),
        ]

        self.init_parser(parser)
        args, kwargs, options = self.parse_args(parser)
        kwargs.extend(meta_kwargs)
        options["tag_name"] = tag_name
        return self.create_node(parser, args, kwargs, lineno=lineno, **options)

    def init_parser(self, parser: Parser) -> None:
        """Initialize parser by skipping the tag name."""
        parser.stream.skip(1)

    def parse_args(
        self,
        parser: Parser,
    ) -> tuple[list[nodes.Expr], list[nodes.Keyword], dict[str, Any]]:
        """Parse arguments from the tag definition."""
        args: list[nodes.Expr] = []
        kwargs: list[nodes.Keyword] = []
        options: dict[str, str | None] = {"target": None}
        require_comma = False
        arguments_finished = False

        while parser.stream.current.type != "block_end":
            if parser.stream.current.test("name:as"):
                parser.stream.skip(1)
                options["target"] = parser.stream.expect("name").value
                arguments_finished = True

            if arguments_finished:
                if not parser.stream.current.test("block_end"):
                    desc = describe_token(parser.stream.current)
                    parser.fail(
                        f"Expected 'block_end', got {desc!r}",
                        parser.stream.current.lineno,
                    )
                break

            if require_comma:
                parser.stream.expect("comma")

                # support for trailing comma
                if parser.stream.current.type == "block_end":
                    break

            token = parser.stream.current
            if token.type == "name" and parser.stream.look().type == "assign":
                key = token.value
                parser.stream.skip(2)  # Skip name and assign tokens
                value = parser.parse_expression()
                kwargs.append(nodes.Keyword(key, value, lineno=value.lineno))
            else:
                if kwargs:
                    parser.fail("Invalid argument syntax", token.lineno)
                args.append(parser.parse_expression())

            require_comma = True

        return args, kwargs, options

    def create_node(
        self,
        parser: Parser,
        args: list[nodes.Expr],
        kwargs: list[nodes.Keyword],
        *,
        lineno: int,
        **options: Any,
    ) -> nodes.Node:
        raise NotImplementedError


class StandaloneTag(BaseTemplateTag):
    """Tag that renders to a single output without content block."""

    safe_output: ClassVar[bool] = False

    def create_node(
        self,
        parser: Parser,
        args: list[nodes.Expr],
        kwargs: list[nodes.Keyword],
        *,
        lineno: int,
        **options: Any,
    ) -> nodes.Node:
        call_node: nodes.Call | nodes.MarkSafeIfAutoescape = self.call_method(
            "render_wrapper",
            args,
            kwargs,
            lineno=lineno,
        )
        if self.safe_output:
            call_node = nodes.MarkSafeIfAutoescape(call_node, lineno=lineno)

        if target := options.get("target"):
            target_node = nodes.Name(target, "store", lineno=lineno)
            return nodes.Assign(target_node, call_node, lineno=lineno)

        return nodes.Output([call_node], lineno=lineno)

    def render_wrapper(self, *args: Any, **kwargs: Any) -> Any:
        self.context = kwargs.pop("_context")
        self.template = kwargs.pop("_template")
        self.lineno = kwargs.pop("_lineno")
        self.tag_name = kwargs.pop("_tag_name")
        return self.render(*args, **kwargs)

    def render(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError


class ContainerTag(BaseTemplateTag):
    """Tag that wraps content and processes it."""

    def create_node(
        self,
        parser: Parser,
        args: list[nodes.Expr],
        kwargs: list[nodes.Keyword],
        *,
        lineno: int,
        **options: Any,
    ) -> nodes.Node:
        """Create a node that processes wrapped content."""
        call_node = self.call_method("render_wrapper", args, kwargs, lineno=lineno)
        body = parser.parse_statements(
            (f"name:end{options['tag_name']}",),
            drop_needle=True,
        )
        call_block = nodes.CallBlock(call_node, [], [], body).set_lineno(lineno)

        if target := options.get("target"):
            target_node = nodes.Name(target, "store", lineno=lineno)
            return nodes.AssignBlock(target_node, None, [call_block], lineno=lineno)
        return call_block

    def render_wrapper(self, *args: Any, **kwargs: Any) -> Any:
        self.context = kwargs.pop("_context")
        self.template = kwargs.pop("_template")
        self.lineno = kwargs.pop("_lineno")
        self.tag_name = kwargs.pop("_tag_name")
        return self.render(*args, **kwargs)

    def render(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError


class InclusionTag(StandaloneTag):
    """Tag that includes other templates with context."""

    template_name: str | None = None
    safe_output: ClassVar[bool] = True

    def render(self, *args: Any, **kwargs: Any) -> str:
        """Render included template with context."""
        template_names = self.get_template_names(*args, **kwargs)
        template = (
            self.environment.get_template(template_names)
            if isinstance(template_names, str)
            else self.environment.select_template(template_names)
        )

        if not self.context:
            msg = "Context not available"
            raise RuntimeError(msg)

        context = template.new_context(
            {**self.context.get_all(), **self.get_context(*args, **kwargs)},
            shared=True,
        )
        return template.render(context)

    def get_context(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Get additional context for template."""
        return {}

    def get_template_names(self, *args: Any, **kwargs: Any) -> str | Sequence[str]:
        """Get template name(s) to include."""
        if not self.template_name:
            msg = "InclusionTag requires 'template_name' or 'get_template_names()'"
            raise RuntimeError(msg)
        return self.template_name


def create_tag_extension(
    typ: Literal["standalone", "container", "inclusion"],
    tag: str | list[str] | set[str],
    render_fn: Callable[..., str],
) -> type[Extension]:
    """Create a Jinja2 extension from a render function."""
    jinja_tag = {tag} if isinstance(tag, str) else set(tag)
    match typ:
        case "standalone":
            base_cls: type[BaseTemplateTag] = StandaloneTag
        case "container":
            base_cls = ContainerTag
        case "inclusion":
            base_cls = InclusionTag
        case _:
            msg = f"Invalid extension type: {typ!r}"
            raise ValueError(msg)

    class Extension(base_cls):  # type: ignore
        tags = jinja_tag
        render = staticmethod(render_fn)

    return Extension


if __name__ == "__main__":
    import hmac

    import jinja2

    def render(
        secret: bytes, digest: str = "sha256", caller: Callable[..., Any] | None = None
    ) -> str:
        content = str(caller() if caller else "").encode()

        if isinstance(secret, str):
            secret = secret.encode()

        signing = hmac.new(secret, content, digestmod=digest)
        return signing.hexdigest()

    HMACExtension = create_tag_extension("container", "hmac", render)

    env = jinja2.Environment(extensions=[HMACExtension])
    template = env.from_string("{% hmac 'SECRET', digest='sha1' %}Hello world!{% endhmac %}")
    print(template.render())
