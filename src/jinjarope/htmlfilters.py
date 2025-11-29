from __future__ import annotations

import base64
import functools
import logging
import posixpath
import re
from typing import TYPE_CHECKING, Any, Literal, TypeVar


if TYPE_CHECKING:
    from collections.abc import Mapping
    from xml.etree import ElementTree as ET


logger = logging.getLogger(__name__)

QueryStr = Literal[
    "fragment",
    "hostname",
    "netloc",
    "password",
    "path",
    "port",
    "query",
    "scheme",
    "username",
]

ANSI_STYLES = {
    1: {"font_weight": "bold"},
    2: {"font_weight": "lighter"},
    3: {"font_weight": "italic"},
    4: {"text_decoration": "underline"},
    5: {"text_decoration": "blink"},
    6: {"text_decoration": "blink"},
    8: {"visibility": "hidden"},
    9: {"text_decoration": "line-through"},
    30: {"color": "black"},
    31: {"color": "red"},
    32: {"color": "green"},
    33: {"color": "yellow"},
    34: {"color": "blue"},
    35: {"color": "magenta"},
    36: {"color": "cyan"},
    37: {"color": "white"},
}


def wrap_in_elem(text: str | None, tag: str, add_linebreaks: bool = False, **kwargs: Any) -> str:
    """Wrap given text in an HTML/XML tag (with attributes).

    If text is empty, just return an empty string.

    Args:
        text: Text to wrap
        tag: Tag to wrap text in
        add_linebreaks: Adds a linebreak before and after the text
        kwargs: additional key-value pairs to be inserted as attributes for tag.
                Key strings will have "_" stripped from the end to allow using keywords.
    """
    if not text:
        return ""
    attrs = [f'{k.rstrip("_")}="{v}"' for k, v in kwargs.items()]
    attr_str = (" " + " ".join(attrs)) if attrs else ""
    nl = "\n" if add_linebreaks else ""
    return f"<{tag}{attr_str}>{nl}{text}{nl}</{tag}>"


def html_link(text: str | None = None, link: str | None = None, **kwargs: Any) -> str:
    """Create a html link.

    If link is empty string or None, just the text will get returned.

    Args:
        text: Text to show for the link
        link: Target url
        kwargs: additional key-value pairs to be inserted as attributes.
                Key strings will have "_" stripped from the end to allow using keywords.
    """
    if not link:
        return text or ""
    attrs = [f'{k.rstrip("_")}="{v}"' for k, v in kwargs.items()]
    attr_str = (" " + " ".join(attrs)) if attrs else ""
    return f"<a href={link!r}{attr_str}>{text or link}</a>"


def format_js_map(mapping: dict[str, Any] | str, indent: int = 4) -> str:
    """Return JS map str for given dictionary.

    Args:
        mapping: Dictionary to dump
        indent: The amount of indentation for the key-value pairs
    """
    import anyenv

    dct = anyenv.load_json(mapping) if isinstance(mapping, str) else mapping
    rows: list[str] = []
    indent_str = " " * indent
    for k, v in dct.items():
        match v:
            case bool():
                rows.append(f"{indent_str}{k}: {str(v).lower()},")
            case dict():
                rows.append(f"{indent_str}{k}: {format_js_map(v)},")
            case None:
                rows.append(f"{indent_str}{k}: null,")
            case _:
                rows.append(f"{indent_str}{k}: {v!r},")
    row_str = "\n" + "\n".join(rows) + "\n"
    return f"{{{row_str}}}"


def svg_to_data_uri(svg: str) -> str:
    """Wrap svg as data URL.

    Args:
        svg: The svg to wrap into a data URL
    """
    if not isinstance(svg, str):
        msg = "Invalid type: %r"
        raise TypeError(msg, type(svg))
    return f"url('data:image/svg+xml;charset=utf-8,{svg}')"


def clean_svg(text: str) -> str:
    """Strip off unwanted stuff from svg text which might be added by external libs.

    Removes xml headers and doctype declarations.

    Args:
        text: The text to cleanup / filter
    """
    text = re.sub(r"<\?xml version.*\?>\s*", "", text, flags=re.DOTALL)
    text = re.sub(r"<!DOCTYPE svg.*?>", "", text, flags=re.DOTALL)
    return text.strip()


def format_css_rule(dct: Mapping[str, Any]) -> str:
    """Format a nested dictionary as CSS rule.

    Mapping must be of shape {".a": {"b": "c"}}

    Args:
        dct: The mapping to convert to CSS text
    """
    data: dict[str, list[str]] = {}

    def _parse(obj: Mapping[str, Any], selector: str = "") -> None:
        for key, value in obj.items():
            if hasattr(value, "items"):
                rule = selector + " " + key
                data[rule] = []
                _parse(value, rule)

            else:
                prop = data[selector]
                prop.append(f"\t{key}: {value};\n")

    _parse(dct)
    string = ""
    for key, value in sorted(data.items()):
        if data[key]:
            string += key[1:] + " {\n" + "".join(value) + "}\n\n"
    return string


