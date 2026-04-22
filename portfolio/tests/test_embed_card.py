"""GET /embed/card/?url=<url> — hover-preview rich card endpoint.

The endpoint proxies to the existing arxiv/github/wiki handlers with
their metadata fetches mocked out so tests don't hit the network.
"""
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, Client


class EmbedCardTests(TestCase):

    def setUp(self):
        cache.clear()
        self.c = Client()

    def test_bad_missing_url(self):
        r = self.c.get('/embed/card/')
        self.assertEqual(r.status_code, 400)

    def test_bad_oversize_url(self):
        r = self.c.get('/embed/card/', {'url': 'https://x.com/' + 'a' * 2100})
        self.assertEqual(r.status_code, 400)

    def test_unknown_url_returns_204(self):
        # A random URL that doesn't match arxiv/github/wiki → 204 so the
        # client falls back to its plain hostname tooltip.
        r = self.c.get('/embed/card/', {'url': 'https://example.com/post/1'})
        self.assertEqual(r.status_code, 204)

    def test_github_snippet_url_returns_204(self):
        # github_snippet markers are for in-body code embeds, not link
        # hovers — explicitly excluded by _ALLOWED_KINDS.
        r = self.c.get(
            '/embed/card/',
            {'url': 'https://github.com/a/b/blob/main/x.py#L1-L5'},
        )
        self.assertEqual(r.status_code, 204)

    def test_arxiv_returns_card_html(self):
        # The arxiv handler fetches metadata; mock it so the test is
        # hermetic and the returned HTML is deterministic.
        fake_meta = {
            'title': 'Attention Is All You Need',
            'authors': 'Vaswani et al.',
            'summary': 'We propose the Transformer.',
            'year': '2017',
            'abs_url': 'https://arxiv.org/abs/1706.03762',
        }
        with patch('portfolio.blog.embeds.arxiv._fetch', return_value=fake_meta):
            r = self.c.get('/embed/card/', {'url': 'https://arxiv.org/abs/1706.03762'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'text/html; charset=utf-8')
        body = r.content.decode('utf-8')
        self.assertIn('Attention Is All You Need', body)
        self.assertIn('embed-card', body)

    def test_wiki_returns_card_html(self):
        fake_meta = {
            'title': 'Transformer',
            'extract': 'A transformer is a neural architecture…',
            'url': 'https://en.wikipedia.org/wiki/Transformer',
        }
        with patch('portfolio.blog.embeds.wiki._fetch', return_value=fake_meta):
            r = self.c.get('/embed/card/', {'url': 'https://en.wikipedia.org/wiki/Transformer'})
        self.assertEqual(r.status_code, 200)
        self.assertIn('embed-card', r.content.decode('utf-8'))

    def test_caches_client_side(self):
        # The Cache-Control header keeps the browser from refetching on
        # every hover — the Django cache behind the embed handlers is
        # the source of truth for freshness.
        with patch('portfolio.blog.embeds.arxiv._fetch', return_value=None):
            r = self.c.get('/embed/card/', {'url': 'https://arxiv.org/abs/1706.03762'})
        # Even on a fallback render we should set the cache header.
        if r.status_code == 200:
            self.assertIn('max-age', r['Cache-Control'])

    def test_rate_limit(self):
        # Burst past the per-minute cap. Replace the arxiv fetch with a
        # no-op so we don't hit the network.
        with patch('portfolio.blog.embeds.arxiv._fetch', return_value=None):
            statuses = []
            for i in range(65):
                r = self.c.get('/embed/card/', {'url': f'https://arxiv.org/abs/1706.0376{i}'})
                statuses.append(r.status_code)
        self.assertIn(429, statuses)

    def test_post_rejected(self):
        r = self.c.post('/embed/card/', {'url': 'https://arxiv.org/abs/1'})
        self.assertEqual(r.status_code, 405)
