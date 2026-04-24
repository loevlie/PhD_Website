import functools
import hashlib
import math
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import frontmatter
import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.toc import TocExtension

POSTS_DIR = Path(__file__).parent / 'posts'

# Fenced code blocks with info-string `python pyfig` get executed
# server-side via matplotlib. Cached by content hash so repeat renders
# are free. This pattern matches the entire fenced block and captures
# (1) any trailing info-string tokens (e.g. `scrolly`, `scrolly=true`)
# and (2) the inner source.
#
# Info-string grammar (after `python pyfig`):
#   ``` python pyfig                      → default behavior
#   ``` python pyfig scrolly              → opt-in extended scroll range
#   ``` python pyfig scrolly=true         → same as above, explicit
#
# TODO scrolly: multi-frame support — we currently recognize the
# `scrolly` flag and propagate it as a `data-scrolly="true"` attribute
# on the rendered <figure>; CSS picks that up and lengthens the reveal
# range. A future iteration could accept multiple fenced pyfig blocks
# keyed by frame index (e.g. `scrolly=1`, `scrolly=2`, `scrolly=3`) and
# cross-fade them as the reader scrolls past the figure.
_PYFIG_RE = re.compile(
    r'```python\s+pyfig([^\n]*)\n(.*?)```',
    re.DOTALL,
)


def _post_extra_deps_path(slug):
    """Optional per-post requirements file at blog/posts/<slug>.deps.txt
    — one package per line. Lets a post that needs e.g. `torch` declare
    it without bloating the global requirements.txt."""
    if not slug:
        return None
    p = POSTS_DIR / f'{slug}.deps.txt'
    return p if p.exists() else None


def _ensure_post_deps(slug, cache_dir):
    """If the post has an extras deps file and any package isn't already
    importable, pip-install the file into <cache_dir>/<slug>/ and return
    that path so it can be prepended to PYTHONPATH. Caches by file hash."""
    deps_file = _post_extra_deps_path(slug)
    if deps_file is None:
        return None
    deps_text = deps_file.read_text(encoding='utf-8').strip()
    if not deps_text:
        return None
    h = hashlib.sha256(deps_text.encode('utf-8')).hexdigest()[:12]
    target = cache_dir / 'pyfig-deps' / f'{slug}-{h}'
    sentinel = target / '.installed'
    if sentinel.exists():
        return str(target)
    target.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '--quiet', '--target', str(target),
             '-r', str(deps_file)],
            timeout=120, capture_output=True, text=True, check=True,
        )
        sentinel.touch()
        return str(target)
    except Exception:
        return None  # fall through; pyfig will fail with a clear ImportError


# SVG > this many bytes → fall back to base64 PNG. Keeps dense scatter
# plots / heatmaps from inflating the post HTML to megabytes.
_PYFIG_SVG_MAX_BYTES = 250 * 1024


