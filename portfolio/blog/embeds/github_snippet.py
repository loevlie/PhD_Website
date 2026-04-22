"""`<div data-github-snippet="owner/repo@ref:path[#Lstart-Lend]">` —
embed a GitHub code range inline.

At render-time we fetch the raw file via
`raw.githubusercontent.com/<owner>/<repo>/<ref>/<path>`, slice the
requested line range, hand it to Pygments for syntax highlighting,
and wrap the result in a card with a "view on GitHub" footer.

Cache: 7 days for success, 1 hour for failure. The ref is usually a
commit SHA (pinned by the source URL's permalink) so the content
won't drift; a branch name like `main` WILL drift, and we accept
that — the cache TTL caps staleness.
"""
import html as html_lib
import re
import urllib.parse
import urllib.request

from django.core.cache import cache

from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer_for_filename
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound

from . import cache_key, render_card, render_error


_RE = (
    r'<div\s+data-github-snippet=["\']'
    r'(?P<owner>[A-Za-z0-9][A-Za-z0-9._\-]*)/(?P<repo>[A-Za-z0-9._\-]+)'
    r'@(?P<ref>[A-Za-z0-9._\-/]+)'
    r':(?P<path>[^#"\']+?)'
    r'(?:#L(?P<lstart>\d+)-L(?P<lend>\d+))?'
    r'["\'][^>]*>\s*</div\s*>'
)

_TTL_OK = 7 * 24 * 60 * 60
_TTL_FAIL = 60 * 60
_MAX_LINES = 80                      # cap to keep posts readable + fast
_MAX_BYTES = 512 * 1024              # never fetch more than 512 KB


def _fetch(owner: str, repo: str, ref: str, path: str) -> str | None:
    """Retrieve raw file content. Returns None on any failure."""
    url = (
        f'https://raw.githubusercontent.com/{owner}/{repo}/{ref}/'
        + urllib.parse.quote(path)
    )
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'dennisloevlie.com/github-snippet',
            'Accept': 'text/plain, */*;q=0.1',
        })
        with urllib.request.urlopen(req, timeout=4) as resp:
            raw = resp.read(_MAX_BYTES + 1)
            if len(raw) > _MAX_BYTES:
                return None        # file too large
            return raw.decode('utf-8', errors='replace')
    except Exception:
        return None


def _slice_lines(text: str, lstart: int | None, lend: int | None) -> tuple[str, int]:
    """Return (sliced_text, start_line_number_for_display). 1-based."""
    if text is None:
        return '', 1
    lines = text.splitlines()
    if lstart is None:
        # Whole file, but only up to _MAX_LINES to keep the page slim.
        window = lines[:_MAX_LINES]
        return '\n'.join(window), 1
    lstart = max(1, lstart)
    lend = max(lstart, lend or lstart)
    # Cap the range length.
    if lend - lstart + 1 > _MAX_LINES:
        lend = lstart + _MAX_LINES - 1
    window = lines[lstart - 1 : lend]
    return '\n'.join(window), lstart


def _highlight(code: str, path: str, start_line: int) -> str:
    """Pygments HTML. `linenos=table` so line numbers are selectable
    and start from `start_line` (matches the source file)."""
    try:
        lexer = guess_lexer_for_filename(path, code)
    except ClassNotFound:
        try:
            # Fallback by extension only.
            ext = path.rsplit('.', 1)[-1]
            lexer = get_lexer_by_name(ext.lower())
        except ClassNotFound:
            lexer = get_lexer_by_name('text')
    formatter = HtmlFormatter(
        cssclass='highlight github-snippet-hl',
        linenos='inline',
        linenostart=start_line,
    )
    return highlight(code, lexer, formatter)


def _render(m: re.Match) -> str:
    owner, repo = m['owner'], m['repo']
    ref, path = m['ref'], m['path']
    lstart = int(m['lstart']) if m['lstart'] else None
    lend = int(m['lend']) if m['lend'] else None

    ck = cache_key('gh_snippet', f'{owner}/{repo}@{ref}:{path}#L{lstart}-L{lend}')
    cached = cache.get(ck)
    if cached is not None:
        if cached == '':
            return _fallback_card(owner, repo, ref, path, lstart, lend)
        return cached

    raw = _fetch(owner, repo, ref, path)
    if raw is None:
        # Cache the failure so we don't hammer on every render.
        cache.set(ck, '', _TTL_FAIL)
        return _fallback_card(owner, repo, ref, path, lstart, lend)

    code, display_start = _slice_lines(raw, lstart, lend)
    highlighted = _highlight(code, path, display_start)

    esc = html_lib.escape
    perma_href = f'https://github.com/{owner}/{repo}/blob/{ref}/{path}'
    if lstart:
        perma_href += f'#L{lstart}'
        if lend and lend != lstart:
            perma_href += f'-L{lend}'

    line_tag = ''
    if lstart:
        line_tag = f'L{lstart}' + (f'–{lend}' if lend and lend != lstart else '')

    header = (
        f'<div class="gh-snippet-head">'
        f'<span class="embed-pill">GitHub</span>'
        f'<span class="embed-id">{esc(owner)}/{esc(repo)}</span>'
        + (f'<span class="embed-ref">@{esc(ref[:10])}</span>' if ref else '')
        + f'<span class="embed-path">{esc(path)}</span>'
        + (f'<span class="embed-lines">{line_tag}</span>' if line_tag else '')
        + '</div>'
    )
    footer = (
        f'<div class="gh-snippet-foot">'
        f'<a href="{perma_href}" target="_blank" rel="noopener">View on GitHub →</a>'
        f'</div>'
    )
    out = (
        f'<div class="github-snippet" data-github-snippet="{esc(owner)}/{esc(repo)}">'
        f'{header}{highlighted}{footer}'
        f'</div>'
    )
    cache.set(ck, out, _TTL_OK)
    return out


def _fallback_card(owner: str, repo: str, ref: str, path: str,
                    lstart: int | None, lend: int | None) -> str:
    """Minimal card when the fetch fails — still links to the permalink."""
    esc = html_lib.escape
    href = f'https://github.com/{owner}/{repo}/blob/{ref}/{path}'
    if lstart:
        href += f'#L{lstart}'
        if lend and lend != lstart:
            href += f'-L{lend}'
    return render_card(
        f'<div class="embed-card-head">'
        f'<span class="embed-pill">GitHub</span>'
        f'<span class="embed-id">{esc(owner)}/{esc(repo)}</span></div>'
        f'<a class="embed-card-title" href="{href}" target="_blank" rel="noopener">'
        f'{esc(path)} →</a>'
        f'<p class="embed-card-excerpt">Snippet unavailable — open on GitHub.</p>',
        slug_attr='data-github-snippet',
        slug_val=f'{owner}/{repo}',
    )


def register_all(register):
    register(_RE, _render)
