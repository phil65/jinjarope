from __future__ import annotations

import jinja2
import pytest

from jinjarope import configloaders


def test_nested_dict_loader():
    templates = {
        "example": {
            "template": "{{ something }}",
        },
    }
    loader = configloaders.NestedDictLoader(templates)
    env = jinja2.Environment(loader=loader)
    template = env.get_template("example/template")
    assert template.render(something="Hello, World!") == "Hello, World!"


def test_nested_dict_loader_not_found():
    templates = {
        "example": {
            "template": "{{ something }}",
        },
    }
    loader = configloaders.NestedDictLoader(templates)
    env = jinja2.Environment(loader=loader)
    with pytest.raises(jinja2.exceptions.TemplateNotFound):
        env.get_template("nonexistent/template")


def test_nested_dict_repr():
    templates = {
        "example": {
            "template": "{{ something }}",
        },
    }
    loader = configloaders.NestedDictLoader(templates)
    assert repr(loader) == "NestedDictLoader(mapping={'example': {'template': '{{ something }}'}})"


def test_nested_dict_list_templates():
    templates = {
        "example": {
            "template": "{{ something }}",
            "another_template": "{{ something_else }}",
        },
        "another_example": {
            "template": "{{ yet_another_thing }}",
        },
    }
    loader = configloaders.NestedDictLoader(templates)
    assert set(loader.list_templates()) == {
        "example/template",
        "example/another_template",
        "another_example/template",
    }


def test_get_source():
    templates = {
        "example": {
            "template": "{{ something }}",
        },
    }
    loader = configloaders.NestedDictLoader(templates)
    source, filename, uptodate = loader.get_source(
        jinja2.Environment(),
        "example/template",
    )
    assert source == "{{ something }}"
    assert filename is None
    assert uptodate() is True


def test_get_source_not_found():
    templates = {
        "example": {
            "template": "{{ something }}",
        },
    }
    loader = configloaders.NestedDictLoader(templates)
    with pytest.raises(jinja2.exceptions.TemplateNotFound):
        loader.get_source(jinja2.Environment(), "nonexistent/template")


if __name__ == "__main__":
    pytest.main([__file__])
