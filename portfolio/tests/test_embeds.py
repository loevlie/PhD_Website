"""Tests for the blog-embed dispatcher and its handlers.

The external-API handlers (arxiv/github/wiki) use the `unittest.mock`
library to skip actual network requests — we assert shape, not
content. Offline fallback behavior is also exercised.
"""
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase

from portfolio.blog import render_markdown
from portfolio.blog.embeds import expand_embeds


class DispatcherTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_empty_content_is_fastpath(self):
        out = expand_embeds('just plain text with no markers at all')
        self.assertEqual(out, 'just plain text with no markers at all')

    def test_multiple_handler_types_in_one_doc(self):
        body = (
            '<div data-demo="frozen-forecaster"></div>\n\n'
            '<div data-equation data-explain="x=input">$$y = x$$</div>\n'
        )
        out = expand_embeds(body)
        self.assertIn('demo-embed-root', out)
        self.assertIn('equation-annotated', out)


class EquationMarkerTests(TestCase):
    def test_equation_with_explain(self):
        body = (
            '<div data-equation data-explain="theta=parameters; x=input">\n'
            '$$y = \\theta^\\top x$$\n'
            '</div>\n'
        )
        html, _ = render_markdown(body)
        self.assertIn('class="equation-annotated"', html)
        self.assertIn('data-glossary', html)
        self.assertIn('theta', html)

    def test_equation_without_explain_still_works(self):
        body = '<div data-equation>$$y = 2x$$</div>\n'
        html, _ = render_markdown(body)
        self.assertIn('class="equation-annotated"', html)


class QuizMarkerTests(TestCase):
    def test_quiz_renders_options(self):
        body = (
            '<div data-quiz>\n'
            'q: What is 2+2?\n'
            'options:\n'
            '  - 3\n'
            '  - 4\n'
            '  - 5\n'
            'answer: 1\n'
            'explain: Two plus two equals four.\n'
            '</div>\n'
        )
        html, _ = render_markdown(body)
        self.assertIn('class="quiz-card"', html)
        self.assertIn('What is 2+2?', html)
        self.assertIn('data-correct="true"', html)
        self.assertIn('quiz-explain', html)

    def test_malformed_quiz_shows_error(self):
        body = '<div data-quiz>nothing parseable</div>\n'
        html, _ = render_markdown(body)
        self.assertIn('demo-embed-error', html)


class ArxivMarkerTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_arxiv_renders_fallback_on_network_failure(self):
        body = '<div data-arxiv="2502.05564"></div>\n'
        with patch('portfolio.blog.embeds.arxiv._fetch', return_value=None):
            html, _ = render_markdown(body)
        # Fallback: id is shown, page link is present.
        self.assertIn('arxiv.org/abs/2502.05564', html)
        self.assertIn('embed-card', html)

    def test_arxiv_renders_full_card_when_fetch_succeeds(self):
        body = '<div data-arxiv="2502.05564"></div>\n'
        fake = {
            'title': 'Attention Is All You Need',
            'summary': 'We propose transformers. They are nice. More sentences.',
            'authors': ['A. Vaswani', 'N. Shazeer', 'N. Parmar'],
            'year': '2017',
        }
        with patch('portfolio.blog.embeds.arxiv._fetch', return_value=fake):
            html, _ = render_markdown(body)
        self.assertIn('Attention Is All You Need', html)
        self.assertIn('A. Vaswani', html)
        self.assertIn('embed-pill', html)


class GithubMarkerTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_github_renders_card(self):
        body = '<div data-github="loevlie/neuropt"></div>\n'
        fake = {
            'name': 'neuropt', 'full_name': 'loevlie/neuropt',
            'description': 'Optimization via LLMs.',
            'language': 'Python', 'stars': 42, 'forks': 0,
            'url': 'https://github.com/loevlie/neuropt',
        }
        with patch('portfolio.blog.embeds.github._fetch', return_value=fake):
            html, _ = render_markdown(body)
        self.assertIn('loevlie/neuropt', html)
        self.assertIn('★ 42', html)
        self.assertIn('embed-lang-dot--python', html)


class WikiMarkerTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_wiki_renders_card(self):
        body = '<div data-wiki="Transformer_(deep_learning_architecture)"></div>\n'
        fake = {
            'title': 'Transformer (deep learning architecture)',
            'extract': 'A transformer is a deep-learning architecture.',
            'url': 'https://en.wikipedia.org/wiki/Transformer_(deep_learning_architecture)',
            'thumbnail': '',
        }
        with patch('portfolio.blog.embeds.wiki._fetch', return_value=fake):
            html, _ = render_markdown(body)
        self.assertIn('Wikipedia', html)
        self.assertIn('deep-learning architecture', html)