def _render_pyfig(code, alt='', timeout_s=15, post_slug=None):
    """Run user matplotlib code in an isolated subprocess and return an
    inline HTML snippet — either a sharp `<svg>` (preferred, scales on
    retina, ~5-30 KB for typical line plots) or a base64 `<img>` PNG
    fallback when the SVG would be too large (dense scatters, heatmaps).

    Returns (inline_html, error_message). Exactly one is None.

    No /media/ dependency: the figure data lives inside the returned
    HTML so the post can be persisted to Post.rendered_html and
    survive deploy-time disk wipes.

    Per-post extra deps: if a file exists at
        portfolio/blog/posts/<slug>.deps.txt
    its packages are pip-installed into a per-post directory and added
    to PYTHONPATH for the subprocess. Cached by deps-file hash, so the
    install only runs once per (slug, deps-content) combo.

    Scroll-driven reveal (Batch B): every <figure class="pyfig"> the
    caller emits is animated in on scroll by pyfig-scrolly.css via the
    native `animation-timeline: view()` primitive — no JS, no observer.
    Authors opt into a longer "slow unveil" reveal range by passing the
    `scrolly` flag in the fenced code-block info-string:

        ``` python pyfig scrolly
        # caption: … (usual)
        fig, ax = plt.subplots(); ax.plot([1, 2, 3])
        ```

    …which stamps `data-scrolly="true"` onto the output <figure>. CSS
    then widens the animation-range so the reveal spans a much larger
    scroll swath. Both default and opt-in reveals honor
    `prefers-reduced-motion: reduce` (the CSS is gated on
    `prefers-reduced-motion: no-preference`).

    TODO scrolly: multi-frame. Today only one figure is rendered per
    block and the `scrolly` flag is a pure CSS hint. A future iteration
    could accept keyed frames (`scrolly=1` … `scrolly=N`) and cross-fade
    between them as the reader scrolls past the figure.

    Security note: this executes arbitrary Python. The editor that
    creates these blocks is staff-only; rendered output is persisted on
    save so untrusted readers never trigger execution at view time.
    """
    import base64
    import html as _html
    import os as _os
    import tempfile
    from django.conf import settings as dj_settings

    # Pyfig dep cache stays on the LOCAL filesystem even when MEDIA
    # lives in R2 — pip install --target can't write to an S3 bucket,
    # and a pyfig dep tree is a per-deploy install anyway.
    pyfig_cache = Path(getattr(dj_settings, 'PYFIG_CACHE_DIR', '/tmp/pyfig-cache'))
    pyfig_cache.mkdir(parents=True, exist_ok=True)
    extras = _ensure_post_deps(post_slug, pyfig_cache)

    with tempfile.TemporaryDirectory() as td_str:
        td = Path(td_str)
        svg_path = td / 'out.svg'
        png_path = td / 'out.png'

        # Save BOTH formats in one subprocess call. The marginal cost over
        # rendering one is negligible (matplotlib already has the figure
        # composed); avoids a second Python startup if SVG turns out too big.
        wrapper = (
            'import os, sys\n'
            'os.environ["MPLBACKEND"] = "Agg"\n'
            'import matplotlib\n'
            'matplotlib.use("Agg")\n'
            'import matplotlib.pyplot as plt\n'
            '# ── user code ──\n'
            f'{code}'
            '\n# ── end user code ──\n'
            'if plt.get_fignums():\n'
            f'    plt.savefig({str(svg_path)!r}, format="svg", bbox_inches="tight", facecolor="white")\n'
            f'    plt.savefig({str(png_path)!r}, format="png", dpi=140, bbox_inches="tight", facecolor="white")\n'
            '    plt.close("all")\n'
        )

        env = _os.environ.copy()
        if extras:
            env['PYTHONPATH'] = extras + _os.pathsep + env.get('PYTHONPATH', '')

        try:
            result = subprocess.run(
                [sys.executable, '-c', wrapper],
                timeout=timeout_s,
                capture_output=True,
                text=True,
                env=env,
            )
        except subprocess.TimeoutExpired:
            return None, f'Render timed out (>{timeout_s}s)'
        except Exception as e:
            return None, f'subprocess failed: {e}'

        if result.returncode != 0:
            err_lines = [ln for ln in (result.stderr or '').splitlines() if ln.strip()]
            return None, err_lines[-1] if err_lines else f'Exit {result.returncode}'

        if not (svg_path.exists() or png_path.exists()):
            return None, 'Code ran but no figure was produced (call plt.plot(...) etc.)'

        # Prefer SVG for sharpness + accessibility (text stays selectable),
        # but fall back to base64 PNG for dense plots where SVG balloons.
        if svg_path.exists() and svg_path.stat().st_size <= _PYFIG_SVG_MAX_BYTES:
            svg = svg_path.read_text(encoding='utf-8')
            # Strip the XML decl + DOCTYPE so the <svg> can be inlined
            # cleanly inside an HTML document (these are XML-only and
            # invalid mid-HTML).
            svg = re.sub(r'^<\?xml[^?]*\?>\s*', '', svg)
            svg = re.sub(r'<!DOCTYPE[^>]*>\s*', '', svg).strip()
            # Inject role + aria-label for screen readers. matplotlib
            # gives the <svg> a width/height and viewBox already.
            label_attr = f' aria-label="{_html.escape(alt)}"' if alt else ''
            svg = re.sub(
                r'<svg\b',
                f'<svg role="img"{label_attr}',
                svg, count=1, flags=re.IGNORECASE,
            )
            return svg, None

        # PNG fallback: inline as a data URL so we still don't depend on
        # /media/ being present at view time. The lazy-load injector in
        # render_markdown will add loading="lazy" to this <img>.
        b64 = base64.b64encode(png_path.read_bytes()).decode('ascii')
        return f'<img src="data:image/png;base64,{b64}" alt="{_html.escape(alt)}">', None


def _highlight_python(code):
    """Pygments-render the code so the source view matches the site's
    other code blocks (same theme, same font, real syntax colors)."""
    from pygments import highlight
    from pygments.lexers import PythonLexer
    from pygments.formatters import HtmlFormatter
    return highlight(
        code,
        PythonLexer(),
        HtmlFormatter(cssclass='highlight', wrapcode=False, nowrap=False),
    )


