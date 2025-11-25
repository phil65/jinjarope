from __future__ import annotations

import dataclasses
from typing import Any, Literal

import jinja2

from jinjarope import utils


@dataclasses.dataclass(unsafe_hash=True)
class EnvConfig:
    """A class representing the config of an Environment.

    Does not include loaders, filters, tests, globals.
    """

    block_start_string: str = "{%"
    """The string marking the beginning of a block. Defaults to '{%'."""
    block_end_string: str = "%}"
    """The string marking the end of a block. Defaults to '%}'."""
    variable_start_string: str = r"{{"
    """The string marking the end of a print statement. Defaults to '}}'."""
    variable_end_string: str = r"}}"
    """The string marking the end of a print statement. Defaults to '}}'."""
    comment_start_string: str = "{#"
    """The string marking the beginning of a comment. Defaults to '{#'."""
    comment_end_string: str = "#}"
    """The string marking the end of a comment. Defaults to '#}'."""
    line_statement_prefix: str | None = None
    """If given and a string, this will be used as prefix for line based statements."""
    line_comment_prefix: str | None = None
    """If given and a string, this will be used as prefix for line based comments."""
    trim_blocks: bool = True
    """Remove first newline after a block (not variable tag!). Defaults to False."""
    lstrip_blocks: bool = False
    """Strip leading spaces / tabs from start of a line to a block. Defaults to False."""
    newline_sequence: Literal["\n", "\r\n", "\r"] = "\n"
    r"""The sequence that starts a newline. ('\r', '\n' or '\r\n'. Defaults to '\n' """
    keep_trailing_newline: bool = False
    """Preserve the trailing newline when rendering templates. The default is False.

    The default causes a single newline, if present,
    to be stripped from the end of the template.
    """
    loader: jinja2.BaseLoader | None = None
    """The template loader."""
    undefined: type[jinja2.Undefined] = jinja2.StrictUndefined
    """The undefined object determining the "Undefined" behavior."""
    extensions: list[str] = dataclasses.field(
        default_factory=list,
    )
    """A list of jinja2 extentions."""

    def __repr__(self) -> str:
        return utils.get_repr(self, **self.as_dict())

    def as_dict(self) -> dict[str, Any]:
        """Return dataclass as a dict, filtering all None-values."""
        return {
            field.name: v
            for field in dataclasses.fields(self)
            if (v := getattr(self, field.name)) is not None
        }


if __name__ == "__main__":
    cfg = EnvConfig(newline_sequence="\n")
    print(repr(cfg))
