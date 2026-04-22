r"""`<div data-equation data-explain="term=gloss; ...">…</div>` —
annotated equation. The LaTeX goes inside the div; KaTeX renders it
at view time. Each `term=gloss` pair becomes a hover-tooltip over
the matching `\term{}` macro in the LaTeX (or a raw substring match).

Simpler authoring pattern that's actually supported today:

    <div data-equation
         data-explain='theta=model parameters; x=input features'>
    $$\hat{y} = \mathrm{softmax}(\theta^\top x)$$
    </div>

At render time we preserve the inner markup (KaTeX handles the $$),
but we attach the `data-explain` dict to a wrapper the equation
glossary JS reads. Hover a highlighted symbol in the rendered
equation → tooltip. Purely client-side; no pre-parsing of the LaTeX.
"""
import html as html_lib
import re

from . import render_error


# Captures the whole tag incl. body. Lazy match on .*? to avoid
# greedy spans when multiple markers are in one post. [^>]* on the
# opening tag in case data-explain contains spaces etc.
_RE = r'<div\s+data-equation(?:\s+[^>]*)?>(.*?)</div\s*>'


def _render(m: re.Match) -> str:
    full_tag = m.group(0)
    body = m.group(1).strip()

    # Pull `data-explain="..."` out of the opening tag without needing
    # a full HTML parser. Accept single or double quotes.
    explain_m = re.search(
        r'data-explain=(?:"([^"]*)"|\'([^\']*)\')',
        full_tag,
    )
    explain_raw = (explain_m.group(1) or explain_m.group(2)) if explain_m else ''

    # Parse `term=gloss; term2=gloss2` → dict. Handles trailing semi,
    # empty terms, and commas (authors forget). Loose by design.
    pairs = []
    for frag in re.split(r'[;,]\s*', explain_raw):
        if '=' not in frag:
            continue
        term, gloss = frag.split('=', 1)
        term, gloss = term.strip(), gloss.strip()
        if term and gloss:
            pairs.append((term, gloss))
    if not pairs and not body:
        return render_error(
            'Empty <code>&lt;div data-equation&gt;</code>. Put '
            '<code>$$…$$</code> LaTeX inside and '
            '<code>data-explain="term=gloss; …"</code> on the tag.'
        )

    # JSON-encode inline so the client can pick up the glossary
    # without a second round-trip. Kept minimal — 7-bit safe.
    import json
    gloss_json = html_lib.escape(json.dumps(dict(pairs)))
    return (
        f'<div class="equation-annotated" data-glossary="{gloss_json}">'
        f'{body}'
        f'</div>'
    )


def register_all(register):
    # Multiline = True so $$…$$ on its own line is captured.
    register(r'(?s)' + _RE, _render)
