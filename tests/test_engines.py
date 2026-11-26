"""The template engine protocol, run against every backend."""

from typing import Any

import jinja2
import pytest

import jinjarope
from jinjarope import engine


@pytest.fixture(params=engine.ENGINES)
def engine_name(request: pytest.FixtureRequest) -> str:
    if request.param == "minijinja":
        pytest.importorskip("minijinja")
    return request.param


@pytest.fixture
def env(engine_name: str) -> jinjarope.TemplateEngine:
    return jinjarope.create_environment(engine_name)


def test_implements_protocol(env: jinjarope.TemplateEngine, engine_name: str):
    assert isinstance(env, jinjarope.TemplateEngine)
    assert env.engine_name == engine_name
    assert jinjarope.get_engine_class(engine_name) is type(env)


def test_default_engine_is_jinja2():
    assert jinjarope.get_engine_class() is jinjarope.Environment
    assert jinjarope.get_engine_class(None) is jinjarope.Environment


def test_unknown_engine():
    with pytest.raises(ValueError, match="Unknown template engine"):
        jinjarope.get_engine_class("mako")


def test_render_string_variables(env: jinjarope.TemplateEngine):
    assert env.render_string("{{ a }}-{{ b }}", {"a": 1}, b=2) == "1-2"


def test_jinjarope_filters_and_globals(env: jinjarope.TemplateEngine):
    assert env.render_string("{{ 'a b' | slugify }}") == "a_b"
    assert env.render_string("{{ 'a' | add(prefix='<', suffix='>') }}") == "<a>"
    assert "slugify" in env.filters
    assert env.render_string("{% if [1] is list %}yes{% endif %}") == "yes"


def test_added_items_are_used(env: jinjarope.TemplateEngine):
    env.filters["shout"] = lambda v: f"{v}!"
    env.tests["short"] = lambda v: len(v) < 3  # noqa: PLR2004
    env.globals["answer"] = 42
    assert env.render_string("{{ 'a' | shout }}{{ 'ab' is short }}{{ answer }}") == "a!True42"
    env.filters["shout"] = lambda v: f"{v}!!"
    del env.globals["answer"]
    env.set_undefined("silent")
    assert env.render_string("{{ 'a' | shout }}{{ answer }}") == "a!!"


def test_callable_globals_are_values(env: jinjarope.TemplateEngine):
    env.globals["fn"] = len
    env.filters["name_of"] = lambda v: v.__name__
    assert env.render_string("{{ fn | name_of }}{{ fn('abc') }}") == "len3"


def test_pass_arguments(env: jinjarope.TemplateEngine):
    @jinja2.pass_context
    def ctx_filter(ctx: Any, value: str) -> str:
        return f"{value}:{ctx.get('page')}:{ctx['x']}:{ctx.get('missing', 'default')}"

    @jinja2.pass_environment
    def env_filter(environment: Any, value: str) -> bool:
        return environment is env

    env.filters["ctx_filter"] = ctx_filter
    env.filters["env_filter"] = env_filter
    env.globals["ctx_fn"] = ctx_filter
    env.globals["page"] = "home"
    result = env.render_string("{{ 'v' | ctx_filter }} {{ ctx_fn('w') }} {{ 1 | env_filter }}", x=1)
    assert result == "v:home:1:default w:home:1:default True"


def test_jinja2_builtins_available(env: jinjarope.TemplateEngine):
    assert env.render_string("{{ 'ab' | center(4) }}") == " ab "
    assert env.render_string("{{ 'aaa bbb' | wordwrap(3) }}") == "aaa\nbbb"
    assert env.render_string("{{ 'abcdefghij' | truncate(5, leeway=0) }}") == "ab..."
    assert env.render_string("{{ 'a b c' | wordcount }}") == "3"
    assert env.render_string("{{ len is callable }}", len=len) == "True"
    loop = "{% for i in [1, 2, 3] %}{% if i == 2 %}{% break %}{% endif %}{{ i }}{% endfor %}"
    assert env.render_string(loop) == "1"


def test_finalize(engine_name: str):
    env = jinjarope.create_environment(engine_name, finalize=lambda v: f"<{v}>")
    assert env.render_string("a{{ 1 }}b") == "a<1>b"


def test_loader_and_templates(env: jinjarope.TemplateEngine):
    env.loader = jinjarope.DictLoader({
        "page.md": "A{% block body %}B{{ v }}{% block inner %}C{% endblock %}{% endblock %}D",
        "child.md": "{% extends 'page.md' %}{% block inner %}X{% endblock %}",
    })
    assert env.render_template("page.md", v=1) == "AB1CD"
    assert env.render_template("child.md", v=1) == "AB1XD"
    assert env.render_template("page.md", block_name="body", v=2) == "B2C"
    assert env.get_source("child.md").startswith("{% extends")
    assert "page.md" in env
    assert "other.md" not in env
    with pytest.raises(jinjarope.BlockNotFoundError):
        env.render_template("page.md", block_name="nope")


def test_template_not_found(env: jinjarope.TemplateEngine):
    env.loader = jinjarope.DictLoader({})
    with pytest.raises(LookupError):
        env.render_template("missing.md")
    with pytest.raises(LookupError):
        env.get_source("missing.md")


def test_new_loader_drops_cached_templates(env: jinjarope.TemplateEngine):
    env.loader = jinjarope.DictLoader({"a": "old"})
    assert env.render_template("a") == "old"
    env.loader = jinjarope.DictLoader({"a": "new"})
    assert env.render_template("a") == "new"


