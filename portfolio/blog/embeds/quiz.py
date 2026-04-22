"""`<div data-quiz>…YAML…</div>` — micro-quiz.

Authoring shape:

    <div data-quiz>
    q: What does the attention mechanism let the model do?
    options:
      - Average tokens uniformly
      - Softly route information between positions
      - Read tokens sequentially like an RNN
    answer: 1
    explain: Attention computes a soft lookup between each
      token's query and all other tokens' keys.
    </div>

Renders as a standalone card with radio-button options. Client JS
(quiz.js) scores the selection, highlights right/wrong, and reveals
the `explain` text.

Why inline YAML and not attributes: quizzes are prose-heavy.
Wrapping everything in `data-option1="..." data-option2="..."`
makes the markdown source unreadable.
"""
import html as html_lib
import re
import uuid

from . import render_error


_RE = r'(?s)<div\s+data-quiz\b[^>]*>(.*?)</div\s*>'


def _parse_yaml_ish(text: str) -> dict:
    """Tiny YAML-ish parser — we only need `q:`, `options:`, `answer:`,
    `explain:`. Avoids the PyYAML dep (this module is imported from
    templates that don't have it) and keeps the author's source
    predictable."""
    out = {'q': '', 'options': [], 'answer': None, 'explain': ''}
    current_key = None
    lines = [ln for ln in text.splitlines()]
    i = 0
    while i < len(lines):
        ln = lines[i]
        stripped = ln.strip()
        if not stripped:
            i += 1
            continue
        m = re.match(r'^([a-z_]+):\s*(.*)$', stripped)
        if m:
            key, val = m.group(1), m.group(2).strip()
            current_key = key
            if key == 'options':
                # Consume subsequent lines starting with '-'
                opts = []
                i += 1
                while i < len(lines) and (lines[i].lstrip().startswith('-')):
                    opts.append(lines[i].lstrip()[1:].strip())
                    i += 1
                out['options'] = opts
                continue
            if key in ('q', 'explain'):
                out[key] = val
            elif key == 'answer':
                try:
                    out['answer'] = int(val)
                except ValueError:
                    out['answer'] = None
            else:
                # Unknown key — ignore so typos don't break the render
                pass
        else:
            # Continuation line for `q` / `explain`
            if current_key in ('q', 'explain') and out.get(current_key) is not None:
                out[current_key] += ' ' + stripped
        i += 1
    return out


def _render(m: re.Match) -> str:
    raw_yaml = m.group(1)
    data = _parse_yaml_ish(raw_yaml)
    if not data['q'] or not data['options']:
        return render_error(
            'Quiz needs at least <code>q:</code> and an <code>options:</code> '
            'list. See blog/embeds/quiz.py for the format.'
        )
    qid = uuid.uuid4().hex[:8]
    esc = html_lib.escape

    options_html = []
    for i, opt in enumerate(data['options']):
        is_answer = 'true' if data['answer'] == i else 'false'
        options_html.append(
            f'<label class="quiz-opt">'
            f'<input type="radio" name="quiz-{qid}" value="{i}" data-correct="{is_answer}">'
            f'<span>{esc(opt)}</span>'
            f'</label>'
        )
    return (
        f'<div class="quiz-card" data-quiz-id="{qid}">'
        f'<p class="quiz-q">{esc(data["q"])}</p>'
        f'<div class="quiz-opts">{"".join(options_html)}</div>'
        f'<button type="button" class="quiz-check">Check</button>'
        f'<p class="quiz-result" hidden></p>'
        f'<p class="quiz-explain" hidden>{esc(data["explain"])}</p>'
        f'</div>'
    )


def register_all(register):
    register(_RE, _render)
