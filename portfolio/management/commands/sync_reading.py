"""Sync the /reading/ list from a Mind Mapper "Reading" project.

Architecture: every note in a designated Mind Mapper project is treated
as one paper. Each note has YAML frontmatter for metadata
(venue/year/url/status/order) and prose annotation underneath.

Run on demand:
    python manage.py sync_reading

Or with a custom project name:
    python manage.py sync_reading --project Reading

Or as a dry-run (no DB writes):
    python manage.py sync_reading --dry-run

Environment:
    MIND_MAPPER_URL      defaults to https://mind-mapper-x1zt.onrender.com
    MIND_MAPPER_API_KEY  required (Bearer token)

Note format (one per Mind Mapper note in the Reading project):

    Title of the paper goes in the note's title field.

    Note body:
    ---
    venue: arXiv 2503.16302
    year: 2025
    url: https://arxiv.org/abs/2503.16302
    status: this_week        # this_week | lingering | archived
    order: 10                # lower = higher in its bucket; optional
    ---
    One-line italic annotation in your own voice — what makes this
    interesting to you right now. Plain text or markdown.

The frontmatter block is optional but recommended; without it the
title is the only metadata.
"""
import os
import urllib.request
import urllib.parse
import json
from django.core.management.base import BaseCommand, CommandError

import frontmatter


DEFAULT_MM_URL = 'https://mind-mapper-x1zt.onrender.com'
DEFAULT_PROJECT = 'Reading'


def _api_get(path):
    """Fetch path from Mind Mapper, raise CommandError on failure."""
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
    """Convert a Mind Mapper note into the kwargs Reading.objects.update_or_create needs.

    Returns a (defaults_dict, errors_list) tuple. errors is non-empty if
    the note's frontmatter is malformed; we still try to import using
    the title alone."""
    errors = []
    title = (note_detail.get('title') or '').strip() or 'Untitled'
    body = note_detail.get('content') or ''

    venue = ''
    year = None
    url = ''
    annotation = body.strip()
    status = 'this_week'
    order = 0

    try:
        post = frontmatter.loads(body)
        meta = post.metadata or {}
        annotation = (post.content or '').strip()
        venue = str(meta.get('venue', '') or '').strip()
        url = str(meta.get('url', '') or '').strip()
        raw_year = meta.get('year')
        if raw_year is not None and str(raw_year).strip():
            try:
                year = int(str(raw_year).strip())
            except (TypeError, ValueError):
                errors.append(f'invalid year: {raw_year!r}')
        raw_status = str(meta.get('status', 'this_week') or 'this_week').strip().lower().replace('-', '_')
        # Accept legacy `chewing` as an alias for `lingering` so old MM
        # notes don't break sync if you forget to update the frontmatter.
        if raw_status == 'chewing':
            raw_status = 'lingering'
        if raw_status in {'this_week', 'lingering', 'archived'}:
            status = raw_status
        else:
            errors.append(f'invalid status: {raw_status!r} (must be this_week|lingering|archived)')
        try:
            order = int(meta.get('order', 0) or 0)
        except (TypeError, ValueError):
            errors.append(f'invalid order: {meta.get("order")!r}')
    except Exception as e:
        errors.append(f'frontmatter parse failed: {e}')

    defaults = {
        'title': title[:300],
        'venue': venue[:200],
        'year': year,
        'url': url,
        'annotation': annotation,
        'status': status,
        'order': order,
    }
    return defaults, errors


