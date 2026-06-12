"""Per-post asset gating: KaTeX and pygments.css load only on posts
whose rendered HTML actually needs them (blog._content_flags). The flags
derive from the exact content_html string the template renders, so a
false negative (raw $…$ shown unstyled) cannot happen by construction.
"""
from django.templatetags.static import static
from django.test import TestCase

from portfolio.blog import _content_flags

from ._helpers import StaffClientMixin, make_post

# The stacked-notes script tag carries these URLs as data attributes on
# EVERY post page (for per-column lazy loading), so gating assertions
# must match the actual load tags, not bare URL substrings.
KATEX_JS_TAG = f'<script defer src="{static("portfolio/vendor/katex/katex.min.js")}">'
KATEX_CSS_TAG = f'<link rel="stylesheet" href="{static("portfolio/vendor/katex/katex.min.css")}">'
PYGMENTS_TAG = f'<link rel="stylesheet" href="{static("portfolio/css/pygments.css")}">'


class ContentFlagTests(TestCase):
    def test_math_flags(self):
        self.assertTrue(_content_flags('<span class="math-inline">$x$</span>')['has_math'])
        self.assertTrue(_content_flags('<div class="math-display">$$y$$</div>')['has_math'])
        self.assertFalse(_content_flags('<p>plain prose, $5 worth</p>')['has_math'])

    def test_code_flags(self):
        self.assertTrue(_content_flags('<div class="highlight"><pre>x</pre></div>')['has_code'])
        self.assertFalse(_content_flags('<p>no code here</p>')['has_code'])

    def test_escaped_markup_in_code_does_not_false_positive(self):
        # Markup typed inside a code block is HTML-escaped in content_html
        # and must not trigger the math flag.
        escaped = '&lt;span class=&quot;math-inline&quot;&gt;'
        self.assertFalse(_content_flags(escaped)['has_math'])


class BlogPostAssetGatingTests(StaffClientMixin, TestCase):
    def test_math_post_loads_katex(self):
        make_post(slug='gate-math', body='Euler: $e^{i\\pi} + 1 = 0$ inline.')
        r = self.anon_client.get('/blog/gate-math/')
        self.assertContains(r, KATEX_JS_TAG)
        self.assertContains(r, KATEX_CSS_TAG)

    def test_plain_post_skips_katex_and_pygments(self):
        make_post(slug='gate-plain', body='# Plain\n\nJust prose, nothing fancy.')
        r = self.anon_client.get('/blog/gate-plain/')
        self.assertNotContains(r, KATEX_JS_TAG)
        self.assertNotContains(r, KATEX_CSS_TAG)
        self.assertNotContains(r, PYGMENTS_TAG)

    def test_code_post_loads_pygments(self):
        make_post(slug='gate-code', body='# Code\n\n```python\nprint("hi")\n```\n')
        r = self.anon_client.get('/blog/gate-code/')
        self.assertContains(r, PYGMENTS_TAG)

    def test_stacked_notes_carries_lazy_asset_urls(self):
        # Stacked columns fetch OTHER posts in-page; even a math-free
        # host page must hand stacked-notes.js the KaTeX/pygments URLs
        # so it can lazy-load them per column.
        make_post(slug='gate-stack-host', body='# Plain\n\nNo math here.')
        r = self.anon_client.get('/blog/gate-stack-host/')
        self.assertContains(r, 'data-katex-js')
        self.assertContains(r, 'data-katex-autorender')
        self.assertContains(r, 'data-katex-css')
        self.assertContains(r, 'data-pygments-css')
