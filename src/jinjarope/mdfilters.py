from __future__ import annotations

import re
import types
from typing import TYPE_CHECKING, Any, Literal


if TYPE_CHECKING:
    from collections.abc import Callable


HEADER_REGEX = re.compile(r"^(#{1,6}) (.*)", flags=re.MULTILINE)


def md_link(
    text: str | None = None,
    link: str | None = None,
    tooltip: str | None = None,
) -> str:
    """Create a markdown link.

    If link is empty string or None, just the text will get returned.

    Args:
        text: Text to show for the link
        link: Target url
        tooltip: Optional tooltip
    """
    if not link:
        return text or ""
    tt = f" '{tooltip}'" if tooltip else ""
    return f"[{text or link}]({link}{tt})"


def extract_header_section(markdown: str, section_name: str) -> str | None:
    """Extract block with given header from markdown.

    Args:
        markdown: The markdown to extract a section from
        section_name: The header of the section to extract
    """
    header_pattern = re.compile(f"^(#+) {section_name}$", re.MULTILINE)
    md = str(markdown or "")
    header_match = header_pattern.search(md)
    if header_match is None:
        return None
    section_level = len(header_match[1])
    start_index = header_match.span()[1] + 1
    end_pattern = re.compile(f"^#{{1,{section_level}}} ", re.MULTILINE)
    end_match = end_pattern.search(md[start_index:])
    if end_match is None:
        return md[start_index:]
    end_index = end_match.span()[0]
    return md[start_index : end_index + start_index]


def md_escape(text: str, entity_type: str | None = None) -> str:
    """Helper function to escape markup.

    Args:
        text: The text.
        entity_type: For the entity types ``PRE``, ``CODE`` and the link
                     part of ``TEXT_LINKS``, only certain characters need to be escaped.
    """
    if entity_type in ["pre", "code"]:
        escape_chars = r"\`"
    elif entity_type == "text_link":
        escape_chars = r"\)"
    else:
        escape_chars = r"_*[]()~`>#+-=|{}.!"

    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)


def md_style(
    text: str,
    *,
    size: int | None = None,
    bold: bool = False,
    italic: bool = False,
    code: bool = False,
    align: Literal["left", "right", "center"] | None = None,
) -> str:
    """Apply styling to given markdown.

    Args:
        text: Text to style
        size: Optional text size
        bold: Whether styled text should be bold
        italic: Whether styled text should be italic
        code: Whether styled text should styled as (inline) code
        align: Optional text alignment
    """
    if not text:
        return text or ""
    if size:
        text = f"<font size='{size}'>{text}</font>"
    if bold:
        text = f"**{text}**"
    if italic:
        text = f"*{text}*"
    if code:
        text = f"`{text}`"
    if align:
        text = f"<p style='text-align: {align};'>{text}</p>"
    return text


def shift_header_levels(text: str, level_shift: int) -> str:
    """Shift the level of all headers of given text.

    Args:
        text: The Text to shift the header levels from
        level_shift: Level delta. (1 means "increase level by 1")
    """
    if not level_shift:
        return text

    def mod_header(match: re.Match[str], levels: int) -> str:
        header_str = match[1]
        if levels > 0:
            header_str += levels * "#"
        else:
            header_str = header_str[:levels]
        return f"{header_str} {match[2]}"

    return re.sub(HEADER_REGEX, lambda x: mod_header(x, level_shift), str(text or ""))


def autoref_link(
    text: str | None = None,
    link: str | types.ModuleType | Callable[..., Any] | None = None,
) -> str:
    """Create a markdown autorefs-style link (used by MkDocs / MkDocStrings).

    If link is empty string or None, just the text will get returned.

    Args:
        text: Text to show for the link
        link: Target url
    """
    if not link:
        return text or ""
    match link:
        case types.ModuleType():
            link = link.__name__
        case _ if callable(link):
            if (mod := link.__module__) != "builtins":
                link = f"{mod}.{link.__qualname__}"  # ty: ignore[missing-attribute]
            else:
                link = link.__qualname__  # ty: ignore[missing-attribute]

    return f"[{text or link}][{link}]"


if __name__ == "__main__":
    print(autoref_link("a", type))
