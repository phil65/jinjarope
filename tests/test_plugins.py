from __future__ import annotations

from typing import Any

import jinjarope
from jinjarope import utils


def test_broken_environment_plugin_is_skipped(monkeypatch, caplog):
    def broken(env: Any) -> None:
        msg = "No module named 'incompatible_dependency'"
        raise ModuleNotFoundError(msg)

    def working(env: Any) -> None:
        env.globals["plugin_ran"] = True

    plugins = {"broken": broken, "working": working}
    monkeypatch.setattr(utils, "entry_points", lambda group: plugins)
    env = jinjarope.Environment()
    assert env.globals["plugin_ran"] is True
    assert "broken" in caplog.text
