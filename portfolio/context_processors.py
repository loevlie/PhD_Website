from portfolio.data import (
    HERO, NEWS, PUBLICATIONS, PROJECTS, TIMELINE,
    OPENSOURCE, SOCIAL_LINKS, NAV_LINKS, RECIPES, DEMOS,
)
from portfolio.blog import get_all_posts


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
        'news': NEWS,
        'publications': PUBLICATIONS,
        'projects': PROJECTS,
        'timeline': TIMELINE,
        'opensource': OPENSOURCE,
        'social_links': SOCIAL_LINKS,
        'nav_links': NAV_LINKS,
        'recipes': RECIPES,
        'blog_posts': get_all_posts(),
        'social_sameas_urls': [s['url'] for s in SOCIAL_LINKS if s['url'].startswith('http')],
        'featured_demo': featured_demo,
    }
