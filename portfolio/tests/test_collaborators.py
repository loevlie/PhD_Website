"""Tests for per-post collaborator permissions + public signup +
per-post analytics page.

Three concerns covered:
  * Auth gate: staff, collaborator-on-this-post, collaborator-on-another-
    post, anon — each gets the right status on each editor endpoint.
  * Signup: happy path creates a non-staff user, login, profile view.
  * Per-post analytics: staff + collaborator allowed, other user and
    anon rejected.
"""
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, Client

from portfolio.tests._helpers import make_staff_user, make_post


User = get_user_model()


def make_plain_user(username='collab-user', password='test12345'):
    u, _ = User.objects.get_or_create(
        username=username,
        defaults={'email': f'{username}@example.com'},
    )
    u.is_staff = False
    u.is_superuser = False
    u.set_password(password)
    u.save()
    return u


class CollaboratorAuthTests(TestCase):
    """Slug-scoped editor endpoints must respect `post.collaborators`."""

    def setUp(self):
        cache.clear()
        self.staff = make_staff_user()
        self.collab = make_plain_user(username='alice')
        self.other = make_plain_user(username='bob')
        self.post = make_post(slug='alice-post', title='Alice Post', body='# Hi')
        self.post.collaborators.add(self.collab)

        self.staff_client = Client(); self.staff_client.force_login(self.staff)
        self.collab_client = Client(); self.collab_client.force_login(self.collab)
        self.other_client = Client(); self.other_client.force_login(self.other)
        self.anon_client = Client()

    # —— blog_edit ——

    def test_staff_can_open_editor(self):
        r = self.staff_client.get(f'/blog/{self.post.slug}/edit/')
        self.assertEqual(r.status_code, 200)

    def test_collaborator_can_open_editor(self):
        r = self.collab_client.get(f'/blog/{self.post.slug}/edit/')
        self.assertEqual(r.status_code, 200)

    def test_non_collaborator_redirected_to_login(self):
        r = self.other_client.get(f'/blog/{self.post.slug}/edit/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_anon_redirected_to_login(self):
        r = self.anon_client.get(f'/blog/{self.post.slug}/edit/')
        self.assertEqual(r.status_code, 302)

    # —— blog_autosave ——

    def test_collaborator_can_autosave(self):
        r = self.collab_client.post(f'/blog/{self.post.slug}/autosave/', {
            'title': 'Edited by Alice',
        })
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, 'Edited by Alice')

    def test_non_collaborator_cannot_autosave(self):
        r = self.other_client.post(f'/blog/{self.post.slug}/autosave/', {
            'title': 'Hijacked',
        })
        self.assertEqual(r.status_code, 403)
        self.post.refresh_from_db()
        self.assertNotEqual(self.post.title, 'Hijacked')

    # —— spellcheck ——

    def test_collaborator_can_spellcheck(self):
        r = self.collab_client.post(
            f'/blog/{self.post.slug}/spellcheck/',
            data=json.dumps({'text': 'hello wurld'}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)

    def test_non_collaborator_cannot_spellcheck(self):
        r = self.other_client.post(
            f'/blog/{self.post.slug}/spellcheck/',
            data=json.dumps({'text': 'hello'}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 403)

    # —— assist ——

    def test_collaborator_can_hit_assist_with_matching_slug(self):
        from portfolio.editor_assist import ai_assists
        with patch.object(ai_assists, '_call_anthropic', return_value='short.'):
            r = self.collab_client.post(
                f'/blog/{self.post.slug}/assist/tldr/',
                data=json.dumps({'body': 'some body'}),
                content_type='application/json',
            )
        self.assertEqual(r.status_code, 200)

    def test_non_collaborator_cannot_hit_assist(self):
        r = self.other_client.post(
            f'/blog/{self.post.slug}/assist/tldr/',
            data=json.dumps({'body': 'x'}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 403)

    # —— slug-less helper endpoints ——

    def test_collaborator_can_use_smart_paste(self):
        # Slug-less helper — collaborator on any post is enough.
        r = self.collab_client.post(
            '/editor/smart-paste/',
            data=json.dumps({'url': 'https://arxiv.org/abs/1706.03762'}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)

    def test_non_collaborator_cannot_use_smart_paste(self):
        r = self.other_client.post(
            '/editor/smart-paste/',
            data=json.dumps({'url': 'https://arxiv.org/abs/1706.03762'}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 403)

    # —— blog_preview with slug gating ——

    def test_preview_with_post_slug_honours_collaborator(self):
        r = self.collab_client.post('/blog/preview/', {
            'body': '# hi', 'is_explainer': 'false', 'slug': self.post.slug,
        })
        self.assertEqual(r.status_code, 200)

    def test_preview_with_foreign_slug_rejects_non_collaborator(self):
        r = self.other_client.post('/blog/preview/', {
            'body': '# hi', 'is_explainer': 'false', 'slug': self.post.slug,
        })
        self.assertEqual(r.status_code, 403)

    def test_preview_staff_always_ok(self):
        r = self.staff_client.post('/blog/preview/', {
            'body': '# hi', 'is_explainer': 'false', 'slug': self.post.slug,
        })
        self.assertEqual(r.status_code, 200)


class PublicSignupTests(TestCase):

    def test_signup_form_renders(self):
        r = self.client.get('/accounts/signup/')
        self.assertEqual(r.status_code, 200)
        # The heading is "Create an <em>account</em>." — match the
        # submit button text instead of the stylised display title.
        self.assertContains(r, 'Create account')
        self.assertContains(r, 'id="id_username"')

    def test_signup_creates_non_staff_user(self):
        r = self.client.post('/accounts/signup/', {
            'username': 'newbie',
            'email': 'newbie@example.com',
            'password1': 'x@H3yP4ssword!',
            'password2': 'x@H3yP4ssword!',
        }, follow=True)
        self.assertEqual(r.status_code, 200)
        u = User.objects.get(username='newbie')
        self.assertFalse(u.is_staff)
        self.assertFalse(u.is_superuser)
        self.assertEqual(u.email, 'newbie@example.com')

    def test_signup_autologs_in_and_lands_on_profile(self):
        r = self.client.post('/accounts/signup/', {
            'username': 'autobot',
            'email': 'autobot@example.com',
            'password1': 'x@H3yP4ssword!',
            'password2': 'x@H3yP4ssword!',
        }, follow=True)
        self.assertContains(r, 'autobot')             # username on profile
        # Fresh signup has no collaborator assignments → profile shows
        # the "waiting room" state. Match a phrase that's stable
        # across visual polish passes.
        self.assertContains(r, 'no posts have been assigned')

    def test_signup_cannot_create_staff(self):
        # Extra POST fields must be ignored; UserCreationForm.Meta.fields
        # is the whitelist. Belt-and-braces: view defensively flips
        # is_staff/is_superuser to False.
        r = self.client.post('/accounts/signup/', {
            'username': 'tryhard',
            'email': 'tryhard@example.com',
            'password1': 'x@H3yP4ssword!',
            'password2': 'x@H3yP4ssword!',
            'is_staff': 'on',
            'is_superuser': 'on',
        })
        u = User.objects.get(username='tryhard')
        self.assertFalse(u.is_staff)
        self.assertFalse(u.is_superuser)

    def test_profile_shows_editable_posts_for_collaborator(self):
        u = make_plain_user(username='hasposts')
        p = make_post(slug='p1', title='P One')
        p.collaborators.add(u)
        c = Client(); c.force_login(u)
        r = c.get('/accounts/profile/')
        self.assertContains(r, 'P One')
        self.assertContains(r, f'/blog/{p.slug}/edit/')
        self.assertContains(r, f'/site/insights/blog/{p.slug}/')


class PostAnalyticsDashboardTests(TestCase):

    def setUp(self):
        self.staff = make_staff_user()
        self.collab = make_plain_user(username='alice')
        self.other = make_plain_user(username='bob')
        self.post = make_post(slug='post1', title='Post One')
        self.post.collaborators.add(self.collab)
        self.url = f'/site/insights/blog/{self.post.slug}/'

    def test_staff_can_view(self):
        c = Client(); c.force_login(self.staff)
        r = c.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, self.post.title)

    def test_collaborator_can_view(self):
        c = Client(); c.force_login(self.collab)
        r = c.get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_non_collaborator_redirected(self):
        c = Client(); c.force_login(self.other)
        r = c.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/profile/', r['Location'])

    def test_anon_redirected_to_login(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_404_for_unknown_slug(self):
        c = Client(); c.force_login(self.staff)
        r = c.get('/site/insights/blog/does-not-exist/')
        self.assertEqual(r.status_code, 404)