@functools.lru_cache
def format_xml(
    str_or_elem: str | ET.Element,
    indent: str | int = "  ",
    level: int = 0,
    method: Literal["xml", "html", "text", "c14n"] = "html",
    short_empty_elements: bool = True,
    add_declaration: bool = False,
) -> str:
    """(Pretty)print given XML.

    Args:
        str_or_elem: XML to prettyprint
        indent: Amount of spaces to use for indentation
        level: Initial indentation level
        method: Output method
        short_empty_elements: Whether empty elements should get printed in short form
                              (applies when mode is "xml")
        add_declaration: whether a XML declaration should be printed
                         (applies when mode is "xml")
    """
    from xml.etree import ElementTree as ET

    if isinstance(str_or_elem, str):
        str_or_elem = ET.fromstring(str_or_elem)
    space = indent if isinstance(indent, str) else indent * " "
    ET.indent(str_or_elem, space=space, level=level)
    return ET.tostring(
        str_or_elem,
        encoding="unicode",
        method=method,
        xml_declaration=add_declaration,
        short_empty_elements=short_empty_elements,
    )


def ansi2html(ansi_string: str, styles: dict[int, dict[str, str]] | None = None) -> str:
    """Convert ansi string to colored HTML.

    Args:
        ansi_string: text with ANSI color codes.
        styles: A mapping from ANSI codes to a dict with css

    Returns:
        HTML string
    """
    styles = styles or ANSI_STYLES
    previous_end = 0
    in_span = False
    ansi_codes: list[int] = []
    ansi_finder = re.compile("\033\\[([\\d;]*)([a-zA-z])")
    parts = []
    for match in ansi_finder.finditer(ansi_string):
        parts.append(ansi_string[previous_end : match.start()])
        previous_end = match.end()
        params, command = match.groups()

        if command not in "mM":
            continue

        try:
            params = [int(p) for p in params.split(";")]
        except ValueError:
            params = [0]

        for i, v in enumerate(params):
            if v == 0:
                params = params[i + 1 :]
                if in_span:
                    in_span = False
                    parts.append("</span>")
                ansi_codes = []
                if not params:
                    continue

        ansi_codes.extend(params)
        if in_span:
            parts.append("</span>")
            in_span = False

        if not ansi_codes:
            continue

        style = [
            "; ".join([f"{k}: {v}" for k, v in styles[k].items()]).strip()
            for k in ansi_codes
            if k in styles
        ]
        parts.append(f'<span style="{"; ".join(style)}">')

        in_span = True

    parts.append(ansi_string[previous_end:])
    if in_span:
        parts.append("</span>")
        in_span = False
    return "".join(parts)


def split_url(value: str, query: QueryStr | None = None) -> str | dict[str, str]:
    """Split a URL into its parts (and optionally return a specific part).

    Args:
        value: The URL to split
        query: Optional URL part to extract
    """
    from urllib.parse import urlsplit

    def object_to_dict(obj: Any, exclude: list[str] | None = None) -> dict[str, Any]:
        """Converts an object into a dict making the properties into keys.

        Allows excluding certain keys.
        """
        if exclude is None or not isinstance(exclude, list):
            exclude = []
        return {
            key: getattr(obj, key)
            for key in dir(obj)
            if not (key.startswith("_") or key in exclude)
        }

    to_exclude = ["count", "index", "geturl", "encode"]
    results = object_to_dict(urlsplit(value), exclude=to_exclude)

    # If a query is supplied, make sure it's valid then return the results.
    # If no option is supplied, return the entire dictionary.
    if not query:
        return results
    if query not in results:
        msg = "split_url: unknown URL component: %s"
        raise ValueError(msg, query)
    return results[query]  # type: ignore[no-any-return]


@functools.lru_cache
def _get_norm_url(path: str) -> tuple[str, int]:
    from urllib.parse import urlsplit

    if not path:
        path = "."
    elif "\\" in path:
        logger.warning(
            "Path %r uses OS-specific separator '\\'. "
            "That will be unsupported in a future release. Please change it to '/'.",
            path,
        )
        path = path.replace("\\", "/")
    # Allow links to be fully qualified URLs
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc or path.startswith(("/", "#")):
        return path, -1

    # Relative path - preserve information about it
    norm = posixpath.normpath(path) + "/"
    relative_level = 0
    while norm.startswith("../", relative_level * 3):
        relative_level += 1
    return path, relative_level


def normalize_url(path: str, url: str | None = None, base: str = "") -> str:
    """Return a URL relative to the given url or using the base.

    Args:
        path: The path to normalize
        url: Optional relative url
        base: Base path
    """
    path, relative_level = _get_norm_url(path)
    if relative_level == -1:
        return path
    if url is None:
        return posixpath.join(base, path)
    result = relative_url(url, path)
    if relative_level > 0:
        result = "../" * relative_level + result
    return result