def _parse_pyfig_info(info):
    """Parse the trailing tokens in a pyfig fence info-string.

    Input: the substring after `python pyfig` on the opening fence line
    (may be empty, may be `  scrolly`, `  scrolly=true`, etc.).

    Returns a dict of recognized flags. Today only `scrolly` is
    honored — it sets CSS `data-scrolly="true"` on the output <figure>
    and the pyfig-scrolly.css rule stretches the scroll-reveal range.

    Unknown tokens are silently ignored so author-side typos don't
    break the render.

    TODO scrolly: multi-frame — recognize numeric suffixes
    (`scrolly=1` … `scrolly=N`) keying off the block index so multiple
    pyfigs with the same `id=` could cross-fade as the reader scrolls.
    """
    flags = {'scrolly': False}
    if not info:
        return flags
    for tok in info.strip().split():
        key, _, val = tok.partition('=')
        key = key.strip().lower()
        val = val.strip().lower()
        if key == 'scrolly':
            # Bare `scrolly` → True. `scrolly=false` → False.
            # `scrolly=<anything-else>` → True (including `scrolly=1`,
            # which prefigures the multi-frame TODO above).
            flags['scrolly'] = True if val == '' else (val not in ('false', '0', 'no', 'off'))
    return flags


def _process_pyfig_blocks(content, post_slug=None, errors_out=None):
    """Replace ```python pyfig blocks with a clean <figure>:
        - inline SVG (or base64 PNG fallback) — no /media/ dependency
        - optional italic-serif caption underneath
        - tiny, unobtrusive "source" toggle that reveals
          the code highlighted by Pygments (same look as other code blocks).

    Optional caption via a leading `# caption: ...` line.

    Info-string flags (after `python pyfig` on the opening fence):
        `scrolly` / `scrolly=true` → stamp `data-scrolly="true"` on the
        output <figure>. pyfig-scrolly.css uses that attribute to
        extend the scroll-driven reveal range, giving a longer
        "unveil" feel for hero figures. See `_parse_pyfig_info` and
        the docstring on `_render_pyfig` for details.

    On error, render an inline banner with a collapsed source toggle —
    same chrome as success, so nothing leaks visibly. If `errors_out` is
    provided, each error message is appended; the post_save signal uses
    this to skip persistence when any pyfig in the post failed (so a
    partial-failure render isn't frozen into the DB).
    """
    import html as _html

    def sub(m):
        info = m.group(1)
        code = m.group(2)
        flags = _parse_pyfig_info(info)
        scrolly_attr = ' data-scrolly="true"' if flags['scrolly'] else ''
        # Pull an optional caption off the first comment line
        caption = ''
        lines = code.splitlines()
        if lines and lines[0].lstrip().startswith('# caption:'):
            caption = lines[0].split('# caption:', 1)[1].strip()
            code = '\n'.join(lines[1:]) + ('\n' if not code.endswith('\n') else '')
        figure_html, err = _render_pyfig(code, alt=caption, post_slug=post_slug)
        # Render the source through Pygments so it matches the theme
        # of every other code block on the site.
        source_html = _highlight_python(code.rstrip())

        if err:
            if errors_out is not None:
                errors_out.append(err)
            return (
                f'\n<figure class="pyfig pyfig--error"{scrolly_attr}>'
                f'<div class="pyfig-error">Figure failed to render. <small>{_html.escape(err)}</small></div>'
                '<figcaption class="pyfig-caption">'
                '<details class="pyfig-source"><summary>source</summary>'
                f'{source_html}'
                '</details>'
                '</figcaption>'
                '</figure>\n'
            )

        cap_html = (
            f'<span class="pyfig-cap-text">{_html.escape(caption)}</span>'
            if caption else ''
        )
        return (
            f'\n<figure class="pyfig"{scrolly_attr}>'
            # figure_html is either an inline <svg> or a base64 <img>;
            # both inline directly without an external file reference.
            f'{figure_html}'
            '<figcaption class="pyfig-caption">'
            f'{cap_html}'
            '<details class="pyfig-source"><summary>source</summary>'
            f'{source_html}'
            '</details>'
            '</figcaption>'
            '</figure>\n'
        )
    return _PYFIG_RE.sub(sub, content)

# LaTeX protection: replace $...$ and $$...$$ with placeholders before markdown processing
_DISPLAY_MATH_RE = re.compile(r'\$\$(.+?)\$\$', re.DOTALL)
_INLINE_MATH_RE = re.compile(r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)')


def _protect_latex(content):
    """Replace LaTeX delimiters with HTML spans that KaTeX will render client-side."""
    placeholders = []

    def replace_display(m):
        idx = len(placeholders)
        placeholders.append(('display', m.group(1)))
        return f'\n\n<div class="math-display" data-math-idx="{idx}"></div>\n\n'

    def replace_inline(m):
        idx = len(placeholders)
        placeholders.append(('inline', m.group(1)))
        return f'<span class="math-inline" data-math-idx="{idx}"></span>'

    # Protect code blocks first
    code_blocks = []
    def save_code(m):
        code_blocks.append(m.group(0))
        return f'CODEBLOCK{len(code_blocks) - 1}END'

    content = re.sub(r'```[\s\S]*?```', save_code, content)
    content = re.sub(r'`[^`]+`', save_code, content)

    content = _DISPLAY_MATH_RE.sub(replace_display, content)
    content = _INLINE_MATH_RE.sub(replace_inline, content)

    # Restore code blocks
    for i, block in enumerate(code_blocks):
        content = content.replace(f'CODEBLOCK{i}END', block)

    return content, placeholders


