"""Site-wide template context.

Content used to come exclusively from the static `portfolio.data`
dicts; after Track B1 (2026-04) content is DB-backed via
`portfolio.content.live`, which falls back to data.py when the DB is
empty. Templates don't change — the shapes are preserved.
"""
from portfolio.content.hero import HERO
from portfolio.content.nav import NAV_LINKS
from portfolio.content.recipes import RECIPES
from portfolio.content.demos import DEMOS
from portfolio.content import live
from portfolio.blog import get_all_posts


def portfolio_data(request):
    # The featured homepage demo (currently Frozen Forecaster). Resolves
    # to None when the demo is a draft, so the homepage section, the
    # Cmd+K palette entry, and the nav dropdown all hide together.
    featured_demo = next(
        (d for d in DEMOS if d['slug'] == 'frozen-forecaster' and not d.get('draft')),
        None,
    )
    social = live.social_links()
    return {
        'hero': HERO,
        'news': live.news(),
        'publications': live.publications(),
        'projects': live.projects(),
        'timeline': live.timeline(),
        'opensource': live.opensource(),
        'social_links': social,
        'nav_links': NAV_LINKS,
        'recipes': RECIPES,
        'blog_posts': get_all_posts(),
        'social_sameas_urls': [s['url'] for s in social if s['url'].startswith('http')],
        'featured_demo': featured_demo,
    }
