"""Editor endpoints: blog_edit, blog_autosave, blog_preview, blog_new,
blog_upload_image. All require staff auth."""
import io
import re
import tempfile

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from portfolio.models import Post

from ._helpers import StaffClientMixin, make_post

# Smallest valid PNG: 1x1 transparent. Shared by the upload tests.
MINIMAL_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
    b'\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00'
    b'\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\x00\x01'
    b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)


class BlogEditTests(StaffClientMixin, TestCase):
    def test_get_renders_form(self):
        post = make_post(slug='render-me', title='Render me')
        r = self.staff_client.get(f'/blog/{post.slug}/edit/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'editor-body')
        self.assertContains(r, 'fm-drawer')   # frontmatter drawer present
        self.assertContains(r, 'slash-menu')  # slash menu container present
        self.assertContains(r, 'word-count')

    def test_post_persists_basic_fields(self):
        post = make_post(slug='persist-me', title='Original title')
        r = self.staff_client.post(f'/blog/{post.slug}/edit/', {
            'title': 'Updated title',
            'body': '# Updated body',
            'excerpt': 'A new excerpt',
            'is_explainer': 'on',
            'tags': 'ml, tabular',
            'maturity': 'budding',
            'date': '2026-01-15',
            'action': 'save',
        })
        self.assertEqual(r.status_code, 302)  # redirects on save
        post.refresh_from_db()
        self.assertEqual(post.title, 'Updated title')
        self.assertEqual(post.excerpt, 'A new excerpt')
        self.assertTrue(post.is_explainer)
        self.assertEqual(post.maturity, 'budding')
        self.assertEqual(set(t.name for t in post.tags.all()), {'ml', 'tabular'})

    def test_post_save_and_view_action(self):
        post = make_post(slug='save-and-view')
        r = self.staff_client.post(f'/blog/{post.slug}/edit/', {
            'title': 'X',
            'body': 'Y',
            'action': 'view',
        })
        self.assertEqual(r.status_code, 302)
        self.assertIn(f'/blog/{post.slug}/', r.headers['Location'])

    def test_post_save_slugifies_free_form_slug(self):
        """Details-drawer slug input is free-form — Save must run it
        through slugify so "My new title" becomes "my-new-title"
        instead of saving an unroutable URL fragment."""
        post = make_post(slug='slug-free-form')
        r = self.staff_client.post(f'/blog/{post.slug}/edit/', {
            'title': 'T', 'body': 'B', 'slug': 'My New Title!',
            'action': 'save',
        })
        self.assertEqual(r.status_code, 302)
        self.assertIn('/blog/my-new-title/edit/', r.headers['Location'])
        self.assertTrue(Post.objects.filter(slug='my-new-title').exists())

    def test_post_save_empty_slug_keeps_old_one(self):
        """A blank or all-symbols slug input must NOT clear the slug —
        empty PK on Post raises IntegrityError mid-save, and a slug
        rename mid-session orphans the open editor."""
        post = make_post(slug='slug-keep-me')
        r = self.staff_client.post(f'/blog/{post.slug}/edit/', {
            'title': 'T', 'body': 'B', 'slug': '   ',
            'action': 'save',
        })
        self.assertEqual(r.status_code, 302)
        post.refresh_from_db()
        self.assertEqual(post.slug, 'slug-keep-me')

    def test_post_save_colliding_slug_suffixes_instead_of_500(self):
        """A user pasting a slug already in use must get a `-2` suffix
        instead of an IntegrityError 500 mid-save."""
        make_post(slug='occupied-slug', title='Other')
        post = make_post(slug='moving-slug')
        r = self.staff_client.post(f'/blog/{post.slug}/edit/', {
            'title': 'T', 'body': 'B', 'slug': 'occupied-slug',
            'action': 'save',
        })
        self.assertEqual(r.status_code, 302)
        post.refresh_from_db()
        self.assertEqual(post.slug, 'occupied-slug-2')


class BlogEditLockTests(StaffClientMixin, TestCase):
    """Click-through lock with per-render instance tokens.

    Invariants under guard:
      - the lock gates GET only — POST saves and autosaves ALWAYS persist;
      - a tab whose instance no longer matches the lock is told so
        (lock_lost) but never blocked;
      - clients that don't send editor_instance (old pages, e2e scripts)
        see no new response keys.
    """

    def setUp(self):
        super().setUp()
        cache.clear()  # locmem persists across tests in-process

    def _open_editor(self, slug):
        """GET the editor and return the minted instance token."""
        r = self.staff_client.get(f'/blog/{slug}/edit/')
        self.assertEqual(r.status_code, 200)
        m = re.search(r'name="editor_instance" value="([^"]+)"', r.content.decode())
        self.assertIsNotNone(m, 'editor page must embed an instance token')
        return m.group(1)

    def test_editor_get_sets_no_store(self):
        post = make_post(slug='lock-nostore')
        r = self.staff_client.get(f'/blog/{post.slug}/edit/')
        self.assertEqual(r['Cache-Control'], 'no-store')

    def test_two_renders_mint_distinct_instances(self):
        post = make_post(slug='lock-two-tabs')
        inst_a = self._open_editor(post.slug)
        inst_b = self._open_editor(post.slug)
        self.assertNotEqual(inst_a, inst_b)

    def test_heartbeat_states(self):
        post = make_post(slug='lock-heartbeat')
        inst_a = self._open_editor(post.slug)
        inst_b = self._open_editor(post.slug)  # B now holds the lock
        url = f'/blog/{post.slug}/edit/heartbeat/'
        # Stale tab A: lock belongs to a sibling instance.
        d = self.staff_client.post(url, {'editor_instance': inst_a}).json()
        self.assertEqual(d['lock'], 'other')
        self.assertTrue(d['same_user'])
        # Holding tab B: refresh succeeds.
        d = self.staff_client.post(url, {'editor_instance': inst_b}).json()
        self.assertEqual(d['lock'], 'ours')
        # Lock gone entirely (TTL lapse) → re-acquired.
        cache.clear()
        d = self.staff_client.post(url, {'editor_instance': inst_b}).json()
        self.assertEqual(d['lock'], 'acquired')

    def test_takeover_action_reclaims_lock(self):
        post = make_post(slug='lock-takeover')
        inst_a = self._open_editor(post.slug)
        self._open_editor(post.slug)  # B steals
        url = f'/blog/{post.slug}/edit/heartbeat/'
        d = self.staff_client.post(url, {'editor_instance': inst_a, 'action': 'takeover'}).json()
        self.assertEqual(d['lock'], 'acquired')
        d = self.staff_client.post(url, {'editor_instance': inst_a}).json()
        self.assertEqual(d['lock'], 'ours')

    def test_release_from_stale_tab_keeps_sibling_lock(self):
        # Regression guard: a closing stale tab's release beacon used to
        # free the sibling tab's lock (both share the session tab_token).
        post = make_post(slug='lock-release')
        inst_a = self._open_editor(post.slug)
        inst_b = self._open_editor(post.slug)  # B holds
        url = f'/blog/{post.slug}/edit/heartbeat/'
        self.staff_client.post(url, {'editor_instance': inst_a, 'action': 'release'})
        d = self.staff_client.post(url, {'editor_instance': inst_b}).json()
        self.assertEqual(d['lock'], 'ours', 'stale release must not free the holder')
        # A matching release DOES free it — and the tombstone stops the
        # releasing instance's own straggling heartbeat from silently
        # re-acquiring (it reports 'other'; the lock stays free).
        self.staff_client.post(url, {'editor_instance': inst_b, 'action': 'release'})
        d = self.staff_client.post(url, {'editor_instance': inst_b}).json()
        self.assertEqual(d['lock'], 'other')
        self.assertIsNone(cache.get(f'edit_lock:{post.slug}'))
        # A fresh editor render (new instance) acquires normally.
        inst_c = self._open_editor(post.slug)
        d = self.staff_client.post(url, {'editor_instance': inst_c}).json()
        self.assertEqual(d['lock'], 'ours')

    def test_autosave_from_stale_tab_persists_and_reports_lock_lost(self):
        post = make_post(slug='lock-autosave', title='before')
        inst_a = self._open_editor(post.slug)
        self._open_editor(post.slug)  # B holds the lock now
        r = self.staff_client.post(f'/blog/{post.slug}/autosave/', {
            'title': 'stale tab wrote this', 'editor_instance': inst_a,
        })
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d['ok'])
        self.assertTrue(d['lock_lost'])
        self.assertTrue(d['same_user'])
        post.refresh_from_db()
        # The one bounded final write still lands — lock never gates saves.
        self.assertEqual(post.title, 'stale tab wrote this')

    def test_autosave_from_holder_refreshes_without_lock_lost(self):
        post = make_post(slug='lock-autosave-holder')
        inst = self._open_editor(post.slug)
        r = self.staff_client.post(f'/blog/{post.slug}/autosave/', {
            'title': 'fresh', 'editor_instance': inst,
        })
        self.assertNotIn('lock_lost', r.json())

    def test_autosave_without_instance_has_no_new_keys(self):
        post = make_post(slug='lock-backcompat')
        self._open_editor(post.slug)
        r = self.staff_client.post(f'/blog/{post.slug}/autosave/', {'title': 'X'})
        self.assertEqual(sorted(r.json().keys()), ['ok', 'saved_at'])

    def test_explicit_save_proceeds_regardless_of_lock(self):
        # The lock NEVER gates a POST save — recorded design decision.
        from django.core.cache import cache as _cache
        post = make_post(slug='lock-save-anyway', title='before')
        _cache.set(f'edit_lock:{post.slug}', {
            'user_id': 999999, 'username': 'someone-else',
            'tab_token': 'foreign', 'instance': 'foreign-inst',
            'acquired_at': 0, 'last_heartbeat': 0,
        }, 120)
        r = self.staff_client.post(f'/blog/{post.slug}/edit/', {
            'title': 'saved anyway', 'body': 'content', 'action': 'save',
        })
        self.assertEqual(r.status_code, 302)
        post.refresh_from_db()
        self.assertEqual(post.title, 'saved anyway')

    def test_release_tombstone_blocks_straggling_beacons(self):
        # A closing dirty tab fires its release beacon and final autosave
        # beacon concurrently. If the autosave lands second it must NOT
        # re-acquire the lock for the dead tab.
        post = make_post(slug='lock-tombstone')
        inst = self._open_editor(post.slug)
        self.staff_client.post(f'/blog/{post.slug}/edit/heartbeat/',
                               {'editor_instance': inst, 'action': 'release'})
        r = self.staff_client.post(f'/blog/{post.slug}/autosave/', {
            'title': 'final flush', 'editor_instance': inst,
        })
        self.assertTrue(r.json()['ok'])  # the write itself still lands
        self.assertIsNone(cache.get(f'edit_lock:{post.slug}'),
                          'dead tab must not resurrect the released lock')
        post.refresh_from_db()
        self.assertEqual(post.title, 'final flush')

    def test_unloading_flush_never_refreshes_lock(self):
        # The pagehide flush carries unloading=1 — even while the lock is
        # held, a final flush must not extend/refresh it.
        post = make_post(slug='lock-unloading')
        inst = self._open_editor(post.slug)
        cache.delete(f'edit_lock:{post.slug}')  # simulate TTL lapse
        r = self.staff_client.post(f'/blog/{post.slug}/autosave/', {
            'title': 'unload flush', 'editor_instance': inst, 'unloading': '1',
        })
        self.assertTrue(r.json()['ok'])
        self.assertIsNone(cache.get(f'edit_lock:{post.slug}'),
                          'unloading flush must not re-acquire the lock')

    def test_locked_page_for_other_session(self):
        # A different browser session (different tab_token) hits the
        # locked screen instead of the editor.
        from ._helpers import make_staff_user
        from django.test import Client
        post = make_post(slug='lock-other-session')
        self._open_editor(post.slug)
        other = Client()
        other.force_login(make_staff_user(username='second-staff'))
        r = other.get(f'/blog/{post.slug}/edit/')
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, 'portfolio/blog_edit_locked.html')