def _restore_latex(html, placeholders):
    """Replace placeholder spans with actual LaTeX content for KaTeX."""
    for i, (mode, tex) in enumerate(placeholders):
        if mode == 'display':
            html = html.replace(
                f'<div class="math-display" data-math-idx="{i}"></div>',
                f'<div class="math-display">$${tex}$$</div>'
            )
        else:
            html = html.replace(
                f'<span class="math-inline" data-math-idx="{i}"></span>',
                f'<span class="math-inline">${tex}$</span>'
            )
    return html


def _inject_code_langs(html, raw_content):
    """Add data-lang attributes to highlight divs based on fenced code block languages."""
    # Extract languages from fenced code blocks in order
    langs = re.findall(r'```(\w+)', raw_content)

    # Replace each <div class="highlight"> with one that includes data-lang
    idx = [0]
    def replacer(m):
        i = idx[0]
        idx[0] += 1
        if i < len(langs):
            return f'<div class="highlight" data-lang="{langs[i]}">'
        return m.group(0)

    return re.sub(r'<div class="highlight">', replacer, html)


_FOOTNOTE_LI_RE = re.compile(
    r'<li id="fn:([^"]+)">\s*(?:<p>)?(.+?)(?:&#160;)?\s*'
    r'<a class="footnote-backref"[^>]*>[^<]*</a>\s*(?:</p>)?\s*</li>',
    re.DOTALL,
)
_FOOTNOTE_SUP_RE = re.compile(
    r'(<sup id="fnref:([^"]+)">\s*<a class="footnote-ref" href="[^"]*">(\d+)</a>\s*</sup>)'
)
_FOOTNOTE_BLOCK_RE = re.compile(
    r'<div class="footnote">.*?</div>', re.DOTALL,
)


def _transform_footnotes_to_sidenotes(html):
    """For explainer posts: pull footnote bodies out of the bottom
    <div class="footnote"> block and append each one as a
    `<span class="sidenote">` at the END of the paragraph that
    contains the marker.

    Why end-of-paragraph, not immediately after the marker:
    - On narrow viewports the span renders `display: block`, so an
      inline-after-the-sup placement visually "cuts off" the rest of
      the sentence — the sidenote appears between the marker and
      the remaining words.
    - On wide viewports CSS floats the span into the right margin,
      and a paragraph-end placement lets the full sentence flow
      without the floated element splitting it.

    Standard markdown footnote markup (rendered by python-markdown's
    `footnotes` extension) becomes Tufte-style margin notes."""
    notes = {slug: body.strip() for slug, body in _FOOTNOTE_LI_RE.findall(html)}
    if not notes:
        return html

    # Strip the bottom-of-page footnote block — we're relocating the
    # bodies into their paragraphs.
    html = _FOOTNOTE_BLOCK_RE.sub('', html)

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        # Fallback to the original after-marker placement. Rare path
        # — production installs bs4. Keeps render working if the dep
        # goes missing.
        def insert_inline(m):
            sup_html, slug, num = m.group(1), m.group(2), m.group(3)
            body = notes.get(slug, '')
            if not body:
                return sup_html
            return (
                f'{sup_html}'
                f'<span class="sidenote sidenote-{slug}">'
                f'<span class="sidenote-num">{num}.</span> {body}'
                f'</span>'
            )
        return _FOOTNOTE_SUP_RE.sub(insert_inline, html)

    soup = BeautifulSoup(html, 'html.parser')
    for sup in soup.select('sup[id^="fnref:"]'):
        slug = sup.get('id', '')[len('fnref:'):]
        body = notes.get(slug)
        if not body:
            continue
        # Pick the nearest block-level ancestor. Paragraph is the
        # common case; <li> / <blockquote> also carry footnotes.
        block = sup.find_parent(['p', 'li', 'blockquote'])
        if block is None:
            block = sup.parent
        # Keep the visible number text from the sup's <a> for parity
        # with the legacy regex output.
        num_text = (sup.a.get_text(strip=True) if sup.a else '1') or '1'
        sn = soup.new_tag('span')
        sn['class'] = ['sidenote', f'sidenote-{slug}']
        num_span = soup.new_tag('span', attrs={'class': 'sidenote-num'})
        num_span.string = f'{num_text}.'
        sn.append(num_span)
        sn.append(' ')
        # Footnote bodies come back as inner HTML; parse and append
        # child nodes so `<a>`, `<em>`, etc. inside the body stay
        # rendered rather than HTML-escaped.
        body_frag = BeautifulSoup(body, 'html.parser')
        for child in list(body_frag.contents):
            sn.append(child)
        block.append(sn)

    return str(soup)


