"""Tag pages, demo detail pages, /cv/ inline + /cv.pdf download."""
from django.test import TestCase

from portfolio.data import DEMOS

from ._helpers import make_post


class TagPagesTests(TestCase):
    def setUp(self):
        self.p1 = make_post(slug='post-1', title='Post one',
                            tags=['ml', 'tabular'], days_ago=1)
        self.p2 = make_post(slug='post-2', title='Post two',
                            tags=['ml'], days_ago=2)
        self.p3 = make_post(slug='post-3', title='Post three',
                            tags=['rust'], days_ago=3)

    def test_tag_index_lists_tags_with_counts(self):
        r = self.client.get('/tags/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'ml')
        self.assertContains(r, 'tabular')
        self.assertContains(r, 'rust')
        # Total post count visible
        self.assertContains(r, '3 posts')

    def test_tag_detail_filters_to_matching_posts(self):
        r = self.client.get('/tags/ml/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Post one')
        self.assertContains(r, 'Post two')
        self.assertNotContains(r, 'Post three')

    def test_tag_detail_unknown_returns_404(self):
        r = self.client.get('/tags/no-such-tag-xyz/')
        self.assertEqual(r.status_code, 404)

    def test_tag_detail_count_correct(self):
        r = self.client.get('/tags/ml/')
        self.assertContains(r, '2 posts')

    def test_tag_chip_links_to_tag_page(self):
        r = self.client.get(f'/blog/{self.p1.slug}/')
        # Tag chip is an <a> linking to /tags/ml/
        self.assertContains(r, 'href="/tags/ml/"')


class DemoDetailTests(TestCase):
    def test_every_demo_has_a_detail_page(self):
        for d in DEMOS:
            with self.subTest(slug=d['slug']):
                r = self.client.get(f'/demos/{d["slug"]}/')
                self.assertEqual(r.status_code, 200,
                                 msg=f'demo {d["slug"]} returned {r.status_code}')
                self.assertContains(r, d['title'])
                self.assertContains(r, d['summary'])

    def test_unknown_demo_404s(self):
        r = self.client.get('/demos/nonexistent-demo-xyz/')
        self.assertEqual(r.status_code, 404)

    def test_demo_detail_has_back_link(self):
        r = self.client.get('/demos/frozen-forecaster/')
        self.assertContains(r, '/demos/')

    def test_demo_detail_includes_what_why_learned(self):
        r = self.client.get('/demos/frozen-forecaster/')
        self.assertContains(r, 'What')
        self.assertContains(r, 'Why')
        self.assertContains(r, 'What I learned')

    def test_demo_detail_links_to_companion_post_if_exists(self):
        # Make a companion post matching the demo slug
        make_post(slug='frozen-forecaster', title='Frozen Forecaster post')
        r = self.client.get('/demos/frozen-forecaster/')
        self.assertContains(r, 'Companion essay')


class CvPageTests(TestCase):
    def test_cv_page_renders(self):
        r = self.client.get('/cv/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Curriculum Vitae')
        # Embeds the upstream PDF URL
        self.assertContains(r, 'loevlie.github.io/cv/loevlie-cv-latest.pdf')
        # Has a download button pointing at /cv.pdf
        self.assertContains(r, '/cv.pdf')
        # Has a "View source" link to the GitHub repo
        self.assertContains(r, 'github.com/loevlie/cv')

    def test_cv_pdf_download_returns_pdf_or_redirects(self):
        # /cv.pdf either returns 200 with the PDF (network ok) or 302 to upstream
        r = self.client.get('/cv.pdf')
        self.assertIn(r.status_code, (200, 302))
        if r.status_code == 200:
            self.assertEqual(r.headers.get('Content-Type'), 'application/pdf')
            self.assertIn('attachment', r.headers.get('Content-Disposition', ''))

    def test_cv_page_no_longer_serves_pdf(self):
        """Sanity: hitting /cv/ should be HTML, not PDF (we moved download
        to /cv.pdf)."""
        r = self.client.get('/cv/')
        ct = r.headers.get('Content-Type', '')
        self.assertNotIn('pdf', ct.lower())
        self.assertIn('html', ct.lower())