class Command(BaseCommand):
    help = 'Sync /reading/ from a Mind Mapper project (default: "Reading"). One MM note = one paper.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--project', default=DEFAULT_PROJECT,
            help=f'Mind Mapper project name (default: {DEFAULT_PROJECT}). Every note in this project is treated as a paper.',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Print what would change without touching the DB.',
        )
        parser.add_argument(
            '--prune', action='store_true',
            help='Delete local Reading rows whose mind_mapper_note_id no longer exists in the MM project. Off by default to avoid accidents.',
        )

    def handle(self, *args, project, dry_run, prune, **opts):
        from portfolio.models import Reading

        project_q = urllib.parse.quote(project)
        notes = _api_get(f'/api/notes/?project={project_q}')
        if isinstance(notes, dict) and 'results' in notes:
            notes = notes['results']

        # Defensive client-side filter: the MM API does partial / fallback
        # matching on project name; when there's no exact match it returns
        # ALL notes, which would import the entire knowledge base into
        # /reading/. Only process notes whose project field is an exact
        # case-insensitive match.
        notes = [n for n in notes if (n.get('project') or '').strip().lower() == project.strip().lower()]

        self.stdout.write(self.style.NOTICE(
            f'Found {len(notes)} note(s) in MM project "{project}".'
        ))
        if not notes:
            self.stdout.write(self.style.WARNING(
                f'  No notes match. Create a project named "{project}" in Mind Mapper '
                f'and add one note per paper. Each note: title = paper title, '
                f'body = YAML frontmatter (venue/year/url/status/order) + annotation.'
            ))
            return

        seen_ids = set()
        created = updated = errored = 0

        for n in notes:
            note_id = n.get('id')
            if not note_id:
                continue
            # Re-fetch detail because the list endpoint omits content + tags
            detail = _api_get(f'/api/notes/{note_id}/')
            defaults, errors = _parse_note(detail)
            seen_ids.add(int(note_id))

            if errors:
                self.stdout.write(self.style.WARNING(
                    f'  WARN  note {note_id} "{defaults["title"][:40]}": {"; ".join(errors)}'
                ))

            # Resolve which local row this MM note corresponds to:
            #   1. Existing row with this exact mind_mapper_note_id  -> update
            #   2. Manual row (no MM id) with matching url           -> claim
            #   3. Manual row (no MM id) with matching title (case-i) -> claim
            #   4. None of the above                                 -> create
            existing = Reading.objects.filter(mind_mapper_note_id=int(note_id)).first()
            claimed = None
            if existing is None:
                if defaults.get('url'):
                    claimed = Reading.objects.filter(
                        mind_mapper_note_id__isnull=True,
                        url=defaults['url'],
                    ).first()
                if claimed is None:
                    claimed = Reading.objects.filter(
                        mind_mapper_note_id__isnull=True,
                        title__iexact=defaults['title'],
                    ).first()

            if dry_run:
                if existing:
                    self.stdout.write(f'  DRY   UPD note {note_id}: {defaults["title"][:50]}')
                elif claimed:
                    self.stdout.write(f'  DRY   CLAIM existing manual entry "{claimed.title[:40]}" for note {note_id}')
                else:
                    self.stdout.write(f'  DRY   NEW note {note_id}: {defaults["title"][:50]}')
                continue

            if existing:
                for k, v in defaults.items():
                    setattr(existing, k, v)
                existing.save()
                updated += 1
                self.stdout.write(f'  UPD   {existing.title[:60]}')
            elif claimed:
                for k, v in defaults.items():
                    setattr(claimed, k, v)
                claimed.mind_mapper_note_id = int(note_id)
                claimed.save()
                updated += 1
                self.stdout.write(self.style.SUCCESS(f'  CLAIM {claimed.title[:60]} (was manual; now sourced from MM #{note_id})'))
            else:
                obj = Reading.objects.create(
                    mind_mapper_note_id=int(note_id),
                    **defaults,
                )
                created += 1
                self.stdout.write(self.style.SUCCESS(f'  NEW   {obj.title[:60]}'))

        pruned = 0
        if prune and not dry_run:
            stale = Reading.objects.filter(
                mind_mapper_note_id__isnull=False,
            ).exclude(mind_mapper_note_id__in=seen_ids)
            pruned = stale.count()
            for r in stale:
                self.stdout.write(self.style.WARNING(f'  DEL   {r.title[:60]} (note {r.mind_mapper_note_id} no longer in MM)'))
            if pruned and not dry_run:
                stale.delete()
        elif not prune:
            stale = Reading.objects.filter(
                mind_mapper_note_id__isnull=False,
            ).exclude(mind_mapper_note_id__in=seen_ids).count()
            if stale:
                self.stdout.write(self.style.NOTICE(
                    f'  ({stale} local row(s) point at MM notes no longer in the project — pass --prune to delete)'
                ))

        verb = 'Would' if dry_run else ''
        summary = f'\n{verb} created {created}, updated {updated}, pruned {pruned}.'
        self.stdout.write(self.style.NOTICE(summary))
