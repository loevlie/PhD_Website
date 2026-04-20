"""Analytics: beacon recording, privacy, classification, dashboard."""
from django.test import TestCase

from portfolio.models import Pageview, DailySalt
from portfolio import analytics

from ._helpers import StaffClientMixin, REAL_BROWSER_UA


class BeaconRecordingTests(StaffClientMixin, TestCase):
    """The /a/p endpoint writes one Pageview per call (with a real UA)."""

    def test_records_pageview(self):
        n0 = Pageview.objects.count()
        r = self.anon_client.post('/a/p',
            data={'path': '/blog/x/', 'referrer': 'https://example.com/',
                  'viewport_w': '1440', 'viewport_h': '900'},
            HTTP_USER_AGENT=REAL_BROWSER_UA)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Pageview.objects.count(), n0 + 1)
        pv = Pageview.objects.latest('id')
        self.assertEqual(pv.path, '/blog/x/')
        self.assertEqual(pv.referrer, 'https://example.com/')
        self.assertEqual(pv.viewport_w, 1440)
        self.assertEqual(pv.device, 'desktop')
        self.assertEqual(pv.browser, 'Safari')
        self.assertTrue(pv.session_id)
        self.assertTrue(pv.ip_hash)
        self.assertFalse(pv.is_bot)

    def test_returns_id_on_first_view_only(self):
        r1 = self.anon_client.post('/a/p',
            data={'path': '/'}, HTTP_USER_AGENT=REAL_BROWSER_UA)
        self.assertEqual(r1.status_code, 200)
        self.assertIn('id', r1.json())
        # Second hit (cookie now set) returns 204
        r2 = self.anon_client.post('/a/p',
            data={'path': '/blog/'}, HTTP_USER_AGENT=REAL_BROWSER_UA)
        self.assertEqual(r2.status_code, 204)

    def test_post_slug_extracted_from_blog_path(self):
        self.anon_client.post('/a/p',
            data={'path': '/blog/my-post/'}, HTTP_USER_AGENT=REAL_BROWSER_UA)
        pv = Pageview.objects.latest('id')
        self.assertEqual(pv.post_slug, 'my-post')

    def test_post_slug_empty_for_non_blog_path(self):
        self.anon_client.post('/a/p',
            data={'path': '/now/'}, HTTP_USER_AGENT=REAL_BROWSER_UA)
        pv = Pageview.objects.latest('id')
        self.assertEqual(pv.post_slug, '')

    def test_strips_self_referrer(self):
        # If referrer host matches our host, it should be cleared
        self.anon_client.post('/a/p',
            data={'path': '/', 'referrer': 'http://testserver/blog/'},
            HTTP_HOST='testserver',
            HTTP_USER_AGENT=REAL_BROWSER_UA)
        pv = Pageview.objects.latest('id')
        self.assertEqual(pv.referrer, '')

    def test_classifies_phone(self):
        # Real iOS Safari UA — has both "Mobile/" and "Safari/"
        ios_ua = ('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) '
                  'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 '
                  'Mobile/15E148 Safari/604.1')
        self.anon_client.post('/a/p', data={'path': '/'},
                              HTTP_USER_AGENT=ios_ua)
        pv = Pageview.objects.latest('id')
        self.assertEqual(pv.device, 'phone')
        self.assertEqual(pv.browser, 'Safari')

    def test_classifies_chrome(self):
        chrome_ua = ('Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 '
                     '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        self.anon_client.post('/a/p', data={'path': '/'},
                              HTTP_USER_AGENT=chrome_ua)
        pv = Pageview.objects.latest('id')
        self.assertEqual(pv.browser, 'Chrome')

    def test_admin_paths_not_recorded(self):
        n0 = Pageview.objects.count()
        for path in ('/admin/', '/site/insights/', '/a/p'):
            self.anon_client.post('/a/p', data={'path': path},
                                  HTTP_USER_AGENT=REAL_BROWSER_UA)
        self.assertEqual(Pageview.objects.count(), n0)


class PrivacyAndFilteringTests(StaffClientMixin, TestCase):
    def test_dnt_header_blocks(self):
        n0 = Pageview.objects.count()
        r = self.anon_client.post('/a/p', data={'path': '/'},
                                  HTTP_DNT='1', HTTP_USER_AGENT=REAL_BROWSER_UA)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(Pageview.objects.count(), n0)

    def test_gpc_header_blocks(self):
        n0 = Pageview.objects.count()
        r = self.anon_client.post('/a/p', data={'path': '/'},
                                  HTTP_SEC_GPC='1', HTTP_USER_AGENT=REAL_BROWSER_UA)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(Pageview.objects.count(), n0)

    def test_bot_ua_blocks(self):
        n0 = Pageview.objects.count()
        for ua in ('Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
                   'curl/8.4.0',
                   'python-requests/2.31.0',
                   'Slackbot-LinkExpanding 1.0'):
            r = self.anon_client.post('/a/p', data={'path': '/'}, HTTP_USER_AGENT=ua)
            self.assertEqual(r.status_code, 204, msg=f'bot UA leaked: {ua}')
        self.assertEqual(Pageview.objects.count(), n0)


