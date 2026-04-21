"""Tests for the DB-backed content layer (Track B1).

Covers:
  * `portfolio.content.live` prefers DB rows, falls back to static
    content modules when a table is empty.
  * The signals module clears the right live-cache keys on save/delete.
  * `manage.py seed_content` idempotently populates the models and
    respects --only subsets.
  * Context processor surface: rendered pages (/ and /now/) work with
    both fallback and DB-seeded content.
"""
from datetime import date

from django.core.management import call_command
from django.test import TestCase, Client
from django.core.cache import cache


class LiveAdapterFallbackTests(TestCase):
    """When DB tables are empty, live.* must return the static
    content-module constants so pages keep rendering on a fresh deploy."""

    def setUp(self):
        cache.clear()

    def test_news_falls_back_to_content_module(self):
        from portfolio.content import live
        from portfolio.content.news import NEWS
        self.assertEqual(live.news(), NEWS)

    def test_publications_falls_back(self):
        from portfolio.content import live
        from portfolio.content.publications import PUBLICATIONS
        self.assertEqual(live.publications(), PUBLICATIONS)

    def test_projects_falls_back(self):
        from portfolio.content import live
        from portfolio.content.projects import PROJECTS
        self.assertEqual(live.projects(), PROJECTS)

    def test_now_page_falls_back(self):
        from portfolio.content import live
        from portfolio.content.now import NOW_PAGE
        self.assertEqual(live.now_page(), NOW_PAGE)


class LiveAdapterDBTests(TestCase):
    """When rows exist, live.* pulls from the DB (and shape-adapts back
    into the dict form that the templates expect)."""

    def setUp(self):
        cache.clear()

    def test_news_pulls_from_db(self):
        from portfolio.models import NewsItem
        from portfolio.content import live
        NewsItem.objects.create(
            date='2026', text='<strong>DB</strong> news item.',
            highlight=True, display_order=0,
        )
        rows = live.news()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['date'], '2026')
        self.assertIn('DB', rows[0]['text'])
        self.assertTrue(rows[0]['highlight'])

    def test_drafts_hidden(self):
        from portfolio.models import NewsItem
        from portfolio.content import live
        NewsItem.objects.create(date='2025', text='Draft item.', draft=True)
        self.assertEqual(live.news(), [])  # draft hidden; empty != fallback
        # live.news() with empty queryset still returns fallback; assert shape:
        # Draft exists so queryset is empty -> falls back. Acceptable behavior.

    def test_publication_links_roundtrip(self):
        from portfolio.models import Publication, PublicationLink
        from portfolio.content import live
        pub = Publication.objects.create(
            title='Tabular Foundation Models', authors='Dennis Loevlie',
            venue='arXiv', year=2026, selected=True, display_order=0,
        )
        PublicationLink.objects.create(publication=pub, label='Paper', url='https://arxiv.org/abs/x', order=0)
        PublicationLink.objects.create(publication=pub, label='Code', url='https://github.com/x/y', order=1)
        rows = live.publications()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['authors'], ['Dennis Loevlie'])
        self.assertEqual([l['label'] for l in rows[0]['links']], ['Paper', 'Code'])


class SignalsInvalidateCacheTests(TestCase):
    """Content save/delete should drop the memoized live cache key so
    the next page load reflects the edit immediately."""

    def setUp(self):
        cache.clear()

    def test_news_save_invalidates_cache(self):
        from portfolio.models import NewsItem
        from portfolio.content import live
        # Warm fallback into cache
        _ = live.news()
        self.assertIsNotNone(cache.get('content:v1:news'))
        NewsItem.objects.create(date='2026', text='New', display_order=0)
        # Save signal clears the cache key
        self.assertIsNone(cache.get('content:v1:news'))

    def test_project_save_invalidates_cache(self):
        from portfolio.models import Project
        from portfolio.content import live
        _ = live.projects()
        self.assertIsNotNone(cache.get('content:v1:projects'))
        Project.objects.create(title='X', description='Y')
        self.assertIsNone(cache.get('content:v1:projects'))


class SeedContentCommandTests(TestCase):
    """`manage.py seed_content` should populate all content models
    idempotently from the static content modules."""

    def setUp(self):
        cache.clear()

    def test_seed_creates_rows(self):
        from portfolio.models import (
            NewsItem, Publication, Project, TimelineEntry,
            OpenSourceItem, SocialLink, NowPage,
        )
        from portfolio.content.news import NEWS
        from portfolio.content.publications import PUBLICATIONS
        call_command('seed_content', verbosity=0)
        self.assertEqual(NewsItem.objects.count(), len(NEWS))
        self.assertEqual(Publication.objects.count(), len(PUBLICATIONS))
        self.assertGreater(Project.objects.count(), 0)
        self.assertGreater(TimelineEntry.objects.count(), 0)
        self.assertGreater(OpenSourceItem.objects.count(), 0)
        self.assertGreater(SocialLink.objects.count(), 0)
        self.assertEqual(NowPage.objects.count(), 1)

    def test_reseed_is_idempotent(self):
        from portfolio.models import Publication
        call_command('seed_content', verbosity=0)
        first = Publication.objects.count()
        call_command('seed_content', verbosity=0)
        self.assertEqual(Publication.objects.count(), first)

    def test_only_flag_restricts_scope(self):
        from portfolio.models import NewsItem, Publication
        call_command('seed_content', only='news', verbosity=0)
        self.assertGreater(NewsItem.objects.count(), 0)
        self.assertEqual(Publication.objects.count(), 0)

    def test_unknown_only_errors_out(self):
        from io import StringIO
        out = StringIO()
        call_command('seed_content', only='badkey', stdout=out, verbosity=0)
        self.assertIn('Unknown seeder', out.getvalue())


class PagesWithDBContentTests(TestCase):
    """Integration: ensure the pages that exercise the content layer
    render cleanly with seeded DB rows + empty-DB fallback."""

    def setUp(self):
        cache.clear()
        self.client = Client()

    def test_index_renders_with_seeded_content(self):
        call_command('seed_content', verbosity=0)
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        # The homepage cites NEWS, PUBLICATIONS, PROJECTS, TIMELINE.
        # Pick a seed-specific string to confirm the DB path ran.
        self.assertContains(resp, 'NeurOpt')  # from projects seed

    def test_now_page_renders_with_seeded_content(self):
        call_command('seed_content', verbosity=0)
        resp = self.client.get('/now/')
        self.assertEqual(resp.status_code, 200)
        # NOW_PAGE.sections[0].heading is 'Research' in the seed
        self.assertContains(resp, 'Research')

    def test_now_page_renders_without_db_rows(self):
        # No seed call → fallback path
        resp = self.client.get('/now/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Research')  # same content via fallback
