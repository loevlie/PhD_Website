"""Signals for the Post model:

1. Invalidate the get_all_posts() cache on save/delete so listings
   reflect edits on the next request.
2. After save, render markdown → SVG/PNG inline → store in
   Post.rendered_html so subsequent views serve pre-rendered HTML
   without re-running pyfig subprocesses (Render's disk is ephemeral
   so the per-pyfig PNG cache vanishes on every deploy; persisting
   the rendered HTML in Postgres survives deploys cleanly).

The persistence step uses Post.objects.filter(pk=...).update(...) to
bypass the post_save signal, so it cannot recurse.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone

from portfolio.models import (
    Post,
    NewsItem, Publication, PublicationLink,
    Project, ProjectLink, TimelineEntry, OpenSourceItem,
    SocialLink, NowPage, NowSection,
)
from portfolio.blog import invalidate_post_cache, render_markdown
from portfolio.content import live as content_live


# ─── Content cache invalidation ──────────────────────────────────────
# live.* memoizes content for 10 min. Every time a model changes in the
# admin we drop the relevant cache key so the public pages reflect the
# edit without waiting for TTL.
_CONTENT_CACHE_KEYS = {
    NewsItem: 'news',
    Publication: 'publications',
    PublicationLink: 'publications',
    Project: 'projects',
    ProjectLink: 'projects',
    TimelineEntry: 'timeline',
    OpenSourceItem: 'opensource',
    SocialLink: 'social_links',
    NowPage: 'now_page',
    NowSection: 'now_page',
}


@receiver(post_save)
def _content_saved(sender, **kwargs):
    key = _CONTENT_CACHE_KEYS.get(sender)
    if key:
        content_live.invalidate(key)


@receiver(post_delete)
def _content_deleted(sender, **kwargs):
    key = _CONTENT_CACHE_KEYS.get(sender)
    if key:
        content_live.invalidate(key)


@receiver(post_save, sender=Post)
def _post_saved(sender, instance, raw=False, update_fields=None, **kwargs):
    invalidate_post_cache()
    # Skip render in three cases:
    # - `raw=True` happens during loaddata/fixture loads; the body may
    #   be in an inconsistent state with related rows.
    # - `update_fields` is a subset of the rendered_* fields, meaning
    #   this save was the persistence step itself (defensive — we
    #   bypass via .update() so this path normally won't trigger).
    # - `instance._skip_render` is set by the editor's autosave path,
    #   which fires every 1.5s while the author is typing. Running the
    #   full pipeline (pyfig matplotlib, arxiv/github/wiki network
    #   fetches, demo template renders) on every keystroke burst
    #   blocks the single web worker for seconds and queues preview
    #   fetches behind it. The explicit Save button does trigger the
    #   render so the published version is always in sync.
    if raw:
        return
    if update_fields and set(update_fields).issubset(
        {'rendered_html', 'rendered_toc_html', 'rendered_at'}
    ):
        return
    if getattr(instance, '_skip_render', False):
        return
    _render_and_persist(instance)


@receiver(post_delete, sender=Post)
def _post_deleted(sender, **kwargs):
    invalidate_post_cache()


def _render_and_persist(post):
    """Render the post's markdown and store the result on the row.

    Skipped when any pyfig errors — a partial render would freeze a
    visible "Figure failed to render" banner into the DB until the
    next save. Live render in get_post() handles the fallback path.
    """
    try:
        errors = []
        html, toc = render_markdown(
            post.body or '',
            is_explainer=getattr(post, 'is_explainer', False),
            post_slug=post.slug,
            errors_out=errors,
            notation_entries=getattr(post, 'notation', None) or [],
        )
    except Exception:
        # Don't break save() if render itself crashes — fall back to
        # live render at view time.
        return
    if errors:
        return
    Post.objects.filter(pk=post.pk).update(
        rendered_html=html,
        rendered_toc_html=toc,
        rendered_at=timezone.now(),
    )


# ─── UserProfile lifecycle ──────────────────────────────────────────
# Every auth.User gets a UserProfile exactly once, created on first
# save. Keeps `user.profile` safe to access everywhere without
# defensive existence checks. Deletion cascades via the FK.
from django.conf import settings as _django_settings


@receiver(post_save, sender='auth.User')
def _user_profile_created(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    if created:
        from portfolio.models import UserProfile
        UserProfile.objects.get_or_create(user=instance)
