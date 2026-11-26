import pytest

from jinjarope import envglobals


def test_match():
    assert envglobals.match("a", a="hit", b="miss") == "hit"


if __name__ == "__main__":
    pytest.main([__file__])


def test_extract_header_section_with_regex_characters():
    from jinjarope import mdfilters

    md = "## C++ API\nbody\n## Why (not)?\nreason\n## [x\nother"
    assert mdfilters.extract_header_section(md, "C++ API") == "body\n"
    assert mdfilters.extract_header_section(md, "Why (not)?") == "reason\n"
    assert mdfilters.extract_header_section(md, "[x") == "other"
