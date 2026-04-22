"""Tier 1: smart paste + github-snippet embed tests.

Covers three layers:
  * Pure-Python URL detection (portfolio.editor_assist.smart_paste)
  * HTTP endpoint (POST /editor/smart-paste/)
  * Render-time embed expansion (the github_snippet handler inside
    portfolio.blog.embeds)
"""
import json
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase

from portfolio.editor_assist import smart_paste as sp
from portfolio.blog import render_markdown
from portfolio.tests._helpers import StaffClientMixin, make_post


# ─── Pure-module detection ──────────────────────────────────────────

class SmartPasteDetectionTests(TestCase):

    def test_rejects_empty_or_non_url(self):
        self.assertIsNone(sp.detect(''))
        self.assertIsNone(sp.detect(None))
        self.assertIsNone(sp.detect('not a url'))
        self.assertIsNone(sp.detect('ftp://files.example.com/a.pdf'))
        self.assertIsNone(sp.detect('mailto:me@example.com'))

    # arXiv

    def test_arxiv_abs(self):
        r = sp.detect('https://arxiv.org/abs/1706.03762')
        self.assertIsNotNone(r)
        self.assertEqual(r.kind, 'arxiv')
        self.assertEqual(r.marker, '<div data-arxiv="1706.03762"></div>')

    def test_arxiv_with_version(self):
        r = sp.detect('https://arxiv.org/abs/2502.05564v2')
        self.assertEqual(r.marker, '<div data-arxiv="2502.05564v2"></div>')

    def test_arxiv_pdf(self):
        r = sp.detect('https://arxiv.org/pdf/2502.05564.pdf')
        self.assertEqual(r.marker, '<div data-arxiv="2502.05564"></div>')

    def test_arxiv_no_id_nomatch(self):
        self.assertIsNone(sp.detect('https://arxiv.org/about'))

    # GitHub repo

    def test_github_repo(self):
        r = sp.detect('https://github.com/loevlie/neuropt')
        self.assertEqual(r.kind, 'github')
        self.assertEqual(r.marker, '<div data-github="loevlie/neuropt"></div>')

    def test_github_repo_trailing_slash(self):
        r = sp.detect('https://github.com/loevlie/neuropt/')
        self.assertEqual(r.kind, 'github')
        self.assertEqual(r.marker, '<div data-github="loevlie/neuropt"></div>')

    def test_github_not_a_repo_url(self):
        # /blob/ is permalink territory, not a repo card.
        r = sp.detect('https://github.com/loevlie/neuropt/blob/main/README.md')
        self.assertEqual(r.kind, 'github_snippet')
        self.assertNotEqual(r.kind, 'github')

    # GitHub permalink

    def test_github_permalink_single_line(self):
        r = sp.detect('https://github.com/loevlie/neuropt/blob/main/src/main.py#L42')
        self.assertEqual(r.kind, 'github_snippet')
        self.assertIn('#L42-L42', r.marker)
        self.assertEqual(r.meta['lstart'], 42)
        self.assertEqual(r.meta['lend'], 42)

    def test_github_permalink_range(self):
        r = sp.detect('https://github.com/a/b/blob/abc/src/x.py#L10-L20')
        self.assertEqual(r.kind, 'github_snippet')
        self.assertEqual(r.meta['lstart'], 10)
        self.assertEqual(r.meta['lend'], 20)

    def test_github_permalink_no_lines(self):
        r = sp.detect('https://github.com/a/b/blob/main/x.py')
        self.assertEqual(r.kind, 'github_snippet')
        self.assertIsNone(r.meta['lstart'])

    def test_github_permalink_nested_path(self):
        r = sp.detect('https://github.com/a/b/blob/main/src/deep/nested/x.py#L1')
        self.assertEqual(r.meta['path'], 'src/deep/nested/x.py')

    def test_github_permalink_sha_ref(self):
        r = sp.detect('https://github.com/a/b/blob/abc1234/x.py#L1')
        self.assertEqual(r.meta['ref'], 'abc1234')

    # Wikipedia

    def test_wikipedia_article(self):
        r = sp.detect('https://en.wikipedia.org/wiki/Transformer')
        self.assertEqual(r.kind, 'wiki')
        self.assertEqual(r.marker, '<div data-wiki="Transformer"></div>')

    def test_wikipedia_parens_encoded(self):
        r = sp.detect('https://en.wikipedia.org/wiki/Transformer_(deep_learning_architecture)')
        self.assertEqual(r.kind, 'wiki')
        self.assertIn('Transformer_(deep_learning_architecture)', r.marker)

    def test_wikipedia_non_en(self):
        r = sp.detect('https://de.wikipedia.org/wiki/Transformator')
        self.assertEqual(r.kind, 'wiki')
        self.assertEqual(r.meta['lang'], 'de')

    def test_wikipedia_not_article(self):
        r = sp.detect('https://en.wikipedia.org/about')
        self.assertIsNone(r)

    # Registry priority

    def test_permalink_wins_over_repo(self):
        # Regression guard: the permalink regex is a superset of the
        # repo regex; detection order ensures we don't downgrade a
        # snippet-worthy URL into a repo card.
        r = sp.detect('https://github.com/a/b/blob/main/x.py#L1-L5')
        self.assertEqual(r.kind, 'github_snippet')


# ─── HTTP layer ─────────────────────────────────────────────────────

