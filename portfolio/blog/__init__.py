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
# the inner source.
_PYFIG_RE = re.compile(r'```python\s+pyfig\s*\n(.*?)```', re.DOTALL)


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


def _render_pyfig(code, timeout_s=15, post_slug=None):
    """Run user matplotlib code in an isolated subprocess. Cache the
    resulting PNG by sha256 of the code so repeat renders cost nothing.

    Returns (rel_url, error_message). Exactly one is None.

    Per-post extra deps: if a file exists at
        portfolio/blog/posts/<slug>.deps.txt
    its packages are pip-installed into a per-post directory and added
    to PYTHONPATH for the subprocess. Cached by deps-file hash, so the
    install only runs once per (slug, deps-content) combo.

    Security note: this executes arbitrary Python. The editor that
    creates these blocks is staff-only; the rendered post pulls from
    the cache so untrusted readers never trigger execution."""
    import os as _os
    from django.conf import settings as dj_settings

    h = hashlib.sha256(code.encode('utf-8')).hexdigest()[:16]
    media_root = Path(dj_settings.MEDIA_ROOT)
    out_dir = media_root / 'blog-images' / 'python'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f'{h}.png'
    rel_url = f'{dj_settings.MEDIA_URL}blog-images/python/{h}.png'
    if out_path.exists():
        return rel_url, None

    extras = _ensure_post_deps(post_slug, media_root)

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
        f'    plt.savefig({str(out_path)!r}, dpi=140, bbox_inches="tight", facecolor="white")\n'
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
        # Surface the last useful line of stderr (usually the exception)
        err_lines = [ln for ln in (result.stderr or '').splitlines() if ln.strip()]
        return None, err_lines[-1] if err_lines else f'Exit {result.returncode}'

    if not out_path.exists():
        return None, 'Code ran but no figure was produced (call plt.plot(...) etc.)'
    return rel_url, None


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


def _process_pyfig_blocks(content, post_slug=None):
    """Replace ```python pyfig blocks with a clean <figure>:
        - just the image
        - optional italic-serif caption underneath
        - tiny, unobtrusive "source" toggle that reveals
          the code highlighted by Pygments (same look as other code blocks).

    Optional caption via a leading `# caption: ...` line.
    On error, render an inline banner with a collapsed source toggle —
    same chrome as success, so nothing leaks visibly."""
    import html as _html

    def sub(m):
        code = m.group(1)
        # Pull an optional caption off the first comment line
        caption = ''
        lines = code.splitlines()
        if lines and lines[0].lstrip().startswith('# caption:'):
            caption = lines[0].split('# caption:', 1)[1].strip()
            code = '\n'.join(lines[1:]) + ('\n' if not code.endswith('\n') else '')
        url, err = _render_pyfig(code, post_slug=post_slug)
        # Render the source through Pygments so it matches the theme
        # of every other code block on the site (no per-line bubbles,
        # no pill styling — proper syntax highlighting in a single block).
        source_html = _highlight_python(code.rstrip())

        if err:
            # Error path: same chrome (no orphaned visible source).
            return (
                '\n<figure class="pyfig pyfig--error">'
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
        # alt = caption if provided, else empty (decorative)
        alt = _html.escape(caption) if caption else ''
        return (
            '\n<figure class="pyfig">'
            # `loading="lazy"` is added later by render_markdown's lazy-load injector
            f'<img src="{url}" alt="{alt}">'
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
    """For explainer posts: pull footnote bodies out of the bottom <div class="footnote">
    block and inline each one as <aside class="sidenote"> right after its marker.

    Standard markdown footnote markup (rendered by python-markdown's `footnotes`
    extension) becomes Tufte-style margin notes that float into the right gutter
    on wide viewports (CSS in blog.css handles positioning)."""
    # Collect {slug: inner_html} from the footnote list.
    notes = {slug: body.strip() for slug, body in _FOOTNOTE_LI_RE.findall(html)}
    if not notes:
        return html

    # Replace each in-text marker with marker + adjacent <aside class="sidenote">.
    def insert_aside(m):
        sup_html, slug, num = m.group(1), m.group(2), m.group(3)
        body = notes.get(slug, '')
        if not body:
            return sup_html
        return (
            f'{sup_html}'
            f'<aside class="sidenote sidenote-{slug}">'
            f'<span class="sidenote-num">{num}.</span> {body}'
            f'</aside>'
        )
    html = _FOOTNOTE_SUP_RE.sub(insert_aside, html)

    # Strip the now-redundant bottom-of-page footnote block. CSS also hides
    # it (.is-explainer .blog-prose .footnote { display: none }) as a belt-
    # and-braces fallback in case this regex misses an edge case.
    html = _FOOTNOTE_BLOCK_RE.sub('', html)
    return html


def render_markdown(content, is_explainer=False, post_slug=None):
    """Convert markdown string to HTML with syntax highlighting, ToC, and
    (for explainer posts) Tufte-style sidenotes from footnote markup.

    Authors write standard markdown footnotes:
        The transformer architecture[^attention] is everywhere now.
        ...
        [^attention]: Vaswani et al. 2017. Attention Is All You Need.

    On regular posts these render as classic numbered footnotes.
    On `is_explainer=True` posts they're transformed into margin notes
    that float in the right gutter on desktop and collapse inline on mobile.
    """
    # Render Python figure blocks first — replaces ```python pyfig with
    # an inline image, so subsequent passes treat them as ordinary images.
    content = _process_pyfig_blocks(content, post_slug=post_slug)
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
    # Add loading="lazy" to all images
    html = html.replace('<img ', '<img loading="lazy" ')
    # Inject language data attributes on code blocks
    html = _inject_code_langs(html, content)
    toc_html = getattr(md, 'toc', '')

    return html, toc_html


def estimate_reading_time(content):
    """Estimate reading time in minutes (200 wpm)."""
    words = len(content.split())
    return max(1, math.ceil(words / 200))


def _post_to_dict(post_obj, render_html=True):
    """Convert a Post model instance to the standard post dict.

    `render_html=False` skips the markdown render — used by listings and
    by the cached get_all_posts() so a single bad pyfig block can't
    poison every listing for 10 minutes. content_html / toc_html are
    rendered fresh in the single-post view path."""
    is_explainer = bool(getattr(post_obj, 'is_explainer', False))
    is_paper_companion = bool(getattr(post_obj, 'is_paper_companion', False))
    if render_html:
        content_html, toc_html = render_markdown(
            post_obj.body, is_explainer=is_explainer, post_slug=post_obj.slug,
        )
    else:
        content_html, toc_html = '', ''
    return {
        'slug': post_obj.slug,
        'title': post_obj.title,
        'date': post_obj.date,
        'updated': post_obj.updated,
        'author': post_obj.author,
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
        'body': post_obj.body,
        'reading_time': estimate_reading_time(post_obj.body),
        'content_html': content_html,
        'toc_html': toc_html,
        'word_count': len(post_obj.body.split()),
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

    return {
        'slug': slug,
        'title': post.get('title', slug.replace('-', ' ').title()),
        'date': post_date,
        'updated': post.get('updated'),
        'author': post.get('author', 'Dennis Loevlie'),
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
        'body': raw_content,
        'reading_time': reading_time,
        'content_html': content_html,
        'toc_html': toc_html,
        'word_count': len(raw_content.split()),
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
