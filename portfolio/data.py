"""Backward-compatible re-export of the content split.

Content moved into `portfolio.content` (2026-04). Prefer importing from
the submodule directly for new code (e.g. `from portfolio.content.news
import NEWS`); this shim exists so existing `from portfolio.data import
...` call-sites keep working.
"""
from portfolio.content import (
    HERO,
    CURRENTLY,
    NEWS,
    PUBLICATIONS,
    PROJECTS,
    TIMELINE,
    OPENSOURCE,
    SOCIAL_LINKS,
    NOW_PAGE,
    DEMOS,
    NAV_LINKS,
    RECIPES,
)

__all__ = [
    'HERO', 'CURRENTLY', 'NEWS', 'PUBLICATIONS', 'PROJECTS', 'TIMELINE',
    'OPENSOURCE', 'SOCIAL_LINKS', 'NOW_PAGE', 'DEMOS', 'NAV_LINKS',
    'RECIPES',
]
