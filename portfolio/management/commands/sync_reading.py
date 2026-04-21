"""Decorate /reading/ entries with annotations from a Mind Mapper
"Reading" project.

Behavior change (2026-04): sync NEVER creates Reading rows. Adding
new papers is manual (admin or /site/studio/ quick-add). This command
only attaches the MM note's prose annotation to existing rows that
match by URL (preferred) or by title (case-insensitive, fuzzy).

    python manage.py sync_reading                   (match + attach)
    python manage.py sync_reading --dry-run         (print matches, don't write)
    python manage.py sync_reading --project Reading (non-default MM project)

Environment:
    MIND_MAPPER_URL      defaults to https://mind-mapper-x1zt.onrender.com
    MIND_MAPPER_API_KEY  required (Bearer token). Without it, the command
                         errors out with a clear message.

Matched MM note content is written to Reading.mm_annotation and shown
beneath the manual annotation on /reading/. Edit the MM note to update
the text; edit nothing else from MM (sync doesn't touch status/order/
venue/year/url — those are yours).

Note format:
    Title of the paper goes in the note's title field.
    Body: YAML frontmatter (optional) + prose annotation.
    Frontmatter supports `url:` (used as the match key).
"""
import json
import os
import urllib.parse
import urllib.request
import urllib.error

from django.core.management.base import BaseCommand, CommandError

import frontmatter


DEFAULT_MM_URL = 'https://mind-mapper-x1zt.onrender.com'
DEFAULT_PROJECT = 'Reading'


def _api_get(path):
    base = os.environ.get('MIND_MAPPER_URL') or DEFAULT_MM_URL
    key = os.environ.get('MIND_MAPPER_API_KEY')
    if not key:
        raise CommandError(
            'MIND_MAPPER_API_KEY env var is not set. Sync requires the API '
            'token (Bearer auth).'
        )
    url = base.rstrip('/') + path
    req = urllib.request.Request(url, headers={
        'Authorization': f'Bearer {key}',
        'Accept': 'application/json',
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raise CommandError(f'Mind Mapper API {e.code} on {path}: {e.read()[:200]}')
    except Exception as e:
        raise CommandError(f'Mind Mapper API call failed on {path}: {e}')


def _parse_note(note_detail):
    """Return (title, url_hint, annotation_text) for a MM note detail."""
    title = (note_detail.get('title') or '').strip() or 'Untitled'
    body = note_detail.get('content') or ''
    annotation = body.strip()
    url_hint = ''
    try:
        post = frontmatter.loads(body)
        meta = post.metadata or {}
        annotation = (post.content or '').strip()
        url_hint = str(meta.get('url', '') or '').strip()
    except Exception:
        pass
    return title, url_hint, annotation


def _find_matching_reading(Reading, title, url_hint):
    """Return the Reading row that should receive this MM note's
    annotation, or None if there's no manual match. Preference:

      1. Already claimed by this note id (but we compare title/url on caller).
      2. Exact URL match on a manually-added row.
      3. Case-insensitive title match on a manually-added row.
    """
    if url_hint:
        match = Reading.objects.filter(url=url_hint).first()
        if match:
            return match
    if title:
        match = Reading.objects.filter(title__iexact=title).first()
        if match:
            return match
    return None


class Command(BaseCommand):
    help = ('Decorate /reading/ rows with annotations from a Mind Mapper '
            'project. Never creates rows — adding entries is manual.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--project', default=DEFAULT_PROJECT,
            help=f'Mind Mapper project name (default: {DEFAULT_PROJECT}).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Print what would change without touching the DB.',
        )

    def handle(self, *args, project, dry_run, **opts):
        from portfolio.models import Reading

        project_q = urllib.parse.quote(project)
        notes = _api_get(f'/api/notes/?project={project_q}')
        if isinstance(notes, dict) and 'results' in notes:
            notes = notes['results']

        # Defensive client-side filter: the MM API does partial / fallback
        # matching on project name; when there's no exact match it returns
        # ALL notes. Only process notes whose project field is an exact
        # case-insensitive match.
        notes = [n for n in notes if (n.get('project') or '').strip().lower() == project.strip().lower()]

        self.stdout.write(self.style.NOTICE(
            f'Found {len(notes)} note(s) in MM project "{project}".'
        ))
        if not notes:
            return

        matched = skipped = cleared_stale = 0

        seen_reading_ids = set()
        for n in notes:
            note_id = n.get('id')
            if not note_id:
                continue
            detail = _api_get(f'/api/notes/{note_id}/')
            title, url_hint, annotation = _parse_note(detail)

            # Prefer a row already claimed by this note id — so renames in
            # MM don't orphan the attachment.
            row = Reading.objects.filter(mind_mapper_note_id=int(note_id)).first()
            if row is None:
                row = _find_matching_reading(Reading, title, url_hint)

            if row is None:
                self.stdout.write(self.style.WARNING(
                    f'  SKIP   no /reading/ entry matches MM #{note_id} "{title[:50]}" — '
                    f'add it from /site/studio/ first.'
                ))
                skipped += 1
                continue

            seen_reading_ids.add(row.pk)
            if dry_run:
                self.stdout.write(f'  DRY    would attach MM #{note_id} to "{row.title[:50]}"')
                continue

            row.mm_annotation = annotation
            row.mind_mapper_note_id = int(note_id)
            row.save(update_fields=['mm_annotation', 'mind_mapper_note_id', 'modified_at'])
            matched += 1
            self.stdout.write(self.style.SUCCESS(
                f'  OK     attached MM #{note_id} to "{row.title[:50]}"'
            ))

        # Rows previously linked to an MM note that's no longer in the
        # project: clear the link + annotation (keep the row itself).
        if not dry_run:
            stale = Reading.objects.filter(
                mind_mapper_note_id__isnull=False
            ).exclude(pk__in=seen_reading_ids)
            for row in stale:
                row.mm_annotation = ''
                row.mind_mapper_note_id = None
                row.save(update_fields=['mm_annotation', 'mind_mapper_note_id', 'modified_at'])
                cleared_stale += 1
                self.stdout.write(self.style.WARNING(
                    f'  CLEAR  "{row.title[:50]}" — MM note no longer in project '
                    f'(entry kept; only MM annotation cleared)'
                ))

        self.stdout.write(self.style.NOTICE(
            f'\nMatched {matched}, skipped {skipped} (no manual row), cleared {cleared_stale} stale.'
        ))