# NOTE: demo-embed logic moved to portfolio/blog/embeds/demo.py, and
# dispatch is handled by portfolio.blog.embeds.expand_embeds. The old
# _expand_demo_embeds / _DEMO_MARKER_RE / _DEMO_LEGACY_RE were removed
# on 2026-04-22 after the generic dispatcher took over (it now handles
# demo, arxiv, github, wiki, quiz, plot, equation in one pass).


_NOTATION_EMPTY_RE = re.compile(r'<div\s+data-notation[^>]*>\s*</div>', re.IGNORECASE)


_NOTATION_WRAP_SKIP_TAGS = {
    'pre', 'code', 'script', 'style', 'a', 'math', 'abbr',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',  # headings stay clean
}


def _wrap_notation_terms(html, notation_entries):
    """Wrap plain-text occurrences of each post notation term in a
    `<span class="g" data-g="term" data-def="…">…</span>` so the
    reader-side math-glossary.js turns them into hover popovers.

    Skips text inside code / script / headings / existing `.g` spans
    / anchor tags / KaTeX output so we don't double-wrap or mangle
    structural content. Matches are case-insensitive but wrap the
    author's original capitalization.

    LaTeX-kind entries are left alone — they're intended for the
    glossary card and for inline KaTeX, not for prose auto-wrap.
    """
    if not notation_entries:
        return html
    pairs = []
    for e in notation_entries:
        if not isinstance(e, dict):
            continue
        if e.get('kind') == 'latex':
            continue
        term = (e.get('term') or '').strip()
        defn = (e.get('definition') or '').strip()
        if term and defn:
            pairs.append((term, defn))
    if not pairs:
        return html
    # Longest first so multi-word terms win over their single-word prefixes.
    pairs.sort(key=lambda p: -len(p[0]))

    # Graceful skip: auto-wrap requires beautifulsoup4 for safe HTML
    # traversal. If the runtime doesn't have it (e.g. a deploy that
    # landed before the requirements bump), degrade to "glossary-card
    # only" rather than crashing the render.
    try:
        from bs4 import BeautifulSoup, NavigableString
    except ImportError:
        return html
    soup = BeautifulSoup(html, 'html.parser')

    term_map = {t.lower(): (t, d) for t, d in pairs}
    pattern = re.compile(
        r'(?<!\w)(' + '|'.join(re.escape(t) for t, _ in pairs) + r')(?!\w)',
        re.IGNORECASE,
    )

    def _skip(node):
        for parent in node.parents:
            name = getattr(parent, 'name', None)
            if not name:
                continue
            if name in _NOTATION_WRAP_SKIP_TAGS:
                return True
            classes = parent.get('class') or []
            if name == 'span' and ('g' in classes or any('katex' in c for c in classes)):
                return True
        return False

    for node in list(soup.find_all(string=True)):
        if not isinstance(node, NavigableString):
            continue
        if _skip(node):
            continue
        text = str(node)
        if not pattern.search(text):
            continue
        replacements = []
        cursor = 0
        for m in pattern.finditer(text):
            start, end = m.span()
            matched = m.group(0)
            canonical, defn = term_map.get(matched.lower(), (matched, ''))
            if cursor < start:
                replacements.append(text[cursor:start])
            span = soup.new_tag('span')
            span['class'] = ['g']
            span['data-g'] = canonical
            span['data-def'] = defn
            span.string = matched
            replacements.append(span)
            cursor = end
        if cursor < len(text):
            replacements.append(text[cursor:])
        for frag in replacements:
            node.insert_before(frag)
        node.extract()

    return str(soup)


def _populate_notation_marker(content, notation_entries):
    """Substitute the author's empty `<div data-notation></div>`
    markers with a populated glossary block drawn from a post's
    `notation` JSON field. Each entry is one line of `term: definition`;
    the existing `notation` embed handler then renders the card.

    LaTeX-kind entries get wrapped in `$…$` so KaTeX picks them up
    inside the resulting glossary.
    """
    if not notation_entries:
        return content
    lines = []
    for e in notation_entries:
        if not isinstance(e, dict):
            continue
        term = (e.get('term') or '').strip()
        definition = (e.get('definition') or '').strip()
        if not term or not definition:
            continue
        if (e.get('kind') or 'text') == 'latex':
            term = f'${term}$'
        lines.append(f'{term}: {definition}')
    if not lines:
        return content
    body = '\n'.join(lines)
    return _NOTATION_EMPTY_RE.sub(f'<div data-notation>\n{body}\n</div>', content)


