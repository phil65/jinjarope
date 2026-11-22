from __future__ import annotations

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


def test_optional_item_with_broken_import_is_skipped(items_file):
    file = items_file(["broken_optional_pkg"])
    assert "broken" not in file.filters_dict


def test_required_item_with_broken_import_still_raises(items_file):
    file = items_file(None)
    with pytest.raises(ImportError):
        _ = file.filters_dict
