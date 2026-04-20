"""Import markdown blog posts from portfolio/blog/posts/ into the database.

DEFAULT (idempotent + safe): only create posts whose slug isn't already
in the DB. Existing rows are LEFT ALONE — your in-browser-editor edits,
draft toggles, and field changes survive every redeploy. This is what
build.sh runs on every Render deploy.

`--force`: overwrite EVERY existing post with the .md file values.
Destructive — only use when you've authored a post in markdown and
want to re-seed the DB from it.

`--force <slug>`: overwrite only that single post.
"""
from pathlib import Path

import frontmatter
from django.core.management.base import BaseCommand

from portfolio.models import Post


class Command(BaseCommand):
    help = ('Import markdown blog posts into the database. Default is '
            'create-only (existing rows untouched). Use --force to overwrite.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', nargs='?', const=True, default=False,
            help='Overwrite existing posts with .md file values. '
                 'Bare flag = overwrite all. With a slug = overwrite only that one.',
        )

    def handle(self, *args, force=False, **options):
        posts_dir = Path(__file__).resolve().parent.parent.parent / 'blog' / 'posts'
        if not posts_dir.exists():
            self.stdout.write('No posts directory found.')
            return

        only_slug = force if isinstance(force, str) else None
        force_all = force is True

        for filepath in posts_dir.glob('*.md'):
            slug = filepath.stem
            if only_slug and slug != only_slug:
                continue

            existing = Post.objects.filter(slug=slug).first()
            if existing and not (force_all or only_slug == slug):
                self.stdout.write(self.style.WARNING(
                    f'Skipping (already in DB): {existing.title} — '
                    f'use --force {slug} to overwrite from .md'
                ))
                continue

            fm = frontmatter.load(filepath)
            defaults = {
                'title': fm.get('title', slug.replace('-', ' ').title()),
                'excerpt': fm.get('excerpt', ''),
                'body': fm.content,
                'date': fm.get('date'),
                'updated': fm.get('updated'),
                'author': fm.get('author', 'Dennis Loevlie'),
                'image': fm.get('image', ''),
                'series': fm.get('series', ''),
                'series_order': fm.get('series_order', 0),
                'medium_url': fm.get('medium_url', ''),
                'draft': fm.get('draft', False),
                'is_explainer': fm.get('is_explainer', False),
                'is_paper_companion': fm.get('is_paper_companion', False),
                'maturity': fm.get('maturity', ''),
            }
            post, created = Post.objects.update_or_create(
                slug=slug, defaults=defaults,
            )
            tags = fm.get('tags', [])
            if tags:
                post.tags.set(tags, clear=True)

            action = self.style.SUCCESS('Created') if created else self.style.WARNING('Overwrote')
            self.stdout.write(f'{action}: {post.title}')