def render_markdown(content, is_explainer=False, post_slug=None, errors_out=None,
                    preview=False, notation_entries=None):
    """Convert markdown string to HTML with syntax highlighting, ToC, and
    (for explainer posts) Tufte-style sidenotes from footnote markup.

    Authors write standard markdown footnotes:
        The transformer architecture[^attention] is everywhere now.
        ...
        [^attention]: Vaswani et al. 2017. Attention Is All You Need.

    On regular posts these render as classic numbered footnotes.
    On `is_explainer=True` posts they're transformed into margin notes
    that float in the right gutter on desktop and collapse inline on mobile.

    `notation_entries` (list of {term, definition, kind}) populates any
    empty `<div data-notation></div>` markers with the post's per-post
    glossary — see `portfolio/views/blog_editor.py` for the editor-side
    management and Post.notation for storage.

    If `errors_out` is provided (a mutable list), any pyfig rendering
    errors are appended to it. The post_save signal uses this to avoid
    persisting a partial-failure render into Post.rendered_html.
    """
    # Render Python figure blocks first — replaces ```python pyfig with
    # an inline figure (SVG or base64 PNG), so subsequent passes treat
    # them as ordinary images.
    content = _process_pyfig_blocks(content, post_slug=post_slug, errors_out=errors_out)
    # Populate empty notation markers from the post's stored entries
    # BEFORE the embed dispatcher runs — the existing notation handler
    # then treats it like any other author-filled glossary.
    content = _populate_notation_marker(content, notation_entries)
    # Run the full marker dispatcher (portfolio/blog/embeds/) — handles
    # data-demo, data-arxiv, data-github, data-wiki, data-quiz, data-plot,
    # data-equation, data-pyodide, etc. The legacy `_expand_demo_embeds`
    # below is no longer called; the `demo` handler in the dispatcher
    # covers both the canonical and legacy forms.
    from portfolio.blog.embeds import expand_embeds
    content = expand_embeds(content)
    content, latex_placeholders = _protect_latex(content)

    md = markdown.Markdown(extensions=[
        'fenced_code',
        CodeHiliteExtension(css_class='highlight', guess_lang=False, linenums=False),
        'tables',
        TocExtension(toc_depth='2-3', permalink=True, permalink_class='toc-link'),
        'smarty',
        'attr_list',
        'footnotes',
    ])

    html = md.convert(content)
    if is_explainer:
        html = _transform_footnotes_to_sidenotes(html)
    html = _restore_latex(html, latex_placeholders)
    # Auto-wrap per-post notation terms in the prose. Done AFTER markdown
    # + LaTeX restore so the matcher sees the final rendered text,
    # including KaTeX output which is skipped via the class guard.
    html = _wrap_notation_terms(html, notation_entries)
    # Add loading="lazy" to all images
    html = html.replace('<img ', '<img loading="lazy" ')
    if not preview:
        # `_wrap_imgs_with_picture` stat()s disk per unique image via
        # staticfiles.finders — fine on a cold request, wasted work on
        # every keystroke in the editor. `_inject_code_langs` is purely
        # cosmetic (data-lang attrs for the copy-button theme) and
        # never changes between a published render and a preview.
        html = _wrap_imgs_with_picture(html)
        html = _inject_code_langs(html, content)
    toc_html = getattr(md, 'toc', '')

    return html, toc_html


_IMG_RE = re.compile(r'<img\s+([^>]*?)src="([^"]+)"([^>]*?)/?>', re.IGNORECASE)


@functools.lru_cache(maxsize=512)
def _has_webp_sibling(rel_path):
    """rel_path is a staticfiles-relative path like 'portfolio/images/blog/foo.png'.
    Returns the relative .webp path if a sibling .webp exists on disk, else None.
    Cached because finders.find() does disk I/O per call."""
    from django.contrib.staticfiles import finders
    webp_rel = re.sub(r'\.(png|jpe?g)$', '.webp', rel_path, flags=re.IGNORECASE)
    if webp_rel == rel_path:
        return None
    return webp_rel if finders.find(webp_rel) else None


def _wrap_imgs_with_picture(html):
    """Wrap each <img src="/static/X.png"> in a <picture> with a WebP source
    when a sibling X.webp exists. Visitor's browser picks WebP if supported,
    falls back to the original. ~67% smaller on average across blog images."""
    def repl(m):
        full_tag = m.group(0)
        src = m.group(2)
        if not src.startswith('/static/'):
            return full_tag
        rel = src[len('/static/'):]
        if rel.lower().endswith('.webp'):
            return full_tag
        webp_rel = _has_webp_sibling(rel)
        if not webp_rel:
            return full_tag
        webp_url = '/static/' + webp_rel
        return f'<picture><source srcset="{webp_url}" type="image/webp">{full_tag}</picture>'
    return _IMG_RE.sub(repl, html)


