"""`GET /embed/card/?url=<url>` — rendered embed HTML for a URL.

Called by link-hover.js when the reader hovers over an external link
in a blog post. For arxiv / github / wiki URLs, we return the same
rich card the `<div data-*>` markers expand to at render time; for
anything else we return 204 so the client falls back to the plain
hostname tooltip.

Why a separate endpoint rather than pre-rendering every link's card
into the page:
  * Cheap for most links — readers only open a few cards per post.
  * Metadata-fetching embeds (arxiv / github / wiki) already hit the
    network with their own cache; a card fetched on hover is an
    amortised cost of ~one network call per distinct URL, capped by
    the embed cache (hours → days).
  * Keeps the rendered HTML of the main post compact and static.

Public endpoint (readers hit it), rate-limited per IP to stop a scraper
from fan-out-fetching every URL on the site.
"""
from __future__ import annotations

import hashlib

from django.core.cache import cache
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from portfolio.editor_assist import smart_paste as smart_paste_mod
from portfolio.blog.embeds import expand_embeds


# Generous — a post has at most a few dozen unique outbound links, and
# the embeds cache is the expensive layer. This rate limit just stops
# someone scripting /embed/card/ as a URL-metadata scraper.
_PER_MIN = 60
_PER_DAY = 1000

# Only these kinds get a rich card. github_snippet lands in posts via
# explicit markers, not inline prose, so we don't proxy it here.
_ALLOWED_KINDS = {'arxiv', 'github', 'wiki'}


def _client_ip_key(request) -> str:
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    ip = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')
    return hashlib.sha256(ip.encode()).hexdigest()[:16] if ip else 'anon'


def _rate_limit(ip_key: str) -> bool:
    """Returns True if the caller is over the limit."""
    m_key, d_key = f'card:{ip_key}:min', f'card:{ip_key}:day'
    cache.add(m_key, 0, timeout=60)
    cache.add(d_key, 0, timeout=60 * 60 * 24)
    try:
        n_m = cache.incr(m_key)
    except ValueError:
        cache.set(m_key, 1, timeout=60); n_m = 1
    try:
        n_d = cache.incr(d_key)
    except ValueError:
        cache.set(d_key, 1, timeout=60 * 60 * 24); n_d = 1
    return n_m > _PER_MIN or n_d > _PER_DAY


@csrf_exempt
@require_http_methods(['GET'])
def embed_card(request):
    url = (request.GET.get('url') or '').strip()
    if not url or len(url) > 2048:
        return HttpResponse(status=400)

    if _rate_limit(_client_ip_key(request)):
        return HttpResponse(status=429)

    result = smart_paste_mod.detect(url)
    if not result or result.kind not in _ALLOWED_KINDS:
        # Empty body with 204 tells the client: no rich card, fall back
        # to the plain hover tooltip.
        return HttpResponse(status=204)

    html = expand_embeds(result.marker)
    resp = HttpResponse(html, content_type='text/html; charset=utf-8')
    # Allow short browser caching — the underlying metadata cache is
    # hours-to-days, so a minute at the edge just cuts round-trips when
    # a reader hovers the same link twice.
    resp['Cache-Control'] = 'private, max-age=60'
    return resp
