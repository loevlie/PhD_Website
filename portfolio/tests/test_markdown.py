"""Markdown rendering: pyfig blocks, sidenotes, citations, basic markdown.

pyfig tests mock the subprocess to avoid needing matplotlib in CI.
"""
import hashlib
from unittest import mock

from django.test import TestCase

from portfolio.blog import (
    render_markdown, _render_pyfig, _process_pyfig_blocks, estimate_reading_time,
)


class BasicMarkdownTests(TestCase):
    def test_renders_plain_paragraph(self):
        html, _ = render_markdown('Hello world.')
        self.assertIn('<p>Hello world.</p>', html)

    def test_renders_headings_with_anchor(self):
        html, _ = render_markdown('# Hello\n\nbody')
        self.assertIn('<h1', html)
        # TOC extension adds permalink anchors
        self.assertIn('toc-link', html)

    def test_fenced_code_gets_lang_attr(self):
        html, _ = render_markdown('```python\nx = 1\n```')
        self.assertIn('data-lang="python"', html)

    def test_inline_math_protected(self):
        html, _ = render_markdown('We have $x^2$ inline.')
        # Should keep the $...$ inside a math-inline span for KaTeX
        self.assertIn('math-inline', html)
        self.assertIn('$x^2$', html)

    def test_display_math_protected(self):
        html, _ = render_markdown('Block:\n\n$$y = mx + b$$')
        self.assertIn('math-display', html)

    def test_lazy_load_added_to_images(self):
        html, _ = render_markdown('![alt](http://example.com/img.png)')
        self.assertIn('loading="lazy"', html)

    def test_estimate_reading_time(self):
        # ~200 words → 1 minute
        body_one_min = 'word ' * 200
        self.assertEqual(estimate_reading_time(body_one_min), 1)
        # 700 words → ceil(700/200) = 4 minutes
        body_four_min = 'word ' * 700
        self.assertEqual(estimate_reading_time(body_four_min), 4)
        # Empty body → 1 (minimum)
        self.assertEqual(estimate_reading_time(''), 1)


class SidenotesTests(TestCase):
    def test_explainer_transforms_footnotes_to_sidenotes(self):
        src = ('A claim[^one] worth checking.\n\n'
               '[^one]: Source: Vaswani et al., 2017.')
        html, _ = render_markdown(src, is_explainer=True)
        # Sidenotes get wrapped in a span or aside with sidenote class
        # (exact element depends on the transform; we check for the marker)
        self.assertIn('sidenote', html.lower())

    def test_regular_post_keeps_footnotes_as_footnotes(self):
        src = ('A claim[^one].\n\n[^one]: Citation here.')
        html, _ = render_markdown(src, is_explainer=False)
        # Standard markdown footnote rendering
        self.assertIn('footnote', html.lower())


class CitationsTests(TestCase):
    """The site uses inline <cite class="ref" data-key="..."> markup that
    JavaScript turns into hover popovers. Markdown should preserve it."""

    def test_cite_tag_passes_through(self):
        src = 'Per <cite class="ref" data-key="harvey2024">[1]</cite>, the result holds.'
        html, _ = render_markdown(src)
        self.assertIn('<cite class="ref" data-key="harvey2024">[1]</cite>', html)


