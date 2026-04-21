"""Seed the DB content models from portfolio/content/*.py.

Idempotent upsert. Used once to migrate from the static-dict model to
the DB-backed content store (Track B1), and again as a safety net on
fresh deploys / local dev boxes where the content models are empty.

Behavior:
  * Matches by natural key (title for Publications/Projects, name for
    SocialLink/OpenSourceItem, date+text prefix for NewsItem) so
    re-running doesn't duplicate.
  * Creates the NowPage singleton if missing; on re-run, updates fields
    and replaces the NowSection set so order changes in content/now.py
    propagate.
  * Skipped models keep anything you've edited in the admin (diff-
    ignoring re-seed would clobber the admin's changes; we prefer to
    err on the side of preserving hand edits).

Flags:
  --force      overwrite existing rows with values from the content
               module (DANGER: clobbers admin edits).
  --only       restrict to a subset of models (comma-separated), e.g.
               `--only news,publications`.
"""
from django.core.management.base import BaseCommand


_ALL_SEEDERS = ('news', 'publications', 'projects', 'timeline',
                'opensource', 'social', 'now')


class Command(BaseCommand):
    help = 'Seed / re-seed DB content models from portfolio/content/*.py.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help='Overwrite existing rows with the content-module values.',
        )
        parser.add_argument(
            '--only', default='',
            help=f'Comma-separated subset of seeders to run (choices: {", ".join(_ALL_SEEDERS)}).',
        )

    def handle(self, *args, force, only, **opts):
        selected = set(s.strip() for s in only.split(',') if s.strip()) or set(_ALL_SEEDERS)
        unknown = selected - set(_ALL_SEEDERS)
        if unknown:
            self.stdout.write(self.style.ERROR(
                f'Unknown seeder(s): {", ".join(unknown)}. '
                f'Choose from: {", ".join(_ALL_SEEDERS)}.'
            ))
            return

        if 'news' in selected:
            self._seed_news(force)
        if 'publications' in selected:
            self._seed_publications(force)
        if 'projects' in selected:
            self._seed_projects(force)
        if 'timeline' in selected:
            self._seed_timeline(force)
        if 'opensource' in selected:
            self._seed_opensource(force)
        if 'social' in selected:
            self._seed_social(force)
        if 'now' in selected:
            self._seed_now(force)

        self.stdout.write(self.style.SUCCESS('Seed complete.'))

    # ─── Seeders ──────────────────────────────────────────────────

    def _seed_news(self, force):
        from portfolio.models import NewsItem
        from portfolio.content.news import NEWS
        created = updated = 0
        for order, item in enumerate(NEWS):
            # Match on (date, text-prefix) so we don't rely on id.
            lookup = dict(date=item['date'], text__startswith=item['text'][:80])
            existing = NewsItem.objects.filter(**lookup).first()
            fields = {
                'date': item['date'],
                'text': item['text'],
                'highlight': item.get('highlight', False),
                'display_order': order,
            }
            if existing is None:
                NewsItem.objects.create(**fields)
                created += 1
            elif force:
                for k, v in fields.items():
                    setattr(existing, k, v)
                existing.save()
                updated += 1
        self.stdout.write(f'  news: +{created} created, {updated} updated')

    def _seed_publications(self, force):
        from portfolio.models import Publication, PublicationLink
        from portfolio.content.publications import PUBLICATIONS
        created = updated = 0
        for order, pub in enumerate(PUBLICATIONS):
            existing = Publication.objects.filter(title=pub['title']).first()
            authors_csv = ', '.join(pub['authors'])
            fields = {
                'title': pub['title'],
                'authors': authors_csv,
                'venue': pub.get('venue', ''),
                'year': pub['year'],
                'pub_type': pub.get('type', 'conference'),
                'selected': pub.get('selected', False),
                'image': pub.get('image', ''),
                'image_credit': pub.get('image_credit', ''),
                'bibtex': pub.get('bibtex', ''),
                'display_order': order,
            }
            if existing is None:
                obj = Publication.objects.create(**fields)
                self._upsert_links(PublicationLink, 'publication', obj, pub.get('links', []))
                created += 1
            elif force:
                for k, v in fields.items():
                    setattr(existing, k, v)
                existing.save()
                existing.link_set.all().delete()
                self._upsert_links(PublicationLink, 'publication', existing, pub.get('links', []))
                updated += 1
        self.stdout.write(f'  publications: +{created} created, {updated} updated')

    def _seed_projects(self, force):
        from portfolio.models import Project, ProjectLink
        from portfolio.content.projects import PROJECTS
        created = updated = 0
        for order, proj in enumerate(PROJECTS):
            existing = Project.objects.filter(title=proj['title']).first()
            fields = {
                'title': proj['title'],
                'description': proj['description'],
                'tags_csv': ', '.join(proj.get('tags', [])),
                'github': proj.get('github', ''),
                'language': proj.get('language', ''),
                'featured': proj.get('featured', False),
                'display_order': order,
            }
            if existing is None:
                obj = Project.objects.create(**fields)
                self._upsert_links(ProjectLink, 'project', obj, proj.get('links', []))
                created += 1
            elif force:
                for k, v in fields.items():
                    setattr(existing, k, v)
                existing.save()
                existing.link_set.all().delete()
                self._upsert_links(ProjectLink, 'project', existing, proj.get('links', []))
                updated += 1
        self.stdout.write(f'  projects: +{created} created, {updated} updated')

    def _seed_timeline(self, force):
        from portfolio.models import TimelineEntry
        from portfolio.content.timeline import TIMELINE
        created = updated = 0
        for order, row in enumerate(TIMELINE):
            existing = TimelineEntry.objects.filter(year=row['year'], title=row['title']).first()
            fields = {
                'year': row['year'],
                'title': row['title'],
                'org': row.get('org', ''),
                'description': row.get('description', ''),
                'link': row.get('link', ''),
                'link_label': row.get('link_label', ''),
                'display_order': order,
            }
            if existing is None:
                TimelineEntry.objects.create(**fields)
                created += 1
            elif force:
                for k, v in fields.items():
                    setattr(existing, k, v)
                existing.save()
                updated += 1
        self.stdout.write(f'  timeline: +{created} created, {updated} updated')

    def _seed_opensource(self, force):
        from portfolio.models import OpenSourceItem
        from portfolio.content.opensource import OPENSOURCE
        created = updated = 0
        for order, row in enumerate(OPENSOURCE):
            existing = OpenSourceItem.objects.filter(name=row['name']).first()
            fields = {
                'name': row['name'],
                'description': row['description'],
                'url': row['url'],
                'role': row.get('role', ''),
                'display_order': order,
            }
            if existing is None:
                OpenSourceItem.objects.create(**fields)
                created += 1
            elif force:
                for k, v in fields.items():
                    setattr(existing, k, v)
                existing.save()
                updated += 1
        self.stdout.write(f'  opensource: +{created} created, {updated} updated')

    def _seed_social(self, force):
        from portfolio.models import SocialLink
        from portfolio.content.social import SOCIAL_LINKS
        created = updated = 0
        for order, row in enumerate(SOCIAL_LINKS):
            existing = SocialLink.objects.filter(name=row['name']).first()
            fields = {
                'name': row['name'],
                'url': row['url'],
                'icon': row['icon'],
                'display_order': order,
            }
            if existing is None:
                SocialLink.objects.create(**fields)
                created += 1
            elif force:
                for k, v in fields.items():
                    setattr(existing, k, v)
                existing.save()
                updated += 1
        self.stdout.write(f'  social: +{created} created, {updated} updated')

    def _seed_now(self, force):
        from datetime import date as _date
        from portfolio.models import NowPage, NowSection
        from portfolio.content.now import NOW_PAGE
        updated_str = NOW_PAGE.get('updated') or str(_date.today())
        try:
            updated_date = _date.fromisoformat(updated_str)
        except ValueError:
            updated_date = _date.today()

        existing = NowPage.objects.order_by('-modified_at').first()
        sections = NOW_PAGE.get('sections', [])
        if existing is None:
            page = NowPage.objects.create(
                updated=updated_date,
                location=NOW_PAGE.get('location', ''),
            )
            for i, s in enumerate(sections):
                NowSection.objects.create(now_page=page, heading=s['heading'], body=s['body'], order=i)
            self.stdout.write('  now: seeded singleton')
        elif force:
            existing.updated = updated_date
            existing.location = NOW_PAGE.get('location', '')
            existing.save()
            existing.section_set.all().delete()
            for i, s in enumerate(sections):
                NowSection.objects.create(now_page=existing, heading=s['heading'], body=s['body'], order=i)
            self.stdout.write('  now: updated singleton + sections')
        else:
            self.stdout.write('  now: kept existing (pass --force to overwrite)')

    # ─── Helpers ─────────────────────────────────────────────────

    def _upsert_links(self, LinkModel, fk_field, parent, links):
        for i, link in enumerate(links):
            LinkModel.objects.create(
                **{fk_field: parent},
                label=link['label'],
                url=link['url'],
                order=i,
            )
