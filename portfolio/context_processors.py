"""Site-wide template context.

Content used to come exclusively from the static `portfolio.data`
dicts; after Track B1 (2026-04) content is DB-backed via
`portfolio.content.live`, which falls back to data.py when the DB is
empty. Templates don't change — the shapes are preserved.

Every non-trivial value is wrapped in SimpleLazyObject: the work (cache
lookups, cold-cache DB queries) only happens when a template actually
reads the key. Blog pages — including the editor — reference none of
these, so they skip all of it; the homepage resolves what its sections
iterate. Don't add isinstance/identity checks on these values.
"""
from django.utils.functional import SimpleLazyObject

from portfolio.content.hero import HERO
from portfolio.content.nav import NAV_LINKS
from portfolio.content.recipes import RECIPES
from portfolio.content.demos import DEMOS
from portfolio.content import live
from portfolio.blog import get_all_posts


def _sameas_urls():
    # live.social_links() is locmem-cached (10 min), so resolving both
    # social_links and this is one cache hit, not two query chains.
    return [s['url'] for s in live.social_links() if s['url'].startswith('http')]


def portfolio_data(request):
    # The featured homepage demo (currently Frozen Forecaster). Resolves
    # to None when the demo is a draft, so the homepage section, the
    # Cmd+K palette entry, and the nav dropdown all hide together.
    featured_demo = next(
        (d for d in DEMOS if d['slug'] == 'frozen-forecaster' and not d.get('draft')),
        None,
    )
    return {
        'hero': HERO,
        'news': SimpleLazyObject(live.news),
        'publications': SimpleLazyObject(live.publications),
        'projects': SimpleLazyObject(live.projects),
        'timeline': SimpleLazyObject(live.timeline),
        'opensource': SimpleLazyObject(live.opensource),
        'social_links': SimpleLazyObject(live.social_links),
        'nav_links': NAV_LINKS,
        'recipes': RECIPES,
        'blog_posts': SimpleLazyObject(get_all_posts),
        'social_sameas_urls': SimpleLazyObject(_sameas_urls),
        'featured_demo': featured_demo,
    }
