"""HTTP delivery middleware: response compression + cache headers.

Ordering contract (see MIDDLEWARE in settings.py):

    SecurityMiddleware
    WhiteNoiseMiddleware          static files short-circuit here; they are
                                  served pre-compressed (brotli/gzip twins)
                                  with their own immutable cache headers
    NoTransformGZipMiddleware     compresses dynamic HTML/JSON
    ConditionalGetMiddleware      ETags computed on the UNCOMPRESSED body —
                                  Django's gzip adds random padding (BREACH
                                  mitigation), so gzipped bytes are
                                  non-deterministic and must not be hashed
    ... session/csrf/auth ...
    CacheHeadersMiddleware        listed last so its process_response runs
                                  FIRST, before ConditionalGet decides
                                  whether to ETag and before GZip runs

BREACH note: enabling gzip on pages containing the CSRF token is safe on
Django ≥4.2 — GZipMiddleware injects random-length filename padding
("Heal the BREACH") and CSRF tokens are masked per-request.
"""
from django.conf import settings
from django.middleware.gzip import GZipMiddleware


class NoTransformGZipMiddleware(GZipMiddleware):
    """GZipMiddleware that honors `Cache-Control: no-transform`.

    The /blog/<slug>/ask/ SSE stream sets `no-cache, no-transform`
    (ask.py) — wrapping it in gzip would buffer the event stream and
    break incremental delivery.
    """

    def process_response(self, request, response):
        if 'no-transform' in response.get('Cache-Control', ''):
            return response
        return super().process_response(request, response)


class CacheHeadersMiddleware:
    """Default Cache-Control for views that don't set their own.

    Anonymous requests (no session cookie) get a short public TTL with
    stale-while-revalidate: post_save signals invalidate the server-side
    locmem cache but can never purge a browser/CDN cache, so the TTL is
    what bounds publish-to-visible latency for anonymous readers.

    Requests carrying a session cookie get `private, no-cache`: editors
    and collaborators always revalidate (ConditionalGet's ETag still
    gives them 304s), and the response can never land in a shared cache —
    Cloudflare ignores `Vary: Cookie`, so a `public` staff render could
    otherwise be served to anonymous visitors.

    The session-cookie check deliberately avoids touching request.user:
    resolving the user forces session access and adds `Vary: Cookie` to
    every response, fragmenting downstream caches.
    """

    ANON_VALUE = 'public, max-age=120, stale-while-revalidate=600'
    SESSION_VALUE = 'private, no-cache'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (
            request.method in ('GET', 'HEAD')
            and response.status_code == 200
            and not response.has_header('Cache-Control')
            and not getattr(response, 'streaming', False)
        ):
            # CSRF_COOKIE_NEEDS_UPDATE: the view rendered {% csrf_token %}
            # for an anonymous visitor (e.g. /accounts/signup/) — the
            # response will carry a per-user Set-Cookie that must never
            # land in a shared cache. CsrfViewMiddleware sets the cookie
            # AFTER us in the response phase, so the META flag is the
            # only reliable signal at this position.
            if (
                settings.SESSION_COOKIE_NAME in request.COOKIES
                or settings.CSRF_COOKIE_NAME in request.COOKIES
                or request.META.get('CSRF_COOKIE_NEEDS_UPDATE')
            ):
                response['Cache-Control'] = self.SESSION_VALUE
            else:
                response['Cache-Control'] = self.ANON_VALUE
        return response
