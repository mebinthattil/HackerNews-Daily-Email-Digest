"""Render untrusted LLM summary text (markdown) into safe, sanitized HTML.

Summaries are produced by an LLM summarizing arbitrary scraped web pages, so the
text is UNTRUSTED. A summary can legitimately contain literal HTML/CSS -- e.g. a
summary of a CSS/HTML component library like ``98.css`` will include tags such as
``<textarea>`` or ``<input type="text">`` as inline code examples. Injecting that
raw into the digest (as the old ``| safe`` template filter did) makes the browser
/ email client render those as real elements, breaking the whole layout (an
unclosed ``<textarea>`` swallows the rest of the page). It is also an
HTML/CSS/JS injection vector.

To stay safe *and* keep nice formatting we convert markdown -> HTML and then
sanitize the result against a strict allowlist, dropping every tag or attribute
not on the list (``<script>``, ``<style>``, ``<input>``, ``<textarea>``, inline
styles, class names, event handlers, ``javascript:`` links, etc.).

Heavy deps (``markdown``, ``nh3``) are imported lazily inside the function so the
lean web deployment -- which only serves pre-rendered static archives and never
renders this template -- does not need the ``worker`` extras installed.
"""

from typing import Optional

from markupsafe import Markup

# Inline/formatting tags we allow from a summary. Deliberately excludes form
# controls, <style>, <script>, <img>, and anything that can escape the summary
# box or break the surrounding layout.
ALLOWED_TAGS = {
    "p", "br", "hr",
    "strong", "em", "b", "i", "u", "s", "del",
    "ul", "ol", "li",
    "code", "pre",
    "blockquote",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "a",
}

ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
}


def render_summary(text: Optional[str]) -> Markup:
    """Convert an LLM markdown summary into sanitized, injection-safe HTML.

    Returns an empty ``Markup`` for missing/blank input so the template renders
    nothing instead of the literal word ``"None"``. The returned value is a
    ``Markup`` instance and is already sanitized, so Jinja will not re-escape it
    and no ``| safe`` filter is required (or wanted) in the template.
    """
    if text is None:
        return Markup("")
    text = text.strip()
    if not text:
        return Markup("")

    import markdown
    import nh3

    html = markdown.markdown(text, extensions=["sane_lists"])
    cleaned = nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        link_rel="noopener noreferrer nofollow",
    )
    return Markup(cleaned)
