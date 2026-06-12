"""Open Graph card pipeline: og_image_url tag + management command +
view + Pillow renderer + signal lifecycle.

Storage is overridden to a throwaway MEDIA_ROOT per test class so the
tests don't write into the real R2 bucket and don't depend on a prior
run's leftover cards.
"""
import tempfile
from io import StringIO

from django.core.files.storage import default_storage
from django.core.management import call_command, CommandError
from django.template import Context, Template
from django.test import TestCase, override_settings

from ._helpers import StaffClientMixin, make_post


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix='test-og-tag-'))
class OgImageUrlTagTests(TestCase):
    """{% og_image_url <slug> %} returns the storage URL when a card
    is persisted, the site-cover static URL otherwise."""

    def render(self, slug):
        t = Template("{% load portfolio_tags %}{% og_image_url slug %}")
        return t.render(Context({'slug': slug}))

    def test_returns_storage_url_when_card_exists(self):
        from django.core.files.base import ContentFile
        slug = 'tag-test-exists'
        default_storage.save(f'og/{slug}.png', ContentFile(b'fake'))
        url = self.render(slug)
        self.assertIn(f'og/{slug}.png', url)

    def test_falls_back_to_site_cover_when_missing(self):
        from django.conf import settings
        url = self.render('definitely-not-a-real-slug-zzz')
        self.assertEqual(url, f'{settings.STATIC_URL}portfolio/images/og-cover.jpg')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix='test-og-meta-'))
class BlogPostOgMetaTests(TestCase):
    """The blog post template wires the og_image_url tag into the OG meta tags."""

    def test_post_og_meta_uses_per_post_card_when_persisted(self):
        from django.core.files.base import ContentFile
        slug = 'meta-test-post'
        # Pre-persist a card so we don't trip the signal-driven render
        # (which is exercised separately in OgSignalTests).
        default_storage.save(f'og/{slug}.png', ContentFile(b'\x89PNG\r\n\x1a\n'))
        make_post(slug=slug, title='Meta test')
        r = self.client.get(f'/blog/{slug}/')
        self.assertContains(r, f'og/{slug}.png')
        self.assertContains(r, '"og:image:width" content="1200"')
        self.assertContains(r, '"og:image:height" content="630"')

    def test_post_og_meta_falls_back_to_site_cover(self):
        slug = 'meta-test-fallback'
        make_post(slug=slug, title='Meta fallback test')
        # The signal could have minted a card; make sure it isn't there.
        if default_storage.exists(f'og/{slug}.png'):
            default_storage.delete(f'og/{slug}.png')
        r = self.client.get(f'/blog/{slug}/')
        self.assertContains(r, '/static/portfolio/images/og-cover.jpg')

    def test_post_with_explicit_image_takes_precedence(self):
        slug = 'meta-test-explicit'
        from portfolio.models import Post
        from datetime import date
        Post.objects.create(
            slug=slug, title='Has cover', body='x', date=date.today(),
            image='portfolio/images/blog/custom-cover.jpg',
        )
        r = self.client.get(f'/blog/{slug}/')
        self.assertContains(r, '/static/portfolio/images/blog/custom-cover.jpg')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix='test-og-cmd-'))
class GenerateOgCardsCommandTests(TestCase):
    """The management command's --check mode dry-runs; an unknown slug
    raises CommandError; the storage path actually persists a card."""

    def test_check_mode_dry_runs(self):
        make_post(slug='cmd-check-test', title='A real title')
        out = StringIO()
        call_command('generate_og_cards', '--check', stdout=out)
        self.assertIn('Will generate', out.getvalue())

    def test_check_mode_does_not_write(self):
        slug = 'cmd-no-write-test'
        make_post(slug=slug, title='Another real title')
        if default_storage.exists(f'og/{slug}.png'):
            default_storage.delete(f'og/{slug}.png')
        call_command('generate_og_cards', '--check', stdout=StringIO())
        self.assertFalse(default_storage.exists(f'og/{slug}.png'))

    def test_unknown_slug_raises_command_error(self):
        with self.assertRaises(CommandError):
            call_command('generate_og_cards', 'no-such-slug-xyz',
                         stdout=StringIO(), stderr=StringIO())

    def test_explicit_slug_writes_card_via_storage(self):
        slug = 'cmd-real-write'
        make_post(slug=slug, title='Card command end-to-end')
        if default_storage.exists(f'og/{slug}.png'):
            default_storage.delete(f'og/{slug}.png')
        call_command('generate_og_cards', slug, stdout=StringIO())
        self.assertTrue(default_storage.exists(f'og/{slug}.png'))
        with default_storage.open(f'og/{slug}.png', 'rb') as f:
            head = f.read(8)
        self.assertEqual(head, b'\x89PNG\r\n\x1a\n', 'output must be a real PNG')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix='test-og-view-'))
class RegenerateOgCardViewTests(StaffClientMixin, TestCase):
    def test_post_persists_card_and_returns_storage_url(self):
        post = make_post(slug='view-regen-ok', title='A view-driven render')
        if default_storage.exists(f'og/{post.slug}.png'):
            default_storage.delete(f'og/{post.slug}.png')
        r = self.staff_client.post(f'/blog/{post.slug}/regenerate-og/')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['ok'])
        self.assertIn(f'og/{post.slug}.png', data['url'])
        self.assertTrue(default_storage.exists(f'og/{post.slug}.png'))

    def test_unknown_slug_returns_404(self):
        r = self.staff_client.post('/blog/no-such-slug/regenerate-og/')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()['error'], 'unknown slug')

    def test_anon_blocked(self):
        post = make_post(slug='view-regen-anon')
        r = self.anon_client.post(f'/blog/{post.slug}/regenerate-og/')
        self.assertEqual(r.status_code, 403)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix='test-og-sig-'))
class OgSignalTests(TestCase):
    """post_save auto-mints the card; post_delete drops it."""

    def test_save_with_real_title_mints_card(self):
        slug = 'sig-mint'
        from portfolio.models import Post
        from datetime import date
        Post.objects.create(
            slug=slug, title='A genuine title', body='b',
            date=date.today(), excerpt='x',
        )
        self.assertTrue(default_storage.exists(f'og/{slug}.png'))

    def test_save_with_placeholder_title_skips_card(self):
        """Fresh /blog/new/ drafts have placeholder titles — render the
        card only after the author commits a real title to avoid burning
        bytes on cards nobody will ever share."""
        slug = 'sig-placeholder'
        from portfolio.models import Post
        from datetime import date
        Post.objects.create(
            slug=slug, title='Untitled draft', body='b',
            date=date.today(), excerpt='x',
        )
        self.assertFalse(default_storage.exists(f'og/{slug}.png'))

    def test_delete_drops_card(self):
        slug = 'sig-delete'
        from portfolio.models import Post
        from datetime import date
        post = Post.objects.create(
            slug=slug, title='Will be deleted', body='b',
            date=date.today(), excerpt='x',
        )
        self.assertTrue(default_storage.exists(f'og/{slug}.png'))
        post.delete()
        self.assertFalse(default_storage.exists(f'og/{slug}.png'))
