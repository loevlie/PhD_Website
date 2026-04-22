"""`<div data-wiki="Transformer_(deep_learning_architecture)"></div>` —
Wikipedia link-preview card.

Uses Wikipedia's free REST summary API. The returned `extract` is a
few plain sentences stripped of markup — ideal for inline previews.
"""
import html as html_lib
import json
import re
import urllib.parse
import urllib.request

from django.core.cache import cache

from . import cache_key, render_card


_RE = r'<div\s+data-wiki=["\']([^"\']+)["\'][^>]*>\s*</div>'

_TTL_OK = 14 * 24 * 60 * 60     # 14 days
_TTL_FAIL = 60 * 60
_LANG = 'en'                    # Hard-code English; easy to parameterize later.


def _fetch(article: str) -> dict | None:
    encoded = urllib.parse.quote(article, safe='')
    url = f'https://{_LANG}.wikipedia.org/api/rest_v1/page/summary/{encoded}'
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'dennisloevlie.com/blog-embed (https://dennisloevlie.com)',
            'Accept': 'application/json',
        })
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception:
        return None
    if data.get('type') == 'disambiguation':
        # Skip — these pages are just link lists, a bad preview.
        return None
    thumb = data.get('thumbnail') or {}
    return {
        'title': data.get('title') or article.replace('_', ' '),
        'extract': (data.get('extract') or '').strip(),
        'url': (data.get('content_urls', {}).get('desktop', {}).get('page')
                or f'https://{_LANG}.wikipedia.org/wiki/{encoded}'),
        'thumbnail': thumb.get('source', ''),
        'thumbnail_w': thumb.get('width'),
        'thumbnail_h': thumb.get('height'),
    }


def _render(m: re.Match) -> str:
    article = m.group(1)
    ck = cache_key('wiki', article)
    data = cache.get(ck)
    if data is None:
        data = _fetch(article)
        cache.set(ck, data or {}, _TTL_OK if data else _TTL_FAIL)

    fallback_href = (
        f'https://{_LANG}.wikipedia.org/wiki/'
        + urllib.parse.quote(article, safe='')
    )
    esc = html_lib.escape
    if not data:
        return render_card(
            f'<div class="embed-card-head"><span class="embed-pill">Wikipedia</span></div>'
            f'<a class="embed-card-title" href="{fallback_href}" target="_blank" rel="noopener">'
            f'{esc(article.replace("_", " "))} →</a>',
            slug_attr='data-wiki',
            slug_val=article,
        )

    # Wikipedia's summary API returns thumbnail dimensions alongside
    # the source URL; passing them through as width/height attrs
    # preallocates the box so text doesn't reflow when the image
    # loads (no Cumulative-Layout-Shift).
    thumb = ''
    if data.get('thumbnail'):
        w = data.get('thumbnail_w') or 120
        h = data.get('thumbnail_h') or 120
        thumb = (
            f'<img class="embed-thumb" loading="lazy" '
            f'src="{esc(data["thumbnail"])}" alt="" '
            f'width="{w}" height="{h}">'
        )
    return render_card(
        f'<div class="embed-card-head">'
        f'<span class="embed-pill">Wikipedia</span></div>'
        f'<div class="embed-card-body">'
        f'<div class="embed-card-text">'
        f'<a class="embed-card-title" href="{esc(data["url"])}" target="_blank" rel="noopener">'
        f'{esc(data["title"])}</a>'
        f'<p class="embed-card-excerpt">{esc(data["extract"])}</p>'
        f'</div>'
        f'{thumb}'
        f'</div>',
        slug_attr='data-wiki',
        slug_val=article,
    )


def register_all(register):
    register(_RE, _render)
