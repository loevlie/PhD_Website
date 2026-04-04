"""Import markdown blog posts from portfolio/blog/posts/ into the database."""
from pathlib import Path

import frontmatter
from django.core.management.base import BaseCommand

from portfolio.models import Post


class Command(BaseCommand):
    help = 'Import markdown blog posts into the database'

    def handle(self, *args, **options):
        posts_dir = Path(__file__).resolve().parent.parent.parent / 'blog' / 'posts'
        if not posts_dir.exists():
            self.stdout.write('No posts directory found.')
            return

        for filepath in posts_dir.glob('*.md'):
            fm = frontmatter.load(filepath)
            slug = filepath.stem
            post, created = Post.objects.update_or_create(
                slug=slug,
                defaults={
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
                },
            )
            # Set tags
            tags = fm.get('tags', [])
            if tags:
                post.tags.set(tags, clear=True)

            action = 'Created' if created else 'Updated'
            self.stdout.write(f'{action}: {post.title}')
