from typing import TYPE_CHECKING

import jinja2
import pytest

import jinjarope


if TYPE_CHECKING:
    import pathlib


def test_environment_init():
    env = jinjarope.Environment()
    assert isinstance(env, jinja2.Environment)
    assert env.undefined == jinja2.StrictUndefined
    assert env.trim_blocks is True
    assert env.auto_reload is False
    assert repr(env) == "Environment()"


def test_environment_contains():
    env = jinjarope.Environment(
        undefined="strict",
        trim_blocks=True,
        cache_size=-1,
        auto_reload=False,
    )
    env.loader = jinja2.DictLoader({"home.html": "Home", "about.html": "About"})

    assert "home.html" in env
    assert "about.html" in env
    assert "nonexistent.html" not in env


def test_getitem():
    env = jinjarope.Environment()
    env.loader = jinja2.DictLoader({"home.html": "Home", "about.html": "About"})

    assert env["home.html"].render() == "Home"
    assert env["about.html"].render() == "About"
    with pytest.raises(jinja2.exceptions.TemplateNotFound):
        env["nonexistent.html"]


def test_compile():
    env = jinjarope.Environment()
    source = "Hello, {{ name }}!"
    compiled = env.compile(source)
    assert isinstance(compiled, type(compile("", "", "exec")))


def test_inherit_from():
    env1 = jinjarope.Environment()
    env1.globals["global_var"] = "Global Variable"
    env2 = jinjarope.Environment()
    env2.inherit_from(env1)
    assert "global_var" in env2.globals
    assert env2.globals["global_var"] == "Global Variable"


def test_add_template():
    env = jinjarope.Environment()
    env.loader = jinja2.DictLoader({})
    env.add_template("tests/testresources/testfile.jinja")
    assert "tests/testresources/testfile.jinja" in env
    assert env["tests/testresources/testfile.jinja"].render() == "CONTENT!"


def test_add_template_path():
    env = jinjarope.Environment()
    env.add_template_path("templates")
    assert "templates" in env._extra_paths
    assert isinstance(env.loader, jinja2.loaders.FileSystemLoader)


def test__add_loader():
    env = jinjarope.Environment()
    env._add_loader("templates")
    assert isinstance(env.loader, jinja2.loaders.FileSystemLoader)
    env._add_loader({"home.html": "Home"})
    assert isinstance(env.loader, jinja2.loaders.ChoiceLoader)
    assert isinstance(env.loader.loaders[0], jinja2.loaders.DictLoader)
    assert isinstance(env.loader.loaders[1], jinja2.loaders.FileSystemLoader)


def test_render_condition():
    env = jinjarope.Environment()
    assert env.render_condition("{{ 1 == 1 }}") is True
    assert env.render_condition("{{ 1 == 2 }}") is False
    assert env.render_condition("{{ var == 'value' }}", {"var": "value"}) is True
    assert env.render_condition("{{ var == 'value' }}", {"var": "other"}) is False


def test_render_string():
    env = jinjarope.Environment()
    result = env.render_string("Hello, {{ name }}!", {"name": "World"})
    assert result == "Hello, World!"


def test_render_file(tmp_path: pathlib.Path):
    env = jinjarope.Environment()
    file = tmp_path / "test.txt"
    file.write_text("Hello, {{ name }}!")
    result = env.render_file(file, {"name": "World"})
    assert result == "Hello, World!"


def test_render_template():
    env = jinjarope.Environment()
    env.loader = jinja2.DictLoader({"home.html": "Hello, {{ name }}!"})
    result = env.render_template("home.html", {"name": "World"})
    assert result == "Hello, World!"


def test_render_template_block():
    env = jinjarope.Environment()
    dct = {"home.html": "{% block greeting %}Hello, {{ name }}!{% endblock %}"}
    env.loader = jinja2.DictLoader(dct)
    result = env.render_template("home.html", {"name": "World"}, block_name="greeting")
    assert result == "Hello, World!"


def test_render_template_block_not_found():
    env = jinjarope.Environment()
    dct = {"home.html": "{% block greeting %}Hello, {{ name }}!{% endblock %}"}
    env.loader = jinja2.DictLoader(dct)
    with pytest.raises(jinjarope.BlockNotFoundError):
        env.render_template("home.html", {"name": "World"}, block_name="farewell")


def test_with_globals():
    env = jinjarope.Environment()
    assert "name" not in env.globals
    with env.with_globals(name="World"):
        assert env.globals["name"] == "World"
        print(list(env.globals.keys()))
    assert "name" not in env.globals


def test_with_globals_does_not_leak_into_loaded_templates():
    env = jinjarope.Environment(loader=jinja2.DictLoader({"t": "{{ a | default('unset') }}"}))
    template = env.get_template("t")
    with env.with_globals(a="TEMP"):
        assert template.render() == "TEMP"
    assert template.render() == "unset"
    assert env.get_template("t").render() == "unset"


def test_with_globals_restores_on_exception():
    env = jinjarope.Environment()
    env.globals["b"] = "old"
    with pytest.raises(RuntimeError), env.with_globals(b=1, c=2):
        raise RuntimeError
    assert env.globals["b"] == "old"
    assert "c" not in env.globals


def test_setup_loader():
    env = jinjarope.Environment()
    env.setup_loader(dir_paths=["testresources"])
    assert isinstance(env.loader, jinja2.loaders.ChoiceLoader)


def test_evaluate():
    env = jinjarope.Environment()
    result = env.evaluate("1 + 1")
    assert result == 2  # noqa: PLR2004


def test_evaluate_returns_stdout_and_keeps_globals_clean():
    env = jinjarope.Environment()
    result = env.evaluate("print('hi')\nx = 5\nx + 1")
    assert result == "hi\n6"
    assert "x" not in env.globals
    assert "__builtins__" not in env.globals


def test_evaluate_uses_context():
    env = jinjarope.Environment()
    assert env.evaluate("y * 2", context={"y": 21}) == 42  # noqa: PLR2004
    assert "y" not in env.globals


def test_evaluate_does_not_swap_sys_stdout(monkeypatch):
    import sys

    seen = []

    class Spy:
        def write(self, s: str) -> int:
            seen.append(s)
            return len(s)

        def flush(self) -> None:
            pass

    spy = Spy()
    monkeypatch.setattr(sys, "stdout", spy)
    env = jinjarope.Environment()
    assert env.evaluate("import sys\nsys.stdout is __spy__", context={"__spy__": spy}) is True
    assert seen == []


def test_get_config():
    env = jinjarope.Environment(trim_blocks=True)
    config = env.get_config()
    assert config.trim_blocks is True


if __name__ == "__main__":
    pytest.main([__file__])
