"""Tests for the `<div data-demo="slug"></div>` marker — covers the
markdown pre-processor, the conditional JS/CSS loading in
blog_post.html, and the `/blog/new/?template=demo&demo=<slug>` path
in the editor."""
from datetime import date

from django.test import TestCase, Client
from django.contrib.auth import get_user_model

from portfolio.blog import render_markdown
from portfolio.content.demos import DEMOS


User = get_user_model()


class DemoEmbedMarkdownTests(TestCase):
    """render_markdown expands the marker in-place, wraps it in
    `.demo-embed-root`, and appends an 'Open full demo →' footer."""

    def test_marker_expands_to_embed_html(self):
        body = (
            '# My post\n\n'
            'Some prose before the demo.\n\n'
            '<div data-demo="frozen-forecaster"></div>\n\n'
            'More prose after.\n'
        )
        html, _toc = render_markdown(body)
        # Wrapper + slug attribute present
        self.assertIn('class="demo-embed-root" data-demo="frozen-forecaster"', html)
        # Actual embed content (ids from embed_frozen_forecaster.html)
        self.assertIn('id="ff-canvas"', html)
        self.assertIn('id="frozen-forecaster"', html)
        # Footer link to the standalone demo page
        self.assertIn('/demos/frozen-forecaster/', html)
        # Original prose still rendered
        self.assertIn('Some prose before', html)
        self.assertIn('More prose after', html)

    def test_multiple_markers_in_one_post(self):
        body = (
            '<div data-demo="frozen-forecaster"></div>\n\n'
            'Between two demos.\n\n'
            '<div data-demo="nanoparticle-viewer"></div>\n'
        )
        html, _ = render_markdown(body)
        self.assertIn('data-demo="frozen-forecaster"', html)
        self.assertIn('data-demo="nanoparticle-viewer"', html)

    def test_unknown_slug_renders_inline_error(self):
        body = '<div data-demo="not-a-real-demo"></div>\n'
        html, _ = render_markdown(body)
        self.assertIn('demo-embed-error', html)
        self.assertIn('Unknown demo slug', html)
        self.assertIn('not-a-real-demo', html)
        # Importantly, does NOT silently drop the marker — the author
        # needs to see the typo.
        self.assertNotIn('class="demo-embed-root"', html)

    def test_post_without_markers_unaffected(self):
        """Fast-path: no markers → no template-loading overhead."""
        body = '# Normal post\n\nNothing interactive in here.\n'
        html, _ = render_markdown(body)
        self.assertNotIn('demo-embed-root', html)
        self.assertNotIn('demo-embed-error', html)

    def test_legacy_marker_form_also_expands(self):
        """Pre-2026-04 posts used `<div class="demo-embed" data-slug="…"></div>`.
        Both the legacy and canonical forms expand to the same output."""
        body = (
            'Legacy form:\n\n'
            '<div class="demo-embed" data-slug="nanoparticle-viewer"></div>\n\n'
            'Canonical form:\n\n'
            '<div data-demo="nanoparticle-viewer"></div>\n'
        )
        html, _ = render_markdown(body)
        # Both markers render the embed wrapper with the slug.
        self.assertEqual(
            html.count('class="demo-embed-root" data-demo="nanoparticle-viewer"'),
            2,
        )

    def test_legacy_marker_attribute_order_tolerated(self):
        """Authors sometimes write `data-slug` before `class`. Match anyway."""
        body = '<div data-slug="frozen-forecaster" class="demo-embed"></div>\n'
        html, _ = render_markdown(body)
        self.assertIn('class="demo-embed-root" data-demo="frozen-forecaster"', html)
        self.assertIn('id="ff-canvas"', html)


