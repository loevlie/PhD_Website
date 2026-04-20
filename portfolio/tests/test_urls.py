"""All public URLs return expected status codes for both anon and staff users.

This is a fast smoke layer that catches any regression where a route
breaks at the import / URL resolution level. Per-feature tests cover the
content of each response.
"""
from django.test import TestCase

from ._helpers import StaffClientMixin, make_post, REAL_BROWSER_UA


PUBLIC_URLS = [
    '/',
    '/blog/',
    '/blog/feed/',
    '/publications/',
    '/projects/',
    '/recipes/',
    '/demos/',
    '/now/',
    '/garden/',
    '/cv/',
    '/cv.pdf',  # 200 (or 302 to upstream on network failure)
    '/tags/',
    '/sitemap.xml',
    '/robots.txt',
    '/googled2e3ddb216daf4c4.html',
]


STAFF_ONLY_URLS = [
    '/blog/new/',
    '/site/insights/',
]


class PublicUrlsRespondTests(StaffClientMixin, TestCase):
    """Every public URL returns 200 (or a documented redirect) for anon."""

    @classmethod
    def setUpTestData(cls):
        cls.post = make_post(slug='hello-world', title='Hello world')

    def test_public_urls_anon(self):
        for url in PUBLIC_URLS:
            with self.subTest(url=url):
                r = self.anon_client.get(url, HTTP_USER_AGENT=REAL_BROWSER_UA)
                # /cv.pdf may 200 (cached) or 302 (upstream redirect on network fail)
                if url == '/cv.pdf':
                    self.assertIn(r.status_code, (200, 302),
                                  msg=f'{url} returned {r.status_code}')
                else:
                    self.assertEqual(r.status_code, 200, msg=f'{url} returned {r.status_code}')

    def test_blog_post_url(self):
        r = self.anon_client.get(f'/blog/{self.post.slug}/')
        self.assertEqual(r.status_code, 200)

    def test_blog_post_404_for_unknown_slug(self):
        r = self.anon_client.get('/blog/does-not-exist-xyz/')
        self.assertEqual(r.status_code, 404)

    def test_demo_detail_known(self):
        # frozen-forecaster ships in DEMOS
        r = self.anon_client.get('/demos/frozen-forecaster/')
        self.assertEqual(r.status_code, 200)

    def test_demo_detail_404_for_unknown_slug(self):
        r = self.anon_client.get('/demos/does-not-exist-xyz/')
        self.assertEqual(r.status_code, 404)

    def test_tag_detail_known(self):
        post = make_post(slug='tag-test', title='Tag test', tags=['ml', 'tabular'])
        r = self.anon_client.get('/tags/ml/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Tag test')

    def test_tag_detail_404_for_unknown_tag(self):
        r = self.anon_client.get('/tags/no-such-tag-xyz/')
        self.assertEqual(r.status_code, 404)


class StaffOnlyUrlsTests(StaffClientMixin, TestCase):
    """Staff-only URLs redirect to admin login when accessed by anon."""

    def test_staff_only_urls_anon_redirect(self):
        for url in STAFF_ONLY_URLS:
            with self.subTest(url=url):
                r = self.anon_client.get(url)
                self.assertEqual(r.status_code, 302, msg=f'{url} did not redirect')
                self.assertIn('/admin/login/', r.headers.get('Location', ''),
                              msg=f'{url} did not redirect to login')

    def test_staff_only_urls_staff_ok(self):
        for url in STAFF_ONLY_URLS:
            with self.subTest(url=url):
                r = self.staff_client.get(url)
                # blog_new with no template returns the picker (200)
                self.assertEqual(r.status_code, 200, msg=f'{url} returned {r.status_code}')

    def test_blog_edit_anon_redirect(self):
        post = make_post(slug='edit-me')
        r = self.anon_client.get(f'/blog/{post.slug}/edit/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/admin/login/', r.headers.get('Location', ''))

    def test_blog_edit_staff_ok(self):
        post = make_post(slug='edit-me-too')
        r = self.staff_client.get(f'/blog/{post.slug}/edit/')
        self.assertEqual(r.status_code, 200)