def test_errors(env: jinjarope.TemplateEngine):
    with pytest.raises(jinjarope.TemplateSyntaxError):
        env.render_string("{% if %}")
    with pytest.raises(SyntaxError):
        env.render_string("{% for %}")
    with pytest.raises(jinjarope.TemplateRenderError):
        env.render_string("{{ undefined_variable }}")

    def fail(value: Any) -> None:
        raise ValueError(value)

    env.filters["fail"] = fail
    with pytest.raises(RuntimeError) as exc_info:
        env.render_string("{{ 1 | fail }}")
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_undefined_behaviours(env: jinjarope.TemplateEngine):
    env.set_undefined("silent")
    assert env.render_string("a{{ missing }}b") == "ab"
    env.set_undefined("lax")
    assert env.render_string("a{{ missing.attr }}b") == "ab"
    env.set_undefined("strict")
    with pytest.raises(RuntimeError):
        env.render_string("{{ missing }}")


def test_render_condition(env: jinjarope.TemplateEngine):
    assert env.render_condition("{{ 1 == 1 }}")
    assert not env.render_condition("{{ x }}", x="")


def test_with_globals(env: jinjarope.TemplateEngine):
    with env.with_globals(temp="t"):
        assert env.render_string("{{ temp }}") == "t"
    assert "temp" not in env.globals


def test_render_string_filter(env: jinjarope.TemplateEngine):
    assert env.render_string("{{ '{{ 1 + 1 }}' | render_string }}") == "2"


def test_minijinja_lazy_callables_stay_lazy():
    """Registering a callable object must not touch its attributes (lazy imports)."""
    pytest.importorskip("minijinja")
    touched: list[str] = []

    class Proxy:
        def __call__(self, value: Any) -> str:
            return f"called {value}"

        def __getattr__(self, name: str) -> Any:
            touched.append(name)
            raise AttributeError(name)

    env = jinjarope.MiniJinjaEnvironment()
    env.filters["proxy"] = Proxy()
    env.globals["proxy_fn"] = Proxy()
    env.render_string("")
    assert not touched
    assert env.render_string("{{ 1 | proxy }} {{ proxy_fn(2) }}") == "called 1 called 2"


def test_minijinja_unsupported_options():
    pytest.importorskip("minijinja")
    with pytest.raises(ValueError, match="synchronously"):
        jinjarope.MiniJinjaEnvironment(enable_async=True)
    with pytest.raises(ValueError, match="extension"):
        jinjarope.MiniJinjaEnvironment(extensions=["jinja2.ext.i18n"])
    env = jinjarope.MiniJinjaEnvironment(extensions=["jinja2.ext.loopcontrols"])
    with pytest.raises(ValueError, match="not supported"):
        env.set_undefined("keep")


def test_minijinja_extract_block():
    from jinjarope.minijinjaenv import extract_block

    source = (
        "{% block a %}1{%- block b -%}2{% endblock %}3{% endblock a %}{% block c %}4{% endblock %}"
    )
    assert extract_block(source, "a") == "1{%- block b -%}2{% endblock %}3"
    assert extract_block(source, "b") == "2"
    assert extract_block(source, "c") == "4"
    assert extract_block(source, "d") is None


def test_getattr_filter(env: jinjarope.TemplateEngine):
    assert env.render_string('{{ cls | getattr("__name__") }}', cls=int) == "int"
    assert env.render_string('{{ 1 | getattr("missing", "fallback") }}') == "fallback"


def test_jinja2_compatible_builtins(env: jinjarope.TemplateEngine):
    assert env.render_string('{{ "a\nb" | indent(width="> ", first=True) }}') == "> a\n> b"
    assert env.render_string("{{ {'a': 1} is instance(dict) }}") == "True"
    assert env.render_string("{{ dict(a=1)['a'] }}") == "1"


def test_missing_included_template(env: jinjarope.TemplateEngine):
    env.loader = jinjarope.DictLoader({"page.md": "{% include 'missing.md' %}"})
    with pytest.raises(LookupError):
        env.render_template("page.md")


def test_added_loader_drops_cached_templates(env: jinjarope.TemplateEngine):
    env.loader = jinjarope.ChoiceLoader([jinjarope.DictLoader({"a": "old"})])
    assert env.render_template("a") == "old"
    env._add_loader({"a": "new"})  # ty: ignore[unresolved-attribute]
    assert env.render_template("a") == "new"


def test_render_block_whitespace_comments_and_delimiters(engine_name: str):
    env = jinjarope.create_environment(engine_name)
    env.loader = jinjarope.DictLoader({
        "a": "{# {% block b %}old{% endblock %} #}{%- block b -%}\n new \n{%- endblock -%}",
    })
    assert env.render_template("a", block_name="b") == "new"
    env = jinjarope.create_environment(engine_name, block_start_string="[%", block_end_string="%]")
    env.loader = jinjarope.DictLoader({"a": "x[% block b %]hi[% endblock %]y"})
    assert env.render_template("a", block_name="b") == "hi"


def test_constructor_syntax_settings_are_kept(engine_name: str):
    """The default JinjaFiles have no config section: they must not reset the settings."""
    env = jinjarope.create_environment(engine_name, trim_blocks=False)
    assert env.render_string("{% if true %}\nx{% endif %}") == "\nx"
