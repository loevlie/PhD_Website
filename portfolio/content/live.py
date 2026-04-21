"""Thin adapter: read site content from the DB, fall back to the
static content modules when a table is empty or when the DB isn't
available (tests, `manage.py check`, etc.).

Shape contract: each function returns data in the *same* nested-dict
form that the existing templates expect, so switching to DB storage
doesn't require rewriting any template. See portfolio/content/*.py for
the canonical shapes.

Cache: 10 min per function. Invalidated via `portfolio.signals` on
model save/delete; see signals.py (Content*Invalidator).
"""
from django.core.cache import cache


_CACHE_TTL = 60 * 10
_CACHE_PREFIX = 'content:v1:'


def _cached(key, compute):
    ck = _CACHE_PREFIX + key
    hit = cache.get(ck)
    if hit is not None:
        return hit
    val = compute()
    cache.set(ck, val, _CACHE_TTL)
    return val


def invalidate(key=None):
    """Clear a single cache key, or all live-content keys if key is None."""
    if key:
        cache.delete(_CACHE_PREFIX + key)
        return
    for k in ('news', 'publications', 'projects', 'timeline',
              'opensource', 'social_links', 'now_page'):
        cache.delete(_CACHE_PREFIX + k)


# ─── News ─────────────────────────────────────────────────────────────

def news():
    return _cached('news', _compute_news)


def _compute_news():
    # Fallback rule (shared across all seeders): if the *table* has
    # zero rows, use the static content module. If the table has rows
    # but everything's a draft, return []. That way the admin toggling
    # draft=True on every item genuinely hides the section (expected
    # behavior) rather than silently re-surfacing the data.py fallback.
    try:
        from portfolio.models import NewsItem
        if not NewsItem.objects.exists():
            raise NewsItem.DoesNotExist
        rows = list(NewsItem.objects.filter(draft=False).order_by('display_order', '-created_at'))
    except Exception:
        from portfolio.content.news import NEWS
        return NEWS
    return [{'date': r.date, 'text': r.text, 'highlight': r.highlight} for r in rows]


# ─── Publications ─────────────────────────────────────────────────────

def publications():
    return _cached('publications', _compute_publications)


def _compute_publications():
    try:
        from portfolio.models import Publication
        if not Publication.objects.exists():
            raise Publication.DoesNotExist
        qs = (Publication.objects.filter(draft=False)
              .prefetch_related('link_set')
              .order_by('display_order', '-year'))
        rows = list(qs)
    except Exception:
        from portfolio.content.publications import PUBLICATIONS
        return PUBLICATIONS
    out = []
    for r in rows:
        out.append({
            'title': r.title,
            'authors': r.author_list,
            'venue': r.venue,
            'year': r.year,
            'type': r.pub_type,
            'selected': r.selected,
            'image': r.image,
            'image_credit': r.image_credit,
            'bibtex': r.bibtex,
            'links': [{'label': l.label, 'url': l.url}
                      for l in r.link_set.all()],
        })
    return out


# ─── Projects ─────────────────────────────────────────────────────────

def projects():
    return _cached('projects', _compute_projects)


def _compute_projects():
    try:
        from portfolio.models import Project
        if not Project.objects.exists():
            raise Project.DoesNotExist
        qs = (Project.objects.filter(draft=False)
              .prefetch_related('link_set')
              .order_by('display_order', '-modified_at'))
        rows = list(qs)
    except Exception:
        from portfolio.content.projects import PROJECTS
        return PROJECTS
    out = []
    for r in rows:
        out.append({
            'title': r.title,
            'description': r.description,
            'tags': r.tags,
            'github': r.github,
            'language': r.language,
            'featured': r.featured,
            'links': [{'label': l.label, 'url': l.url}
                      for l in r.link_set.all()],
        })
    return out


# ─── Timeline ─────────────────────────────────────────────────────────

def timeline():
    return _cached('timeline', _compute_timeline)


def _compute_timeline():
    try:
        from portfolio.models import TimelineEntry
        if not TimelineEntry.objects.exists():
            raise TimelineEntry.DoesNotExist
        rows = list(TimelineEntry.objects.filter(draft=False).order_by('display_order', '-created_at'))
    except Exception:
        from portfolio.content.timeline import TIMELINE
        return TIMELINE
    return [{
        'year': r.year, 'title': r.title, 'org': r.org,
        'description': r.description,
        'link': r.link, 'link_label': r.link_label,
    } for r in rows]


# ─── Open source ──────────────────────────────────────────────────────

def opensource():
    return _cached('opensource', _compute_opensource)


def _compute_opensource():
    try:
        from portfolio.models import OpenSourceItem
        if not OpenSourceItem.objects.exists():
            raise OpenSourceItem.DoesNotExist
        rows = list(OpenSourceItem.objects.filter(draft=False).order_by('display_order', '-created_at'))
    except Exception:
        from portfolio.content.opensource import OPENSOURCE
        return OPENSOURCE
    return [{
        'name': r.name, 'description': r.description,
        'url': r.url, 'role': r.role,
    } for r in rows]


# ─── Social links ─────────────────────────────────────────────────────

def social_links():
    return _cached('social_links', _compute_social_links)


def _compute_social_links():
    try:
        from portfolio.models import SocialLink
        if not SocialLink.objects.exists():
            raise SocialLink.DoesNotExist
        rows = list(SocialLink.objects.filter(draft=False).order_by('display_order', 'id'))
    except Exception:
        from portfolio.content.social import SOCIAL_LINKS
        return SOCIAL_LINKS
    return [{'name': r.name, 'url': r.url, 'icon': r.icon} for r in rows]


# ─── /now/ page ───────────────────────────────────────────────────────

def now_page():
    return _cached('now_page', _compute_now_page)


def _compute_now_page():
    try:
        from portfolio.models import NowPage
        page = NowPage.current()
    except Exception:
        page = None
    if page is None:
        from portfolio.content.now import NOW_PAGE
        return NOW_PAGE
    sections = list(page.section_set.all())
    # `inspired_by` stays static — it's editorial copy, not per-quarter
    # content. Merge from the content module so the admin doesn't need
    # to know about it.
    from portfolio.content.now import NOW_PAGE as _NOW_STATIC
    return {
        'updated': page.updated.isoformat() if page.updated else '',
        'location': page.location,
        'sections': [{'heading': s.heading, 'body': s.body} for s in sections],
        'inspired_by': _NOW_STATIC.get('inspired_by', []),
    }
