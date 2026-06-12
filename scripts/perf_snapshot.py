"""Snapshot site performance for before/after comparison.

Usage:
    python3 manage.py runserver 8123  (in another shell)
    python3 scripts/perf_snapshot.py <label> [base_url]

Writes docs/perf-snapshots/<label>.json and prints a summary table.
Measures, per page: HTML wire bytes (with Accept-Encoding: gzip), median
TTFB-ish latency over 5 requests, Cache-Control / ETag / Content-Encoding
headers, script/stylesheet tag counts, and the summed raw + gzipped size
of every referenced local /static/ asset. Also inventories the key static
files the perf pass targets.

Best-effort editor measurement: if EDITOR_USER/EDITOR_PASS env vars are
set, logs in via /accounts/login/ and times /blog/<slug>/edit/.
"""
import gzip
import http.cookiejar
import io
import json
import os
import re
import statistics
import sys
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_SRC = BASE_DIR / 'portfolio' / 'static'

PAGES = [
    ('home', '/'),
    ('blog_list', '/blog/'),
    ('post_plain', '/blog/perf-plain-post/'),
    ('post_math_code', '/blog/multiple-instance-learning/'),
    ('post_math_only', '/blog/embed-showcase/'),
    ('reading', '/reading/'),
    ('demo_ff', '/demos/frozen-forecaster/'),
    ('tags', '/tags/'),
]

KEY_ASSETS = [
    'portfolio/images/og-cover.png',
    'portfolio/images/og-cover.jpg',
    'portfolio/images/hero-video.mp4',
    'portfolio/images/profile.png',
    'portfolio/data/frozen-forecaster/atlas.png',
    'portfolio/data/frozen-forecaster/atlas.webp',
    'portfolio/data/frozen-forecaster/configs.json',
    'portfolio/vendor/katex/katex.min.js',
    'portfolio/vendor/katex/katex.min.css',
    'portfolio/js/frozen-forecaster.js',
    'portfolio/js/main.js',
]

KEY_DIRS = [
    'portfolio/css',
    'portfolio/fonts',
    'portfolio/images',
    'portfolio/images/og',
    'portfolio/data/frozen-forecaster',
]


def fetch(opener, url, n=5):
    """Return (median_ms, body_bytes, headers) for GET url."""
    timings = []
    body = b''
    headers = {}
    req_headers = {'Accept-Encoding': 'gzip', 'User-Agent': 'perf-snapshot'}
    # warmup (caches, connection)
    try:
        opener.open(urllib.request.Request(url, headers=req_headers), timeout=60).read()
    except Exception as e:
        return None, b'', {'error': str(e)}
    for _ in range(n):
        t0 = time.perf_counter()
        with opener.open(urllib.request.Request(url, headers=req_headers), timeout=60) as r:
            body = r.read()
            headers = {k.lower(): v for k, v in r.headers.items()}
        timings.append((time.perf_counter() - t0) * 1000)
    return statistics.median(timings), body, headers


def gz_size(data: bytes) -> int:
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb', compresslevel=6) as f:
        f.write(data)
    return buf.tell()


def page_assets(html: str):
    """Local static assets referenced by the page (scripts, stylesheets,
    preloads). Returns (script_count, css_count, [paths])."""
    scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
    styles = re.findall(r'<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"', html)
    styles += re.findall(r'<link[^>]+href="([^"]+)"[^>]+rel="stylesheet"', html)
    preloads = re.findall(r'<link[^>]+rel="preload"[^>]+href="([^"]+)"', html)
    local = []
    for u in scripts + styles + preloads:
        if u.startswith('/static/'):
            local.append(u[len('/static/'):].split('?')[0])
    return len(scripts), len(styles), sorted(set(local))