class BlogEditRenderFailureTests(StaffClientMixin, TestCase):
    """Explicit-Save render failures must be surfaced, never swallowed:
    the body save still commits, but the author is returned to the
    editor with ?render_failed=1 instead of (worse) a stale public page."""

    def _post_with_broken_render(self, slug, action):
        from unittest.mock import patch
        with patch('portfolio.blog.render_markdown', side_effect=RuntimeError('boom')):
            return self.staff_client.post(f'/blog/{slug}/edit/', {
                'title': 'saved despite render crash',
                'body': 'new body',
                'action': action,
            })

    def test_save_redirects_with_flag_and_persists(self):
        post = make_post(slug='render-fail-save', title='before')
        r = self._post_with_broken_render(post.slug, 'save')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers['Location'], f'/blog/{post.slug}/edit/?render_failed=1')
        post.refresh_from_db()
        self.assertEqual(post.title, 'saved despite render crash')

    def test_save_and_view_returns_to_editor_not_stale_page(self):
        post = make_post(slug='render-fail-view')
        r = self._post_with_broken_render(post.slug, 'view')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/edit/?render_failed=1', r.headers['Location'])

    def test_flag_renders_banner(self):
        post = make_post(slug='render-fail-banner')
        r = self.staff_client.get(f'/blog/{post.slug}/edit/?render_failed=1')
        self.assertContains(r, 'render failed')

    def test_clean_save_keeps_existing_redirects(self):
        post = make_post(slug='render-ok')
        r = self.staff_client.post(f'/blog/{post.slug}/edit/', {
            'title': 'X', 'body': 'Y', 'action': 'view',
        })
        self.assertEqual(r.status_code, 302)
        self.assertIn(f'/blog/{post.slug}/', r.headers['Location'])
        self.assertNotIn('render_failed', r.headers['Location'])


