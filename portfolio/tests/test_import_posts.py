"""import_posts deploy safety: build.sh runs this on EVERY deploy, so it
must never clobber DB edits (create-only) and never resurrect a post the
owner renamed or deleted since it was first seeded (the ledger)."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from portfolio.models import ImportedPostLedger, Post

# A slug that actually exists as a file in portfolio/blog/posts/.
FILE_SLUG = 'multiple-instance-learning'


def run_import(*args):
    out = StringIO()
    call_command('import_posts', *args, stdout=out)
    return out.getvalue()


class ImportPostsTests(TestCase):
    def test_first_import_creates_and_records_ledger(self):
        self.assertFalse(Post.objects.filter(slug=FILE_SLUG).exists())
        run_import()
        self.assertTrue(Post.objects.filter(slug=FILE_SLUG).exists())
        self.assertTrue(ImportedPostLedger.objects.filter(slug=FILE_SLUG).exists())

    def test_existing_db_row_is_left_alone_and_backfills_ledger(self):
        run_import()
        post = Post.objects.get(slug=FILE_SLUG)
        post.title = 'Edited in the browser'
        post.save()
        ImportedPostLedger.objects.all().delete()  # simulate pre-ledger deploys
        run_import()
        post.refresh_from_db()
        self.assertEqual(post.title, 'Edited in the browser')
        self.assertTrue(ImportedPostLedger.objects.filter(slug=FILE_SLUG).exists())

    def test_deleted_post_is_not_resurrected_on_next_deploy(self):
        run_import()
        Post.objects.filter(slug=FILE_SLUG).delete()
        out = run_import()
        self.assertFalse(Post.objects.filter(slug=FILE_SLUG).exists(),
                         'deploy must not resurrect a deleted post')
        self.assertIn('renamed or deleted since', out)

    def test_renamed_post_is_not_duplicated_on_next_deploy(self):
        run_import()
        post = Post.objects.get(slug=FILE_SLUG)
        post.slug = 'my-renamed-essay'
        post.save()
        run_import()
        self.assertFalse(
            Post.objects.filter(slug=FILE_SLUG).exists(),
            'deploy must not re-create the old slug as a duplicate post',
        )
        self.assertTrue(Post.objects.filter(slug='my-renamed-essay').exists())

    def test_force_overrides_the_ledger(self):
        run_import()
        Post.objects.filter(slug=FILE_SLUG).delete()
        run_import('--force', FILE_SLUG)
        self.assertTrue(Post.objects.filter(slug=FILE_SLUG).exists(),
                        '--force <slug> must still re-import explicitly')
