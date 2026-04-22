"""`<div data-plot>…Vega-Lite JSON…</div>` — client-side chart.

Authoring:

    <div data-plot>
    {
      "mark": "line",
      "data": {"values": [{"x": 0, "y": 0}, {"x": 1, "y": 0.7}]},
      "encoding": {"x": {"field": "x"}, "y": {"field": "y"}}
    }
    </div>

Complement to the server-side ```python pyfig``` blocks:
  * pyfig: heavy, matplotlib, rendered at save-time into inline SVG.
  * data-plot: lightweight, interactive, rendered in-browser by
    Vega-Lite (vendored at static/portfolio/js/vendor/vega-embed/).

Rendering is pure passthrough: we emit a `<div class="vega-plot">`
with the JSON attached as a `data-spec` attribute. A tiny script on
post load looks up every `.vega-plot` and calls `vegaEmbed` on it.
"""
import html as html_lib
import json
import re

from . import render_error


_RE = r'(?s)<div\s+data-plot\b[^>]*>(.*?)</div\s*>'


def _render(m: re.Match) -> str:
    raw = m.group(1).strip()
    if not raw:
        return render_error(
            'Empty <code>&lt;div data-plot&gt;</code> — put a Vega-Lite '
            'JSON spec inside.'
        )
    try:
        # Validate by parsing; re-serialize to minimize whitespace and
        # protect against weird inner markdown that looks like JSON.
        spec = json.loads(raw)
    except json.JSONDecodeError as e:
        return render_error(
            f'Invalid Vega-Lite JSON in <code>data-plot</code>: '
            f'{html_lib.escape(str(e))}.'
        )
    encoded = html_lib.escape(json.dumps(spec, separators=(',', ':')), quote=True)
    return f'<div class="vega-plot" data-spec="{encoded}"></div>'


def register_all(register):
    register(_RE, _render)