def asset_sizes(paths):
    total_raw = total_gz = 0
    missing = []
    for p in paths:
        f = STATIC_SRC / p
        if not f.exists():
            missing.append(p)
            continue
        data = f.read_bytes()
        total_raw += len(data)
        if f.suffix in ('.js', '.css', '.json', '.svg', '.html'):
            total_gz += gz_size(data)
        else:
            total_gz += len(data)
    return total_raw, total_gz, missing


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else 'snapshot'
    base = (sys.argv[2] if len(sys.argv) > 2 else 'http://127.0.0.1:8123').rstrip('/')

    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    snap = {'label': label, 'base': base, 'ts': time.strftime('%Y-%m-%d %H:%M:%S'), 'pages': {}, 'assets': {}, 'dirs': {}}

    for name, path in PAGES:
        ms, body, headers = fetch(opener, base + path)
        if ms is None:
            snap['pages'][name] = {'path': path, 'error': headers.get('error', 'fetch failed')}
            print(f'{name:16s} {path:42s} ERROR {headers.get("error", "")[:60]}')
            continue
        enc = headers.get('content-encoding', 'identity')
        html = body if enc == 'identity' else gzip.decompress(body)
        html_text = html.decode('utf-8', 'replace')
        n_scripts, n_css, assets = page_assets(html_text)
        a_raw, a_gz, missing = asset_sizes(assets)
        snap['pages'][name] = {
            'path': path,
            'median_ms': round(ms, 1),
            'html_wire_bytes': len(body),
            'html_raw_bytes': len(html),
            'content_encoding': enc,
            'cache_control': headers.get('cache-control', '—'),
            'etag': bool(headers.get('etag')),
            'script_tags': n_scripts,
            'stylesheet_tags': n_css,
            'referenced_static_assets': assets,
            'assets_raw_bytes': a_raw,
            'assets_gz_bytes': a_gz,
            'assets_missing': missing,
        }
        print(f'{name:16s} {path:42s} {ms:7.1f}ms  html {len(body)/1024:7.1f}KB wire ({enc}), '
              f'{n_scripts} scripts/{n_css} css, static refs {a_raw/1024:8.1f}KB raw / {a_gz/1024:8.1f}KB gz')

    # Optional logged-in editor timing
    user, pw = os.environ.get('EDITOR_USER'), os.environ.get('EDITOR_PASS')
    if user and pw:
        try:
            login_url = base + '/accounts/login/'
            with opener.open(login_url, timeout=30) as r:
                page = r.read().decode('utf-8', 'replace')
            m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page)
            data = urllib.parse.urlencode({
                'csrfmiddlewaretoken': m.group(1), 'username': user, 'password': pw,
            }).encode()
            req = urllib.request.Request(login_url, data=data, headers={'Referer': login_url})
            opener.open(req, timeout=30).read()
            ms, body, headers = fetch(opener, base + '/blog/embed-showcase/edit/')
            if ms is None:
                raise RuntimeError(headers.get('error', 'fetch failed'))
            snap['pages']['editor'] = {
                'path': '/blog/embed-showcase/edit/', 'median_ms': round(ms, 1),
                'html_wire_bytes': len(body),
                'content_encoding': headers.get('content-encoding', 'identity'),
                'cache_control': headers.get('cache-control', '—'),
            }
            print(f'{"editor":16s} /blog/embed-showcase/edit/                 {ms:7.1f}ms  html {len(body)/1024:7.1f}KB wire')
        except Exception as e:
            print(f'editor timing skipped: {e}')

    for p in KEY_ASSETS:
        f = STATIC_SRC / p
        snap['assets'][p] = f.stat().st_size if f.exists() else None
    for d in KEY_DIRS:
        dd = STATIC_SRC / d
        if dd.exists():
            snap['dirs'][d] = sum(f.stat().st_size for f in dd.rglob('*') if f.is_file())

    out = BASE_DIR / 'docs' / 'perf-snapshots'
    out.mkdir(parents=True, exist_ok=True)
    (out / f'{label}.json').write_text(json.dumps(snap, indent=2))
    print(f'\nwrote docs/perf-snapshots/{label}.json')


if __name__ == '__main__':
    import urllib.parse  # noqa: E402  (used in login flow)
    main()
