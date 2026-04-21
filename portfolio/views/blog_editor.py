"""Staff-only in-browser post editor.

Routes served here:

    /blog/new/                 blog_new       — template picker + draft create
    /blog/<slug>/edit/         blog_edit      — markdown / live-preview editor
    /blog/<slug>/autosave/     blog_autosave  — background JSON save
    /blog/preview/             blog_preview   — render markdown to HTML for the preview pane
    /blog/upload-image/        blog_upload_image

Auth: every endpoint requires request.user.is_staff (see `_can_edit`).
"""
from datetime import date as date_cls
import os
import re

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.text import slugify

from portfolio.data import DEMOS


# ─── Auth helper ─────────────────────────────────────────────────────

def _can_edit(request):
    """True if the request is authenticated as a staff/superuser. Used to
    gate the in-browser editor at /blog/<slug>/edit/ and /blog/new/."""
    return request.user.is_authenticated and request.user.is_staff


# ─── POST-field → Post attribute adapter ─────────────────────────────

def _apply_post_fields(post, data):
    """Apply editor POST fields onto a Post instance. Shared by full-save
    and autosave so behavior stays identical."""
    for field in ('title', 'excerpt', 'body', 'slug', 'series', 'image', 'medium_url'):
        v = data.get(field)
        if v is not None:
            setattr(post, field, v)
    if 'maturity' in data:
        m = data.get('maturity', '')
        post.maturity = m if m in {'', 'seedling', 'budding', 'evergreen'} else ''
    if 'kind' in data:
        k = data.get('kind', 'essay')
        post.kind = k if k in {'essay', 'lab_note'} else 'essay'
    for bool_field in ('is_explainer', 'is_paper_companion', 'draft'):
        if bool_field in data:
            post.__dict__[bool_field] = data.get(bool_field) in ('on', 'true', '1')
    if 'date' in data and data.get('date'):
        try:
            from datetime import date as _date
            post.date = _date.fromisoformat(data['date'])
        except (ValueError, TypeError):
            pass


# ─── /blog/<slug>/edit/ ──────────────────────────────────────────────

def blog_edit(request, slug):
    """In-browser WYSIWYG-ish editor for a single Post.
    Two-column layout: markdown source on the left, live server-rendered
    preview on the right. Auth: staff only."""
    if not _can_edit(request):
        return redirect(f'/admin/login/?next=/blog/{slug}/edit/')

    from portfolio.models import Post
    try:
        post = Post.objects.get(slug=slug)
    except Post.DoesNotExist:
        raise Http404("Post not found")

    if request.method == 'POST':
        _apply_post_fields(post, request.POST)
        post.save()
        if request.POST.get('tags') is not None:
            tag_str = request.POST.get('tags', '').strip()
            tag_list = [t.strip() for t in tag_str.split(',') if t.strip()] if tag_str else []
            post.tags.set(tag_list)
        if request.POST.get('action') == 'view':
            return redirect('blog_post', slug=post.slug)
        return redirect('blog_edit', slug=post.slug)

    return render(request, 'portfolio/blog_edit.html', {
        'post': post,
        'is_new': False,
        'tag_csv': ', '.join(t.name for t in post.tags.all()),
        'demos': DEMOS,
    })


# ─── /blog/<slug>/autosave/ ──────────────────────────────────────────

def blog_autosave(request, slug):
    """Background autosave for the editor. Same field handling as
    blog_edit POST but returns JSON, doesn't redirect, and never fails
    loud (always 200 with {ok, saved_at})."""
    if not _can_edit(request):
        return JsonResponse({'ok': False, 'error': 'unauthorized'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    from portfolio.models import Post
    try:
        post = Post.objects.get(slug=slug)
    except Post.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'not found'}, status=404)
    try:
        _apply_post_fields(post, request.POST)
        post.save()
        if request.POST.get('tags') is not None:
            tag_str = request.POST.get('tags', '').strip()
            tag_list = [t.strip() for t in tag_str.split(',') if t.strip()] if tag_str else []
            post.tags.set(tag_list)
        return JsonResponse({'ok': True, 'saved_at': timezone.now().isoformat()})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


# ─── /blog/new/ (template picker + draft creator) ─────────────────────

