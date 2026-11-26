"""Signature filters with annotations naming TYPE_CHECKING-only imports (PEP 649)."""

from typing import TYPE_CHECKING

from jinjarope import inspectfilters, iterfilters, textfilters


if TYPE_CHECKING:
    from fractions import Fraction


def uses_missing_name(value: Fraction, n: int = 1) -> str:
    return str(n)


def test_format_signature_falls_back_to_source_strings() -> None:
    result = textfilters.format_signature(uses_missing_name)
    assert result == "(value: 'Fraction', n: 'int' = 1) -> 'str'"


def test_format_signature_evaluates_when_possible() -> None:
    assert textfilters.format_signature(iterfilters.do_zip) == (
        "(*items: collections.abc.Iterable[T]) -> collections.abc.Iterator[tuple[T, ...]]"
    )


def test_format_filter_signature() -> None:
    result = textfilters.format_filter_signature(uses_missing_name, "ffs")
    assert result == "value: 'Fraction' | ffs(n: 'int' = 1) -> 'str'"


def test_get_signature() -> None:
    sig = inspectfilters.get_signature(uses_missing_name)
    assert list(sig.parameters) == ["value", "n"]
    assert sig.parameters["value"].annotation == "Fraction"
