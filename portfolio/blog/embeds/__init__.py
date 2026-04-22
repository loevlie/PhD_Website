"""Pluggable `<div data-*="…">` marker system for blog posts.

Each handler in this package registers a marker attribute (e.g.
`data-demo`, `data-arxiv`, `data-github`, `data-wiki`, `data-quiz`,
`data-plot`, `data-equation`) and provides a function that turns the
marker's attributes into rendered HTML. Before markdown conversion,
`render_markdown` calls `expand_embeds(content)` which runs every
registered handler once.

Why one system instead of per-marker regexes scattered across the
blog module: each handler wants the same primitives (cache, network
retry, inline-error rendering, template rendering). Centralising them
keeps the individual handlers one-screen small and the
markdown-to-HTML pipeline obvious.

Adding a new marker:
  1. Create portfolio/blog/embeds/<name>.py implementing a `render(
     match_dict)` function that returns HTML.
  2. Import + register it below.
  3. Add a gate in blog_post.html if the marker needs a JS/CSS asset.
  4. Write a test in tests/test_embeds.py.
"""
import re
from functools import lru_cache
from typing import Callable, List


# ─── Primitive helpers the individual handlers share ─────────────────

def render_error(message: str) -> str:
    """Inline red-box error used when a marker references something
    that doesn't exist (unknown demo slug, arxiv not reachable, etc.).
    Styled by demos-embed.css. Visible so authors notice the typo."""
    return f'<div class="demo-embed-error">{message}</div>'


def render_card(body_html: str, *, slug_attr: str = '', slug_val: str = '') -> str:
    """Wrap the given HTML in the standard `.embed-card` chrome so
    every rich-link preview (arxiv / github / wiki / …) has the same
    outer shape, spacing, and dark-mode contract."""
    attr = f' {slug_attr}="{slug_val}"' if slug_attr and slug_val else ''
    return f'<div class="embed-card"{attr}>{body_html}</div>'


def cache_key(namespace: str, key: str) -> str:
    """Namespaced Django cache key. The `v1:` prefix means any
    schema-breaking change can force a cold refresh by bumping it."""
    return f'embed:v1:{namespace}:{key}'


# ─── Dispatcher ──────────────────────────────────────────────────────

# Each entry: (regex, handler). The regex MUST have a single .group(1)
# capture that identifies the marker (slug / id / arxiv-id / repo-path).
_HANDLERS: List[tuple] = []


def register(pattern: str, handler: Callable[[re.Match], str]) -> None:
    """Register a marker. `pattern` is a regex string with one capture
    group for the primary identifier; `handler` receives the match
    object and returns HTML."""
    _HANDLERS.append((re.compile(pattern, re.IGNORECASE), handler))


def expand_embeds(content: str) -> str:
    """Entry point called by render_markdown. Runs every registered
    handler against the content; returns the expanded string. O(N*M)
    where N = handlers, M = content length; N ≈ 10 so this is cheap."""
    # Fast-path: if no `data-` attribute is present anywhere, skip
    # the whole dispatcher — most blog posts don't embed anything.
    if 'data-' not in content:
        return content
    for regex, handler in _HANDLERS:
        content = regex.sub(lambda m: handler(m), content)
    return content


# ─── Register built-in handlers ───────────────────────────────────────
#
# Order matters: the more specific marker is registered first so a
# generic scanner (e.g. `<div data-*>` — there isn't one, but mentally)
# can't short-circuit a specific one. Today all markers use disjoint
# attribute names, so order is only relevant if we ever add a fallback.
from . import demo        as _demo
from . import arxiv       as _arxiv
from . import github      as _github
from . import wiki        as _wiki
from . import equation    as _equation
from . import quiz        as _quiz
from . import plot        as _plot


_demo.register_all(register)
_arxiv.register_all(register)
_github.register_all(register)
_wiki.register_all(register)
_equation.register_all(register)
_quiz.register_all(register)
_plot.register_all(register)
