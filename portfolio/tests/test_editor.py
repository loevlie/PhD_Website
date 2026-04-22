"""Editor endpoints: blog_edit, blog_autosave, blog_preview, blog_new,
blog_upload_image. All require staff auth."""
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from portfolio.models import Post

from ._helpers import StaffClientMixin, make_post


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
        r = self.staff_client.get('/blog/new/?template=explainer')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/edit/', r.headers['Location'])
        # The created post should be a draft + an explainer
        slug = r.headers['Location'].rsplit('/edit/', 1)[0].rsplit('/', 1)[-1]
        p = Post.objects.get(slug=slug)
        self.assertTrue(p.draft)
        self.assertTrue(p.is_explainer)
        self.assertEqual(p.maturity, 'budding')

    def test_unknown_template_falls_back_to_picker(self):
        r = self.staff_client.get('/blog/new/?template=nonsense')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Choose a template')

    def test_anon_redirected_to_login(self):
        r = self.anon_client.get('/blog/new/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/admin/login/', r.headers['Location'])


class BlogUploadImageTests(StaffClientMixin, TestCase):
    def test_upload_returns_markdown_snippet(self):
        # Smallest valid PNG: 1x1 transparent
        png_bytes = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
            b'\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00'
            b'\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\x00\x01'
            b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        f = SimpleUploadedFile('test.png', png_bytes, content_type='image/png')
        r = self.staff_client.post('/blog/upload-image/', {'image': f, 'alt': 'test'})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn('![test]', data['markdown'])
        self.assertIn('blog-images', data['url'])

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
