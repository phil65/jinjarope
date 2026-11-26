import json
from typing import TYPE_CHECKING

import jinja2
import pytest

from jinjarope import configloaders


if TYPE_CHECKING:
    import pathlib


def test_template_file_loader_json(tmp_path: pathlib.Path):
    d = tmp_path / "example"
    d.mkdir()
    p = d / "template.json"
    p.write_text(json.dumps({"template": "{{ something }}"}))

    loader = configloaders.TemplateFileLoader(p)
    env = jinja2.Environment(loader=loader)
    template = env.get_template("template")
    assert template.render(something="Hello, World!") == "Hello, World!"


def test_template_file_loader_toml(tmp_path: pathlib.Path):
    d = tmp_path / "example"
    d.mkdir()
    p = d / "template.toml"
    p.write_text(r"template = '{{something}}'")

    loader = configloaders.TemplateFileLoader(p)
    env = jinja2.Environment(loader=loader)
    template = env.get_template("template")
    assert template.render(something="Hello, World!") == "Hello, World!"


def test_template_file_loader_not_found(tmp_path: pathlib.Path):
    d = tmp_path / "example"
    d.mkdir()
    p = d / "template.json"
    p.write_text(json.dumps({"template": "{{ something }}"}))

    loader = configloaders.TemplateFileLoader(p)
    env = jinja2.Environment(loader=loader)
    with pytest.raises(jinja2.exceptions.TemplateNotFound):
        env.get_template("nonexistent")


def test_template_file_loader_repr(tmp_path: pathlib.Path):
    d = tmp_path / "example"
    d.mkdir()
    p = d / "template.json"
    p.write_text("{}")

    loader = configloaders.TemplateFileLoader(p)
    assert repr(loader) == f"TemplateFileLoader(path='{p.as_posix()}')"


if __name__ == "__main__":
    pytest.main([__file__])
