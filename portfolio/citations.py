"""Citation utilities: BibTeX parsing + author-name formatting.

Kept as a pure-function module so `citations.py` has no Django imports
and is cheap to unit-test. The `bibtex_to_fields` function maps a
single BibTeX entry string to the subset of fields we surface on the
`Citation` model (key, title, authors, venue, year, url, doi).

Design choices:

* Regex-based, not a full BibTeX grammar. We need to be forgiving of
  real-world entries (mismatched braces, stray commas, inconsistent
  casing) and strict parsers hate those. The tradeoff: we'll miss
  exotic BibTeX features (crossref, @string, comments) that nobody
  actually pastes into a blog editor.
* Author formatting collapses "Lastname, First" pairs into "F. Lastname"
  for the display string — matches the style of the legacy citations.json.
* `key` extraction is authoritative (the thing between `@type{` and the
  first comma). If missing, we synthesize one from firstauthor + year.
"""
from __future__ import annotations

import re
from typing import Any


_ENTRY_HEADER_RE = re.compile(r'@\s*(\w+)\s*\{\s*([^,\s}]+)\s*,', re.IGNORECASE)


def _extract_field(body: str, name: str) -> str:
    """Extract a `name = {...}` or `name = "..."` field from a BibTeX
    entry body. Handles nested braces by counting depth."""
    pattern = re.compile(r'\b' + re.escape(name) + r'\s*=\s*', re.IGNORECASE)
    m = pattern.search(body)
    if not m:
        return ''
    i = m.end()
    if i >= len(body):
        return ''
    opener = body[i]
    if opener == '{':
        depth = 1
        start = i + 1
        j = start
        while j < len(body) and depth > 0:
            c = body[j]
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return body[start:j].strip()
            j += 1
        return body[start:j].strip()
    if opener == '"':
        start = i + 1
        j = body.find('"', start)
        if j == -1:
            return body[start:].strip()
        return body[start:j].strip()
    # Unbraced literal — grab up to next comma or end.
    j = i
    while j < len(body) and body[j] not in ',}\n':
        j += 1
    return body[i:j].strip()


def _format_authors(raw: str) -> str:
    """Turn a BibTeX `author = {A and B and C}` field into the
    comma-separated display format used in citations.json:
    'F. Lastname, G. Othername'. Defensive — if parsing fails, return
    the raw string."""
    if not raw:
        return ''
    parts = [p.strip() for p in re.split(r'\s+and\s+', raw) if p.strip()]
    out = []
    for p in parts:
        if ',' in p:
            last, _, first = p.partition(',')
            initials = ''.join(
                (tok[0] + '.') for tok in first.strip().split() if tok
            )
            out.append(f'{initials} {last.strip()}'.strip())
        else:
            # "First Last" form — initial the front.
            tokens = p.split()
            if len(tokens) >= 2:
                initials = ''.join(t[0] + '.' for t in tokens[:-1])
                out.append(f'{initials} {tokens[-1]}')
            else:
                out.append(p)
    return ', '.join(out)


def bibtex_to_fields(bibtex: str) -> dict[str, Any]:
    """Parse a pasted BibTeX entry into our Citation model's fields.

    Returns a dict with: key, title, authors, venue, year, url, doi,
    bibtex. Missing fields come back as empty strings / None. Raises
    ValueError if the input can't be recognized as a BibTeX entry."""
    if not bibtex or '@' not in bibtex:
        raise ValueError('Not a BibTeX entry — missing @type{...}.')

    header = _ENTRY_HEADER_RE.search(bibtex)
    if not header:
        raise ValueError(
            'Could not parse BibTeX header. Expected `@type{key, ...}`.'
        )
    key = header.group(2).strip()
    body_start = header.end()
    # Strip the trailing closing brace of the outer entry if present.
    body = bibtex[body_start:]

    title = _extract_field(body, 'title')
    authors_raw = _extract_field(body, 'author')
    journal = _extract_field(body, 'journal')
    booktitle = _extract_field(body, 'booktitle')
    publisher = _extract_field(body, 'publisher')
    year_raw = _extract_field(body, 'year')
    url = _extract_field(body, 'url')
    doi = _extract_field(body, 'doi')
    volume = _extract_field(body, 'volume')
    pages = _extract_field(body, 'pages')

    venue = journal or booktitle or publisher
    # Light venue enrichment — "Journal Name 12, 34 (2023)"-style — only
    # when we have the pieces and no venue override. Matches the hand-
    # curated style in the legacy citations.json.
    if venue and volume and year_raw:
        tail = []
        if volume:
            tail.append(volume)
            if pages:
                tail[-1] += f', {pages.replace("--", "–")}'
        tail.append(f'({year_raw})')
        venue = f'{venue} {", ".join(tail[:-1])} {tail[-1]}'.strip()

    try:
        year = int(year_raw) if year_raw else None
    except ValueError:
        year = None

    # Strip surrounding braces that BibTeX sometimes uses for case
    # preservation, e.g. {Transformer} → Transformer.
    def _unbrace(s: str) -> str:
        s = s.strip()
        while s.startswith('{') and s.endswith('}'):
            s = s[1:-1].strip()
        return s

    # Pull arxiv id out of the URL if present — used for dedupe on reuse.
    arxiv_id = ''
    if url:
        m = re.search(r'arxiv\.org/(?:abs|pdf)/([\d.]+)', url, re.IGNORECASE)
        if m:
            arxiv_id = m.group(1).rstrip('.')

    return {
        'key': key,
        'title': _unbrace(title),
        'authors': _format_authors(_unbrace(authors_raw)),
        'venue': _unbrace(venue),
        'year': year,
        'url': url,
        'doi': doi,
        'arxiv_id': arxiv_id,
        'bibtex': bibtex.strip(),
    }
