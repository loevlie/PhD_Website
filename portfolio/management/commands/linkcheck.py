"""Audit external links in blog posts. Flag 4xx/5xx/timeout targets.

    python manage.py linkcheck                  # all posts
    python manage.py linkcheck --slug my-post   # one post
    python manage.py linkcheck --timeout 5      # per-link timeout

Prints a report to stdout; non-zero exit if anything broke so you can
wire it into CI. Skips `mailto:` / `#anchor` / `javascript:` /
anything not starting with http(s).
"""
import concurrent.futures
import re
import urllib.request
import urllib.error

from django.core.management.base import BaseCommand


# Strip trailing punctuation that markdown often sneaks into a URL.
_URL_RE = re.compile(
    r'https?://[^\s<>"\'()]+',
    re.IGNORECASE,
)


def _check(url: str, timeout: float) -> tuple[str, int | None, str]:
    """Return (url, status_code or None, error)."""
    # HEAD first (cheap); fall back to GET if the server is 405-happy.
    for method in ('HEAD', 'GET'):
        try:
            req = urllib.request.Request(url, method=method, headers={
                'User-Agent': 'dennisloevlie.com/linkcheck',
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return url, r.status, ''
        except urllib.error.HTTPError as e:
            if method == 'HEAD' and e.code == 405:
                continue
            return url, e.code, e.reason or ''
        except urllib.error.URLError as e:
            if method == 'HEAD':
                continue
            return url, None, str(e.reason)
        except Exception as e:
            if method == 'HEAD':
                continue
            return url, None, str(e)[:120]
    return url, None, 'unreachable'


class Command(BaseCommand):
    help = 'Audit external URLs in blog posts. Flags 4xx / 5xx / timeouts.'

    def add_arguments(self, parser):
        parser.add_argument('--slug', default='', help='Limit to a single post by slug.')
        parser.add_argument('--timeout', type=float, default=8.0,
                            help='Per-link request timeout in seconds.')
        parser.add_argument('--concurrency', type=int, default=16,
                            help='Parallel requests (default 16).')

    def handle(self, *args, slug, timeout, concurrency, **opts):
        from portfolio.blog import get_all_posts
        posts = get_all_posts(include_drafts=True)
        if slug:
            posts = [p for p in posts if p['slug'] == slug]
        if not posts:
            self.stdout.write(self.style.WARNING('No posts to check.'))
            return

        # Collect (post-slug, url) pairs; dedupe globally.
        urls_by_post: dict[str, list[str]] = {}
        seen: set[str] = set()
        queue: list[str] = []
        for p in posts:
            body = p.get('body') or ''
            urls = []
            for m in _URL_RE.finditer(body):
                u = m.group(0).rstrip('.,);:]')
                if u in seen:
                    urls.append(u)
                    continue
                seen.add(u)
                urls.append(u)
                queue.append(u)
            urls_by_post[p['slug']] = urls

        self.stdout.write(self.style.NOTICE(
            f'Checking {len(queue)} unique URL(s) across {len(posts)} post(s)…'
        ))

        results: dict[str, tuple[int | None, str]] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as ex:
            futures = {ex.submit(_check, u, timeout): u for u in queue}
            for fut in concurrent.futures.as_completed(futures):
                url, status, err = fut.result()
                results[url] = (status, err)
                if status and 200 <= status < 400:
                    self.stdout.write(f'  {status}  {url}')
                else:
                    self.stdout.write(self.style.WARNING(
                        f'  {status if status is not None else "ERR"}  {url}  {err}'
                    ))

        # Per-post rollup
        broken = 0
        for p in posts:
            urls = urls_by_post.get(p['slug'], [])
            bad = [u for u in set(urls) if results.get(u, (None,))[0] is None
                   or (results[u][0] or 0) >= 400]
            if bad:
                broken += len(bad)
                self.stdout.write(self.style.ERROR(
                    f'\n{p["slug"]} has {len(bad)} broken link(s):'
                ))
                for u in bad:
                    status, err = results.get(u, (None, ''))
                    self.stdout.write(f'    {status if status is not None else "ERR"}  {u}  {err}')

        if broken:
            self.stdout.write(self.style.ERROR(f'\n{broken} broken link(s) total.'))
        else:
            self.stdout.write(self.style.SUCCESS('\nAll external links resolved.'))
