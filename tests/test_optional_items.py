import pytest

from jinjarope import jinjafile


@pytest.fixture
def items_file(tmp_path, monkeypatch):
    """A package that is installed but fails on import (e.g. incompatible deps)."""
    (tmp_path / "broken_optional_pkg.py").write_text(
        "import incompatible_dependency_that_does_not_exist\n\ndef func(x):\n    return x\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    def make(required: list[str] | None):
        req = f"required_packages = {required!r}\n" if required else ""
        p = tmp_path / "items.toml"
        p.write_text(f'[filters.broken]\nfn = "broken_optional_pkg.func"\ngroup = "test"\n{req}')
        return jinjafile.JinjaFile(p)

    return make


def test_broken_import_does_not_break_loading(items_file):
    """Items are imported lazily: a broken (optional) dependency can't break environments."""
    for required in (["broken_optional_pkg"], None):
        file = items_file(required)
        fn = file.filters_dict["broken"]
        with pytest.raises(ImportError):
            fn("x")


def test_missing_optional_package_is_left_out(tmp_path):
    p = tmp_path / "items.toml"
    p.write_text(
        '[filters.gone]\nfn = "not_installed_pkg.func"\ngroup = "test"\n'
        'required_packages = ["not_installed_pkg"]\n'
    )
    assert "gone" not in jinjafile.JinjaFile(p).filters_dict


def test_builtin_items_resolve():
    """Every built-in item whose packages are installed points to an importable callable."""
    import pathlib

    import jinjarope

    resources = pathlib.Path(jinjarope.__file__).parent / "resources"
    for path in resources.glob("*.toml"):
        file = jinjafile.JinjaFile(path)
        for item in [*file.filters, *file.tests, *file.functions]:
            if not item.required_packages:
                assert callable(item.filter_fn), item
            # Optional items may point to installed-but-broken packages: only
            # typos in jinjarope's own targets must fail here.


def test_lazy_callable_forwards_attributes(tmp_path, monkeypatch):
    """Jinja reads `jinja_pass_arg` (pass_context & co.), inspect follows `__wrapped__`."""
    import inspect

    import jinjarope

    (tmp_path / "ctx_filters.py").write_text(
        "import jinja2\n\n@jinja2.pass_context\ndef who(ctx, value):\n"
        "    return f\"{value}:{ctx['name']}\"\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    item = jinjafile.JinjaItem("who", typ="filter", fn="ctx_filters.who", group="test")
    lazy = item.lazy_fn
    assert "resolved" not in repr(lazy)
    assert inspect.unwrap(lazy) is item.filter_fn
    env = jinjarope.Environment()
    env.filters["who"] = lazy
    assert env.render_string("{{ 'x' | who }}", {"name": "n"}) == "x:n"
