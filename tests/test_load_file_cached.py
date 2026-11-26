from __future__ import annotations

import os
from typing import TYPE_CHECKING

import upath

from jinjarope import envglobals


if TYPE_CHECKING:
    import pathlib


def _touch_later(path: pathlib.Path, text: str) -> None:
    """Rewrite a file and move its mtime forward (coarse file system clocks)."""
    stat = path.stat()
    path.write_text(text, encoding="utf-8")
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))


def test_local_edits_are_seen(tmp_path: pathlib.Path):
    path = tmp_path / "t.jinja"
    path.write_text("old", encoding="utf-8")
    assert envglobals.load_file_cached(path) == "old"
    _touch_later(path, "new")
    assert envglobals.load_file_cached(str(path)) == "new"
    assert envglobals.load_file_cached(upath.UPath(path)) == "new"


def test_unchanged_file_is_read_once(tmp_path: pathlib.Path, monkeypatch):
    path = tmp_path / "t.jinja"
    path.write_text("text", encoding="utf-8")
    reads: list[str] = []
    real = envglobals._read_text
    monkeypatch.setattr(envglobals, "_read_text", lambda p: reads.append(str(p)) or real(p))
    for _ in range(3):
        assert envglobals.load_file_cached(path) == "text"
    assert len(reads) == 1


def test_cache_is_bounded(tmp_path: pathlib.Path):
    envglobals.clear_file_cache()
    for i in range(envglobals.FILE_CACHE_SIZE + 10):
        path = tmp_path / f"{i}.txt"
        path.write_text(str(i), encoding="utf-8")
        envglobals.load_file_cached(path)
    assert len(envglobals._file_cache) == envglobals.FILE_CACHE_SIZE


def test_remote_paths_are_cached_by_url():
    path = upath.UPath("memory://jinjarope-test/t.txt")
    path.write_text("remote", encoding="utf-8")
    assert envglobals.load_file_cached(path) == "remote"
    assert envglobals.load_file_cached("memory://jinjarope-test/t.txt") == "remote"