def estimate_reading_time(content):
    """Estimate reading time in minutes (200 wpm)."""
    words = len(content.split())
    return max(1, math.ceil(words / 200))


def _post_to_dict(post_obj, render_html=True):
    """Convert a Post model instance to the standard post dict.

    `render_html=False` skips the markdown render — used by listings and
    by the cached get_all_posts() so a single bad pyfig block can't
    poison every listing for 10 minutes. content_html / toc_html are
    rendered fresh in the single-post view path.

    Render path: if the Post has a persisted rendered_html that is
    not stale (modified_at <= rendered_at), use it directly — no
    pyfig subprocess, no markdown parse. Otherwise live-render and
    opportunistically warm the persisted cache via the same path the
    post_save signal uses, so subsequent views are cheap.
    """
    is_explainer = bool(getattr(post_obj, 'is_explainer', False))
    is_paper_companion = bool(getattr(post_obj, 'is_paper_companion', False))
    if render_html:
        cached_html = getattr(post_obj, 'rendered_html', '') or ''
        cached_at = getattr(post_obj, 'rendered_at', None)
        modified_at = getattr(post_obj, 'modified_at', None)
        is_fresh = bool(
            cached_html
            and cached_at is not None
            and (modified_at is None or modified_at <= cached_at)
        )
        if is_fresh:
            content_html = cached_html
            toc_html = getattr(post_obj, 'rendered_toc_html', '') or ''
        else:
            errors = []
            content_html, toc_html = render_markdown(
                post_obj.body, is_explainer=is_explainer, post_slug=post_obj.slug,
                errors_out=errors,
                notation_entries=getattr(post_obj, 'notation', None) or [],
            )
            # Warm the persisted render only when the body actually has
            # an id (not an unsaved instance) and no pyfig errored.
            # .filter().update() bypasses the post_save signal so this
            # doesn't recurse.
            if not errors and getattr(post_obj, 'pk', None):
                from django.utils import timezone
                from portfolio.models import Post as _Post
                _Post.objects.filter(pk=post_obj.pk).update(
                    rendered_html=content_html,
                    rendered_toc_html=toc_html,
                    rendered_at=timezone.now(),
                )
    else:
        content_html, toc_html = '', ''
    # Byline list — primary author + collaborators, pre-sorted. Computed
    # only when rendering the full single-post view (`render_html=True`)
    # since listings don't show per-author detail and the extra query
    # would N+1 across the list.
    byline_authors = post_obj.byline_authors if render_html and hasattr(post_obj, 'byline_authors') else []
    # Cover image — prefer the uploaded ImageField (`cover_image`);
    # fall back to the legacy `image` CharField as a raw /static/ URL
    # so pre-upload posts still paint without a staticfiles lookup.
    cover_upload = getattr(post_obj, 'cover_image', None)
    cover_src = ''
    if cover_upload:
        try:
            cover_src = cover_upload.url
        except ValueError:
            cover_src = ''
    if not cover_src and post_obj.image:
        cover_src = '/static/' + post_obj.image.lstrip('/')
    return {
        'slug': post_obj.slug,
        'title': post_obj.title,
        'date': post_obj.date,
        'updated': post_obj.updated,
        'author': post_obj.author,
        'byline_authors': byline_authors,
        'cover_src': cover_src,
        # Use .all() (not .names()) so this hits the prefetch_related cache
        # set up in _load_all_posts. .names() would issue a fresh query per
        # post and defeat the prefetch entirely (5 queries for 2 posts → 3).
        'tags': [t.name for t in post_obj.tags.all()],
        'excerpt': post_obj.excerpt,
        'image': post_obj.image,
        'draft': post_obj.draft,
        'series': post_obj.series,
        'series_order': post_obj.series_order,
        'medium_url': post_obj.medium_url,
        'is_explainer': is_explainer,
        'is_paper_companion': is_paper_companion,
        'maturity': getattr(post_obj, 'maturity', ''),
        'kind': getattr(post_obj, 'kind', '') or 'essay',
        'body': post_obj.body,
        'reading_time': estimate_reading_time(post_obj.body),
        'content_html': content_html,
        'toc_html': toc_html,
        'word_count': len(post_obj.body.split()),
        'modified_at': getattr(post_obj, 'modified_at', None),
        'rendered_at': getattr(post_obj, 'rendered_at', None),
    }