class SmartPasteViewTests(StaffClientMixin, TestCase):

    def _post(self, client, body):
        return client.post(
            '/editor/smart-paste/',
            data=json.dumps(body),
            content_type='application/json',
        )

    def test_staff_match(self):
        r = self._post(self.staff_client, {'url': 'https://arxiv.org/abs/1706.03762'})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d['ok'])
        self.assertEqual(d['match']['kind'], 'arxiv')
        self.assertEqual(d['match']['marker'], '<div data-arxiv="1706.03762"></div>')

    def test_staff_no_match(self):
        r = self._post(self.staff_client, {'url': 'https://example.com/foo'})
        d = r.json()
        self.assertTrue(d['ok'])
        self.assertIsNone(d['match'])

    def test_anon_rejected(self):
        r = self._post(self.anon_client, {'url': 'https://arxiv.org/abs/1706.03762'})
        self.assertEqual(r.status_code, 403)

    def test_get_rejected(self):
        r = self.staff_client.get('/editor/smart-paste/')
        self.assertEqual(r.status_code, 405)

    def test_bad_json_rejected(self):
        r = self.staff_client.post(
            '/editor/smart-paste/', data='gibberish', content_type='application/json',
        )
        self.assertEqual(r.status_code, 400)

    def test_missing_url_rejected(self):
        r = self._post(self.staff_client, {})
        self.assertEqual(r.status_code, 400)

    def test_oversized_url_rejected(self):
        r = self._post(self.staff_client, {'url': 'https://example.com/' + 'a' * 2100})
        self.assertEqual(r.status_code, 413)


# ─── GitHub-snippet embed handler ───────────────────────────────────

class GithubSnippetEmbedTests(TestCase):
    """The handler fetches raw file text, slices a line range, and
    feeds it through Pygments. We mock the fetch so tests don't hit
    the network."""

    def setUp(self):
        cache.clear()

    def test_expands_with_fetched_content(self):
        fake = """line 1
line 2
line 3
line 4
line 5
"""
        with patch(
            'portfolio.blog.embeds.github_snippet._fetch',
            return_value=fake,
        ):
            html, _ = render_markdown(
                '<div data-github-snippet="a/b@main:x.py#L2-L4"></div>\n'
            )
        self.assertIn('class="github-snippet"', html)
        self.assertIn('gh-snippet-head', html)
        self.assertIn('gh-snippet-foot', html)
        self.assertIn('a/b', html)
        self.assertIn('L2', html)            # line-range label shows
        # Pygments tokenises each line into spans, so "line 2" isn't a
        # contiguous substring — check for the token + line-number gutter.
        self.assertIn('>2</span>', html)
        self.assertIn('>4</span>', html)
        # Line 5 is past our range and should NOT appear in the snippet.
        self.assertNotIn('>5</span>', html)

    def test_single_line_permalink(self):
        fake = 'alpha\nbeta\ngamma\n'
        with patch(
            'portfolio.blog.embeds.github_snippet._fetch',
            return_value=fake,
        ):
            html, _ = render_markdown(
                '<div data-github-snippet="o/r@main:x.py#L2-L2"></div>\n'
            )
        self.assertIn('beta', html)
        self.assertNotIn('alpha', html)
        self.assertNotIn('gamma', html)

    def test_fallback_on_fetch_failure(self):
        with patch(
            'portfolio.blog.embeds.github_snippet._fetch',
            return_value=None,
        ):
            html, _ = render_markdown(
                '<div data-github-snippet="o/r@main:x.py#L1-L5"></div>\n'
            )
        # Fallback card still links to the permalink so the reader can
        # click through.
        self.assertIn('github.com/o/r/blob/main/x.py', html)
        self.assertIn('Snippet unavailable', html)

    def test_fetch_cached_after_first_render(self):
        fake = 'x\n'
        marker = '<div data-github-snippet="owner/repo@sha:x.py#L1-L1"></div>\n'
        with patch(
            'portfolio.blog.embeds.github_snippet._fetch',
            return_value=fake,
        ) as m:
            render_markdown(marker)
            render_markdown(marker)
        self.assertEqual(m.call_count, 1)

    def test_github_snippet_wins_over_plain_github_in_dispatcher(self):
        """If a document has both a `data-github` and a
        `data-github-snippet` marker, the snippet handler must fire
        for the snippet marker without the plain-github regex
        swallowing it."""
        with patch(
            'portfolio.blog.embeds.github_snippet._fetch',
            return_value='hello\n',
        ):
            with patch('portfolio.blog.embeds.github._fetch') as gh_fetch:
                gh_fetch.return_value = None
                html, _ = render_markdown(
                    '<div data-github-snippet="o/r@main:x.py#L1-L1"></div>\n\n'
                    '<div data-github="o/r"></div>\n'
                )
        self.assertIn('github-snippet', html)
        # The plain-github card falls back (fetch returned None), so the
        # embed-card chrome appears — both should coexist in the output.
        self.assertIn('embed-card', html)

    def test_path_cap_on_giant_range(self):
        """A 1000-line range should be capped to our _MAX_LINES (80)
        so posts don't balloon when an author permalinks a huge file
        section."""
        big = '\n'.join(f'line {i}' for i in range(1, 1001))
        with patch(
            'portfolio.blog.embeds.github_snippet._fetch',
            return_value=big,
        ):
            html, _ = render_markdown(
                '<div data-github-snippet="o/r@main:x.py#L10-L900"></div>\n'
            )
        # 80 is the cap in the module. Verify first and 89th line
        # gutters are present (Pygments tokenises the content itself).
        self.assertIn('>10</span>', html)
        self.assertIn('>89</span>', html)
        # Line 90 is one past the cap and the 900th definitely shouldn't
        # be there.
        self.assertNotIn('>90</span>', html)
        self.assertNotIn('>900</span>', html)