_POST_TEMPLATES = {
    'blank': {
        'label': 'Blank',
        'desc': 'Empty draft. Start from scratch.',
        'title': 'Untitled draft',
        'body': '# Untitled\n\nStart writing…\n',
        'maturity': 'seedling',
        'is_explainer': False,
        'is_paper_companion': False,
    },
    'explainer': {
        'label': 'Explainer',
        'desc': 'Tufte sidenotes + hover citations + drop cap. For technical posts that lean on a margin column.',
        'title': 'New explainer',
        'body': (
            '# New explainer\n\n'
            'A one-sentence framing of what this post explains and who it\'s for.\n\n'
            '## The setup\n\n'
            'Lay the ground[^groundnote]. Two or three sentences max.\n\n'
            '[^groundnote]: A sidenote — appears in the right margin on wide screens, inline on mobile.\n\n'
            '## The argument\n\n'
            'Make the case. Cite where you build on others <cite class="ref" data-key="key2024">[1]</cite>.\n\n'
            '## What this means\n\n'
            'Consequences. End with one concrete next step or open question.\n'
        ),
        'maturity': 'budding',
        'is_explainer': True,
        'is_paper_companion': False,
    },
    'paper': {
        'label': 'Paper companion',
        'desc': 'Magazine-grade single-column with drop cap, real footnotes, pull-quotes. For essays accompanying a paper.',
        'title': 'Paper companion: <title>',
        'body': (
            '# Paper companion: <title>\n\n'
            'A two-sentence pitch. What the paper does in one sentence; why it matters in another.\n\n'
            '## The problem\n\n'
            'Set up the gap. Cite the prior art[^cite1].\n\n'
            '[^cite1]: Smith et al., 2024. Full citation here.\n\n'
            '> "A pull-quote that captures the contribution."\n\n'
            '## What we did\n\n'
            'The technical setup in plain English. One figure if it helps.\n\n'
            '## What we found\n\n'
            'The result. Honest about the caveats.\n\n'
            '## Where this goes\n\n'
            'Next steps. Open questions.\n'
        ),
        'maturity': 'evergreen',
        'is_explainer': False,
        'is_paper_companion': True,
    },
    'note': {
        'label': 'Quick note',
        'desc': 'A short Andy-Matuschak-style atomic note. One idea, one screen.',
        'title': 'A short note',
        'body': (
            '# A short note\n\n'
            'The idea in one paragraph. Make it self-contained — link out to longer pieces if needed.\n\n'
            'A second paragraph if the first didn\'t finish the thought.\n'
        ),
        'maturity': 'seedling',
        'is_explainer': False,
        'is_paper_companion': False,
    },
    'demo': {
        'label': 'Demo writeup',
        'desc': (
            'Embed a live demo + writeup explaining what it shows. '
            'Append <code>?demo=&lt;slug&gt;</code> to pre-fill from a specific demo.'
        ),
        'title': 'Demo: <name>',
        'body': (
            '# Demo: <name>\n\n'
            'One sentence on what the demo shows.\n\n'
            '<div data-demo="<slug>"></div>\n\n'
            '## What you\'re seeing\n\n'
            'Plain-English explanation of the underlying mechanism.\n\n'
            '## What surprised me\n\n'
            'The non-obvious thing the demo made clear.\n\n'
            '## Caveats\n\n'
            'What the demo *isn\'t* showing.\n'
        ),
        'maturity': 'budding',
        'is_explainer': True,
        'is_paper_companion': False,
    },
    'lab_note': {
        'label': 'Lab note',
        'desc': 'Dated, status-tagged entry for /notebook/. Short format; updated iteratively.',
        'title': 'Lab note — <topic>',
        'body': (
            '# <topic>\n\n'
            '**Status:** open — iterating.\n\n'
            'What I tried today and what happened. One paragraph.\n\n'
            '## Next step\n\n'
            'The smallest testable follow-up.\n'
        ),
        'maturity': 'seedling',
        'is_explainer': False,
        'is_paper_companion': False,
    },
}


