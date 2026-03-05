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
