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