class BlogAutosaveTests(StaffClientMixin, TestCase):
    def test_autosave_returns_ok(self):
        post = make_post(slug='auto-me', title='before')
        r = self.staff_client.post(f'/blog/{post.slug}/autosave/', {
            'title': 'after',
            'body': 'body content',
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['ok'])
        self.assertIn('saved_at', data)
        post.refresh_from_db()
        self.assertEqual(post.title, 'after')

    def test_autosave_unauth_403(self):
        post = make_post(slug='unauth-auto')
        r = self.anon_client.post(f'/blog/{post.slug}/autosave/', {'title': 'X'})
        self.assertEqual(r.status_code, 403)

    def test_autosave_get_405(self):
        post = make_post(slug='get-auto')
        r = self.staff_client.get(f'/blog/{post.slug}/autosave/')
        self.assertEqual(r.status_code, 405)

    def test_autosave_404_for_unknown_slug(self):
        r = self.staff_client.post('/blog/no-such-slug/autosave/', {'title': 'X'})
        self.assertEqual(r.status_code, 404)

    def test_autosave_skips_full_render(self):
        # Autosave must NOT trigger the expensive _render_and_persist
        # path. Otherwise each keystroke re-runs pyfig + arxiv/github/
        # wiki fetches and blocks the web worker. Explicit Save still
        # renders (tested via the blog_edit POST path).
        from unittest.mock import patch
        post = make_post(slug='auto-render', body='# Hi')
        with patch('portfolio.signals._render_and_persist') as render:
            r = self.staff_client.post(f'/blog/{post.slug}/autosave/', {
                'title': 'After', 'body': '# Hi there',
            })
        self.assertEqual(r.status_code, 200)
        render.assert_not_called()

    def test_explicit_save_still_renders(self):
        # The Save button (POST /blog/<slug>/edit/) must persist a fresh
        # render so the published HTML stays in sync. The view's own
        # render_markdown call is the authoritative one for this path —
        # the post_save signal's render is skipped to avoid rendering
        # the post twice on pyfig-heavy bodies.
        post = make_post(slug='save-render', body='# Hi')
        self.staff_client.post(f'/blog/{post.slug}/edit/', {
            'title': 'Updated', 'body': '# Updated body', 'action': 'save',
        })
        post.refresh_from_db()
        self.assertIn('Updated body', post.rendered_html or '')

    def test_explicit_save_skips_signal_render(self):
        # Regression guard for the "Save renders twice" bug: the explicit
        # render in the view is the only one that should run; the signal
        # path must be short-circuited via post._skip_render.
        from unittest.mock import patch
        post = make_post(slug='save-once', body='# Hi')
        with patch('portfolio.signals._render_and_persist') as render:
            self.staff_client.post(f'/blog/{post.slug}/edit/', {
                'title': 'Updated', 'body': '# Updated body', 'action': 'save',
            })
        render.assert_not_called()

    def test_autosave_persists_tags_and_maturity(self):
        post = make_post(slug='auto-tags', tags=['old'])
        r = self.staff_client.post(f'/blog/{post.slug}/autosave/', {
            'title': 'Updated', 'tags': 'ml, tabular, new',
            'maturity': 'evergreen',
        })
        self.assertEqual(r.status_code, 200)
        post.refresh_from_db()
        self.assertEqual(post.maturity, 'evergreen')
        self.assertEqual(set(t.name for t in post.tags.all()), {'ml', 'tabular', 'new'})

    def test_autosave_clears_tags_with_empty_string(self):
        post = make_post(slug='auto-clear', tags=['old', 'tags'])
        self.staff_client.post(f'/blog/{post.slug}/autosave/', {
            'title': post.title, 'tags': '',
        })
        post.refresh_from_db()
        self.assertEqual(list(post.tags.all()), [])


class AutosaveSlugSafetyTests(StaffClientMixin, TestCase):
    """Slug edits must NOT apply on autosave: a mid-session rename
    orphans the open editor (every later autosave/heartbeat/Save targets
    the old slug's URLs and 404s). Slug changes land on explicit Save,
    whose redirect re-enters the editor under the new slug."""

    def test_autosave_ignores_slug_changes(self):
        post = make_post(slug='slug-stays', title='t')
        r = self.staff_client.post(f'/blog/{post.slug}/autosave/', {
            'title': 'still me', 'slug': 'renamed-by-autosave',
        })
        self.assertTrue(r.json()['ok'])
        post.refresh_from_db()
        self.assertEqual(post.slug, 'slug-stays')
        self.assertEqual(post.title, 'still me')

    def test_explicit_save_applies_slug_and_redirects_to_new_editor(self):
        post = make_post(slug='slug-moves', title='t')
        r = self.staff_client.post(f'/blog/{post.slug}/edit/', {
            'title': 't', 'body': 'b', 'slug': 'slug-moved', 'action': 'save',
        })
        self.assertEqual(r.status_code, 302)
        self.assertIn('/blog/slug-moved/edit/', r.headers['Location'])
        post.refresh_from_db()
        self.assertEqual(post.slug, 'slug-moved')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix='test-cover-'))