def _parse_file_post(filepath, render_html=True):
    """Parse a single markdown file into a post dict.
    `render_html=False` skips the markdown render (see _post_to_dict)."""
    post = frontmatter.load(filepath)
    slug = filepath.stem

    raw_content = post.content
    is_explainer = bool(post.get('is_explainer', False))
    is_paper_companion = bool(post.get('is_paper_companion', False))
    if render_html:
        content_html, toc_html = render_markdown(
            raw_content, is_explainer=is_explainer, post_slug=slug,
        )
    else:
        content_html, toc_html = '', ''
    reading_time = estimate_reading_time(raw_content)

    post_date = post.get('date', date.today())
    if isinstance(post_date, str):
        post_date = date.fromisoformat(post_date)

    author_name = post.get('author', 'Dennis Loevlie')
    return {
        'slug': slug,
        'title': post.get('title', slug.replace('-', ' ').title()),
        'date': post_date,
        'updated': post.get('updated'),
        'author': author_name,
        'byline_authors': [{
            'order': 1, 'name': author_name, 'avatar_url': None,
            'bio': 'ELLIS PhD Student at CWI & University of Amsterdam',
            'homepage_url': '/', 'is_primary': True,
        }] if render_html else [],
        'cover_src': '',
        'tags': post.get('tags', []),
        'excerpt': post.get('excerpt', ''),
        'image': post.get('image', ''),
        'draft': post.get('draft', False),
        'series': post.get('series', ''),
        'series_order': post.get('series_order', 0),
        'medium_url': post.get('medium_url', ''),
        'is_explainer': is_explainer,
        'is_paper_companion': is_paper_companion,
        'maturity': post.get('maturity', ''),
        'kind': post.get('kind', '') or 'essay',
        'body': raw_content,
        'reading_time': reading_time,
        'content_html': content_html,
        'toc_html': toc_html,
        'word_count': len(raw_content.split()),
        'modified_at': None,
    }


def _has_db():
    """Return True only if the Post table exists AND has at least one row.
    An empty table (e.g., fresh dev DB after running migrations but before
    `manage.py import_posts`) falls through to file-based posts so the
    markdown-author workflow keeps working without a populated DB."""
    try:
        from portfolio.models import Post
        return Post.objects.exists()
    except Exception:
        return False


def get_all_posts(include_drafts=False):
    """Load all blog posts from DB (if available) or markdown files.

    Cached per (include_drafts) variant. Cache key is invalidated by the
    Post post_save / post_delete signals (see portfolio/signals.py) so
    edits land in the listing on the next request without a manual flush."""
    from django.core.cache import cache
    cache_key = f'all_posts:drafts={int(bool(include_drafts))}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    posts = _load_all_posts(include_drafts=include_drafts)
    cache.set(cache_key, posts, 600)  # 10-min TTL — also invalidated on Post save
    return posts


def invalidate_post_cache():
    """Drop the get_all_posts cache for both variants. Called from the
    Post post_save / post_delete signals."""
    from django.core.cache import cache
    cache.delete_many(['all_posts:drafts=0', 'all_posts:drafts=1'])


def _load_all_posts(include_drafts=False):
    """Uncached implementation of get_all_posts. Listings only need
    metadata; content_html is rendered on demand by get_post()."""
    if _has_db():
        from portfolio.models import Post
        qs = Post.objects.all().prefetch_related('tags')
        if not include_drafts:
            qs = qs.filter(draft=False)
        return [_post_to_dict(p, render_html=False) for p in qs]

    # Fallback to file-based posts
    posts = []
    if not POSTS_DIR.exists():
        return posts
    for filepath in POSTS_DIR.glob('*.md'):
        post = _parse_file_post(filepath, render_html=False)
        if post['draft'] and not include_drafts:
            continue
        posts.append(post)
    posts.sort(key=lambda p: p['date'], reverse=True)
    return posts


def get_post(slug, include_drafts=False):
    """Load a single blog post by slug, with full content_html rendered.

    Not cached — pyfig blocks have their own file-level cache (PNG by
    SHA-256 of the code), so cache hits are still cheap. Skipping the
    in-memory cache here means a fresh render on every page-view, which
    avoids stale-error caching when matplotlib isn't installed yet.

    By default drafts return None (so anon visitors get a 404 / WIP stub).
    Pass `include_drafts=True` to fetch a draft for staff preview or for
    the working-on-it stub renderer."""
    if _has_db():
        from portfolio.models import Post
        try:
            qs = Post.objects.filter(slug=slug).prefetch_related('tags')
            if not include_drafts:
                qs = qs.filter(draft=False)
            p = qs.get()
            return _post_to_dict(p, render_html=True)
        except Post.DoesNotExist:
            pass

    # Fallback to file
    filepath = POSTS_DIR / f'{slug}.md'
    if not filepath.exists():
        return None
    post = _parse_file_post(filepath, render_html=True)
    if post['draft'] and not include_drafts:
        return None
    return post
