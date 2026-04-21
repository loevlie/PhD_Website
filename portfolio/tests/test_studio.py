"""Studio dashboard + Reading quick-add tests (Track B3 + Reading rework)."""
from django.test import TestCase
from django.core.cache import cache

from portfolio.tests._helpers import StaffClientMixin, make_post


class StudioAccessTests(StaffClientMixin, TestCase):
    """/site/studio/ is staff-only; anonymous visitors bounce to
    /admin/login/?next=/site/studio/."""

    def setUp(self):
        super().setUp()
        cache.clear()

    def test_staff_sees_dashboard(self):
        r = self.staff_client.get('/site/studio/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Studio')
        # Quick-add form present (<details> inside a card), with the
        # reading-quickadd endpoint wired.
        self.assertContains(r, 'name="title"')
        self.assertContains(r, 'action="/site/reading/add/"')

    def test_anon_redirects_to_admin_login(self):
        r = self.anon_client.get('/site/studio/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/admin/login/', r['Location'])
        self.assertIn('next=/site/studio/', r['Location'])

    def test_studio_shows_counts_and_recent_activity(self):
        # Seed a couple of posts so the recent-activity lists aren't empty.
        make_post(slug='essay-a', title='An essay', tags=['ml'])
        lab = make_post(slug='lab-b', title='A lab note', tags=['research'])
        lab.kind = 'lab_note'
        lab.save()
        r = self.staff_client.get('/site/studio/')
        self.assertContains(r, 'An essay')
        self.assertContains(r, 'A lab note')


class ReadingQuickAddTests(StaffClientMixin, TestCase):

    def setUp(self):
        super().setUp()
        cache.clear()
        # Migration 0010 seeds 5 starter papers so prod has content on
        # first deploy. Clear them for tests that assert on row counts.
        from portfolio.models import Reading
        Reading.objects.all().delete()

    def test_staff_can_add_minimal_entry(self):
        from portfolio.models import Reading
        r = self.staff_client.post('/site/reading/add/', {
            'title': 'Attention Is All You Need',
            'url': 'https://arxiv.org/abs/1706.03762',
        })
        # Redirects back to the admin by default.
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Reading.objects.count(), 1)
        entry = Reading.objects.first()
        self.assertEqual(entry.title, 'Attention Is All You Need')
        self.assertEqual(entry.status, 'this_week')

    def test_staff_add_honors_fields(self):
        from portfolio.models import Reading
        self.staff_client.post('/site/reading/add/', {
            'title': 'Gradient Descent',
            'url': 'https://example.com',
            'venue': 'arXiv',
            'year': '2024',
            'status': 'lingering',
            'annotation': 'A one-liner.',
            'next': '/reading/',
        })
        e = Reading.objects.get(title='Gradient Descent')
        self.assertEqual(e.year, 2024)
        self.assertEqual(e.status, 'lingering')
        self.assertEqual(e.annotation, 'A one-liner.')

    def test_anon_cannot_add(self):
        from portfolio.models import Reading
        r = self.anon_client.post('/site/reading/add/', {'title': 'X'})
        self.assertEqual(r.status_code, 302)
        self.assertIn('/admin/login/', r['Location'])
        self.assertEqual(Reading.objects.count(), 0)

    def test_missing_title_does_not_create(self):
        from portfolio.models import Reading
        r = self.staff_client.post('/site/reading/add/', {'title': '  '})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Reading.objects.count(), 0)

    def test_bad_status_falls_back_to_this_week(self):
        from portfolio.models import Reading
        self.staff_client.post('/site/reading/add/', {
            'title': 'Paper',
            'status': 'malicious_value',
        })
        self.assertEqual(Reading.objects.get(title='Paper').status, 'this_week')

    def test_bad_year_becomes_null(self):
        from portfolio.models import Reading
        self.staff_client.post('/site/reading/add/', {
            'title': 'Paper',
            'year': 'notanumber',
        })
        self.assertIsNone(Reading.objects.get(title='Paper').year)

    def test_non_local_next_is_stripped(self):
        r = self.staff_client.post('/site/reading/add/', {
            'title': 'Paper',
            'next': 'https://evil.example.com/phish',
        })
        self.assertEqual(r.status_code, 302)
        self.assertFalse(r['Location'].startswith('https://evil.example.com'))

    def test_reading_page_shows_staff_quickadd_for_staff(self):
        r = self.staff_client.get('/reading/')
        self.assertEqual(r.status_code, 200)
        # The form posts to the quick-add endpoint; its presence = staff mode.
        self.assertContains(r, 'action="/site/reading/add/"')

    def test_reading_page_hides_quickadd_for_anon(self):
        r = self.anon_client.get('/reading/')
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'action="/site/reading/add/"')


class ReadingMMAnnotationTests(StaffClientMixin, TestCase):
    """Reading.mm_annotation renders on /reading/ beneath the manual annotation."""

    def setUp(self):
        super().setUp()
        cache.clear()

    def test_mm_annotation_visible(self):
        from portfolio.models import Reading
        Reading.objects.create(
            title='Some paper', status='this_week', order=0,
            annotation='my own note',
            mm_annotation='external mm note from mind-mapper',
        )
        r = self.anon_client.get('/reading/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'my own note')
        self.assertContains(r, 'external mm note from mind-mapper')
        # Both shown with distinct classes so CSS can style them differently
        self.assertContains(r, 'pnote--mm')
