"""`POST /blog/<slug>/ask/` — reader-facing Q&A chat grounded on the
post body.

Proxies to Anthropic Claude Haiku so the API key never reaches the
browser, streams the answer back as SSE so the bubble in the reader
fills in a token at a time, and rate-limits per-IP so a drive-by can't
burn the budget.

Why SSE over NDJSON:
- Built-in browser `EventSource` not strictly needed (we parse the
  stream manually in JS), but SSE is dead simple: one `data: {json}\n\n`
  frame per event, heartbeat-free, easy to eyeball in curl.
- NDJSON would work too, but SSE is the de-facto LLM streaming format
  and matches what the anthropic SDK emits out of the box.

Graceful degradation:
- `ANTHROPIC_API_KEY` unset → HTTP 503 with `{"error": "chat_offline"}`.
  The client JS reads that and shows a polite "chat offline" message
  in the bubble. Keeping this out of the frontend means the key leak
  surface is exactly one env-var on one server.
"""
from __future__ import annotations

import hashlib
import json
import os

from django.core.cache import cache
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from portfolio.blog import get_post


# ── Rate limiting ────────────────────────────────────────────────────
# Per-IP caps chosen to let a genuinely curious reader converse for a
# while (20 questions / day) without letting a script burn through the
# Anthropic budget in seconds (3 / minute burst).
RATE_LIMIT_PER_MINUTE = 3
RATE_LIMIT_PER_DAY = 20

# Haiku is cheap, fast, and plenty good for grounded post Q&A. Upgrade
# path: swap to Sonnet here if/when the answers get noticeably terse.
MODEL = 'claude-haiku-4-5'
MAX_OUTPUT_TOKENS = 600

# System prompt — the grounding. We paste the full post body into the
# system so the model doesn't need retrieval; posts top out in the low
# thousands of tokens which is well under Haiku's context window.
SYSTEM_PROMPT_TEMPLATE = (
    "You answer strictly questions about this blog post. Use the post "
    "body below as your ONLY ground truth. If a question cannot be "
    "answered from the post, say so politely. Cite paragraph sections "
    "(e.g., \"Under 'What we did'\") when relevant. Keep answers under "
    "200 words.\n\n"
    "POST TITLE: {title}\n"
    "POST BODY:\n"
    "{body}\n"
)