class CoverImageLifecycleTests(StaffClientMixin, TestCase):
    """Cover upload/clear is explicit-Save-only, and 'remove + replace'
    must replace — not delete the fresh upload."""

    def setUp(self):
        super().setUp()
        cache.clear()

    def _post_with_cover(self, slug):
        post = make_post(slug=slug)
        self.staff_client.post(f'/blog/{post.slug}/edit/', {
            'title': post.title, 'body': post.body, 'action': 'save',
        })
        f = SimpleUploadedFile('cover.png', MINIMAL_PNG, content_type='image/png')
        self.staff_client.post(f'/blog/{post.slug}/edit/', {
            'title': post.title, 'body': post.body, 'action': 'save',
            'cover_image': f,
        }, format='multipart')
        post.refresh_from_db()
        self.assertTrue(post.cover_image, 'fixture should have a cover')
        return post

    def test_autosave_never_clears_cover(self):
        # The checkbox says "Remove current cover ON SAVE" — an autosave
        # carrying the ticked box must not delete the stored file.
        post = self._post_with_cover('cover-autosave-safe')
        name = post.cover_image.name
        from django.core.files.storage import default_storage
        r = self.staff_client.post(f'/blog/{post.slug}/autosave/', {
            'title': post.title, 'cover_image_clear': '1',
        })
        self.assertTrue(r.json()['ok'])
        post.refresh_from_db()
        self.assertTrue(post.cover_image, 'cover must survive autosave')
        self.assertTrue(default_storage.exists(name), 'file must survive autosave')

    def test_save_with_clear_removes_cover(self):
        post = self._post_with_cover('cover-clear')
        self.staff_client.post(f'/blog/{post.slug}/edit/', {
            'title': post.title, 'body': post.body, 'action': 'save',
            'cover_image_clear': '1',
        })
        post.refresh_from_db()
        self.assertFalse(post.cover_image)

    def test_save_with_clear_and_new_file_replaces(self):
        # Tick "remove" + pick a replacement = replace. The clear must
        # not delete the fresh upload.
        post = self._post_with_cover('cover-replace')
        old_name = post.cover_image.name
        f = SimpleUploadedFile('new-cover.png', MINIMAL_PNG, content_type='image/png')
        self.staff_client.post(f'/blog/{post.slug}/edit/', {
            'title': post.title, 'body': post.body, 'action': 'save',
            'cover_image_clear': '1', 'cover_image': f,
        }, format='multipart')
        post.refresh_from_db()
        self.assertTrue(post.cover_image, 'replacement cover must persist')
        self.assertNotEqual(post.cover_image.name, old_name)


