"""Signals that keep the get_all_posts() cache fresh.

When a Post is saved or deleted (admin, editor, autosave, mgmt command),
the cached listing for both variants (drafts on/off) is dropped so the
next request rebuilds it. Cheap — the cache key is two strings."""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from portfolio.models import Post
from portfolio.blog import invalidate_post_cache


@receiver(post_save, sender=Post)
def _post_saved(sender, **kwargs):
    invalidate_post_cache()


@receiver(post_delete, sender=Post)
def _post_deleted(sender, **kwargs):
    invalidate_post_cache()
