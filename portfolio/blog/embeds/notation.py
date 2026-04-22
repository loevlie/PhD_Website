"""`<div data-notation>…</div>` — inline symbol glossary.

The author writes a line-separated list of `TERM: DEFINITION`,
`TERM — DEFINITION`, or `TERM | DEFINITION` pairs between the opening
and closing tags; the handler renders a compact glossary card that
readers can glance at while reading dense mathematical prose.

    <div data-notation>
    θ: the parameters we optimise
    α: learning rate (default 3e-4)
    L: loss function — L(θ) = E[(y - f(θ,x))²]
    </div>

Why in-body rather than an attribute: glossary definitions frequently
contain colons, parens, and quotes, which would need painful escaping
inside `data-notation="…"`. Keeping the content between the tags
matches how authors already write fenced blocks.

Terms surrounded by `$...$` are rendered through KaTeX at read-time
(the math pass runs later in the pipeline and picks up any $x$ inside
the rendered HTML). Keeps the glossary consistent with inline math in
the main body.
"""
import html as html_lib
import re


_RE = r'<div\s+data-notation[^>]*>([\s\S]*?)</div\s*>'

# Split a line into (term, definition) on the first of :, —, |, or -
# (but NOT a plain hyphen inside a word — we require whitespace).
_SPLIT_RE = re.compile(r'\s*[:—|]\s+|\s+[-–]\s+')

# Cap the number of entries we render. A glossary with 40+ rows is
# almost certainly a mistake and would blow up the reading column.
_MAX_ENTRIES = 30
_MAX_TERM_LEN = 64
_MAX_DEF_LEN = 300


def _parse(body: str) -> list[tuple[str, str]]:
    """Split the body into (term, definition) pairs. Skips blank lines
    and lines that don't have a recognised separator — the dispatcher
    never fails a post over a malformed glossary entry, but malformed
    rows simply don't appear in the rendered card."""
    entries: list[tuple[str, str]] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = _SPLIT_RE.split(line, maxsplit=1)
        if len(parts) != 2:
            continue
        term = parts[0].strip()
        definition = parts[1].strip()
        if not term or not definition:
            continue
        if len(term) > _MAX_TERM_LEN or len(definition) > _MAX_DEF_LEN:
            continue
        entries.append((term, definition))
        if len(entries) >= _MAX_ENTRIES:
            break
    return entries


def _render_term(term: str) -> str:
    """Escape the term for HTML but preserve `$...$` math spans so the
    downstream KaTeX pass finds them intact. We escape the non-math
    segments and leave the math passthrough."""
    out_parts: list[str] = []
    i = 0
    n = len(term)
    while i < n:
        if term[i] == '$':
            close = term.find('$', i + 1)
            if close == -1:
                # Unmatched $ — treat as literal.
                out_parts.append(html_lib.escape(term[i:]))
                break
            out_parts.append(term[i : close + 1])  # leave math raw
            i = close + 1
        else:
            next_math = term.find('$', i)
            if next_math == -1:
                out_parts.append(html_lib.escape(term[i:]))
                break
            out_parts.append(html_lib.escape(term[i:next_math]))
            i = next_math
    return ''.join(out_parts)


def _render_definition(definition: str) -> str:
    # Same math-aware escape as terms.
    return _render_term(definition)


def _render(match: re.Match) -> str:
    body = match.group(1) or ''
    entries = _parse(body)
    if not entries:
        # Author wrote an empty glossary — drop the marker rather than
        # leaving the raw <div> in the document.
        return ''
    rows = []
    for term, definition in entries:
        rows.append(
            f'<div class="notation-row">'
            f'<dt class="notation-term">{_render_term(term)}</dt>'
            f'<dd class="notation-def">{_render_definition(definition)}</dd>'
            f'</div>'
        )
    inner = ''.join(rows)
    return (
        f'<aside class="notation-glossary" aria-label="Notation">'
        f'<div class="notation-head">Notation</div>'
        f'<dl class="notation-list">{inner}</dl>'
        f'</aside>'
    )


def register_all(register):
    register(_RE, _render)
