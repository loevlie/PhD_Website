"""HTTP layer for editor-assist features. Kept thin — all real work
lives in `portfolio/editor_assist/`.

Endpoints here share two properties:
  * Staff-only. The editor itself is staff-only; we reuse the same
    auth check (`_can_edit`) so there's exactly one place to change
    if auth policy ever evolves.
  * JSON in / JSON out. Calls happen from the editor JS on a debounced
    keystroke cycle — simplest possible wire format.
"""
import json

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from portfolio.editor_assist import ai_assists as assists_mod
from portfolio.editor_assist import smart_paste as smart_paste_mod
from portfolio.editor_assist import spellcheck as spellcheck_mod


def _can_edit(request) -> bool:
    return request.user.is_authenticated and request.user.is_staff


# AI-assist rate limits are per-user (not per-IP) because the editor
# is staff-only, so identifying the user is trivially cheap and there's
# no PII concern. Limits sit above realistic editing cadence but stop
# a runaway loop in JS from burning through the Anthropic budget.
_ASSIST_PER_MINUTE = 20
_ASSIST_PER_DAY = 300


def _assist_rate_limit(user_id: int) -> tuple[bool, str]:
    """Returns (over_limit, scope). Uses the same cache.add + incr dance
    as the reader-facing /ask endpoint so the semantics match (see
    portfolio/views/ask.py:_rate_limit_hit for the rationale)."""
    min_key = f'assist:user:{user_id}:min'
    day_key = f'assist:user:{user_id}:day'
    cache.add(min_key, 0, timeout=60)
    cache.add(day_key, 0, timeout=60 * 60 * 24)
    try:
        n_min = cache.incr(min_key)
    except ValueError:
        cache.set(min_key, 1, timeout=60)
        n_min = 1
    try:
        n_day = cache.incr(day_key)
    except ValueError:
        cache.set(day_key, 1, timeout=60 * 60 * 24)
        n_day = 1
    if n_min > _ASSIST_PER_MINUTE:
        return True, 'minute'
    if n_day > _ASSIST_PER_DAY:
        return True, 'day'
    return False, ''


@require_POST
def spellcheck(request, slug):
    """POST /blog/<slug>/spellcheck/
       body: {"text": "<markdown>", "extras": ["optional", "words"]}
       returns: {"ok": true, "misspellings": [{word, line, col, offset, suggestions}]}

    Kept slug-scoped (rather than global) so we can eventually persist
    a per-post "ignored words" list if that proves useful. Today the
    slug is just used to confirm the post exists + the caller is a
    legit author."""
    if not _can_edit(request):
        return JsonResponse({'ok': False, 'error': 'unauthorized'}, status=403)

    # Post must exist (or be a draft). We don't load it; just 404
    # early on a mistyped slug so callers see a clean error.
    from portfolio.models import Post
    get_object_or_404(Post, slug=slug)

    try:
        payload = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'bad json'}, status=400)

    text = payload.get('text', '') or ''
    extras = payload.get('extras', []) or []
    if not isinstance(text, str) or not isinstance(extras, list):
        return JsonResponse({'ok': False, 'error': 'bad types'}, status=400)

    # Hard cap on input size so a runaway paste doesn't hammer CPU.
    # 200k chars ≈ a 33k-word post; generous headroom.
    if len(text) > 200_000:
        return JsonResponse({'ok': False, 'error': 'text too large'}, status=413)

    misspellings = spellcheck_mod.check_text(text, extra_words=extras)
    return JsonResponse({
        'ok': True,
        'count': len(misspellings),
        'misspellings': [m.to_dict() for m in misspellings],
    })


@require_POST
def check_word(request):
    """POST /editor/check-word/
       body: {"word": "tabicl"}
       returns: {"known": true|false}

    Cheap utility the editor uses when a user clicks "Add to
    dictionary" to confirm the word is now accepted (i.e. they've
    already appended it to their personal extras)."""
    if not _can_edit(request):
        return JsonResponse({'ok': False, 'error': 'unauthorized'}, status=403)
    try:
        payload = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'bad json'}, status=400)
    word = (payload.get('word') or '').strip()
    extras = payload.get('extras', []) or []
    if not word:
        return JsonResponse({'ok': False, 'error': 'no word'}, status=400)
    return JsonResponse({'ok': True, 'known': spellcheck_mod.is_known(word, extras=extras)})


@require_POST
def smart_paste(request):
    """POST /editor/smart-paste/
       body: {"url": "<url>"}
       returns: {"ok": true, "match": {kind, marker, meta} | null}

    Called from the editor JS on every `paste` that contains exactly
    one URL. Server-side detection keeps the regex patterns in one
    place (see portfolio/editor_assist/smart_paste.py) instead of
    duplicating them into JS, where they'd drift.

    Latency isn't critical — the paste flow IS blocked on the
    response, but a single-URL check is <5ms on the server and the
    JS falls through to default paste on any failure."""
    if not _can_edit(request):
        return JsonResponse({'ok': False, 'error': 'unauthorized'}, status=403)
    try:
        payload = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'bad json'}, status=400)
    url = (payload.get('url') or '').strip()
    if not url:
        return JsonResponse({'ok': False, 'error': 'no url'}, status=400)
    # Bound input size so a pasted megabyte of text doesn't choke us.
    if len(url) > 2048:
        return JsonResponse({'ok': False, 'error': 'url too long'}, status=413)
    result = smart_paste_mod.detect(url)
    return JsonResponse({
        'ok': True,
        'match': result.to_dict() if result else None,
    })


@require_POST
def assist(request, slug, action):
    """POST /blog/<slug>/assist/<action>/
       body varies by action (see portfolio.editor_assist.ai_assists.ACTIONS)
       returns: {"ok": true, "result": <str | list[str]>}

    Thin wrapper around ai_assists.run. We handle auth, rate-limiting,
    JSON parsing, and status-code mapping; everything else — prompt
    building, the Anthropic call, response parsing — lives in the
    module so the logic is unit-testable without hitting the network."""
    if not _can_edit(request):
        return JsonResponse({'ok': False, 'error': 'unauthorized'}, status=403)

    from portfolio.models import Post
    get_object_or_404(Post, slug=slug)

    try:
        payload = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'bad json'}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({'ok': False, 'error': 'bad payload'}, status=400)

    over, scope = _assist_rate_limit(request.user.id)
    if over:
        return JsonResponse(
            {'ok': False, 'error': 'rate_limited', 'scope': scope},
            status=429,
        )

    try:
        result = assists_mod.run(action, payload)
    except assists_mod.AssistUnknown:
        return JsonResponse({'ok': False, 'error': 'unknown action'}, status=400)
    except assists_mod.AssistBadInput as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    except assists_mod.AssistUnavailable:
        return JsonResponse({'ok': False, 'error': 'offline'}, status=503)
    except assists_mod.AssistError:
        # Don't leak the upstream exception text — it can contain quota
        # details, partial key fragments in some SDK errors, etc.
        return JsonResponse({'ok': False, 'error': 'upstream_error'}, status=502)

    return JsonResponse({'ok': True, 'action': action, 'result': result})