class CreateNonceTests(StaffClientMixin, TestCase):
    """One creation per rendered form: a double-click (or cold-start
    re-click) re-submits the same nonce and must not duplicate."""

    def setUp(self):
        super().setUp()
        cache.clear()

    def test_blog_new_duplicate_nonce_reuses_draft(self):
        before = Post.objects.count()
        payload = {'template': 'blank', 'create_nonce': 'nonce-dupe-test'}
        r1 = self.staff_client.post('/blog/new/', payload)
        r2 = self.staff_client.post('/blog/new/', payload)
        self.assertEqual(Post.objects.count(), before + 1,
                         'duplicate submit must not create a second draft')
        self.assertEqual(r1.headers['Location'], r2.headers['Location'])

    def test_blog_new_fresh_nonces_create_separately(self):
        before = Post.objects.count()
        self.staff_client.post('/blog/new/', {'template': 'blank', 'create_nonce': 'n1'})
        self.staff_client.post('/blog/new/', {'template': 'blank', 'create_nonce': 'n2'})
        self.assertEqual(Post.objects.count(), before + 2)

    def test_blog_new_without_nonce_still_creates(self):
        # Back-compat: old pages / tests post without a nonce.
        before = Post.objects.count()
        r = self.staff_client.post('/blog/new/', {'template': 'blank'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Post.objects.count(), before + 1)

    def test_picker_renders_nonce(self):
        r = self.staff_client.get('/blog/new/')
        self.assertContains(r, 'name="create_nonce"')

    def test_reading_quickadd_duplicate_nonce_skipped(self):
        from portfolio.models import Reading
        before = Reading.objects.count()
        payload = {'title': 'Dup paper', 'create_nonce': 'read-nonce-1',
                   'next': '/site/studio/'}
        self.staff_client.post('/site/reading/add/', payload)
        self.staff_client.post('/site/reading/add/', payload)
        self.assertEqual(Reading.objects.count(), before + 1)


class BlogPreviewTests(StaffClientMixin, TestCase):
    def test_preview_renders_markdown(self):
        r = self.staff_client.post('/blog/preview/', {
            'body': '# Hello\n\nA paragraph with **bold**.',
            'is_explainer': 'false',
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn('<h1', data['html'])
        self.assertIn('<strong>bold</strong>', data['html'])

    def test_preview_unauth_403(self):
        r = self.anon_client.post('/blog/preview/', {'body': 'x'})
        self.assertEqual(r.status_code, 403)

    def test_preview_skips_heavy_embeds(self):
        # Heavy markers should render as cheap placeholders so the preview
        # round-trip never hits the network / never runs matplotlib.
        body = (
            '# Post\n\n'
            '<div data-demo="nanoparticle-viewer"></div>\n\n'
            '<div data-arxiv="1706.03762"></div>\n\n'
            '<div data-github="loevlie/neuropt"></div>\n\n'
            '<div data-github-snippet="o/r@main:x.py#L1-L5"></div>\n\n'
            '<div data-wiki="Transformer"></div>\n\n'
            '```python pyfig\n'
            'import matplotlib.pyplot as plt\n'
            'plt.plot([1, 2, 3])\n'
            '```\n'
        )
        r = self.staff_client.post('/blog/preview/', {
            'body': body, 'is_explainer': 'false',
        })
        self.assertEqual(r.status_code, 200)
        html = r.json()['html']
        # Every heavy marker is a compact placeholder in preview mode.
        self.assertEqual(html.count('preview-placeholder'), 6)
        # None of the real embed chrome made it through.
        self.assertNotIn('embed-card', html)
        self.assertNotIn('github-snippet', html)
        self.assertNotIn('demo-embed-root', html)
        self.assertNotIn('<figure', html)   # pyfig <figure> suppressed
        # The placeholder tells the author which embed it stands for.
        self.assertIn('nanoparticle-viewer', html)
        self.assertIn('1706.03762', html)
        self.assertIn('Transformer', html)

    def test_preview_caches_identical_renders(self):
        # Hitting preview with the same body twice should go through
        # the in-process LRU the second time. We don't assert wall-clock
        # timing (flaky) — instead we assert the Server-Timing header
        # drops to 0ms on the cached hit.
        body = '# Hello\n\nsome text'
        payload = {'body': body, 'is_explainer': 'false'}
        r1 = self.staff_client.post('/blog/preview/', payload)
        r2 = self.staff_client.post('/blog/preview/', payload)
        t1 = r1.get('Server-Timing', '')
        t2 = r2.get('Server-Timing', '')
        self.assertTrue(t1.startswith('render;dur='))
        self.assertEqual(t2, 'render;dur=0')
        self.assertEqual(r1.json()['html'], r2.json()['html'])

    def test_preview_notation_parity_and_slug_scoped_cache(self):
        # Two posts with IDENTICAL bodies but different Post.notation
        # must get different previews — the cache key includes the slug
        # and a notation hash, and the preview populates the glossary
        # exactly like the published page (preview/published parity).
        body = '# T\n\n<div data-notation>\n</div>\n'
        a = make_post(slug='notation-a', body=body)
        a.notation = [{'term': 'α', 'definition': 'alpha-def-only-in-a', 'kind': 'text'}]
        a.save()
        b = make_post(slug='notation-b', body=body)
        b.notation = [{'term': 'β', 'definition': 'beta-def-only-in-b', 'kind': 'text'}]
        b.save()
        ra = self.staff_client.post('/blog/preview/', {
            'body': body, 'is_explainer': 'false', 'slug': a.slug,
        }).json()['html']
        rb = self.staff_client.post('/blog/preview/', {
            'body': body, 'is_explainer': 'false', 'slug': b.slug,
        }).json()['html']
        self.assertIn('alpha-def-only-in-a', ra)
        self.assertNotIn('beta-def-only-in-b', ra)
        self.assertIn('beta-def-only-in-b', rb)

    def test_preview_keeps_cheap_embeds(self):
        # Cheap, pure-Python embeds (notation, repro) should still render
        # fully — the fast-path only strips network/compute-heavy ones.
        body = (
            '<div data-notation>\n'
            'θ: parameters\n'
            '</div>\n'
        )
        r = self.staff_client.post('/blog/preview/', {
            'body': body, 'is_explainer': 'false',
        })
        html = r.json()['html']
        self.assertIn('notation-glossary', html)


class BlogNewTests(StaffClientMixin, TestCase):
    def test_picker_renders(self):
        r = self.staff_client.get('/blog/new/')
        self.assertEqual(r.status_code, 200)
        # The picker should list every template label
        for label in ('Blank', 'Explainer', 'Paper companion', 'Quick note', 'Demo writeup'):
            self.assertContains(r, label, msg_prefix=f'{label!r} not in picker')

    def test_template_creates_post_and_redirects(self):
        # POST-only: a GET creating posts spawns duplicates on browser
        # refresh / back-nav / link prefetch.
        r = self.staff_client.post('/blog/new/', {'template': 'explainer'})
        self.assertEqual(r.status_code, 302)
        self.assertIn('/edit/', r.headers['Location'])
        # The created post should be a draft + an explainer
        slug = r.headers['Location'].rsplit('/edit/', 1)[0].rsplit('/', 1)[-1]
        p = Post.objects.get(slug=slug)
        self.assertTrue(p.draft)
        self.assertTrue(p.is_explainer)
        self.assertEqual(p.maturity, 'budding')

    def test_unknown_template_falls_back_to_picker(self):
        # Unknown template via POST still renders the picker (no create).
        r = self.staff_client.post('/blog/new/', {'template': 'nonsense'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Choose a template')

    def test_get_never_creates_post(self):
        """GET /blog/new/?template=X must NOT create a draft, no matter
        what the query string says. Regression guard for the duplicate-
        draft bug: browsers prefetch / back-navigate to this URL, which
        used to spawn a new post on every hit."""
        before = Post.objects.count()
        r = self.staff_client.get('/blog/new/?template=explainer')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Post.objects.count(), before)

    def test_anon_redirected_to_login(self):
        r = self.anon_client.get('/blog/new/')
        self.assertEqual(r.status_code, 302)
        # blog_new now gates on the `portfolio.add_post` permission and
        # routes anon visitors through the public auth flow.
        self.assertIn('/accounts/login/', r.headers['Location'])

    def test_guest_author_lands_in_editor_for_own_draft(self):
        """A non-staff user with `portfolio.add_post` must be enrolled as
        a PostCollaborator on the draft they just created — otherwise the
        redirect into /blog/<slug>/edit/ bounces them through _can_edit
        and they can't open the post they just made.
        """
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission
        User = get_user_model()
        # Make the staff user a superuser-fixture so the byline-owner
        # signal has someone to enroll at order=1.
        u = User.objects.create_user(
            'guest-author', email='g@example.com', password='pw')
        u.user_permissions.add(
            Permission.objects.get(codename='add_post'))
        c = Client()
        c.force_login(u)

        r = c.post('/blog/new/', {'template': 'blank'})
        self.assertEqual(r.status_code, 302)
        slug = r.headers['Location'].rsplit('/edit/', 1)[0].rsplit('/', 1)[-1]

        # Follow the redirect and confirm the editor renders (no second
        # bounce through _can_edit → /accounts/login/).
        r = c.get(f'/blog/{slug}/edit/')
        self.assertEqual(r.status_code, 200)
        # And the row actually exists on the through model.
        from portfolio.models import PostCollaborator
        self.assertTrue(
            PostCollaborator.objects.filter(post__slug=slug, user=u).exists())


class GetPostFallbackTests(TestCase):
    """Once any Post row exists, get_post must NOT fall back to a
    matching .md file for a drafted/missing slug — that bug let the
    public page serve a stale published markdown after the author
    had explicitly drafted or deleted the DB row.
    """

    def test_drafted_db_post_does_not_resurrect_md_file(self):
        from pathlib import Path
        from portfolio.blog import get_post, POSTS_DIR
        # Seed any post so _has_db() returns True.
        from datetime import date
        Post.objects.create(
            slug='other-post', title='Other', body='hi',
            excerpt='x', date=date.today(), draft=False)
        # Create a .md file that would HAVE served if fallback were
        # still active.
        POSTS_DIR.mkdir(parents=True, exist_ok=True)
        md = Path(POSTS_DIR) / 'drafted-with-md.md'
        md.write_text(
            '---\ntitle: From file\ndate: 2024-01-01\ndraft: false\n---\n\nFile body\n',
            encoding='utf-8')
        self.addCleanup(md.unlink)

        # Now draft the DB row for that slug.
        Post.objects.create(
            slug='drafted-with-md', title='From DB', body='db body',
            excerpt='x', date=date.today(), draft=True)

        # Public fetch must return None (drafted), not the file's body.
        self.assertIsNone(get_post('drafted-with-md', include_drafts=False))


# Uploads land in a throwaway MEDIA_ROOT — without this, every test run
# left test_*.png clutter in the real media/blog-images tree.
@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix='test-media-'))
class BlogUploadImageTests(StaffClientMixin, TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()  # webp-sib:* entries must not leak between tests

    def test_upload_returns_markdown_snippet(self):
        f = SimpleUploadedFile('test.png', MINIMAL_PNG, content_type='image/png')
        r = self.staff_client.post('/blog/upload-image/', {'image': f, 'alt': 'test'})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn('![test]', data['markdown'])
        self.assertIn('blog-images', data['url'])

    def test_upload_generates_webp_sibling(self):
        from django.core.files.storage import default_storage
        f = SimpleUploadedFile('sibling.png', MINIMAL_PNG, content_type='image/png')
        r = self.staff_client.post('/blog/upload-image/', {'image': f})
        self.assertEqual(r.status_code, 200)
        saved = r.json()['filename']
        webp = saved.rsplit('.', 1)[0] + '.webp'
        self.assertTrue(default_storage.exists(webp),
                        'PNG upload must produce a .webp sibling')

    def test_upload_survives_webp_failure(self):
        # The sibling is best-effort — a Pillow crash must never fail
        # the upload itself, and no sibling may be left behind.
        from unittest.mock import patch
        from django.core.files.storage import default_storage
        f = SimpleUploadedFile('nowebp.png', MINIMAL_PNG, content_type='image/png')
        with patch('PIL.Image.open', side_effect=OSError('decoder boom')):
            r = self.staff_client.post('/blog/upload-image/', {'image': f})
        self.assertEqual(r.status_code, 200)
        saved = r.json()['filename']
        self.assertEqual(sorted(r.json().keys()), ['filename', 'markdown', 'url'])
        self.assertFalse(default_storage.exists(saved.rsplit('.', 1)[0] + '.webp'))

    def test_same_stem_different_ext_never_pairs_with_wrong_webp(self):
        # foo.png then foo.jpg: the jpg must get its own stem (and its
        # own sibling) — deriving foo.webp from foo_Xy.jpg's name space
        # could otherwise pair the jpg with the PNG's webp.
        import io
        from PIL import Image
        from django.core.files.storage import default_storage
        f1 = SimpleUploadedFile('shared-stem.png', MINIMAL_PNG, content_type='image/png')
        name1 = self.staff_client.post('/blog/upload-image/', {'image': f1}).json()['filename']
        buf = io.BytesIO()
        Image.new('RGB', (5, 5), 'red').save(buf, 'JPEG')
        f2 = SimpleUploadedFile('shared-stem.jpg', buf.getvalue(), content_type='image/jpeg')
        name2 = self.staff_client.post('/blog/upload-image/', {'image': f2}).json()['filename']
        stem1 = name1.rsplit('.', 1)[0]
        stem2 = name2.rsplit('.', 1)[0]
        self.assertNotEqual(stem1, stem2, 'second upload must get a fresh stem')
        self.assertTrue(default_storage.exists(stem2 + '.webp'),
                        "jpg's own webp sibling must exist under its stem")

    def test_media_img_wrapped_in_picture_on_save_render_not_preview(self):
        # Save-time renders wrap MEDIA_URL images that have a .webp
        # sibling in <picture>; the preview hot path never does (no
        # storage I/O per keystroke).
        from portfolio.blog import render_markdown
        f = SimpleUploadedFile('wrapme.png', MINIMAL_PNG, content_type='image/png')
        url = self.staff_client.post('/blog/upload-image/', {'image': f}).json()['url']
        body = f'![pic]({url})'
        html, _ = render_markdown(body, preview=False)
        self.assertIn('<picture><source srcset=', html)
        self.assertIn('.webp', html.split('<img', 1)[0])
        cache.clear()
        preview_html, _ = render_markdown(body, preview=True)
        self.assertNotIn('<picture>', preview_html)

    def test_upload_rejects_non_image(self):
        f = SimpleUploadedFile('evil.exe', b'MZsomeexe', content_type='application/x-executable')
        r = self.staff_client.post('/blog/upload-image/', {'image': f})
        self.assertEqual(r.status_code, 400)

    def test_upload_unauth_403(self):
        f = SimpleUploadedFile('test.png', b'fake', content_type='image/png')
        r = self.anon_client.post('/blog/upload-image/', {'image': f})
        self.assertEqual(r.status_code, 403)

    def test_upload_rejects_oversize(self):
        # Manufacture an >8MB "image" payload
        big = b'x' * (9 * 1024 * 1024)
        f = SimpleUploadedFile('big.png', big, content_type='image/png')
        r = self.staff_client.post('/blog/upload-image/', {'image': f})
        self.assertEqual(r.status_code, 400)
        self.assertIn('too large', r.json()['error'])

    def test_upload_get_returns_405(self):
        r = self.staff_client.get('/blog/upload-image/')
        self.assertEqual(r.status_code, 405)
