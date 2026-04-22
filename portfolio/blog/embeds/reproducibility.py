"""`<div data-repro>…</div>` — "How to reproduce" card.

The author writes `key: value` pairs between the tags:

    <div data-repro>
    python: 3.11
    commit: abc1234
    dataset: cifar10 (sha256:ab12ef)
    seed: 42
    command: python train.py --lr 3e-4
    wall-clock: 6h on 1x A100
    </div>

Rendered as a labelled card so readers know exactly what they need to
replicate the result. Unknown keys are shown verbatim; known keys
(python, commit, dataset, seed, command, wall-clock, hardware) get
typed rendering (monospace for commands, linked repo SHA when a
`commit-repo:` key is also present, …).

Scope: display-only. We never execute the command, never hit the net,
never infer hashes. Authors are responsible for the accuracy of what
they paste in — just like a code block.
"""
import html as html_lib
import re


_RE = r'<div\s+data-repro[^>]*>([\s\S]*?)</div\s*>'

# One line = one key:value pair. Keys are lowercase, alphanumeric +
# hyphen only; values are whatever remains after the first colon.
_LINE_RE = re.compile(r'^\s*([a-z][a-z0-9\-]{0,31})\s*:\s*(.+?)\s*$', re.IGNORECASE)

# Keys we render with custom chrome (ordering is the display order).
_KNOWN_KEYS = [
    'python',
    'hardware',
    'commit',
    'dataset',
    'seed',
    'command',
    'wall-clock',
    'notes',
]

# Cap each value — a 10 KB command line almost certainly means the
# author fat-fingered the template, and we don't want to render it.
_MAX_VAL = 400
_MAX_KEYS = 20


def _parse(body: str) -> dict[str, str]:
    """Extract key:value pairs from the body. Duplicate keys keep the
    first occurrence (so authors can't accidentally produce a page
    that says two contradictory things about the Python version)."""
    out: dict[str, str] = {}
    for line in body.splitlines():
        m = _LINE_RE.match(line)
        if not m:
            continue
        key = m.group(1).lower()
        value = m.group(2).strip()
        if not value or len(value) > _MAX_VAL:
            continue
        if key in out:
            continue
        out[key] = value
        if len(out) >= _MAX_KEYS:
            break
    return out


def _render_value(key: str, value: str, all_fields: dict[str, str]) -> str:
    """Per-key value HTML. Everything non-trivial sits in a <code> so
    copy-paste into a terminal is one click."""
    esc = html_lib.escape(value)
    if key == 'command':
        return f'<code class="repro-command">{esc}</code>'
    if key == 'commit':
        # If the author supplied a repo-url, link the SHA to the tree.
        repo = all_fields.get('commit-repo') or all_fields.get('repo')
        if repo and _looks_like_repo_slug(repo):
            owner_repo = repo.strip()
            return (
                f'<a class="repro-commit" '
                f'href="https://github.com/{html_lib.escape(owner_repo)}/commit/{esc}" '
                f'target="_blank" rel="noopener"><code>{esc}</code></a>'
            )
        return f'<code class="repro-commit">{esc}</code>'
    if key == 'seed':
        return f'<code class="repro-seed">{esc}</code>'
    if key == 'python':
        return f'<code class="repro-python">Python {esc}</code>'
    return esc


def _looks_like_repo_slug(s: str) -> bool:
    return bool(re.match(r'^[A-Za-z0-9][A-Za-z0-9._\-]*/[A-Za-z0-9._\-]+$', s.strip()))


def _render(match: re.Match) -> str:
    body = match.group(1) or ''
    fields = _parse(body)
    if not fields:
        return ''

    # Render known keys first in fixed order, then any unknown keys
    # the author supplied (repo-link aux fields like `commit-repo`
    # are consumed by the commit renderer and skipped here).
    shown: list[tuple[str, str]] = []
    seen: set[str] = set()
    for k in _KNOWN_KEYS:
        if k in fields:
            shown.append((k, fields[k]))
            seen.add(k)
    for k, v in fields.items():
        if k in seen or k in ('commit-repo', 'repo'):
            continue
        shown.append((k, v))

    rows = []
    for k, v in shown:
        label = html_lib.escape(k.replace('-', ' ').title())
        rows.append(
            f'<div class="repro-row">'
            f'<dt class="repro-key">{label}</dt>'
            f'<dd class="repro-val">{_render_value(k, v, fields)}</dd>'
            f'</div>'
        )
    inner = ''.join(rows)
    return (
        f'<aside class="repro-card" aria-label="Reproducibility">'
        f'<div class="repro-head"><span class="repro-badge">↻</span> '
        f'How to reproduce</div>'
        f'<dl class="repro-list">{inner}</dl>'
        f'</aside>'
    )


def register_all(register):
    register(_RE, _render)