class DemoEmbedBlogPostIntegrationTests(TestCase):
    """When a blog post body contains the marker, blog_post.html loads
    the matching JS + the demos-embed.css stylesheet."""

    def setUp(self):
        from portfolio.models import Post
        self.post = Post.objects.create(
            slug='ff-deepdive',
            title='Frozen Forecaster deep-dive',
            body=(
                '# Deep-dive\n\n'
                'Here is the live demo:\n\n'
                '<div data-demo="frozen-forecaster"></div>\n'
            ),
            excerpt='A deep-dive on FF.',
            date=date.today(),
        )

    def test_demo_css_linked_when_marker_present(self):
        r = Client().get(f'/blog/{self.post.slug}/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'portfolio/css/demos-embed.css')

    def test_frozen_forecaster_js_loaded_when_marker_present(self):
        r = Client().get(f'/blog/{self.post.slug}/')
        self.assertContains(r, 'portfolio/js/frozen-forecaster.js')

    def test_other_demo_js_not_loaded(self):
        r = Client().get(f'/blog/{self.post.slug}/')
        # The nanoparticle / depth-demo JS modules should NOT be
        # on the page — we only load the module for the slug that's
        # actually embedded.
        self.assertNotContains(r, 'portfolio/js/nanoparticle.js')
        self.assertNotContains(r, 'portfolio/js/depth-demo.js')

    def test_embed_html_rendered_in_post_body(self):
        r = Client().get(f'/blog/{self.post.slug}/')
        # The embed template's main ids end up in the response.
        self.assertContains(r, 'id="ff-canvas"')

    def test_post_without_marker_skips_demo_assets(self):
        from portfolio.models import Post
        p = Post.objects.create(
            slug='plain-post',
            title='Plain post',
            body='# Plain\n\nNo demos here.\n',
            excerpt='Plain.',
            date=date.today(),
        )
        r = Client().get(f'/blog/{p.slug}/')
        self.assertNotContains(r, 'portfolio/css/demos-embed.css')
        self.assertNotContains(r, 'portfolio/js/frozen-forecaster.js')

    def test_legacy_marker_triggers_asset_loading(self):
        """Posts that use the old `<div class="demo-embed" data-slug="…">`
        form get the same CSS + JS loaded as posts using the new form."""
        from portfolio.models import Post
        p = Post.objects.create(
            slug='legacy-demo-post',
            title='Legacy post',
            body=(
                '# Legacy post\n\n'
                '<div class="demo-embed" data-slug="nanoparticle-viewer"></div>\n'
            ),
            excerpt='.',
            date=date.today(),
        )
        r = Client().get(f'/blog/{p.slug}/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'portfolio/css/demos-embed.css')
        self.assertContains(r, 'portfolio/js/nanoparticle.js')


class DemoWriteupTemplateTests(TestCase):
    """`/blog/new/?template=demo&demo=<slug>` pre-fills title + body
    from the DEMOS entry so the new draft already embeds the widget."""

    def setUp(self):
        self.user = User.objects.create_user('staff', password='pw', is_staff=True, is_superuser=True)
        self.client = Client()
        self.client.force_login(self.user)

    def test_demo_slug_prefills_body_marker(self):
        from portfolio.models import Post
        # New-post creation is POST-only (GET would create a draft
        # on every browser refresh / prefetch otherwise).
        r = self.client.post('/blog/new/', {'template': 'demo', 'demo': 'frozen-forecaster'})
        self.assertEqual(r.status_code, 302)
        self.assertIn('/edit/', r['Location'])
        p = Post.objects.filter(title__startswith='Demo:').order_by('-id').first()
        self.assertIsNotNone(p)
        self.assertIn('<div data-demo="frozen-forecaster"></div>', p.body)
        self.assertIn('The Frozen Forecaster', p.title)

    def test_missing_demo_slug_still_creates_draft(self):
        from portfolio.models import Post
        before = Post.objects.count()
        r = self.client.post('/blog/new/', {'template': 'demo'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Post.objects.count(), before + 1)
        p = Post.objects.order_by('-id').first()
        self.assertIn('<div data-demo="<slug>"></div>', p.body)

    def test_unknown_demo_slug_falls_back_to_generic_body(self):
        """Typo in ?demo= shouldn't 500; just falls back to the
        generic template with the placeholder still in the body."""
        from portfolio.models import Post
        r = self.client.post('/blog/new/', {'template': 'demo', 'demo': 'not-a-real-demo'})
        self.assertEqual(r.status_code, 302)
        p = Post.objects.order_by('-id').first()
        self.assertIn('<slug>', p.body)

    def test_studio_lists_demos(self):
        r = self.client.get('/site/studio/')
        self.assertEqual(r.status_code, 200)
        # Studio now submits demo picks via a POST form with a hidden
        # `template=demo` field and a button per demo with `name="demo"
        # value="<slug>"`. Assert the per-demo button is present.
        for d in DEMOS:
            self.assertContains(r, f'name="demo" value="{d["slug"]}"')