def _get_client_ip(request) -> str:
    """Return an IP identifier for rate-limiting. We hash with a daily
    salt (same pattern as `portfolio/analytics._hash_ip`) so rate-limit
    keys rotate daily and never persist a raw IP in cache.

    Falls back to a sha256 of the raw IP when the DailySalt model/table
    isn't available (e.g., in the very first test before migrations, or
    in narrow import cycles). Either way the returned string is a short
    opaque digest, never a raw IP."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    ip = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')
    if not ip:
        return 'anon'
    try:
        from portfolio.models import DailySalt
        salt = DailySalt.for_today()
    except Exception:
        salt = 'no-salt'
    return hashlib.sha256(f'{salt}|{ip}'.encode()).hexdigest()[:24]


def _rate_limit_hit(ip_key: str) -> tuple[bool, str]:
    """Bump per-minute and per-day counters in cache. Returns
    (over_limit, reason). We use `cache.add` first to initialize the
    TTL and `cache.incr` to bump atomically — locmem backs this fine
    for the single-worker prod we run, and the semantics match what
    Redis would give us when we scale."""
    min_key = f'ask:ip:{ip_key}:min'
    day_key = f'ask:ip:{ip_key}:day'

    # .add() is a no-op if the key already exists — a cheap way to set
    # an initial TTL without clobbering the existing counter.
    cache.add(min_key, 0, timeout=60)
    cache.add(day_key, 0, timeout=60 * 60 * 24)

    # incr() is atomic on both locmem and shared backends. If the key
    # expired between add and incr we fall back to setting 1.
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

    if n_min > RATE_LIMIT_PER_MINUTE:
        return True, 'minute'
    if n_day > RATE_LIMIT_PER_DAY:
        return True, 'day'
    return False, ''


def _sse_event(payload: dict) -> bytes:
    """Encode a single SSE frame. One `data:` line per event, followed
    by the required blank line separator. JSON lets us pass structured
    errors/tokens without a separate event-type channel."""
    return f'data: {json.dumps(payload)}\n\n'.encode('utf-8')


def _build_messages(history, question):
    """Convert the client's history + new question into the Anthropic
    messages list. We drop any empty messages (they trip a 400 on the
    API) and cap total history to the last 10 turns to bound context
    growth even if the client tries to replay a long conversation."""
    msgs = []
    for m in (history or [])[-10:]:
        if not isinstance(m, dict):
            continue
        role = m.get('role')
        content = (m.get('content') or '').strip()
        if role not in ('user', 'assistant') or not content:
            continue
        msgs.append({'role': role, 'content': content})
    msgs.append({'role': 'user', 'content': question})
    return msgs


def _stream_anthropic(system_prompt, messages):
    """Generator yielding SSE frames from a live Anthropic stream.

    Wraps the SDK's `with client.messages.stream(...) as stream:` block,
    forwarding each text delta to the browser as soon as it arrives. On
    any SDK-level exception we flush a final `{"error": "..."}` event
    so the client can display a failure message instead of hanging."""
    try:
        import anthropic
        client = anthropic.Anthropic()
        with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=system_prompt,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                if text:
                    yield _sse_event({'delta': text})
        yield _sse_event({'done': True})
    except Exception as e:
        # Never leak the actual exception text to the client — that can
        # reveal rate-limit cause, quota details, etc. A generic message
        # is enough; the server logs have the real thing.
        yield _sse_event({'error': 'upstream_error'})


@csrf_exempt
@require_http_methods(['POST'])
def ask_post(request, slug):
    """Stream an answer to the reader's question about a specific post.

    Body: {"question": str, "history": [{"role", "content"}, ...]}
    Response: SSE stream of `{"delta": "..."}` events, terminated by
    `{"done": true}` or `{"error": "..."}`.
    """
    # 1. Post must exist and be published (drafts aren't public, so
    #    neither is the chat about them).
    post = get_post(slug, include_drafts=False)
    if not post:
        raise Http404('post not found')

    # 2. API key gate — keep the key server-side, fail fast if missing.
    if not os.environ.get('ANTHROPIC_API_KEY'):
        return JsonResponse({'error': 'chat_offline'}, status=503)

    # 3. Body parse.
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except (ValueError, json.JSONDecodeError):
        return JsonResponse({'error': 'bad_json'}, status=400)

    question = (data.get('question') or '').strip()
    if not question:
        return JsonResponse({'error': 'empty_question'}, status=400)
    # Cap to keep obviously-abusive payloads out of Anthropic entirely.
    if len(question) > 2000:
        return JsonResponse({'error': 'question_too_long'}, status=400)

    history = data.get('history') or []
    if not isinstance(history, list):
        return JsonResponse({'error': 'bad_history'}, status=400)

    # 4. Rate limit — after the post/env checks so a 404/503 doesn't
    #    consume the reader's quota.
    ip_key = _get_client_ip(request)
    over, reason = _rate_limit_hit(ip_key)
    if over:
        return JsonResponse(
            {'error': 'rate_limited', 'scope': reason},
            status=429,
        )

    # 5. Build the prompt + stream.
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        title=post.get('title', ''),
        body=post.get('body', ''),
    )
    messages = _build_messages(history, question)

    response = StreamingHttpResponse(
        _stream_anthropic(system_prompt, messages),
        content_type='text/event-stream',
    )
    # Disable buffering at every hop — otherwise the reader sees nothing
    # until the full answer is generated and the streaming UX is lost.
    response['Cache-Control'] = 'no-cache, no-transform'
    response['X-Accel-Buffering'] = 'no'
    return response
