import markdown as _md

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='md')
def render_md(text):
    """Render an inline Markdown string to safe HTML.
    Used by /now/ and other small editorial pages where the source
    string is hand-authored (in data.py) and uses **bold** / *italic* /
    [link](url) and inline `<br>` tags for paragraph spacing."""
    if not text:
        return ''
    html = _md.markdown(
        text,
        extensions=['extra', 'smarty'],
        output_format='html',
    )
    return mark_safe(html)


AUTHOR_VARIANTS = [
    'Dennis Johan Loevlie',
    'Dennis J. Loevlie',
    'Dennis Loevlie',
    'Denny Loevlie',
]


@register.filter
def highlight_author(name):
    for variant in AUTHOR_VARIANTS:
        if variant in name:
            return mark_safe(
                name.replace(variant, f'<strong class="highlight-author">{variant}</strong>')
            )
    return name


@register.simple_tag
def og_image_url(post_slug):
    """Return the per-post OG card URL if one is persisted in
    default_storage, otherwise the site-wide cover.

    The card is rendered by `portfolio.og.generate_card` (run by the
    `generate_og_cards` management command, the `regenerate_og_card`
    view, or auto-fired on Post save) and lives at `og/<slug>.png` in
    storage — R2 in prod, MEDIA_ROOT in dev. Both paths survive
    deploys; the previous static-tree variant did not."""
    from django.conf import settings as dj_settings
    from portfolio.og import card_url_for
    url = card_url_for(post_slug)
    if url:
        return url
    return f'{dj_settings.STATIC_URL}portfolio/images/og-cover.jpg'


@register.filter
def unique_attr(items, attr):
    """De-duplicate a sequence of dicts (or objects) by one attribute,
    preserving first-seen order. Used by publications.html to render
    year + type filter chips without duplicates."""
    seen = set()
    out = []
    for item in items:
        v = item.get(attr) if isinstance(item, dict) else getattr(item, attr, None)
        if v is None or v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out