@functools.cache
def _norm_parts(path: str) -> list[str]:
    if not path.startswith("/"):
        path = "/" + path
    path = posixpath.normpath(path)[1:]
    return path.split("/") if path else []


def relative_url_mkdocs(url: str, other: str) -> str:
    """Return given url relative to other (MkDocs implementation).

    Both are operated as slash-separated paths, similarly to the 'path' part of a URL.
    The last component of `other` is skipped if it contains a dot (considered a file).
    Actual URLs (with schemas etc.) aren't supported. The leading slash is ignored.
    Paths are normalized ('..' works as parent directory), but going higher than the
    root has no effect ('foo/../../bar' ends up just as 'bar').

    Args:
        url: URL A.
        other: URL B.
    """
    # Remove filename from other url if it has one.
    dirname, _, basename = other.rpartition("/")
    if "." in basename:
        other = dirname

    other_parts = _norm_parts(other)
    dest_parts = _norm_parts(url)
    common = 0
    for a, b in zip(other_parts, dest_parts):
        if a != b:
            break
        common += 1

    rel_parts = [".."] * (len(other_parts) - common) + dest_parts[common:]
    relurl = "/".join(rel_parts) or "."
    return relurl + "/" if url.endswith("/") else relurl


def relative_url(url_a: str, url_b: str) -> str:
    """Compute the relative path from URL A to URL B.

    Args:
        url_a: URL A.
        url_b: URL B.

    Returns:
        The relative URL to go from A to B.
    """
    parts_a = url_a.split("/")
    if "#" in url_b:
        url_b, anchor = url_b.split("#", 1)
    else:
        anchor = None
    parts_b = url_b.split("/")

    # remove common left parts
    while parts_a and parts_b and parts_a[0] == parts_b[0]:
        parts_a.pop(0)
        parts_b.pop(0)

    # go up as many times as remaining a parts' depth
    levels = len(parts_a) - 1
    parts_relative = [".."] * levels + parts_b
    relative = "/".join(parts_relative)
    return f"{relative}#{anchor}" if anchor else relative


def url_to_b64(image_url: str) -> str | None:
    """Convert an image URL to a base64-encoded string.

    Args:
        image_url: The URL of the image to convert.

    Returns:
        The base64-encoded string of the image.

    Raises:
        requests.RequestException: If there's an error downloading the image.
    """
    import httpx

    # Download the image
    with httpx.Client(follow_redirects=True) as client:
        response = client.get(image_url)
        response.raise_for_status()
        image_data = response.content

    # Encode the image to base64
    return base64.b64encode(image_data).decode("utf-8")


StrOrBytes = TypeVar("StrOrBytes", bytes, str)


# TypeVar for maintaining input/output type consistency
ContentType = TypeVar("ContentType", str, bytes)
Position = Literal["body", "head", "end_head", "end_body"]


def inject_javascript[ContentType: (str, bytes)](
    html_content: ContentType,
    javascript: str,
    *,
    position: Position = "end_body",
) -> ContentType:
    """Injects JavaScript code into an HTML string or bytes object.

    Args:
        html_content: The HTML content to inject the JavaScript into
        javascript: The JavaScript code to inject
        position: The position to inject the JavaScript ('body' by default)

    Returns:
        The modified HTML content with the same type as the input

    Raises:
        ValueError: If the specified position tag is not found in the HTML content
        TypeError: If the input type is neither str nor bytes
    """
    # Convert bytes to str if needed
    is_bytes = isinstance(html_content, bytes)
    working_content: str = html_content.decode() if is_bytes else html_content  # type: ignore[assignment, attr-defined]

    # Prepare the JavaScript tag
    script_tag = f"<script>{javascript}</script>"

    # Define the injection patterns
    patterns = {
        "body": (r"<body[^>]*>", lambda m: f"{m.group(0)}{script_tag}"),
        "head": (r"<head[^>]*>", lambda m: f"{m.group(0)}{script_tag}"),
        "end_head": (r"</head>", lambda m: f"{script_tag}{m.group(0)}"),
        "end_body": (r"</body>", lambda m: f"{script_tag}{m.group(0)}"),
    }

    if position not in patterns:
        msg = f"Invalid position: {position}. Must be one of {list(patterns.keys())}"
        raise ValueError(msg)

    pattern, replacement = patterns[position]
    modified_content = re.sub(pattern, replacement, working_content, count=1)

    # If no substitution was made, the tag wasn't found
    if modified_content == working_content:
        msg = f"Could not find {position} tag in HTML content"
        raise ValueError(msg)
    # Return the same type as input
    return modified_content.encode() if is_bytes else modified_content  # type: ignore[return-value]


if __name__ == "__main__":
    print(format_js_map({"key": {"nested_key": "nested_value"}}))
