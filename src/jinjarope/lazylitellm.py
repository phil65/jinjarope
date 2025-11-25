from __future__ import annotations

import importlib


class LazyLiteLLM:
    _lazy_module = None

    def __getattr__(self, name):
        if name == "_lazy_module":
            return super()
        self._load_litellm()
        return getattr(self._lazy_module, name)

    def _load_litellm(self) -> None:
        if self._lazy_module is not None:
            return

        self._lazy_module = importlib.import_module("litellm")

        self._lazy_module.suppress_debug_info = True  # type: ignore[attr-defined]
        self._lazy_module.set_verbose = False  # type: ignore[attr-defined]
        self._lazy_module.drop_params = True  # type: ignore[attr-defined]
        self._lazy_module._logging._disable_debugging()


if __name__ == "__main__":
    litellm = LazyLiteLLM()