class PyFigTests(TestCase):
    """python pyfig blocks: detection, hashing, subprocess invocation,
    error path, cache hit. Subprocess is mocked so tests don't need
    matplotlib installed in the CI environment."""

    def test_pyfig_block_is_detected(self):
        # _render_pyfig now returns the inline figure HTML directly
        # (SVG preferred, base64 PNG fallback) — no /media/ URL.
        src = '```python pyfig\nx = 1\n```'
        with mock.patch('portfolio.blog._render_pyfig') as m:
            m.return_value = ('<svg role="img" aria-label="">FAKE-SVG</svg>', None)
            out = _process_pyfig_blocks(src)
            m.assert_called_once()
            self.assertIn('<figure class="pyfig">', out)
            self.assertIn('FAKE-SVG', out)
            self.assertIn('<summary>source</summary>', out)
            self.assertIn('<details', out)
            # Pygments-highlighted, not raw <code>
            self.assertIn('<div class="highlight">', out)

    def test_pyfig_caption_extracted_from_first_line(self):
        src = '```python pyfig\n# caption: A tasty figure.\nplt.plot([1,2])\n```'
        with mock.patch('portfolio.blog._render_pyfig') as m:
            m.return_value = ('<svg>x</svg>', None)
            out = _process_pyfig_blocks(src)
            self.assertIn('A tasty figure.', out)
            # The caption is passed to _render_pyfig as the alt text
            # so it lands as aria-label on the SVG (or alt= on the PNG).
            self.assertEqual(m.call_args.kwargs.get('alt'), 'A tasty figure.')
            # The caption comment line should be stripped from the source
            # pre block (only the actual code remains in the <details>)
            self.assertNotIn('# caption: A tasty figure.', out)

    def test_pyfig_error_uses_banner_with_collapsed_source(self):
        """Error path renders a compact banner + a collapsed <details>
        for the source. No raw code spills into the post by default."""
        src = '```python pyfig\nthis_breaks\n```'
        with mock.patch('portfolio.blog._render_pyfig') as m:
            m.return_value = (None, "NameError: name 'this_breaks' is not defined")
            out = _process_pyfig_blocks(src)
            self.assertIn('pyfig--error', out)
            self.assertIn('NameError', out)
            self.assertIn('Figure failed to render', out)
            # Source is in a collapsed <details>, not free-floating
            self.assertIn('<details class="pyfig-source"', out)
            self.assertIn('this_breaks', out)

    def test_pyfig_persistence_skipped_on_pyfig_error(self):
        """When any pyfig block errors, render_markdown should append to
        the errors_out list — the post_save signal uses this to skip
        persisting a render with a "Figure failed to render" banner
        frozen in. Without this guard, a one-time matplotlib hiccup
        would freeze a broken figure into the DB until the next save."""
        src = '# t\n\n```python pyfig\nthis_breaks\n```'
        with mock.patch('portfolio.blog._render_pyfig') as m:
            m.return_value = (None, 'NameError')
            errors = []
            html, _ = render_markdown(src, errors_out=errors)
            self.assertEqual(len(errors), 1)
            self.assertIn('NameError', errors[0])
            # Successful path appends nothing
            errors2 = []
            m.return_value = ('<svg>ok</svg>', None)
            render_markdown(src, errors_out=errors2)
            self.assertEqual(errors2, [])

    def test_get_all_posts_skips_html_render_for_speed(self):
        """Listings should not pay the markdown-render cost. content_html
        is empty; full render happens in get_post() per-post-view."""
        from portfolio.blog import get_all_posts, invalidate_post_cache
        from portfolio.tests._helpers import make_post
        invalidate_post_cache()
        make_post(slug='cheap-listing', title='Cheap', body='# H\n\ntext.')
        listing = get_all_posts()
        for p in listing:
            self.assertEqual(p['content_html'], '',
                             msg=f'{p["slug"]} should not have content_html in listing')

    def test_get_post_renders_html_fresh_each_call(self):
        """get_post is uncached; pyfig file-cache makes hot calls cheap.
        Important so a fixed pyfig env (e.g. matplotlib install) doesn't
        leave stale cached errors visible."""
        from portfolio.blog import get_post
        from portfolio.tests._helpers import make_post
        make_post(slug='render-fresh', title='X', body='# Heading\n\nbody.')
        p = get_post('render-fresh')
        self.assertIn('<h1', p['content_html'])

    def test_pyfig_render_pipeline_replaces_block_with_figure(self):
        """End-to-end: render_markdown turns pyfig into a <figure>
        containing the inline rendered figure (SVG or base64 PNG) and
        a collapsible source <details>."""
        src = '# title\n\n```python pyfig\nplt.plot([1,2])\n```\n\nend.'
        with mock.patch('portfolio.blog._render_pyfig') as m:
            m.return_value = ('<svg role="img"><g>FAKE</g></svg>', None)
            html, _ = render_markdown(src)
        self.assertIn('<svg', html)
        self.assertIn('FAKE', html)
        self.assertNotIn('python pyfig', html)
        self.assertIn('pyfig-source', html)

    def test_get_post_uses_persisted_rendered_html_when_fresh(self):
        """When Post.rendered_html is set and not stale, get_post should
        return it without invoking the markdown render path."""
        from portfolio.tests._helpers import make_post
        from portfolio.blog import get_post
        from portfolio.models import Post
        from django.utils import timezone
        make_post(slug='persisted', title='P', body='# body\n\nstuff.')
        # Stamp a custom rendered_html that doesn't match what render
        # would produce; if get_post truly uses the stored field, we'll
        # see this string back.
        sentinel = '<p>STORED-HTML-SENTINEL</p>'
        Post.objects.filter(slug='persisted').update(
            rendered_html=sentinel,
            rendered_toc_html='',
            rendered_at=timezone.now(),
        )
        with mock.patch('portfolio.blog.render_markdown') as m:
            p = get_post('persisted')
            m.assert_not_called()
        self.assertEqual(p['content_html'], sentinel)
