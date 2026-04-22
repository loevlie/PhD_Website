"""`<div data-demo="slug">` — portfolio demo embed.

Supersedes the old _expand_demo_embeds function in blog/__init__.py.
Kept in its own handler so the legacy `class="demo-embed" data-slug="…"`
marker can still be understood by the same module.
"""
from . import render_error


_NEW_FORM = r'<div\s+data-demo=["\']([a-z0-9\-]+)["\'][^>]*>\s*</div>'
_LEGACY_FORM = (
    r'<div\b'
    r'(?=[^>]*\bclass=["\']demo-embed["\'])'
    r'(?=[^>]*\bdata-slug=["\']([a-z0-9\-]+)["\'])'
    r'[^>]*>\s*</div>'
)


def _render(slug: str) -> str:
    from django.template.loader import render_to_string, TemplateDoesNotExist
    from portfolio.content.demos import DEMOS

    demo = next((d for d in DEMOS if d['slug'] == slug), None)
    if demo is None:
        return render_error(
            f'Unknown demo slug: <code>{slug}</code>. '
            f'Add it to portfolio/content/demos.py or pick an existing slug.'
        )
    template_name = f'portfolio/demos/{demo["embed"]}'
    try:
        embed_html = render_to_string(template_name)
    except TemplateDoesNotExist:
        return render_error(
            f'Missing embed template <code>{template_name}</code> for demo '
            f'<code>{slug}</code>.'
        )
    footer = (
        f'<div class="demo-embed-footer">'
        f'<span>{demo["title"]}</span>'
        f'<a href="/demos/{slug}/">Open full demo →</a>'
        f'</div>'
    )
    return (
        f'<div class="demo-embed-root" data-demo="{slug}">'
        f'{embed_html}{footer}'
        f'</div>'
    )


def register_all(register):
    register(_NEW_FORM, lambda m: _render(m.group(1)))
    register(_LEGACY_FORM, lambda m: _render(m.group(1)))
