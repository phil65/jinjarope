from __future__ import annotations

from typing import TYPE_CHECKING

import jinja2
import pytest

from jinjarope import environment, fsspecloaders


if TYPE_CHECKING:
    import pathlib


def test_fsspec_protocol_loader():
    env = environment.Environment()
    env.loader = fsspecloaders.FsSpecProtocolPathLoader()
    assert env.get_template("file://tests/testresources/testfile.jinja").render()
    assert "file://tests/testresources/testfile.jinja" in env.loader
    assert "file://not_existing.jinja" not in env.loader
    with pytest.raises(jinja2.TemplateNotFound):
        env.get_template("file://tests/testresources/not-existing.jinja")


def test_fsspec_filesystem_loader():
    env = environment.Environment()
    env.loader = fsspecloaders.FsSpecFileSystemLoader("file")
    assert env.get_template("tests/testresources/testfile.jinja").render()
    env.loader = fsspecloaders.FsSpecFileSystemLoader("file://")
    assert env.get_template("tests/testresources/testfile.jinja").render()
    with pytest.raises(jinja2.TemplateNotFound):
        env.get_template("tests/testresources/not-existing.jinja")


def test_fsspec_filesystem_loader_with_dir_prefix():
    env = environment.Environment()
    env.loader = fsspecloaders.FsSpecFileSystemLoader("dir::file://tests/testresources")
    assert env.get_template("testfile.jinja").render()
    with pytest.raises(jinja2.TemplateNotFound):
        env.get_template("not-existing.jinja")


async def test_protocol_loader_async_twice(tmp_path: pathlib.Path):
    (tmp_path / "a.jinja").write_text("hello")
    path = (tmp_path / "a.jinja").as_posix()
    loader = fsspecloaders.FsSpecProtocolPathLoader()
    for _ in range(2):
        src, _name, _uptodate = await loader.get_source_async(None, path)
        assert src == "hello"
    with pytest.raises(jinja2.TemplateNotFound):
        await loader.get_source_async(None, (tmp_path / "missing.jinja").as_posix())


def test_filesystem_loader_uses_url_path(tmp_path: pathlib.Path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.jinja").write_text("A")
    (tmp_path / "sub" / "b.jinja").write_text("B")
    loader = fsspecloaders.FsSpecFileSystemLoader(f"file://{tmp_path.as_posix()}")
    env = environment.Environment(loader=loader)
    assert env.get_template("a.jinja").render() == "A"
    assert env.get_template("sub/b.jinja").render() == "B"
    assert sorted(loader.list_templates()) == ["a.jinja", "sub/b.jinja"]
    assert "a.jinja" in loader
    assert "missing.jinja" not in loader
    with pytest.raises(jinja2.TemplateNotFound):
        env.get_template("../outside.jinja")


def test_filesystem_loader_memory_url():
    loader = fsspecloaders.FsSpecFileSystemLoader("memory://jinjarope-test/tpl")
    loader.fs.pipe("x.jinja", b"X")  # written under the URL path
    assert loader.list_templates() == ["x.jinja"]
    assert loader.get_source(None, "x.jinja")[0] == "X"


async def test_filesystem_loader_async(tmp_path: pathlib.Path):
    (tmp_path / "a.jinja").write_text("A")
    loader = fsspecloaders.FsSpecFileSystemLoader(f"file://{tmp_path.as_posix()}")
    src, _name, _uptodate = await loader.get_source_async(None, "a.jinja")
    assert src == "A"
    with pytest.raises(jinja2.TemplateNotFound):
        await loader.get_source_async(None, "missing.jinja")


if __name__ == "__main__":
    pytest.main([__file__])
