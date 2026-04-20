"""Shared test fixtures and helpers."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, Client


User = get_user_model()


def make_staff_user(username='editor-staff', password='test12345'):
    u, _ = User.objects.get_or_create(
        username=username,
        defaults={'is_staff': True, 'is_superuser': True, 'email': f'{username}@example.com'},
    )
    u.is_staff = True
    u.is_superuser = True
    u.set_password(password)
    u.save()
    return u


def make_post(slug='test-post', title='Test post', body='# Test\n\nA test post body with content.',
              draft=False, is_explainer=False, is_paper_companion=False,
              maturity='', tags=None, days_ago=0):
    from portfolio.models import Post
    p = Post.objects.create(
        slug=slug,
        title=title,
        body=body,
        excerpt='Test excerpt for the post.',
        date=date.today() - timedelta(days=days_ago),
        draft=draft,
        is_explainer=is_explainer,
        is_paper_companion=is_paper_companion,
        maturity=maturity,
        author='Dennis Loevlie',
    )
    if tags:
        p.tags.set(tags)
    return p


class StaffClientMixin:
    """Mixin that provides self.staff_client (force-logged-in superuser)
    and self.anon_client (clean Client). Use in unittest TestCase classes."""

    def setUp(self):
        super().setUp()
        self.staff_user = make_staff_user()
        self.staff_client = Client()
        self.staff_client.force_login(self.staff_user)
        self.anon_client = Client()


REAL_BROWSER_UA = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 '
    '(KHTML, like Gecko) Version/17.0 Safari/605.1.15'
)
