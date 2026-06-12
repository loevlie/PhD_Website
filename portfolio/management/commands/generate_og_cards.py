"""Generate per-post Open Graph social-share images (1200×630 PNG).

Replaces the previous Playwright/HTML pipeline — uses Pillow with
bundled IBM Plex TTFs, so there's no chromium dependency on Render —
and writes through default_storage so the output survives deploys
(R2 in prod via django-storages, local MEDIA_ROOT in dev).

Usage:
    python manage.py generate_og_cards            # every published post
    python manage.py generate_og_cards <slug>     # one post (includes drafts)
    python manage.py generate_og_cards --check    # report what would render
    python manage.py generate_og_cards --force    # rerender even if present
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from portfolio.blog import get_all_posts, get_post
from portfolio.og import generate_card, card_exists


class Command(BaseCommand):
    help = 'Generate per-post Open Graph social-share PNGs (1200×630) via Pillow.'

    def add_arguments(self, parser):
        parser.add_argument('slug', nargs='?',
                            help='Optional slug to regenerate one post (includes drafts).')
        parser.add_argument('--check', action='store_true',
                            help='List which posts would be generated; do not write.')
        parser.add_argument('--force', action='store_true',
                            help='Regenerate even if a card already exists.')

    def handle(self, *args, slug=None, check=False, force=False, **opts):
        if slug:
            # Explicit slugs include drafts — staff often want to preview
            # a card before publishing.
            post = get_post(slug, include_drafts=True)
            if not post:
                raise CommandError(f'No post with slug "{slug}".')
            posts = [post]
        else:
            posts = get_all_posts()

        to_render = []
        for p in posts:
            slug_ = p.get('slug')
            if not slug_:
                continue
            if card_exists(slug_) and not force:
                self.stdout.write(f'  [skip] {slug_} (already in storage)')
                continue
            to_render.append(p)

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\nWill generate {len(to_render)} of {len(posts)} cards.'))

        if check:
            for p in to_render:
                self.stdout.write(f'  [would] {p["slug"]} → og/{p["slug"]}.png')
            return

        for p in to_render:
            try:
                key = generate_card(p)
            except Exception as e:
                self.stderr.write(self.style.ERROR(
                    f'  [err]  {p["slug"]}: {e}'))
                continue
            self.stdout.write(self.style.SUCCESS(f'  [ok]   {p["slug"]} → {key}'))

        if to_render:
            self.stdout.write(self.style.SUCCESS(
                f'\nDone. Persisted {len(to_render)} cards via default_storage.'))
