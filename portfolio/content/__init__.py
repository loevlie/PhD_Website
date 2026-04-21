"""Portfolio content split by topic.

Each submodule defines one top-level constant (HERO, NEWS, …) so edits
are isolated and diffs stay small. Use the submodules directly where
you can; the legacy `portfolio.data` module still re-exports all names
for backward compatibility.
"""
from .hero import HERO, CURRENTLY
from .news import NEWS
from .publications import PUBLICATIONS
from .projects import PROJECTS
from .timeline import TIMELINE
from .opensource import OPENSOURCE
from .social import SOCIAL_LINKS
from .now import NOW_PAGE
from .demos import DEMOS
from .nav import NAV_LINKS
from .recipes import RECIPES

__all__ = [
    'HERO', 'CURRENTLY', 'NEWS', 'PUBLICATIONS', 'PROJECTS', 'TIMELINE',
    'OPENSOURCE', 'SOCIAL_LINKS', 'NOW_PAGE', 'DEMOS', 'NAV_LINKS',
    'RECIPES',
]
