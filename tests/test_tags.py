from __future__ import annotations

import datetime
import hmac
from typing import Any

import jinja2
from jinja2 import Environment
import pytest

from jinjarope.tags import ContainerTag, InclusionTag, StandaloneTag


class CurrentTimeTag(StandaloneTag):
    """Tag that outputs current time in specified format."""

    tags = {"current_time"}  # noqa: RUF012

    def render(self, format_str: str = "%H:%M:%S") -> str:
        return datetime.datetime.now().strftime(format_str)


class AlertTag(StandaloneTag):
    """Tag that creates an HTML alert box."""

    tags = {"alert"}  # noqa: RUF012
    safe_output = True

    def render(self, message: str, type_: str = "info") -> str:
        return f'<div class="alert alert-{type_}">{message}</div>'


class EncryptTag(ContainerTag):
    """Tag that encrypts its content using HMAC."""

    tags = {"encrypt"}  # noqa: RUF012

    def render(
        self, secret: str, digest: str = "sha256", caller: Any | None = None
    ) -> str:
        if caller is None:
            return ""

        content = str(caller()).encode()
        secret_bytes = secret.encode() if isinstance(secret, str) else secret

        signing = hmac.new(secret_bytes, content, digestmod=digest)
        return signing.hexdigest()


class HeaderTag(InclusionTag):
    """Tag that includes a header template."""

    tags = {"header"}  # noqa: RUF012
    template_name = "header.html"

    def get_context(self, title: str, **kwargs: Any) -> dict[str, Any]:
        return {"title": title, **kwargs}


@pytest.fixture
def env() -> Environment:
    """Create a Jinja2 environment with custom tags."""
    return Environment(
        extensions=[
            CurrentTimeTag,
            AlertTag,
            EncryptTag,
            HeaderTag,
        ]
    )


def test_current_time_tag(env: Environment):
    """Test CurrentTimeTag renders current time correctly."""
    template = env.from_string('{% current_time "%H:%M" %}')
    result = template.render()

    # Test that output matches time format
    expected_len = 5  # HH:MM
    assert len(result) == expected_len
    assert ":" in result
    assert result.replace(":", "").isdigit()


def test_current_time_tag_with_assignment(env: Environment):
    """Test CurrentTimeTag with variable assignment."""
    template = env.from_string('{% current_time "%H:%M" as time %}Time is: {{ time }}')
    result = template.render()

    assert "Time is: " in result
    len_string = 14  # "Time is: " + HH:MM
    assert len(result) == len_string


def test_alert_tag(env: Environment):
    """Test AlertTag renders HTML correctly."""
    template = env.from_string('{% alert "Hello World" %}')
    result = template.render()

    assert 'class="alert alert-info"' in result
    assert ">Hello World<" in result


def test_alert_tag_with_type(env: Environment):
    """Test AlertTag with custom alert type."""
    template = env.from_string('{% alert "Error occurred", type_="danger" %}')
    result = template.render()

    assert 'class="alert alert-danger"' in result
    assert ">Error occurred<" in result


def test_encrypt_tag(env: Environment):
    """Test EncryptTag encrypts content correctly."""
    template = env.from_string(
        '{% encrypt "secret", digest="sha1" %}test content{% endencrypt %}'
    )
    result = template.render()

    # Test that output is a valid hex string
    len_result = 40  # SHA-1 produces 40 hex chars
    assert len(result) == len_result
    assert all(c in "0123456789abcdef" for c in result)


def test_header_tag(env: Environment):
    """Test HeaderTag includes template correctly."""
    # Mock template loader
    content = "<h1>{{ title }}</h1>{% if subtitle %}<h2>{{ subtitle }}</h2>{% endif %}"
    env.loader = jinja2.DictLoader({"header.html": content})

    template = env.from_string('{% header title="Welcome", subtitle="Hello" %}')
    result = template.render()

    assert "<h1>Welcome</h1>" in result
    assert "<h2>Hello</h2>" in result


def test_header_tag_minimal(env: Environment):
    """Test HeaderTag with minimal parameters."""
    # Mock template loader
    env.loader = jinja2.DictLoader({"header.html": "<h1>{{ title }}</h1>"})

    template = env.from_string('{% header title="Welcome" %}')
    result = template.render()

    assert "<h1>Welcome</h1>" in result
    assert "<h2>" not in result
