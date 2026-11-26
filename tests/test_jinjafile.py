import pytest

import jinjarope


def test_loading_filters():
    file = jinjarope.JinjaFile("src/jinjarope/resources/filters.toml")
    assert isinstance(file.filters[0], jinjarope.JinjaItem)
    assert file.filters_dict


def test_loading_functions():
    file = jinjarope.JinjaFile("src/jinjarope/resources/functions.toml")
    assert isinstance(file.functions[0], jinjarope.JinjaItem)
    assert file.functions_dict


def test_loading_tests():
    file = jinjarope.JinjaFile("src/jinjarope/resources/tests.toml")
    assert isinstance(file.tests[0], jinjarope.JinjaItem)
    assert file.tests_dict


def test_loading_config():
    file = jinjarope.JinjaFile("tests/testresources/testconfig.toml")
    assert file.envconfig.trim_blocks


def test_loading_loaders():
    env = jinjarope.Environment()
    env.load_jinja_file("tests/testresources/testconfig.toml")
    assert env.get_template("testfile.jinja").render()


if __name__ == "__main__":
    pytest.main([__file__])
