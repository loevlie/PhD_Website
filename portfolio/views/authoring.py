"""Author-facing endpoints: BibTeX citation export, OG-card regeneration.

Kept separate from blog_editor.py — those are for editing post
content; these are for packaging / sharing the finished post.
"""
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect

from portfolio.blog import get_post


def _citation_id(post):
    """A BibTeX-friendly citation id: author-last-name + year + first
    significant title word. Deterministic so tools that track cites
    don't see a new id on every save."""
    import re as _re
    year = post.get('date')
    year = year.year if hasattr(year, 'year') else 'nd'
    first_word = ''
    for w in _re.split(r'\W+', post['title']):
        if len(w) > 3 and w.lower() not in {'with', 'from', 'into', 'this', 'that', 'when', 'using'}:
            first_word = w.lower()
            break
    return f'loevlie{year}{first_word or post["slug"].replace("-", "")[:12]}'


def _name_to_bibtex(name):
    """Convert a display name ("Alice Young") to BibTeX author form
    ("Young, Alice"). Names already containing a comma are returned
    unchanged on the assumption they're pre-formatted."""
    name = (name or '').strip()
    if not name or ',' in name:
        return name
    parts = name.split()
    if len(parts) == 1:
        return parts[0]
    last = parts[-1]
    first = ' '.join(parts[:-1])
    return f'{last}, {first}'


def bibtex_author_field(post):
    """Build the BibTeX `author = {…}` value from a post's byline, in
    the author order set by the admin (PostCollaborator.order). Falls
    back to the legacy `post.author` CharField when byline_authors
    isn't populated (file-based posts, list views)."""
    byline = post.get('byline_authors') or []
    names = [a.get('name', '') for a in byline if a.get('name')]
    if not names:
        legacy = post.get('author') or 'Dennis Loevlie'
        names = [legacy]
    return ' and '.join(_name_to_bibtex(n) for n in names)


def blog_cite_bib(request, slug):
    """GET /blog/<slug>/cite.bib — return a BibTeX @misc entry for
    the post, so academic readers can cite it verbatim in a paper."""
    post = get_post(slug)
    if post is None:
        raise Http404("Post not found")
    cite_id = _citation_id(post)
    url = request.build_absolute_uri(f'/blog/{slug}/')
    date_obj = post.get('date')
    year = date_obj.year if hasattr(date_obj, 'year') else ''
    month = date_obj.strftime('%b').lower() if hasattr(date_obj, 'strftime') else ''
    author = bibtex_author_field(post)
    title = post['title']
    # Escape for BibTeX: curly-protect the title (stops
    # capitalization-folding by downstream processors).
    bib = (
        f'@misc{{{cite_id},\n'
        f'  author       = {{{author}}},\n'
        f'  title        = {{{{{title}}}}},\n'
        f'  year         = {{{year}}},\n'
        + (f'  month        = {month},\n' if month else '')
        + f'  howpublished = {{Blog post}},\n'
        f'  url          = {{{url}}},\n'
        f'  note         = {{Accessed: \\today}}\n'
        '}\n'
    )
    resp = HttpResponse(bib, content_type='application/x-bibtex; charset=utf-8')
    resp['Content-Disposition'] = f'inline; filename="{cite_id}.bib"'
    return resp


def regenerate_og_card(request, slug):
    """POST /blog/<slug>/regenerate-og/ — run the generate_og_cards
    management command for a single post. Staff only. Kicks off the
    Playwright render and returns JSON with the new URL."""
    if not (request.user.is_authenticated and request.user.is_staff):
        return JsonResponse({'ok': False, 'error': 'unauthorized'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    from django.core.management import call_command
    from io import StringIO
    out = StringIO()
    try:
        call_command('generate_og_cards', slug=slug, stdout=out, stderr=out)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)
    return JsonResponse({
        'ok': True,
        'log': out.getvalue().splitlines()[-5:],
        'url': f'/media/og/{slug}.png',
    })
