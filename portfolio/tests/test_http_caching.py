"""HTTP caching layer: CacheHeadersMiddleware defaults, per-view
Cache-Control overrides, NoTransformGZipMiddleware, ConditionalGet
ETag/304 handling, and context-processor laziness.

Middleware order under test (settings.MIDDLEWARE):
Security, WhiteNoise, NoTransformGZip, ConditionalGet, Session,
Common, Csrf, Auth, Message, XFrame, CacheHeaders — so on the
response phase CacheHeaders runs first (sets defaults), then
ConditionalGet (ETag on the uncompressed body), then gzip.
"""
import gzip
from unittest import mock

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase

from portfolio.middleware import CacheHeadersMiddleware, NoTransformGZipMiddleware

from ._helpers import StaffClientMixin, make_post

ANON_VALUE = 'public, max-age=120, stale-while-revalidate=600'
SESSION_VALUE = 'private, no-cache'

User = get_user_model()


class AnonDefaultHeaderTests(TestCase):
    """(a) anonymous GETs pick up the public short-TTL default."""

    def test_blog_list_gets_anon_default(self):
        r = Client().get('/blog/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers['Cache-Control'], ANON_VALUE)

    def test_blog_list_is_gzipped_for_gzip_clients(self):
        r = Client().get('/blog/', HTTP_ACCEPT_ENCODING='gzip')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get('Content-Encoding'), 'gzip')
        # GZipMiddleware skips bodies <200 bytes — prove ours qualified
        # and that the payload round-trips.
        self.assertGreater(len(gzip.decompress(r.content)), 200)
        # The default header survives compression untouched.
        self.assertEqual(r.headers['Cache-Control'], ANON_VALUE)

    def test_anon_blog_post_gets_anon_default(self):
        post = make_post(slug='cache-anon-post', title='Cache anon post')
        r = Client().get(f'/blog/{post.slug}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers['Cache-Control'], ANON_VALUE)

    def test_anon_signup_page_is_never_publicly_cacheable(self):
        # /accounts/signup/ renders {% csrf_token %} and mints a per-user
        # csrftoken cookie for anonymous visitors — a shared cache that
        # ignores Vary: Cookie would hand one user's CSRF secret to
        # everyone. The middleware must treat it like session traffic.
        r = Client().get('/accounts/signup/')
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('public', r.headers.get('Cache-Control', ''))


class SessionCookieHeaderTests(TestCase):
    """(b) any session-cookie-bearing request gets private, no-cache."""

    def test_logged_in_non_staff_homepage_is_private(self):
        user = User.objects.create_user(
            username='plain-reader', password='test12345')
        c = Client()
        c.force_login(user)
        r = c.get('/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers['Cache-Control'], SESSION_VALUE)

    def test_logged_in_blog_list_is_private(self):
        user = User.objects.create_user(
            username='plain-reader-2', password='test12345')
        c = Client()
        c.force_login(user)
        r = c.get('/blog/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers['Cache-Control'], SESSION_VALUE)


class ViewOverrideTests(StaffClientMixin, TestCase):
    """(c)(e)(h) views that set their own Cache-Control keep it —
    the middleware only fills in when the header is absent."""

    def test_staff_blog_post_keeps_no_store(self):
        # blog_public.blog_post sets this exact header when the viewer
        # can edit the post (staff or collaborator).
        post = make_post(slug='cache-staff-post', title='Cache staff post')
        r = self.staff_client.get(f'/blog/{post.slug}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.headers['Cache-Control'],
            'no-store, no-cache, must-revalidate, max-age=0',
        )
        self.assertNotIn('public', r.headers['Cache-Control'])

    def test_staff_blog_edit_is_no_store(self):
        post = make_post(slug='cache-edit-me', title='Cache edit me')
        r = self.staff_client.get(f'/blog/{post.slug}/edit/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers['Cache-Control'], 'no-store')

    def test_autosave_post_is_never_public(self):
        # POSTs are outside the middleware's GET/HEAD guard entirely.
        post = make_post(slug='cache-auto-me', title='Cache auto me')
        r = self.staff_client.post(f'/blog/{post.slug}/autosave/', {
            'title': 'updated',
            'body': 'updated body',
        })
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('public', r.headers.get('Cache-Control', ''))


class ConditionalGetTests(TestCase):
    """(d) ConditionalGetMiddleware ETags anon GETs and answers
    If-None-Match with 304."""

    def test_anon_homepage_revalidates_to_304(self):
        c = Client()
        r1 = c.get('/')
        self.assertEqual(r1.status_code, 200)
        etag = r1.headers.get('ETag')
        self.assertTrue(etag, 'ConditionalGetMiddleware should set an ETag')
        r2 = c.get('/', HTTP_IF_NONE_MATCH=etag)
        self.assertEqual(r2.status_code, 304)
        self.assertEqual(r2.content, b'')

    def test_no_etag_on_no_store_responses(self):
        # blog_edit sets no-store; ConditionalGet must not ETag it
        # (a 304 would resurrect a stale editor form from cache).
        post = make_post(slug='cache-no-etag', title='Cache no etag')
        staff = User.objects.create_user(
            username='etag-staff', password='test12345', is_staff=True)
        c = Client()
        c.force_login(staff)
        r = c.get(f'/blog/{post.slug}/edit/')
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.headers.get('ETag'))


class ExplicitlyHeaderedRouteTests(TestCase):
    """(f)(g) routes with explicit Cache-Control are not overridden."""

    def test_cv_pdf_keeps_explicit_one_hour_header(self):
        # download_cv proxies loevlie.github.io — stub the upstream
        # fetch so the test runs offline and exercises the 200 path
        # that sets the explicit header.
        fake = mock.MagicMock()
        fake.__enter__.return_value.read.return_value = (
            b'%PDF-1.4\n' + b'x' * 400)
        with mock.patch('urllib.request.urlopen', return_value=fake):
            r = Client().get('/cv.pdf')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers['Cache-Control'], 'public, max-age=3600')
        self.assertEqual(r.headers['Content-Type'], 'application/pdf')

    def test_sitemap_is_public_one_hour(self):
        r = Client().get('/sitemap.xml')
        self.assertEqual(r.status_code, 200)
        cc = r.headers['Cache-Control']
        self.assertIn('public', cc)
        self.assertIn('max-age=3600', cc)


class NoTransformGZipUnitTests(TestCase):
    """(i) the gzip subclass leaves no-transform responses untouched."""

    BODY = b'event: token\ndata: hello\n\n' * 30  # well over 200 bytes

    def _run(self, cache_control=None):
        def get_response(request):
            resp = HttpResponse(self.BODY)
            if cache_control:
                resp['Cache-Control'] = cache_control
            return resp
        mw = NoTransformGZipMiddleware(get_response)
        request = RequestFactory().get('/x/', HTTP_ACCEPT_ENCODING='gzip')
        return mw(request)

    def test_no_transform_skips_compression(self):
        resp = self._run(cache_control='no-cache, no-transform')
        self.assertFalse(resp.has_header('Content-Encoding'))
        self.assertEqual(resp.content, self.BODY)

    def test_without_no_transform_still_compresses(self):
        # Control case: same body, no no-transform → gzip applies.
        resp = self._run(cache_control='no-cache')
        self.assertEqual(resp.headers.get('Content-Encoding'), 'gzip')
        self.assertEqual(gzip.decompress(resp.content), self.BODY)


class CacheHeadersMiddlewareUnitTests(TestCase):
    """Direct unit coverage of the guard conditions."""

    def _run(self, request, status=200, preset=None, streaming=False):
        def get_response(req):
            if streaming:
                from django.http import StreamingHttpResponse
                resp = StreamingHttpResponse(iter([b'chunk']))
            else:
                resp = HttpResponse(b'ok', status=status)
            if preset:
                resp['Cache-Control'] = preset
            return resp
        return CacheHeadersMiddleware(get_response)(request)

    def test_non_200_untouched(self):
        resp = self._run(RequestFactory().get('/x/'), status=404)
        self.assertFalse(resp.has_header('Cache-Control'))

    def test_streaming_untouched(self):
        resp = self._run(RequestFactory().get('/x/'), streaming=True)
        self.assertFalse(resp.has_header('Cache-Control'))

    def test_existing_header_untouched(self):
        resp = self._run(RequestFactory().get('/x/'), preset='max-age=99')
        self.assertEqual(resp.headers['Cache-Control'], 'max-age=99')

    def test_head_gets_default(self):
        resp = self._run(RequestFactory().head('/x/'))
        self.assertEqual(resp.headers['Cache-Control'], ANON_VALUE)


class ContextProcessorLazinessTests(TestCase):
    """(j) SimpleLazyObject wrappers only resolve when a template reads
    the key: blog pages read none of them; the homepage reads several."""

    def test_blog_list_never_resolves_news(self):
        with mock.patch('portfolio.content.live.news', return_value=[]) as m:
            r = Client().get('/blog/')
            self.assertEqual(r.status_code, 200)
        m.assert_not_called()

    def test_blog_post_never_resolves_news(self):
        post = make_post(slug='cache-lazy-post', title='Cache lazy post')
        with mock.patch('portfolio.content.live.news', return_value=[]) as m:
            r = Client().get(f'/blog/{post.slug}/')
            self.assertEqual(r.status_code, 200)
        m.assert_not_called()

    def test_homepage_resolves_news(self):
        with mock.patch('portfolio.content.live.news', return_value=[]) as m:
            r = Client().get('/')
            self.assertEqual(r.status_code, 200)
        m.assert_called()
