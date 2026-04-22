"""Spell-check for markdown blog posts.

Pure-Python, no Django. Takes raw markdown text, returns a list of
`Misspelling` records with suggestions. Intended to be called from
the editor's autosave cycle via
`portfolio.views.editor_assist.check_text`.

Design notes:
  * Dictionary: `pyspellchecker` ships a ~2M-word English corpus.
    Augmented at module-import time with every line in
    `terms/ml.txt` and `terms/tech.txt` so domain-specific words
    ("pytorch", "arxiv", "tabicl") aren't flagged.
  * Scoping: we deliberately DON'T check inside fenced code blocks,
    inline `code`, URLs, markdown link/image syntax, LaTeX math
    ($...$ and $$...$$), HTML entity references, or YAML
    frontmatter. Those are noise sources a writer doesn't want to
    see underlined.
  * Per-author extras: `check_text(..., extra_words=...)` takes an
    iterable of words the caller knows are fine (personal
    dictionary stored in DB/localStorage). Merged into the check
    without mutating the module-level spellchecker state.
  * Output shape is stable: each misspelling has a 0-based line +
    column offset into the ORIGINAL input, the word itself, and
    up to 5 candidate corrections ranked by pyspellchecker's edit-
    distance score. The editor uses line/col to jump the cursor.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Sequence

from spellchecker import SpellChecker


_TERMS_DIR = Path(__file__).parent / 'terms'


# ─── Region masker ────────────────────────────────────────────────────

# Regex patterns identifying stretches of the source we DON'T want to
# spell-check. Each pattern is applied in turn; matched spans are
# blanked out (replaced with spaces of the same length so line + column
# offsets stay stable) before tokenization.
#
# Ordering matters — a fenced block can contain an inline URL; we strip
# the fence first so we don't try to strip the URL out of code.
_MASK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r'```.*?```', re.DOTALL),           # fenced code blocks
    re.compile(r'~~~.*?~~~', re.DOTALL),           # tilde fences
    re.compile(r'`[^`\n]+`'),                      # inline code spans
    re.compile(r'\$\$.*?\$\$', re.DOTALL),         # display math
    re.compile(r'\$[^$\n]+\$'),                    # inline math
    re.compile(r'!?\[[^\]]*\]\([^)]+\)'),          # markdown image/link
    re.compile(r'<[^>]+>'),                        # raw HTML tags
    re.compile(r'https?://\S+'),                   # bare URLs
    re.compile(r'&[a-zA-Z0-9#]+;'),                # HTML entities
    # Frontmatter (---\n...\n---) at the very top of the body:
    re.compile(r'\A---\n.*?\n---\n', re.DOTALL),
)

# Regex for a candidate word. We accept Unicode letters + inner
# apostrophes (it's, won't, O'Brien). Numbers alone aren't words;
# hyphenated compounds are tokenized as two words (the dictionary
# usually has the parts).
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z']*[A-Za-z]")


def _mask_regions(text: str) -> str:
    """Blank out spans we shouldn't spell-check. Replacement keeps the
    original length so absolute offsets line up with the source."""
    for pat in _MASK_PATTERNS:
        text = pat.sub(lambda m: ' ' * (m.end() - m.start()), text)
    return text


# ─── Dictionary loader ────────────────────────────────────────────────

def _read_terms(path: Path) -> set[str]:
    """Parse a terms file — one word per line, `#`-prefixed lines ignored.
    Returns a set of lowercase strings for direct use with pyspellchecker."""
    if not path.exists():
        return set()
    out: set[str] = set()
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        out.add(line.lower())
    return out


@lru_cache(maxsize=1)
def _get_checker() -> SpellChecker:
    """Lazy-initialized, module-level singleton. The first call loads
    the English corpus (~10 MB → a second or two) and injects every
    word from `terms/*.txt`. Subsequent calls return the cached
    instance."""
    spell = SpellChecker(language='en', case_sensitive=False)
    for stem in ('ml', 'tech'):
        spell.word_frequency.load_words(_read_terms(_TERMS_DIR / f'{stem}.txt'))
    return spell


# ─── Public API ───────────────────────────────────────────────────────

@dataclass
class Misspelling:
    """A single flagged word. Offsets are 0-based and index into the
    ORIGINAL markdown text (not the masked version)."""
    word: str
    line: int            # 0-based line number in the source
    col: int             # 0-based column offset within that line
    offset: int          # 0-based character offset from start of text
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def check_text(
    text: str,
    *,
    extra_words: Iterable[str] = (),
    max_suggestions: int = 5,
    max_results: int = 500,
) -> list[Misspelling]:
    """Find misspellings in `text`. Tokens inside fenced code blocks,
    inline code, URLs, math, link syntax, and HTML are skipped.

    `extra_words` lets the caller add user/post-level allowed words
    without touching the module-level dictionary. Case-insensitive.

    `max_results` caps the list — an editor pane doesn't need 5,000
    entries, and a runaway post shouldn't hog the response.
    """
    if not text:
        return []

    spell = _get_checker()
    extras = {w.lower().strip() for w in extra_words if w and w.strip()}

    masked = _mask_regions(text)
    # Precompute line-start offsets for fast (offset → line, col) lookup.
    line_starts = [0]
    for i, ch in enumerate(text):
        if ch == '\n':
            line_starts.append(i + 1)

    def line_col(offset: int) -> tuple[int, int]:
        # Binary search for the line containing `offset`.
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo, offset - line_starts[lo]

    results: list[Misspelling] = []
    seen_keys: set[tuple[str, int]] = set()   # dedupe same word + offset

    for m in _WORD_RE.finditer(masked):
        word = m.group(0)
        lower = word.lower()
        # Skip extras first (cheap), then punt to the checker.
        if lower in extras:
            continue
        # pyspellchecker.unknown() returns a set of the unknown words
        # from a given collection. We check one at a time here so we
        # can keep the offset; batching doesn't buy us much because
        # unknown() is already O(n) over the input.
        if not spell.unknown([lower]):
            continue
        # Skip all-caps short acronyms (DNA, URL, GPU). These are almost
        # always legitimate in technical writing even when absent from
        # the dictionary. We still flag CamelCase / Title-Case since
        # those are more often real misspellings of brand names.
        if word.isupper() and len(word) <= 5:
            continue
        key = (lower, m.start())
        if key in seen_keys:
            continue
        seen_keys.add(key)
        line, col = line_col(m.start())
        # `candidates()` returns None for unknown words with no close
        # match. Guard, then take the top N ranked by frequency.
        candidates = spell.candidates(lower) or set()
        top = sorted(candidates, key=lambda w: -spell.word_frequency[w])[:max_suggestions]
        results.append(Misspelling(
            word=word, line=line, col=col, offset=m.start(),
            suggestions=top,
        ))
        if len(results) >= max_results:
            break
    return results


def is_known(word: str, *, extras: Sequence[str] = ()) -> bool:
    """Single-word utility — used by the "Add to dictionary" pathway to
    confirm a word is now accepted."""
    if not word:
        return True
    lower = word.lower().strip()
    if lower in {e.lower() for e in extras}:
        return True
    spell = _get_checker()
    return not spell.unknown([lower])


def load_term_list(name: str) -> set[str]:
    """Expose the term-file loader for callers (Django shell, tests)
    that want to inspect which words are baked in."""
    return _read_terms(_TERMS_DIR / f'{name}.txt')
