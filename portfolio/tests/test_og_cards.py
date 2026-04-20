"""Open Graph card pipeline: og_image_url filter + management command shape.

The actual PNG generation requires Playwright — we don't run that in
tests. Instead we test the *contract*: the template tag returns the
right URL based on file existence, and the management command's --check
mode dry-runs without writing.
"""
import os
import shutil
from pathlib import Path

from django.conf import settings
from django.template import Context, Template
from django.test import TestCase
from django.core.management import call_command
from io import StringIO

from ._helpers import make_post


OG_DIR = Path(settings.BASE_DIR) / 'portfolio' / 'static' / 'portfolio' / 'images' / 'og'


class OgImageUrlTagTests(TestCase):
    """{% og_image_url <slug> %} returns per-post URL when file exists,
    site-cover fallback otherwise."""

    def setUp(self):
        OG_DIR.mkdir(parents=True, exist_ok=True)
        # Track files we create so we can clean them up
        self.cleanup = []

    def tearDown(self):
        for p in self.cleanup:
            p.unlink(missing_ok=True)

    def render(self, slug):
        t = Template("{% load portfolio_tags %}{% og_image_url slug %}")
        return t.render(Context({'slug': slug}))

    def test_returns_per_post_url_when_file_exists(self):
        slug = 'test-card-exists'
        path = OG_DIR / f'{slug}.png'
        path.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\0' * 100)
        self.cleanup.append(path)
        url = self.render(slug)
        self.assertEqual(url, f'{settings.STATIC_URL}portfolio/images/og/{slug}.png')

    def test_falls_back_to_site_cover_when_missing(self):
        url = self.render('definitely-not-a-real-slug-zzz')
        self.assertEqual(url, f'{settings.STATIC_URL}portfolio/images/og-cover.png')


class BlogPostOgMetaTests(TestCase):
    """The blog post template wires the og_image_url tag into the OG meta tags."""

    def test_post_og_meta_uses_per_post_card_when_present(self):
        OG_DIR.mkdir(parents=True, exist_ok=True)
        slug = 'meta-test-post'
        path = OG_DIR / f'{slug}.png'
        path.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\0' * 100)
        try:
            make_post(slug=slug, title='Meta test')
            r = self.client.get(f'/blog/{slug}/')
            self.assertContains(r, f'/static/portfolio/images/og/{slug}.png')
            self.assertContains(r, '"og:image:width" content="1200"')
            self.assertContains(r, '"og:image:height" content="630"')
        finally:
            path.unlink(missing_ok=True)

    def test_post_og_meta_falls_back_to_site_cover(self):
        slug = 'meta-test-fallback'
        make_post(slug=slug, title='Meta fallback test')
        # Make sure no per-post card exists
        path = OG_DIR / f'{slug}.png'
        path.unlink(missing_ok=True)
        r = self.client.get(f'/blog/{slug}/')
        self.assertContains(r, '/static/portfolio/images/og-cover.png')

    def test_post_with_explicit_image_takes_precedence(self):
        slug = 'meta-test-explicit'
        from portfolio.models import Post
        from datetime import date
        p = Post.objects.create(
            slug=slug, title='Has cover', body='x', date=date.today(),
            image='portfolio/images/blog/custom-cover.jpg',
        )
        r = self.client.get(f'/blog/{slug}/')
        self.assertContains(r, '/static/portfolio/images/blog/custom-cover.jpg')


class GenerateOgCardsCommandTests(TestCase):
    """The management command's --check mode lists what *would* be
    generated without writing anything."""

    def test_check_mode_dry_runs(self):
        make_post(slug='cmd-check-test')
        out = StringIO()
        call_command('generate_og_cards', '--check', stdout=out)
        s = out.getvalue()
        # We can't be sure whether a card already exists from prior
        # commands; just confirm the command runs and prints something
        self.assertTrue(s.strip())

    def test_check_mode_does_not_write(self):
        slug = 'cmd-no-write-test'
        make_post(slug=slug)
        path = OG_DIR / f'{slug}.png'
        path.unlink(missing_ok=True)
        call_command('generate_og_cards', '--check', stdout=StringIO())
        self.assertFalse(path.exists())

    def test_unknown_slug_errors(self):
        out, err = StringIO(), StringIO()
        call_command('generate_og_cards', 'no-such-slug-xyz', '--check',
                     stdout=out, stderr=err)
        self.assertIn('No post', err.getvalue())
