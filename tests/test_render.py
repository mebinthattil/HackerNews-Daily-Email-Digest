"""Regression tests for src/render.py.

These lock in the fix for the malformed July 24, 2026 digest, where an LLM
summary of the ``98.css`` component library contained literal HTML tags
(``<label>``, ``<textarea>``, ``<input>`` ...). The old template rendered
summaries with ``| safe``, so those tags became real elements and an unclosed
``<textarea>`` swallowed the rest of the digest.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from render import render_summary  # noqa: E402


# The exact shape of content that broke the July 24 digest.
NINETY_EIGHT_CSS_SUMMARY = """98.css styles semantic HTML to mimic Windows 98.

* **Checkbox** require associated `<label>` elements.
* **GroupBox** implemented with `<fieldset>`/`<legend>`.
* **TextBox** single-line `<input type="text">` or multiline `<textarea>`.
* **Slider** `<input type="range">` with `.has-box-indicator`.
"""


@pytest.mark.unit
@pytest.mark.parametrize(
    "tag",
    ["<textarea", "<input", "<label", "<fieldset", "<legend", "<select", "<form"],
)
def test_literal_html_tags_are_not_emitted_as_elements(tag):
    """Literal HTML tags in a summary must never render as real elements."""
    out = str(render_summary(NINETY_EIGHT_CSS_SUMMARY))
    assert tag not in out


@pytest.mark.unit
def test_dangerous_tags_are_stripped():
    out = str(render_summary("<script>alert(1)</script><style>body{display:none}</style>hi"))
    assert "<script" not in out
    assert "<style" not in out
    assert "hi" in out


@pytest.mark.unit
def test_javascript_links_are_neutralized():
    out = str(render_summary("[click](javascript:alert(1))"))
    assert "javascript:" not in out


@pytest.mark.unit
def test_markdown_formatting_is_preserved():
    out = str(render_summary(NINETY_EIGHT_CSS_SUMMARY))
    assert "<strong>Checkbox</strong>" in out
    assert "<ul>" in out and "<li>" in out
    # The literal tags survive as visible, escaped code text.
    assert "&lt;textarea&gt;" in out


@pytest.mark.unit
@pytest.mark.parametrize("value", [None, "", "   ", "\n\t "])
def test_blank_input_renders_empty(value):
    """Missing summaries render nothing, not the literal word 'None'."""
    assert str(render_summary(value)) == ""


@pytest.mark.unit
def test_output_is_markup_safe():
    from markupsafe import Markup

    assert isinstance(render_summary("**hi**"), Markup)
