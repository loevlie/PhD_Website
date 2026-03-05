from portfolio.data import (
    HERO, NEWS, PUBLICATIONS, PROJECTS, TIMELINE,
    OPENSOURCE, SOCIAL_LINKS, NAV_LINKS,
)


def portfolio_data(request):
    return {
        'hero': HERO,
        'news': NEWS,
        'publications': PUBLICATIONS,
        'projects': PROJECTS,
        'timeline': TIMELINE,
        'opensource': OPENSOURCE,
        'social_links': SOCIAL_LINKS,
        'nav_links': NAV_LINKS,
    }