class PlotMarkerTests(TestCase):
    def test_plot_inlines_spec(self):
        body = (
            '<div data-plot>\n'
            '{"mark": "point", "data": {"values": [{"x": 1, "y": 2}]}}\n'
            '</div>\n'
        )
        html, _ = render_markdown(body)
        self.assertIn('class="vega-plot"', html)
        self.assertIn('data-spec', html)

    def test_plot_with_invalid_json_shows_error(self):
        body = '<div data-plot>not json</div>\n'
        html, _ = render_markdown(body)
        self.assertIn('demo-embed-error', html)
        self.assertIn('Invalid Vega-Lite JSON', html)


class CacheBehaviorTests(TestCase):
    """External-API markers cache their results. A successful lookup
    cached once should satisfy a second render without calling the
    network again."""

    def setUp(self):
        cache.clear()

    def test_arxiv_second_render_hits_cache(self):
        body = '<div data-arxiv="1706.03762"></div>\n'
        fake = {
            'title': 'Attention', 'summary': 'x.',
            'authors': ['A'], 'year': '2017',
        }
        with patch('portfolio.blog.embeds.arxiv._fetch', return_value=fake) as fetch:
            render_markdown(body)
            render_markdown(body)
        self.assertEqual(fetch.call_count, 1)


class BlogMapTests(TestCase):
    """/blog/map/ renders without 500-ing when there are no posts, and
    includes a <script id=blog-graph-data> JSON payload when there are."""

    def test_empty_state(self):
        from django.test import Client
        r = Client().get('/blog/map/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'blog-graph-data')

    def test_with_posts(self):
        from django.test import Client
        from portfolio.tests._helpers import make_post
        make_post(slug='alpha', title='Alpha')
        make_post(slug='beta', title='Beta', body='link to [/blog/alpha/](/blog/alpha/)')
        r = Client().get('/blog/map/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'alpha')
        self.assertContains(r, 'beta')


class BibExportTests(TestCase):
    def test_bib_citation_id_stable(self):
        from django.test import Client
        from portfolio.tests._helpers import make_post
        make_post(slug='my-paper', title='A deep dive into attention')
        r = Client().get('/blog/my-paper/cite.bib')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'@misc{', r.content)
        self.assertIn('inline; filename=', r.headers['Content-Disposition'])
        self.assertIn(b'howpublished', r.content)

    def test_bib_for_missing_post_404s(self):
        from django.test import Client
        r = Client().get('/blog/does-not-exist/cite.bib')
        self.assertEqual(r.status_code, 404)


class NewPostTemplateTests(TestCase):
    """The four new /blog/new/ templates all create valid drafts."""

    def setUp(self):
        from django.test import Client
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user('staff', password='p', is_staff=True, is_superuser=True)
        self.client = Client()
        self.client.force_login(self.user)

    def test_deepdive_template(self):
        from portfolio.models import Post
        # POST-only creation; GET would duplicate drafts on refresh.
        r = self.client.post('/blog/new/', {'template': 'deepdive'})
        self.assertEqual(r.status_code, 302)
        p = Post.objects.order_by('-id').first()
        self.assertTrue(p.is_explainer)
        self.assertIn('data-arxiv', p.body)
        self.assertIn('data-quiz', p.body)

    def test_livenotes_template(self):
        from portfolio.models import Post
        r = self.client.post('/blog/new/', {'template': 'livenotes'})
        self.assertEqual(r.status_code, 302)
        p = Post.objects.order_by('-id').first()
        self.assertIn('**Status:** thinking', p.body)

    def test_thread_template(self):
        from portfolio.models import Post
        r = self.client.post('/blog/new/', {'template': 'thread'})
        self.assertEqual(r.status_code, 302)
        p = Post.objects.order_by('-id').first()
        self.assertIn('**1/**', p.body)

    def test_arxiv_template_with_id(self):
        from portfolio.models import Post
        with patch('portfolio.blog.embeds.arxiv._fetch', return_value={
            'title': 'Attention Is All You Need',
            'summary': 'x.', 'authors': ['A'], 'year': '2017',
        }):
            r = self.client.post('/blog/new/', {'template': 'arxiv', 'arxiv': '1706.03762'})
        self.assertEqual(r.status_code, 302)
        p = Post.objects.order_by('-id').first()
        self.assertIn('Attention Is All You Need', p.title)
        self.assertIn('<div data-arxiv="1706.03762">', p.body)
