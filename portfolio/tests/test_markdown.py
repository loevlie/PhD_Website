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
        src = '```python pyfig\nx = 1\n```'
        with mock.patch('portfolio.blog._render_pyfig') as m:
            m.return_value = ('/media/blog-images/python/abc.png', None)
            out = _process_pyfig_blocks(src)
            m.assert_called_once()
            self.assertIn('<figure class="pyfig">', out)
            self.assertIn('/media/blog-images/python/abc.png', out)
            self.assertIn('view source', out)
            self.assertIn('<details', out)

    def test_pyfig_caption_extracted_from_first_line(self):
        src = '```python pyfig\n# caption: A tasty figure.\nplt.plot([1,2])\n```'
        with mock.patch('portfolio.blog._render_pyfig') as m:
            m.return_value = ('/media/x.png', None)
            out = _process_pyfig_blocks(src)
            self.assertIn('A tasty figure.', out)
            # The caption comment line should be stripped from the source pre block
            # (only the actual code remains in the <details>)
            # caption is HTML escaped so check the text
            self.assertNotIn('# caption: A tasty figure.', out)

    def test_pyfig_error_keeps_source_visible(self):
        src = '```python pyfig\nthis_breaks\n```'
        with mock.patch('portfolio.blog._render_pyfig') as m:
            m.return_value = (None, "NameError: name 'this_breaks' is not defined")
            out = _process_pyfig_blocks(src)
            self.assertIn('callout--error', out)
            self.assertIn('NameError', out)
            self.assertIn('this_breaks', out)

    def test_pyfig_cache_hit_skips_subprocess(self):
        """When the PNG already exists, no subprocess call is made."""
        from pathlib import Path
        from django.conf import settings as dj_settings
        # Pre-create the cached file
        code = 'import matplotlib.pyplot as plt\nplt.plot([1,2,3])'
        h = hashlib.sha256(code.encode()).hexdigest()[:16]
        out_dir = Path(dj_settings.MEDIA_ROOT) / 'blog-images' / 'python'
        out_dir.mkdir(parents=True, exist_ok=True)
        cached = out_dir / f'{h}.png'
        cached.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\0' * 100)
        try:
            with mock.patch('subprocess.run') as m:
                url, err = _render_pyfig(code)
                self.assertIsNone(err)
                self.assertIn(h, url)
                m.assert_not_called()
        finally:
            cached.unlink(missing_ok=True)

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
        """End-to-end: render_markdown turns pyfig into a <figure> with
        the rendered image and a collapsible source <details>."""
        src = '# title\n\n```python pyfig\nplt.plot([1,2])\n```\n\nend.'
        with mock.patch('portfolio.blog._render_pyfig') as m:
            m.return_value = ('/media/blog-images/python/zzz.png', None)
            html, _ = render_markdown(src)
        self.assertIn('<img', html)
        self.assertIn('/media/blog-images/python/zzz.png', html)
        self.assertNotIn('python pyfig', html)
        self.assertIn('pyfig-source', html)
