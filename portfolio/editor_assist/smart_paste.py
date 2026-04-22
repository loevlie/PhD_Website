"""URL-shape detection for smart-paste in the editor.

Pure-Python, no Django, no network. Mirrors the same regex patterns
the client-side editor-smart-paste.js uses, so the two sides stay
aligned and can be tested from Python without spinning a browser.

Contract:
    detect(url) -> SmartPasteResult | None

Each result carries a `marker` string the editor inserts verbatim
into the markdown source. The embeds dispatcher
(portfolio/blog/embeds/) then expands those markers at
render-time.

Extending:
    1. Add a new RE + handler function below.
    2. Append to _DETECTORS in priority order (more specific first).
    3. Add a client-side mirror in editor-smart-paste.js.
    4. Write a test in tests/test_smart_paste.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Callable, Optional


@dataclass
class SmartPasteResult:
    """Structured output of a successful detection."""
    kind: str            # 'arxiv' / 'github' / 'github_snippet' / 'wiki'
    marker: str          # text inserted into the markdown body
    # For github_snippet we pass the parsed components through so the
    # editor can display a one-line preview ("fetching owner/repo@sha…")
    # while the server renders the actual snippet at post-save time.
    meta: dict = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.meta is None:
            d.pop('meta', None)
        return d


# ─── arXiv ────────────────────────────────────────────────────────────
# https://arxiv.org/abs/2502.05564
# https://arxiv.org/abs/2502.05564v2
# https://arxiv.org/pdf/2502.05564.pdf
# Modern IDs (YYMM.NNNNN); optional version; optional .pdf extension.
_ARXIV_RE = re.compile(
    r'^https?://(?:www\.)?arxiv\.org/(?:abs|pdf)/'
    r'(?P<id>\d{4}\.\d{4,6}(?:v\d+)?)'
    r'(?:\.pdf)?/?$',
    re.IGNORECASE,
)


def _detect_arxiv(url: str) -> Optional[SmartPasteResult]:
    m = _ARXIV_RE.match(url)
    if not m:
        return None
    return SmartPasteResult(
        kind='arxiv',
        marker=f'<div data-arxiv="{m["id"]}"></div>',
        meta={'id': m['id']},
    )


# ─── GitHub permalink (code snippet) ─────────────────────────────────
# /owner/repo/blob/<sha-or-branch>/path/to/file#L10-L20
# /owner/repo/blob/<sha-or-branch>/path/to/file#L10
# Line anchors are optional — without them we get the full file, which
# is rarely what an author wants; still, legitimate use case.
_GH_PERMALINK_RE = re.compile(
    r'^https?://github\.com/'
    r'(?P<owner>[A-Za-z0-9][A-Za-z0-9._\-]*)/'
    r'(?P<repo>[A-Za-z0-9._\-]+)/'
    r'blob/(?P<ref>[^/]+)/'
    r'(?P<path>[^#?]+?)'
    r'(?:#L(?P<lstart>\d+)(?:-L(?P<lend>\d+))?)?/?$',
    re.IGNORECASE,
)


def _detect_github_permalink(url: str) -> Optional[SmartPasteResult]:
    m = _GH_PERMALINK_RE.match(url)
    if not m:
        return None
    # Marker encodes everything the embeds handler needs to fetch +
    # render. Format: owner/repo@ref:path[#Lstart-Lend]
    owner, repo, ref = m['owner'], m['repo'], m['ref']
    path = m['path']
    lstart = m['lstart']
    lend = m['lend'] or lstart  # single line L10 → range L10-L10
    slug = f'{owner}/{repo}@{ref}:{path}'
    if lstart:
        slug += f'#L{lstart}-L{lend}'
    return SmartPasteResult(
        kind='github_snippet',
        marker=f'<div data-github-snippet="{slug}"></div>',
        meta={
            'owner': owner, 'repo': repo, 'ref': ref, 'path': path,
            'lstart': int(lstart) if lstart else None,
            'lend': int(lend) if lend else None,
        },
    )


# ─── GitHub repo (card) ──────────────────────────────────────────────
# /owner/repo  (trailing slash optional; no /blob, /tree, etc.)
_GH_REPO_RE = re.compile(
    r'^https?://github\.com/'
    r'(?P<owner>[A-Za-z0-9][A-Za-z0-9._\-]*)/'
    r'(?P<repo>[A-Za-z0-9._\-]+)/?$',
    re.IGNORECASE,
)


def _detect_github_repo(url: str) -> Optional[SmartPasteResult]:
    m = _GH_REPO_RE.match(url)
    if not m:
        return None
    path = f'{m["owner"]}/{m["repo"]}'
    return SmartPasteResult(
        kind='github',
        marker=f'<div data-github="{path}"></div>',
        meta={'path': path},
    )


# ─── Wikipedia ──────────────────────────────────────────────────────
_WIKI_RE = re.compile(
    r'^https?://(?P<lang>[a-z]{2,3})\.wikipedia\.org/wiki/'
    r'(?P<article>[^?#]+?)/?$',
    re.IGNORECASE,
)


def _detect_wiki(url: str) -> Optional[SmartPasteResult]:
    import urllib.parse
    m = _WIKI_RE.match(url)
    if not m:
        return None
    # Wikipedia article slugs are URL-encoded (spaces as %20 or _).
    # Store the URL-encoded form since that's what Wikipedia's summary
    # API accepts, but pass a readable title through meta for preview.
    article = m['article']
    readable = urllib.parse.unquote(article).replace('_', ' ')
    return SmartPasteResult(
        kind='wiki',
        marker=f'<div data-wiki="{article}"></div>',
        meta={'article': article, 'title': readable, 'lang': m['lang']},
    )


# ─── Registry ────────────────────────────────────────────────────────
# Priority matters: github_permalink MUST fire before github_repo
# because the permalink regex is a superset.

_DETECTORS: tuple[Callable[[str], Optional[SmartPasteResult]], ...] = (
    _detect_arxiv,
    _detect_github_permalink,   # must come before _detect_github_repo
    _detect_github_repo,
    _detect_wiki,
)


def detect(url: str) -> Optional[SmartPasteResult]:
    """Classify a pasted URL. Returns None when no handler matches
    (caller should fall through to the browser's default paste)."""
    if not url:
        return None
    url = url.strip()
    # Only check http(s) strings; anything else (mailto, file, raw text
    # that happens to contain a URL) isn't our concern.
    if not (url.startswith('http://') or url.startswith('https://')):
        return None
    for det in _DETECTORS:
        result = det(url)
        if result is not None:
            return result
    return None
