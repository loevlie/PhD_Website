from django import template
from django.utils.safestring import mark_safe

register = template.Library()


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
