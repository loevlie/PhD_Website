"""One-shot importer from the legacy `portfolio/static/portfolio/data/
citations.json` manifest into the `Citation` model. Idempotent:
existing keys are updated in place, new keys inserted. Safe to re-run.

Run after the 0022_citation migration lands on prod:
    python manage.py seed_citations
"""
from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from portfolio.models import Citation


DEFAULT_PATH = (
    Path(settings.BASE_DIR) / 'portfolio' / 'static'
    / 'portfolio' / 'data' / 'citations.json'
)


class Command(BaseCommand):
    help = 'Import citations from the legacy citations.json manifest.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--path', default=str(DEFAULT_PATH),
            help=f'Manifest path (default: {DEFAULT_PATH}).',
        )

    def handle(self, *args, **opts):
        path = Path(opts['path'])
        if not path.exists():
            self.stderr.write(self.style.ERROR(f'Manifest not found: {path}'))
            return

        data = json.loads(path.read_text(encoding='utf-8'))
        created = updated = 0
        for key, entry in data.items():
            defaults = {
                'title': entry.get('title', ''),
                'authors': entry.get('authors', ''),
                'venue': entry.get('venue', ''),
                'url': entry.get('url', ''),
                'bibtex': entry.get('bibtex', ''),
            }
            obj, was_created = Citation.objects.update_or_create(
                key=key, defaults=defaults,
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(
            f'Imported citations from {path}: {created} created, {updated} updated.'
        ))
