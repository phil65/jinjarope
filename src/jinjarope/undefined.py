from __future__ import annotations

from typing import Any, Literal

import jinja2


UndefinedStr = Literal["keep", "silent", "strict", "lax"]


class LaxUndefined(jinja2.Undefined):
    """Pass anything wrong as blank."""

    def _fail_with_undefined_error(self, *args: Any, **kwargs: Any) -> str:  # type: ignore[override]
        return ""


UNDEFINED_BEHAVIOR: dict[UndefinedStr, type[jinja2.Undefined]] = {
    "keep": jinja2.DebugUndefined,
    "silent": jinja2.Undefined,
    "strict": jinja2.StrictUndefined,
    # lax will even pass unknown objects:
    "lax": LaxUndefined,
}


if __name__ == "__main__":
    pass
