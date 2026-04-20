"""Bulk-render every Post into Post.rendered_html.

Use after deploying a renderer change (e.g., new pyfig output format,
new markdown extension) to refresh every persisted render in one go.

    python manage.py render_posts          # all posts
    python manage.py render_posts --slug X # one post
    python manage.py render_posts --stale  # only posts whose modified_at > rendered_at

The post_save signal handles ongoing renders; this command exists to
backfill the persisted render for posts that pre-date the field, or
to roll forward after a renderer upgrade.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from portfolio.models import Post
from portfolio.blog import render_markdown


class Command(BaseCommand):
    help = 'Render Post.body markdown into Post.rendered_html for every (or one) post.'

    def add_arguments(self, parser):
        parser.add_argument('--slug', help='Render only this post slug.')
        parser.add_argument(
            '--stale', action='store_true',
            help='Only render posts whose modified_at is newer than rendered_at '
                 '(or whose rendered_html is empty).',
        )
        parser.add_argument(
            '--quiet', action='store_true',
            help='Suppress per-post output; print only the summary.',
        )

    def handle(self, *args, slug=None, stale=False, quiet=False, **opts):
        qs = Post.objects.all()
        if slug:
            qs = qs.filter(slug=slug)

        if stale:
            # "stale" = persisted render missing OR older than the body.
            from django.db.models import Q, F
            qs = qs.filter(
                Q(rendered_html='') | Q(rendered_at__isnull=True) | Q(modified_at__gt=F('rendered_at'))
            )

        rendered = errored = unchanged = 0
        for post in qs:
            errors = []
            try:
                html, toc = render_markdown(
                    post.body or '',
                    is_explainer=post.is_explainer,
                    post_slug=post.slug,
                    errors_out=errors,
                )
            except Exception as e:
                errored += 1
                if not quiet:
                    self.stdout.write(self.style.ERROR(f'  CRASH {post.slug}: {e}'))
                continue
            if errors:
                errored += 1
                if not quiet:
                    self.stdout.write(self.style.WARNING(
                        f'  PYFIG-ERR {post.slug}: {len(errors)} block(s) failed — '
                        f'rendered_html NOT updated. First error: {errors[0]}'
                    ))
                continue
            # Bypass the post_save signal so we don't recurse.
            Post.objects.filter(pk=post.pk).update(
                rendered_html=html,
                rendered_toc_html=toc,
                rendered_at=timezone.now(),
            )
            rendered += 1
            if not quiet:
                kb = len(html) // 1024
                self.stdout.write(self.style.SUCCESS(f'  OK    {post.slug}  ({kb} KB)'))

        self.stdout.write(self.style.NOTICE(
            f'\n{rendered} rendered, {errored} errored, {unchanged} unchanged.'
        ))
