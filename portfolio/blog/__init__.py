import math
import re
from datetime import date
from pathlib import Path

import frontmatter
import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.toc import TocExtension

POSTS_DIR = Path(__file__).parent / 'posts'

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


def render_markdown(content):
    """Convert markdown string to HTML with syntax highlighting and ToC."""
    content, latex_placeholders = _protect_latex(content)

    md = markdown.Markdown(extensions=[
        'fenced_code',
        CodeHiliteExtension(css_class='highlight', guess_lang=False, linenums=False),
        'tables',
        TocExtension(toc_depth='2-3', permalink=True, permalink_class='toc-link'),
        'smarty',
        'attr_list',
    ])

    html = md.convert(content)
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


def _post_to_dict(post_obj):
    """Convert a Post model instance to the standard post dict."""
    content_html, toc_html = render_markdown(post_obj.body)
    return {
        'slug': post_obj.slug,
        'title': post_obj.title,
        'date': post_obj.date,
        'updated': post_obj.updated,
        'author': post_obj.author,
        'tags': list(post_obj.tags.names()),
        'excerpt': post_obj.excerpt,
        'image': post_obj.image,
        'draft': post_obj.draft,
        'medium_url': post_obj.medium_url,
        'reading_time': estimate_reading_time(post_obj.body),
        'content_html': content_html,
        'toc_html': toc_html,
        'word_count': len(post_obj.body.split()),
    }


def _parse_file_post(filepath):
    """Parse a single markdown file into a post dict."""
    post = frontmatter.load(filepath)
    slug = filepath.stem

    raw_content = post.content
    content_html, toc_html = render_markdown(raw_content)
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
        'medium_url': post.get('medium_url', ''),
        'reading_time': reading_time,
        'content_html': content_html,
        'toc_html': toc_html,
        'word_count': len(raw_content.split()),
    }


def _has_db():
    """Check if the Post table exists (database is set up)."""
    try:
        from portfolio.models import Post
        Post.objects.exists()
        return True
    except Exception:
        return False


def get_all_posts(include_drafts=False):
    """Load all blog posts from DB (if available) or markdown files."""
    if _has_db():
        from portfolio.models import Post
        qs = Post.objects.all()
        if not include_drafts:
            qs = qs.filter(draft=False)
        return [_post_to_dict(p) for p in qs]

    # Fallback to file-based posts
    posts = []
    if not POSTS_DIR.exists():
        return posts
    for filepath in POSTS_DIR.glob('*.md'):
        post = _parse_file_post(filepath)
        if post['draft'] and not include_drafts:
            continue
        posts.append(post)
    posts.sort(key=lambda p: p['date'], reverse=True)
    return posts


def get_post(slug):
    """Load a single blog post by slug."""
    if _has_db():
        from portfolio.models import Post
        try:
            p = Post.objects.get(slug=slug, draft=False)
            return _post_to_dict(p)
        except Post.DoesNotExist:
            pass

    # Fallback to file
    filepath = POSTS_DIR / f'{slug}.md'
    if not filepath.exists():
        return None
    post = _parse_file_post(filepath)
    if post['draft']:
        return None
    return post
