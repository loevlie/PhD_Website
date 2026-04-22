"""`<div data-arxiv="2502.05564"></div>` — rich paper card.

Fetches arXiv metadata (title / authors / abstract / pdf) via the
public Atom API, caches it for 30 days, renders as an `.embed-card`.
On network failure renders a minimal card with just the id linking
to arxiv.org — never breaks the post.
"""
import html as html_lib
import re
import urllib.parse
import urllib.request
from xml.etree import ElementTree as ET

from django.core.cache import cache

from . import cache_key, render_card, render_error


_RE = r'<div\s+data-arxiv=["\']([0-9]{4}\.[0-9]{4,6}(?:v[0-9]+)?)["\'][^>]*>\s*</div>'

_TTL_OK = 30 * 24 * 60 * 60       # 30 days for a successful hit
_TTL_FAIL = 60 * 60               # 1 hour for a failure (retry later)
_ATOM_NS = '{http://www.w3.org/2005/Atom}'


def _fetch(arxiv_id: str) -> dict | None:
    """Hit the arXiv Atom API once. Returns parsed dict or None on
    any failure (timeout, 4xx, malformed XML)."""
    url = (
        'https://export.arxiv.org/api/query?'
        + urllib.parse.urlencode({'id_list': arxiv_id, 'max_results': 1})
    )
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'dennisloevlie.com/blog-embed',
        })
        with urllib.request.urlopen(req, timeout=3) as resp:
            raw = resp.read()
    except Exception:
        return None
    try:
        root = ET.fromstring(raw)
        entry = root.find(f'{_ATOM_NS}entry')
        if entry is None:
            return None
        title = (entry.findtext(f'{_ATOM_NS}title') or '').strip()
        summary = (entry.findtext(f'{_ATOM_NS}summary') or '').strip()
        authors = [
            (a.findtext(f'{_ATOM_NS}name') or '').strip()
            for a in entry.findall(f'{_ATOM_NS}author')
        ]
        published = (entry.findtext(f'{_ATOM_NS}published') or '').strip()
        return {
            'title': title,
            'summary': summary,
            'authors': [a for a in authors if a],
            'year': published[:4] if published else '',
        }
    except ET.ParseError:
        return None


def _render(m: re.Match) -> str:
    arxiv_id = m.group(1)
    ck = cache_key('arxiv', arxiv_id)
    data = cache.get(ck)
    if data is None:
        data = _fetch(arxiv_id)
        cache.set(ck, data or {}, _TTL_OK if data else _TTL_FAIL)

    href_abs = f'https://arxiv.org/abs/{arxiv_id}'
    href_pdf = f'https://arxiv.org/pdf/{arxiv_id}'

    if not data:
        # Minimal fallback so the post still reads:
        return render_card(
            f'<div class="embed-card-head"><span class="embed-pill">arXiv</span>'
            f'<span class="embed-id">{html_lib.escape(arxiv_id)}</span></div>'
            f'<a class="embed-card-title" href="{href_abs}" target="_blank" rel="noopener">'
            f'arXiv:{html_lib.escape(arxiv_id)} →</a>',
            slug_attr='data-arxiv',
            slug_val=arxiv_id,
        )

    esc = html_lib.escape
    authors_line = ', '.join(data['authors'][:3])
    if len(data['authors']) > 3:
        authors_line += f' + {len(data["authors"]) - 3} more'
    # Abstract: keep it short; the full thing bloats the post. First
    # 2 sentences ≈ the gist. `. ` split is crude but adequate.
    sentences = re.split(r'(?<=[.!?])\s+', data['summary'])
    short = ' '.join(sentences[:2])
    if len(sentences) > 2:
        short += ' …'

    return render_card(
        f'<div class="embed-card-head">'
        f'<span class="embed-pill">arXiv</span>'
        f'<span class="embed-id">{esc(arxiv_id)}</span>'
        f'{("<span class=embed-year>" + esc(data["year"]) + "</span>") if data["year"] else ""}'
        f'</div>'
        f'<a class="embed-card-title" href="{href_abs}" target="_blank" rel="noopener">'
        f'{esc(data["title"])}</a>'
        f'<p class="embed-card-authors">{esc(authors_line)}</p>'
        f'<p class="embed-card-excerpt">{esc(short)}</p>'
        f'<div class="embed-card-actions">'
        f'<a href="{href_abs}" target="_blank" rel="noopener">Abstract →</a>'
        f'<a href="{href_pdf}" target="_blank" rel="noopener">PDF</a>'
        f'</div>',
        slug_attr='data-arxiv',
        slug_val=arxiv_id,
    )


def register_all(register):
    register(_RE, _render)
