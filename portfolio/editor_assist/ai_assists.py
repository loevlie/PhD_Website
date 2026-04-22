"""Tier-2 AI author assists.

Actions the editor can ask for (tighten, tldr, title, alt-text, sidenote).
Each action has a system prompt, a user-prompt builder that reads a
payload dict, a max-tokens budget, and an output parser. The registry
below is the single source of truth — adding a new assist is one entry.

Why non-streaming: editor assists are short (≤ 400 tokens typical) and
the UI wants the whole result before deciding where to insert it. The
~1-2s round trip is fine; the complexity of a streaming path plus a
"commit this partial output" button isn't worth it here. The reader-
facing /ask endpoint still streams — that's a different UX.

Graceful failure:
  * Missing API key → AssistUnavailable (caller → 503)
  * SDK error      → AssistError     (caller → 502)
  * Unknown action → AssistUnknown   (caller → 400)
  * Bad payload    → AssistBadInput  (caller → 400)
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Callable


MODEL = 'claude-haiku-4-5'


# ─── Exceptions ─────────────────────────────────────────────────────

class AssistError(Exception):
    """SDK-level failure (network, quota, etc.). Caller should 502."""


class AssistUnavailable(Exception):
    """API key unset. Caller should 503 so the client can hide the UI."""


class AssistUnknown(Exception):
    """Action name not in registry. Caller should 400."""


class AssistBadInput(Exception):
    """Payload missing required fields or out of bounds. Caller 400."""


# ─── Spec + registry ────────────────────────────────────────────────

@dataclass(frozen=True)
class ActionSpec:
    system: str
    build_user: Callable[[dict], str]
    max_tokens: int
    parse: Callable[[str], Any]      # raw Claude text → whatever the UI wants


def _require(payload: dict, key: str, *, max_len: int) -> str:
    v = (payload.get(key) or '').strip()
    if not v:
        raise AssistBadInput(f'missing {key}')
    if len(v) > max_len:
        raise AssistBadInput(f'{key} too long')
    return v


# —— tighten —————————————————————————————————————————————————————

def _tighten_user(p: dict) -> str:
    return _require(p, 'text', max_len=8_000)


def _tighten_parse(raw: str) -> str:
    # Claude sometimes wraps the answer in quotes or prepends
    # "Tightened version:". Strip both.
    t = raw.strip()
    for prefix in ('Tightened version:', 'Tightened:', 'Revised:'):
        if t.lower().startswith(prefix.lower()):
            t = t[len(prefix):].strip()
    if len(t) >= 2 and t[0] in ('"', '“', '«') and t[-1] in ('"', '”', '»'):
        t = t[1:-1].strip()
    return t


_TIGHTEN = ActionSpec(
    system=(
        "You are an editor. Tighten the given prose: remove filler, "
        "redundant qualifiers, and hedging without changing meaning or "
        "voice. Keep all technical claims and numbers exactly. Output "
        "ONLY the tightened version. No preamble. No commentary. No "
        "quotes around the output. Target length: 70–90% of the input."
    ),
    build_user=_tighten_user,
    max_tokens=800,
    parse=_tighten_parse,
)


# —— tldr ————————————————————————————————————————————————————————

def _tldr_user(p: dict) -> str:
    return _require(p, 'body', max_len=40_000)


def _tldr_parse(raw: str) -> str:
    return raw.strip().strip('"“”«»').strip()


_TLDR = ActionSpec(
    system=(
        "Summarize this blog post in 2–3 sentences. Lead with the main "
        "claim or finding. State the method in one clause. No hedging "
        "(\"this post explores\", \"we consider\"). Output ONLY the "
        "summary — no heading, no bullet points."
    ),
    build_user=_tldr_user,
    max_tokens=300,
    parse=_tldr_parse,
)


# —— title ——————————————————————————————————————————————————————

_TITLE_LINE_RE = re.compile(r'^\s*(?:\d+[.)]|[-*•])\s*(.+?)\s*$')


def _title_user(p: dict) -> str:
    body = _require(p, 'body', max_len=40_000)
    current = (p.get('current_title') or '').strip()
    if current:
        return f'Current title (for style reference only): {current}\n\nPOST:\n{body}'
    return body


def _title_parse(raw: str) -> list[str]:
    out: list[str] = []
    for line in raw.splitlines():
        m = _TITLE_LINE_RE.match(line)
        if m:
            out.append(m.group(1).strip().strip('"“”'))
    # Fallback: if Claude returned plain lines with no bullets, take the
    # non-empty lines directly.
    if not out:
        out = [l.strip().strip('"“”') for l in raw.splitlines() if l.strip()]
    return out[:5]


_TITLE = ActionSpec(
    system=(
        "Suggest 5 titles for this blog post. Each ≤70 characters. "
        "Specific over clever. Avoid colons unless they add real signal. "
        "No clickbait, no rhetorical questions. Output as a numbered "
        "list (1. … 2. …). Nothing else — no preface, no commentary."
    ),
    build_user=_title_user,
    max_tokens=300,
    parse=_title_parse,
)


# —— alt_text ————————————————————————————————————————————————————

def _alt_user(p: dict) -> str:
    caption = (p.get('caption') or '').strip()
    context = (p.get('context') or '').strip()
    if not caption and not context:
        raise AssistBadInput('need caption or context')
    if len(caption) > 400 or len(context) > 2_000:
        raise AssistBadInput('caption/context too long')
    bits = []
    if caption:
        bits.append(f'CAPTION: {caption}')
    if context:
        bits.append(f'CONTEXT: {context}')
    return '\n\n'.join(bits)


def _alt_parse(raw: str) -> str:
    t = raw.strip().strip('"“”«»').strip()
    # If Claude returns multiple lines, the first is typically the alt.
    return t.splitlines()[0].strip() if t else ''


_ALT = ActionSpec(
    system=(
        "Write alt text for an image in a technical blog post. 1 "
        "sentence, ≤125 characters. Describe what a sighted reader would "
        "see (objects, relationships, layout) — NOT what the image is "
        "for or why it matters. Output ONLY the alt text."
    ),
    build_user=_alt_user,
    max_tokens=100,
    parse=_alt_parse,
)


# —— sidenote ———————————————————————————————————————————————————

def _side_user(p: dict) -> str:
    return _require(p, 'passage', max_len=3_000)


def _side_parse(raw: str) -> str:
    return raw.strip().strip('"“”«»').strip()


_SIDENOTE = ActionSpec(
    system=(
        "Suggest a 1–2 sentence sidenote that clarifies ONE technical "
        "term or concept from this passage for a curious-but-non-expert "
        "reader. Pick the item most likely to trip someone up. Output "
        "in the form \"TERM: explanation.\" — nothing else."
    ),
    build_user=_side_user,
    max_tokens=200,
    parse=_side_parse,
)


# —— Registry ————————————————————————————————————————————————————

ACTIONS: dict[str, ActionSpec] = {
    'tighten':  _TIGHTEN,
    'tldr':     _TLDR,
    'title':    _TITLE,
    'alt-text': _ALT,
    'sidenote': _SIDENOTE,
}


# ─── Anthropic call ─────────────────────────────────────────────────

def _call_anthropic(system: str, user: str, max_tokens: int) -> str:
    """Single-turn Anthropic call returning the full concatenated text.

    Kept tiny and synchronous. The SDK import is deferred so tests can
    patch `anthropic.Anthropic` without importing the real client."""
    if not os.environ.get('ANTHROPIC_API_KEY'):
        raise AssistUnavailable('ANTHROPIC_API_KEY is unset')
    try:
        import anthropic
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{'role': 'user', 'content': user}],
        )
    except AssistUnavailable:
        raise
    except Exception as e:
        raise AssistError(str(e)) from e

    # The SDK returns a list of content blocks. We concatenate text
    # blocks and ignore tool-use blocks (we don't hand the model tools).
    parts: list[str] = []
    for block in getattr(resp, 'content', []) or []:
        text = getattr(block, 'text', None)
        if isinstance(text, str):
            parts.append(text)
    return ''.join(parts)


def run(action: str, payload: dict) -> Any:
    """Entry point. Dispatches to the named action, runs Claude, parses
    the result. Raises one of the Assist* exceptions on any non-success.
    """
    spec = ACTIONS.get(action)
    if spec is None:
        raise AssistUnknown(f'unknown action: {action!r}')
    user_prompt = spec.build_user(payload)   # may raise AssistBadInput
    raw = _call_anthropic(spec.system, user_prompt, spec.max_tokens)
    return spec.parse(raw)