def blog_new(request):
    """Create a new draft post and redirect to its editor.
    GET without ?template=: show the template-picker page.
    GET with ?template=<key>: create a draft from that template.
    """
    if not _can_edit(request):
        return redirect('/admin/login/?next=/blog/new/')

    template_key = request.GET.get('template')
    if template_key not in _POST_TEMPLATES:
        return render(request, 'portfolio/blog_new.html', {
            'templates': [(k, v) for k, v in _POST_TEMPLATES.items()],
        })

    tmpl = _POST_TEMPLATES[template_key]
    from portfolio.models import Post
    body = tmpl['body']
    base_title = request.GET.get('title') or tmpl['title']

    # For the `demo` template, a ?demo=<slug> param pre-fills the title
    # and the data-demo marker from the chosen DEMOS entry so the
    # resulting post renders the live widget out of the box.
    if template_key == 'demo':
        demo_slug = (request.GET.get('demo') or '').strip()
        if demo_slug:
            from portfolio.content.demos import DEMOS
            demo = next((d for d in DEMOS if d['slug'] == demo_slug), None)
            if demo:
                base_title = request.GET.get('title') or f'Demo: {demo["title"]}'
                body = (
                    f'# {demo["title"]}\n\n'
                    f'{demo["summary"]}\n\n'
                    f'<div data-demo="{demo_slug}"></div>\n\n'
                    '## What you\'re seeing\n\n'
                    'Plain-English explanation of the underlying mechanism.\n\n'
                    '## What surprised me\n\n'
                    'The non-obvious thing the demo made clear.\n\n'
                    '## Caveats\n\n'
                    'What the demo *isn\'t* showing.\n'
                )

    base_slug = slugify(base_title) or 'untitled-draft'
    slug = base_slug
    n = 1
    while Post.objects.filter(slug=slug).exists():
        n += 1
        slug = f'{base_slug}-{n}'
    # Lab-note template lands in /notebook/; everything else is an essay.
    kind = 'lab_note' if template_key == 'lab_note' else 'essay'
    p = Post.objects.create(
        slug=slug,
        title=base_title,
        body=body,
        date=date_cls.today(),
        draft=True,
        kind=kind,
        maturity=tmpl['maturity'],
        is_explainer=tmpl['is_explainer'],
        is_paper_companion=tmpl['is_paper_companion'],
    )
    return redirect('blog_edit', slug=p.slug)


# ─── /blog/preview/ ──────────────────────────────────────────────────

def blog_preview(request):
    """Server-renders a markdown payload to HTML for the live-preview
    pane in the editor. POST {body, is_explainer} -> {html, toc}."""
    if not _can_edit(request):
        return JsonResponse({'error': 'unauthorized'}, status=403)
    from portfolio.blog import render_markdown
    body = request.POST.get('body', '')
    is_explainer = request.POST.get('is_explainer') == 'true'
    html, toc = render_markdown(body, is_explainer=is_explainer)
    return JsonResponse({'html': html, 'toc': toc})


# ─── /blog/upload-image/ ─────────────────────────────────────────────

def blog_upload_image(request):
    """Editor image upload. POST a multipart `image` file; returns
    {url, markdown}. The editor inserts the markdown snippet at the
    cursor. Files land in MEDIA_ROOT/blog-images/YYYY/MM/<slug>-<n>.ext.

    Production caveat: ephemeral filesystems (Render free tier) lose
    these on every redeploy. Move MEDIA_ROOT to S3 or equivalent
    before relying on this in prod."""
    if not _can_edit(request):
        return JsonResponse({'error': 'unauthorized'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    f = request.FILES.get('image')
    if not f:
        return JsonResponse({'error': 'no file'}, status=400)
    # Basic content-type allow-list: PNG/JPEG/WEBP/GIF/AVIF + size cap (8 MB).
    if (f.content_type or '').split('/')[0] != 'image':
        return JsonResponse({'error': 'not an image'}, status=400)
    if f.size > 8 * 1024 * 1024:
        return JsonResponse({'error': 'file too large (8 MB max)'}, status=400)

    today = date_cls.today()
    subdir = f'blog-images/{today:%Y}/{today:%m}'
    base, ext = os.path.splitext(f.name)
    safe_base = slugify(base) or 'image'
    safe_ext = re.sub(r'[^a-zA-Z0-9]', '', ext.lower())[:5] or 'png'
    fname = f'{safe_base}.{safe_ext}'

    storage = FileSystemStorage(
        location=os.path.join(settings.MEDIA_ROOT, subdir),
        base_url=settings.MEDIA_URL + subdir + '/',
    )
    saved_name = storage.save(fname, f)  # auto-suffixes on collisions
    url = storage.url(saved_name)
    alt = request.POST.get('alt', '') or safe_base.replace('-', ' ')
    return JsonResponse({
        'url': url,
        'markdown': f'![{alt}]({url})',
        'filename': saved_name,
    })
