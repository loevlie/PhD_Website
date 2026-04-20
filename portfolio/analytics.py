"""First-party privacy analytics.

Design choices:
- No cookies beyond a 30-min session cookie `sid`. No persistent user ID.
- IPs are hashed with a per-day salt, then discarded. Yesterday's hash
  can't be re-derived once today's salt rotates.
- Respect Do Not Track (DNT: 1) and Sec-GPC (Global Privacy Control).
- Skip common bot UAs server-side so the dashboard isn't polluted.
- No third-party requests. No fingerprinting. No PII.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import timedelta

from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


BOT_RE = re.compile(
    r'(bot|crawl|spider|slurp|facebookexternalhit|embedly|preview|scraper|'
    r'whatsapp|telegram|pingdom|uptimerobot|lighthouse|headlesschrome|playwright|'
    r'curl|wget|python-requests|postman|insomnia)',
    re.IGNORECASE,
)

SESSION_COOKIE = 'sid'
SESSION_TTL = 60 * 30  # 30 minutes idle


def _classify_device(ua: str) -> str:
    ua_l = ua.lower()
    if any(t in ua_l for t in ('ipad', 'tablet')):
        return 'tablet'
    if any(t in ua_l for t in ('android', 'iphone', 'mobile')):
        return 'phone'
    return 'desktop'


def _classify_browser(ua: str) -> str:
    ua_l = ua.lower()
    if 'edg/' in ua_l:
        return 'Edge'
    if 'chrome/' in ua_l and 'safari/' in ua_l:
        return 'Chrome'
    if 'firefox/' in ua_l:
        return 'Firefox'
    if 'safari/' in ua_l:
        return 'Safari'
    return 'Other'


def _hash_ip(request) -> str:
    """Return an HMAC-like hash of the client IP using today's rotating
    salt. Returns '' if no IP found. Accepts X-Forwarded-For for
    reverse-proxied prod; falls back to REMOTE_ADDR."""
    from portfolio.models import DailySalt
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    ip = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')
    if not ip:
        return ''
    salt = DailySalt.for_today()
    return hashlib.sha256(f'{salt}|{ip}'.encode()).hexdigest()[:32]


def _session_id(request) -> tuple[str, bool]:
    """Return (sid, is_new). Rotates on TTL expiry via the beacon's
    `update` endpoint — we just trust the cookie until it's stale."""
    sid = request.COOKIES.get(SESSION_COOKIE)
    if not sid or len(sid) < 16:
        return secrets.token_hex(12), True
    return sid, False


def _is_bot(ua: str) -> bool:
    return bool(BOT_RE.search(ua or ''))


def _respects_dnt(request) -> bool:
    """Return True if the client has signaled they do NOT want tracking.
    We honor DNT and Global Privacy Control."""
    if request.META.get('HTTP_DNT') == '1':
        return True
    if request.META.get('HTTP_SEC_GPC') == '1':
        return True
    return False


def _post_slug_from_path(path: str) -> str:
    # /blog/<slug>/ → slug; everything else → ''
    m = re.fullmatch(r'/blog/([^/]+)/?', path)
    return m.group(1) if m else ''


@csrf_exempt
@require_POST
def beacon_pageview(request):
    """Beacon endpoint for pageview records. CSRF-exempt because
    navigator.sendBeacon can't include CSRF tokens easily, and this
    endpoint only writes a single bounded row per request. No authentication.

    Body (JSON or multipart): { path, referrer, viewport_w, viewport_h }
    Response: 204 No Content (or 200 with sid cookie on first view).
    """
    from portfolio.models import Pageview

    if _respects_dnt(request):
        return HttpResponse(status=204)

    ua = request.META.get('HTTP_USER_AGENT', '')
    if _is_bot(ua):
        return HttpResponse(status=204)

    # Payload parsing — accept both JSON and form-encoded (sendBeacon
    # usually sends form-encoded FormData).
    try:
        if request.content_type and 'json' in request.content_type:
            data = json.loads(request.body.decode('utf-8') or '{}')
        else:
            data = {k: request.POST.get(k, '') for k in ('path', 'referrer', 'viewport_w', 'viewport_h')}
    except (ValueError, json.JSONDecodeError):
        data = {}

    path = (data.get('path') or '/')[:500]
    # Don't track the admin, insights pages, or the beacon itself
    if path.startswith(('/admin/', '/a/', '/site/insights')):
        return HttpResponse(status=204)

    referrer = (data.get('referrer') or '')[:500]
    # Strip own-domain referrers for cleaner "top referrers" view
    host = request.get_host()
    if host and host in referrer:
        referrer = ''

    try:
        vw = int(data.get('viewport_w') or 0)
        vh = int(data.get('viewport_h') or 0)
    except (ValueError, TypeError):
        vw = vh = 0
    vw = min(vw, 65000)
    vh = min(vh, 65000)

    sid, is_new = _session_id(request)
    pv = Pageview.objects.create(
        path=path,
        referrer=referrer,
        country=request.META.get('HTTP_CF_IPCOUNTRY', '')[:2],
        device=_classify_device(ua),
        browser=_classify_browser(ua),
        viewport_w=vw,
        viewport_h=vh,
        session_id=sid,
        ip_hash=_hash_ip(request),
        is_bot=False,
        post_slug=_post_slug_from_path(path),
    )
    response = JsonResponse({'id': pv.id}) if is_new else HttpResponse(status=204)
    if is_new:
        response.set_cookie(
            SESSION_COOKIE, sid,
            max_age=SESSION_TTL,
            httponly=True,
            samesite='Lax',
            secure=not request.is_secure() is False,  # secure in prod
        )
    return response


@csrf_exempt
@require_POST
def beacon_update(request):
    """Second beacon, sent on `beforeunload` with scroll depth + dwell.
    Body: { id, scroll_depth (0-100), dwell_ms }
    Returns 204. Silent no-op if id missing or row doesn't exist."""
    from portfolio.models import Pageview

    if _respects_dnt(request):
        return HttpResponse(status=204)

    try:
        if request.content_type and 'json' in request.content_type:
            data = json.loads(request.body.decode('utf-8') or '{}')
        else:
            data = {k: request.POST.get(k, '') for k in ('id', 'scroll_depth', 'dwell_ms')}
    except (ValueError, json.JSONDecodeError):
        data = {}

    try:
        pv_id = int(data.get('id') or 0)
        scroll = max(0, min(100, int(data.get('scroll_depth') or 0)))
        dwell = max(0, min(2 ** 31 - 1, int(data.get('dwell_ms') or 0)))
    except (ValueError, TypeError):
        return HttpResponse(status=204)

    if not pv_id:
        return HttpResponse(status=204)

    try:
        Pageview.objects.filter(id=pv_id).update(scroll_depth=scroll, dwell_ms=dwell)
    except Exception:
        pass
    return HttpResponse(status=204)
