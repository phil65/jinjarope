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


def test_slow_entry_point_is_logged(monkeypatch, caplog):
    import logging
    import time

    class FakeEntryPoint:
        value = "slowpkg:setup"

        def load(self) -> Any:
            time.sleep(0.02)
            return lambda env: None

    class FakeRegistry:
        def __init__(self, group: str) -> None:
            pass

        def __class_getitem__(cls, item: Any) -> type:
            return cls

        def get_all(self) -> dict[str, Any]:
            return {"slow": FakeEntryPoint()}

    import epregistry

    monkeypatch.setattr(epregistry, "EntryPointRegistry", FakeRegistry)
    monkeypatch.setattr(utils, "SLOW_ENTRY_POINT_SECONDS", 0.01)
    with caplog.at_level(logging.INFO, logger="jinjarope.utils"):
        assert set(utils.entry_points("jinjarope.environment")) == {"slow"}
    assert "slowpkg:setup" in caplog.text
