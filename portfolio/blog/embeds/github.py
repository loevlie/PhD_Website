"""`<div data-github="owner/repo"></div>` — rich repo card.

Fetches repo metadata (stars/description/language) from the public
GitHub API, caches 24 h, renders as an `.embed-card`. Unauthed limit
is 60 req/hour per IP — for a personal blog that's plenty.
"""
import html as html_lib
import json
import re
import urllib.request

from django.core.cache import cache

from . import cache_key, render_card, render_error


_RE = r'<div\s+data-github=["\']([A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+)["\'][^>]*>\s*</div>'

_TTL_OK = 24 * 60 * 60     # 24 h — stars drift slowly
_TTL_FAIL = 60 * 60


def _fetch(repo_path: str) -> dict | None:
    url = f'https://api.github.com/repos/{repo_path}'
    try:
        req = urllib.request.Request(url, headers={
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'dennisloevlie.com/blog-embed',
        })
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception:
        return None
    return {
        'name': data.get('name') or repo_path.split('/')[-1],
        'full_name': data.get('full_name') or repo_path,
        'description': (data.get('description') or '').strip(),
        'language': data.get('language') or '',
        'stars': data.get('stargazers_count', 0),
        'forks': data.get('forks_count', 0),
        'url': data.get('html_url') or f'https://github.com/{repo_path}',
    }


def _fmt_stars(n: int) -> str:
    if n >= 1000:
        return f'{n / 1000:.1f}k'
    return str(n)


def _render(m: re.Match) -> str:
    repo_path = m.group(1)
    ck = cache_key('github', repo_path)
    data = cache.get(ck)
    if data is None:
        data = _fetch(repo_path)
        cache.set(ck, data or {}, _TTL_OK if data else _TTL_FAIL)

    href = f'https://github.com/{repo_path}'
    esc = html_lib.escape
    if not data:
        return render_card(
            f'<div class="embed-card-head"><span class="embed-pill">GitHub</span>'
            f'<span class="embed-id">{esc(repo_path)}</span></div>'
            f'<a class="embed-card-title" href="{href}" target="_blank" rel="noopener">{esc(repo_path)} →</a>',
            slug_attr='data-github',
            slug_val=repo_path,
        )

    lang_dot = ''
    if data['language']:
        lang_dot = (
            f'<span class="embed-lang">'
            f'<span class="embed-lang-dot embed-lang-dot--{esc(data["language"].lower())}"></span>'
            f'{esc(data["language"])}</span>'
        )

    return render_card(
        f'<div class="embed-card-head">'
        f'<span class="embed-pill">GitHub</span>'
        f'<span class="embed-id">{esc(repo_path)}</span>'
        f'<span class="embed-stars">★ {_fmt_stars(data["stars"])}</span>'
        f'</div>'
        f'<a class="embed-card-title" href="{href}" target="_blank" rel="noopener">'
        f'{esc(data["full_name"])}</a>'
        + (f'<p class="embed-card-excerpt">{esc(data["description"])}</p>' if data['description'] else '')
        + f'<div class="embed-card-actions">{lang_dot}'
          f'<a href="{href}" target="_blank" rel="noopener">View repo →</a>'
          f'</div>',
        slug_attr='data-github',
        slug_val=repo_path,
    )


def register_all(register):
    register(_RE, _render)
