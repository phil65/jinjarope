"""Tests for JinjaLoaderFileSystem."""

from __future__ import annotations

import fsspec
import jinja2
import pytest

from jinjarope import jinjaloaderfilesystem


# Test data
TEMPLATE_DATA = {
    "home.html": "Home",
    "about.html": "About",
    "subfolder/sub.html": "Sub",
    "subfolder/nested/deep.html": "Deep",
}


@pytest.fixture
def env() -> jinja2.Environment:
    """Create a Jinja environment with test templates."""
    return jinja2.Environment(loader=jinja2.DictLoader(TEMPLATE_DATA))


@pytest.fixture
def fs(env: jinja2.Environment) -> jinjaloaderfilesystem.JinjaLoaderFileSystem:
    """Create a JinjaLoaderFileSystem instance."""
    return jinjaloaderfilesystem.JinjaLoaderFileSystem(env)


def test_protocol(fs: jinjaloaderfilesystem.JinjaLoaderFileSystem):
    """Test protocol attribute."""
    assert fs.protocol == "jinja"
    assert fs.async_impl is True


def test_ls_root(fs: jinjaloaderfilesystem.JinjaLoaderFileSystem):
    """Test listing root directory."""
    assert fs.ls("") == [
        {"name": "subfolder", "type": "directory"},
        {"name": "about.html", "type": "file"},
        {"name": "home.html", "type": "file"},
    ]
    assert fs.ls("", detail=False) == ["subfolder", "about.html", "home.html"]


def test_ls_subdirectory(fs: jinjaloaderfilesystem.JinjaLoaderFileSystem):
    """Test listing subdirectory."""
    assert fs.ls("subfolder/", detail=False) == ["nested", "sub.html"]
    assert fs.ls("subfolder/", detail=True) == [
        {"name": "nested", "type": "directory"},
        {"name": "sub.html", "type": "file"},
    ]


def test_ls_nested_directory(fs: jinjaloaderfilesystem.JinjaLoaderFileSystem):
    """Test listing nested directory."""
    assert fs.ls("subfolder/nested/", detail=False) == ["deep.html"]
    assert fs.ls("subfolder/nested/", detail=True) == [
        {"name": "deep.html", "type": "file"},
    ]


def test_cat_single_file(fs: jinjaloaderfilesystem.JinjaLoaderFileSystem):
    """Test reading a single file."""
    assert fs.cat("home.html") == b"Home"
    assert fs.cat("about.html") == b"About"
    assert fs.cat("subfolder/sub.html") == b"Sub"


def test_cat_multiple_files(fs: jinjaloaderfilesystem.JinjaLoaderFileSystem):
    """Test reading multiple files."""
    result = fs.cat(["home.html", "about.html"])
    assert result == {"home.html": b"Home", "about.html": b"About"}


def test_isfile(fs: jinjaloaderfilesystem.JinjaLoaderFileSystem):
    """Test isfile method."""
    assert fs.isfile("home.html") is True
    assert fs.isfile("subfolder/sub.html") is True
    assert fs.isfile("nonexistent.html") is False
    assert fs.isfile("subfolder") is False


def test_isdir(fs: jinjaloaderfilesystem.JinjaLoaderFileSystem):
    """Test isdir method."""
    assert fs.isdir("") is True
    assert fs.isdir("/") is True
    assert fs.isdir(".") is True
    assert fs.isdir("subfolder") is True
    assert fs.isdir("subfolder/nested") is True
    assert fs.isdir("home.html") is False
    assert fs.isdir("nonexistent") is False


async def test_async_operations(fs: jinjaloaderfilesystem.JinjaLoaderFileSystem):
    """Test async operations."""
    assert await fs._cat_file("home.html") == b"Home"
    assert await fs._ls("", detail=True) == fs.ls("", detail=True)
    file = await fs._open_async("home.html")
    assert file.read() == b"Home"


def test_error_cases(fs: jinjaloaderfilesystem.JinjaLoaderFileSystem):
    """Test error cases."""
    with pytest.raises(FileNotFoundError, match="Template not found"):
        fs.cat("nonexistent.html")

    with pytest.raises(FileNotFoundError, match="Directory not found"):
        fs.ls("not-existing-dir")

    # Test with environment having no loader
    fs.env = jinja2.Environment()
    with pytest.raises(FileNotFoundError, match="Environment has no loader"):
        fs.ls("no-loader-set")

    with pytest.raises(FileNotFoundError, match="Environment has no loader"):
        fs.open("no-loader-set")


def test_fsspec_integration(env: jinja2.Environment):
    """Test integration with fsspec."""
    fsspec.register_implementation("jinja", jinjaloaderfilesystem.JinjaLoaderFileSystem)
    fs = fsspec.filesystem("jinja", env=env)
    assert fs.cat("home.html") == b"Home"


def test_exists(fs: jinjaloaderfilesystem.JinjaLoaderFileSystem):
    """Test exists method."""
    assert fs.exists("home.html") is True
    assert fs.exists("subfolder") is True
    assert fs.exists("nonexistent") is False


def test_info(fs: jinjaloaderfilesystem.JinjaLoaderFileSystem):
    """Test info method."""
    file_info = fs.info("home.html")
    assert file_info["type"] == "file"
    assert file_info["size"] == 4  # len("Home")  # noqa: PLR2004

    dir_info = fs.info("subfolder")
    assert dir_info["type"] == "directory"
    assert dir_info["size"] == 0

    with pytest.raises(FileNotFoundError):
        fs.info("nonexistent")


if __name__ == "__main__":
    pytest.main([__file__])
