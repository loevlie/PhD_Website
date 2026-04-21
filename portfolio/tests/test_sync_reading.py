"""Tests for the post-2026-04 sync_reading behavior:

  * Never creates Reading rows — adding is manual.
  * Never modifies title/url/venue/year/status/order.
  * Updates `mm_annotation` + `mind_mapper_note_id` on URL or title match.
  * Clears the link on re-run when an MM note is removed from the project.
"""
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase


# One "fetched" Mind Mapper note in the canonical shape. The sync
# command calls _api_get twice: once for the project listing, once
# per note detail. We patch the module-level _api_get to short-circuit
# both calls without a network round-trip.
_MM_PROJECT_LIST = [
    {'id': 42, 'project': 'Reading', 'title': 'Attention Is All You Need'},
]
_MM_NOTE_DETAIL = {
    'id': 42,
    'title': 'Attention Is All You Need',
    'content': (
        '---\n'
        'url: https://arxiv.org/abs/1706.03762\n'
        '---\n'
        'Foundational attention paper — re-reading for pretraining intuition.\n'
    ),
}


def _fake_api_get(path):
    if path.startswith('/api/notes/?project='):
        return _MM_PROJECT_LIST
    if path.startswith('/api/notes/') and path.endswith('/'):
        return _MM_NOTE_DETAIL
    raise RuntimeError(f'unexpected path in fake _api_get: {path!r}')


class SyncReadingAnnotationOnlyTests(TestCase):
    """Sync attaches the MM note's annotation to an already-existing
    Reading row matching by URL; never creates rows."""

    def setUp(self):
        # Migration 0010 seeds 5 Reading rows (incl. one called
        # "Attention Is All You Need"). Clear so each test starts clean.
        from portfolio.models import Reading
        Reading.objects.all().delete()

    def test_sync_attaches_annotation_on_url_match(self):
        from portfolio.models import Reading
        entry = Reading.objects.create(
            title='Attention',
            url='https://arxiv.org/abs/1706.03762',
            status='this_week',
        )
        with patch('portfolio.management.commands.sync_reading._api_get', side_effect=_fake_api_get):
            call_command('sync_reading', verbosity=0)
        entry.refresh_from_db()
        self.assertEqual(entry.mind_mapper_note_id, 42)
        self.assertIn('attention paper', entry.mm_annotation.lower())
        # Untouched fields stay manual:
        self.assertEqual(entry.title, 'Attention')
        self.assertEqual(entry.status, 'this_week')
        # No new rows:
        self.assertEqual(Reading.objects.count(), 1)

    def test_sync_attaches_on_title_match_when_url_missing(self):
        from portfolio.models import Reading
        entry = Reading.objects.create(
            title='Attention Is All You Need',
            url='',  # no URL so matching happens via title
            status='this_week',
        )
        with patch('portfolio.management.commands.sync_reading._api_get', side_effect=_fake_api_get):
            call_command('sync_reading', verbosity=0)
        entry.refresh_from_db()
        self.assertEqual(entry.mind_mapper_note_id, 42)
        self.assertTrue(entry.mm_annotation)

    def test_sync_skips_when_no_manual_row_matches(self):
        from portfolio.models import Reading
        # Nothing in the DB to match
        with patch('portfolio.management.commands.sync_reading._api_get', side_effect=_fake_api_get):
            call_command('sync_reading', verbosity=0)
        self.assertEqual(Reading.objects.count(), 0)

    def test_dry_run_does_not_write(self):
        from portfolio.models import Reading
        entry = Reading.objects.create(
            title='Attention',
            url='https://arxiv.org/abs/1706.03762',
            status='this_week',
        )
        with patch('portfolio.management.commands.sync_reading._api_get', side_effect=_fake_api_get):
            call_command('sync_reading', dry_run=True, verbosity=0)
        entry.refresh_from_db()
        self.assertEqual(entry.mm_annotation, '')
        self.assertIsNone(entry.mind_mapper_note_id)

    def test_sync_clears_stale_annotation_when_mm_note_removed(self):
        from portfolio.models import Reading
        entry = Reading.objects.create(
            title='Old paper',
            url='https://arxiv.org/abs/0000.99999',
            status='this_week',
            mm_annotation='annotation that was synced previously',
            mind_mapper_note_id=999,  # stale note id not in the MM project
        )
        # Project listing only has note 42, not 999
        with patch('portfolio.management.commands.sync_reading._api_get', side_effect=_fake_api_get):
            call_command('sync_reading', verbosity=0)
        entry.refresh_from_db()
        # The row is kept:
        self.assertEqual(Reading.objects.count(), 1)
        # But the mm_* fields are cleared:
        self.assertIsNone(entry.mind_mapper_note_id)
        self.assertEqual(entry.mm_annotation, '')
