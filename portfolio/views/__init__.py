"""Views package. Split for readability (2026-04).

Public surface mirrors the pre-split single-file module, so existing
`from portfolio import views; views.blog(...)` call-sites keep
working.

  pages        — portfolio-side views: homepage, publications, projects,
                 demos, recipes, CV, now, garden, tags, misc (robots,
                 google verification, presentation proxy).
  blog_public  — public blog surface: /blog/, /notebook/, /reading/,
                 individual post pages, experiment variants.
  blog_editor  — staff-only in-browser editor: /blog/new/, /blog/<slug>/edit/,
                 autosave, preview, image upload.
  webmentions  — webmention.io fetcher used by blog_post.
  studio       — unified admin-landing dashboard (/site/studio/).
"""
from .pages import (
    index,
    recipes,
    recipe_detail,
    projects,
    publications,
    demos,
    demo_detail,
    now,
    garden,
    tag_index,
    tag_detail,
    cv_page,
    download_cv,
    presentation,
    google_verify,
    robots_txt,
)
from .blog_public import (
    blog,
    notebook,
    reading,
    blog_experiments_index,
    blog_experiment,
    blog_post,
    blog_map,
)
from .blog_editor import (
    blog_new,
    blog_edit,
    blog_preview,
    blog_upload_image,
    blog_autosave,
)
from .authoring import (
    blog_cite_bib,
    regenerate_og_card,
)
from .studio import studio
from .reading_quickadd import reading_quickadd
from .ask import ask_post

__all__ = [
    'index',
    'recipes',
    'recipe_detail',
    'projects',
    'publications',
    'demos',
    'demo_detail',
    'now',
    'garden',
    'tag_index',
    'tag_detail',
    'cv_page',
    'download_cv',
    'presentation',
    'google_verify',
    'robots_txt',
    'blog',
    'notebook',
    'reading',
    'blog_experiments_index',
    'blog_experiment',
    'blog_post',
    'blog_new',
    'blog_edit',
    'blog_preview',
    'blog_upload_image',
    'blog_autosave',
    'studio',
    'reading_quickadd',
]
