"""HTTP layer for editor-assist features. Kept thin — all real work
lives in `portfolio/editor_assist/`.

Endpoints here share two properties:
  * Staff-only. The editor itself is staff-only; we reuse the same
    auth check (`_can_edit`) so there's exactly one place to change
    if auth policy ever evolves.
  * JSON in / JSON out. Calls happen from the editor JS on a debounced
    keystroke cycle — simplest possible wire format.

Today: /blog/<slug>/spellcheck/ (POST).
Room to grow: /blog/<slug>/assist/<action>/ for Tier 2 AI assists.
"""
import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from portfolio.editor_assist import spellcheck as spellcheck_mod
from portfolio.editor_assist import smart_paste as smart_paste_mod


def _can_edit(request) -> bool:
    return request.user.is_authenticated and request.user.is_staff


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