class IpHashingTests(TestCase):
    def test_daily_salt_is_per_day_and_64_hex_chars(self):
        salt = DailySalt.for_today()
        self.assertEqual(len(salt), 64)
        # Calling again returns the same salt for the same day
        salt2 = DailySalt.for_today()
        self.assertEqual(salt, salt2)

    def test_hash_ip_is_deterministic_for_same_ip_same_day(self):
        from django.test import RequestFactory
        rf = RequestFactory()
        r1 = rf.post('/', REMOTE_ADDR='1.2.3.4')
        r2 = rf.post('/', REMOTE_ADDR='1.2.3.4')
        self.assertEqual(analytics._hash_ip(r1), analytics._hash_ip(r2))

    def test_hash_ip_differs_for_different_ips(self):
        from django.test import RequestFactory
        rf = RequestFactory()
        r1 = rf.post('/', REMOTE_ADDR='1.2.3.4')
        r2 = rf.post('/', REMOTE_ADDR='5.6.7.8')
        self.assertNotEqual(analytics._hash_ip(r1), analytics._hash_ip(r2))

    def test_hash_ip_uses_xff_in_proxy_setup(self):
        from django.test import RequestFactory
        rf = RequestFactory()
        r1 = rf.post('/', HTTP_X_FORWARDED_FOR='9.9.9.9, 10.10.10.10', REMOTE_ADDR='127.0.0.1')
        r2 = rf.post('/', REMOTE_ADDR='9.9.9.9')
        self.assertEqual(analytics._hash_ip(r1), analytics._hash_ip(r2))


class BeaconUpdateTests(StaffClientMixin, TestCase):
    def test_update_persists_scroll_dwell(self):
        # Record a pageview first
        r = self.anon_client.post('/a/p', data={'path': '/'},
                                  HTTP_USER_AGENT=REAL_BROWSER_UA)
        pv_id = r.json()['id']
        # Then update it
        r2 = self.anon_client.post('/a/u',
            data={'id': str(pv_id), 'scroll_depth': '85', 'dwell_ms': '12000'},
            HTTP_USER_AGENT=REAL_BROWSER_UA)
        self.assertEqual(r2.status_code, 204)
        pv = Pageview.objects.get(id=pv_id)
        self.assertEqual(pv.scroll_depth, 85)
        self.assertEqual(pv.dwell_ms, 12000)

    def test_update_clamps_out_of_range_values(self):
        r = self.anon_client.post('/a/p', data={'path': '/'},
                                  HTTP_USER_AGENT=REAL_BROWSER_UA)
        pv_id = r.json()['id']
        self.anon_client.post('/a/u',
            data={'id': str(pv_id), 'scroll_depth': '500', 'dwell_ms': '-99'},
            HTTP_USER_AGENT=REAL_BROWSER_UA)
        pv = Pageview.objects.get(id=pv_id)
        self.assertEqual(pv.scroll_depth, 100)  # clamped to 100
        self.assertEqual(pv.dwell_ms, 0)        # clamped to 0

    def test_update_silently_ignores_unknown_id(self):
        r = self.anon_client.post('/a/u',
            data={'id': '999999', 'scroll_depth': '50', 'dwell_ms': '1000'},
            HTTP_USER_AGENT=REAL_BROWSER_UA)
        self.assertEqual(r.status_code, 204)


class DashboardTests(StaffClientMixin, TestCase):
    def test_dashboard_anon_redirected(self):
        r = self.anon_client.get('/site/insights/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/admin/login/', r.headers['Location'])

    def test_dashboard_staff_renders_empty_state(self):
        r = self.staff_client.get('/site/insights/')
        self.assertEqual(r.status_code, 200)
        # Should render the title even with zero data
        self.assertContains(r, 'Site insights')
        # KPIs should default to 0
        self.assertContains(r, '0 online now')

    def test_dashboard_aggregates_data(self):
        # Seed a few pageviews
        for path in ('/', '/', '/blog/x/'):
            self.anon_client.post('/a/p', data={'path': path},
                                  HTTP_USER_AGENT=REAL_BROWSER_UA)
        r = self.staff_client.get('/site/insights/')
        self.assertEqual(r.status_code, 200)
        # The home path should appear in top pages
        self.assertContains(r, '/blog/x/')


class StaffSkipsBeaconTests(StaffClientMixin, TestCase):
    """analytics.js is conditionally rendered based on user.is_staff."""

    def test_anon_sees_analytics_script(self):
        r = self.anon_client.get('/')
        self.assertContains(r, 'analytics.js')

    def test_staff_does_not_see_analytics_script(self):
        r = self.staff_client.get('/')
        self.assertNotContains(r, 'analytics.js')
