"""Webmention.io fetcher, factored out of blog_post() for clarity + testability."""
import json
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.cache import cache


def fetch(target_url, limit=25):
    """Fetch incoming webmentions for a URL from the webmention.io public
    API. Cached locally. Returns a list of dicts:
    {author, content, url, type, published}. Empty list on any failure.

    Gated on settings.WEBMENTIONS_ENABLED (env: WEBMENTIONS_ENABLED=1).
    Until the domain is registered at webmention.io, keep this disabled —
    every blog-post view would otherwise eat a 1-2s external round-trip
    waiting for a 404. Flip the env var after registering.

    When enabled: 1s timeout (fast-fail on network hiccups), success
    cached 10 min, failure cached 24h (so one slow failure doesn't
    punish every subsequent visitor)."""
    if not getattr(settings, 'WEBMENTIONS_ENABLED', False):
        return []

    cache_key = f'webmentions:{target_url}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    api = (
        'https://webmention.io/api/mentions.jf2?'
        + urllib.parse.urlencode({'target': target_url, 'per-page': limit, 'sort-dir': 'down'})
    )
    items = []
    ok = False
    try:
        req = urllib.request.Request(api, headers={'User-Agent': 'dennisloevlie.com/webmentions'})
        with urllib.request.urlopen(req, timeout=1) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        for it in data.get('children', []):
            author = it.get('author') or {}
            items.append({
                'type': it.get('wm-property', 'mention'),
                'url': it.get('wm-source') or it.get('url'),
                'author_name': author.get('name', 'Anonymous'),
                'author_url': author.get('url', ''),
                'author_photo': author.get('photo', ''),
                'content': (it.get('content') or {}).get('text', '') if isinstance(it.get('content'), dict) else '',
                'published': it.get('published') or it.get('wm-received'),
            })
        ok = True
    except Exception:
        items = []
    # Hit-path TTL: 10 min. Miss-path TTL: 24h so a flaky/404 response
    # doesn't re-cost us on every visitor for the next 5 minutes.
    cache.set(cache_key, items, 600 if ok else 86400)
    return items
