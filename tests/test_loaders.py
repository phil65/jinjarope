import pytest

import jinjarope


def test_prefix_loader():
    loader = "test" / jinjarope.DictLoader({"a": "b"})
    env = jinjarope.Environment(loader=loader)
    assert env.render_template("test/a") == "b"
    assert "test/a" in loader
    loader1 = jinjarope.PrefixLoader({"prefix": jinjarope.DictLoader({})})
    loader2 = jinjarope.PrefixLoader({"prefix": jinjarope.DictLoader({})})
    assert loader1 == loader2
    assert len({loader1, loader2}) == 1
    assert repr(loader1)


def test_loader_getitem():
    loader = jinjarope.DictLoader({"a": "{{ 1 + 1 }}"})
    assert loader["a"].render() == "2"
    assert loader.get_template_source("a") == "{{ 1 + 1 }}"


def test_function_loader():
    def load_fn(path: str) -> str:
        return "abc"

    loader1 = jinjarope.FunctionLoader(load_fn)
    loader2 = jinjarope.FunctionLoader(load_fn)
    assert loader1 == loader2
    assert len({loader1, loader2}) == 1
    assert repr(loader1)


def test_packageloader():
    loader1 = jinjarope.PackageLoader("jinjarope")
    loader2 = jinjarope.PackageLoader(jinjarope)
    assert loader1 == loader2
    assert len({loader1, loader2}) == 1
    assert repr(loader1)


def test_filesystemloader():
    loader1 = jinjarope.FileSystemLoader("")
    loader2 = jinjarope.FileSystemLoader("")
    assert loader1 == loader2
    assert len({loader1, loader2}) == 1
    assert repr(loader1)


def test_choiceloader():
    ld = jinjarope.DictLoader({"path": "content"})
    loader = jinjarope.ChoiceLoader([ld])
    assert repr(loader)
    assert bool(loader)
    assert list(loader) == [ld]


if __name__ == "__main__":
    pytest.main([__file__])
