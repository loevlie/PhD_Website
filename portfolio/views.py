from django.shortcuts import render
from django.http import Http404

from portfolio.data import RECIPES, DEMOS
from portfolio.blog import get_all_posts, get_post


def index(request):
    # `featured_demo` (None when Frozen Forecaster is a draft) is provided
    # by portfolio.context_processors.portfolio_data so all templates —
    # the homepage section, Cmd+K palette, and nav dropdown — hide together.
    return render(request, 'portfolio/index.html')


def recipes(request):
    return render(request, 'portfolio/recipes.html')


def recipe_detail(request, slug):
    recipe = next((r for r in RECIPES if r['slug'] == slug), None)
    if recipe is None:
        raise Http404("Recipe not found")
    return render(request, 'portfolio/recipe_detail.html', {'recipe': recipe})


def blog(request):
    """Long-form essays at /blog/. Default view is the image-led photo
    grid (see portfolio/blog.html); ?view=list flips to the typographic
    Postcard list. Filters Post.kind == 'essay' so lab notes don't leak
    into the essay surface."""
    view = request.GET.get('view', '')
    if view == 'list':
        template = 'portfolio/blog_list.html'
    else:
        template = 'portfolio/blog.html'
    return _blog_render(request, template=template, kind='essay', view=view)


def notebook(request):
    """Open research log at /notebook/. Filters Post.kind == 'lab_note';
    renders with status pills, dual dates, and the sticky `currently:`
    bar (text from data.CURRENTLY)."""
    from portfolio.data import CURRENTLY
    return _blog_render(
        request, template='portfolio/notebook.html',
        kind='lab_note', extra={'currently': CURRENTLY},
    )


def reading(request):
    """Curated reading list at /reading/. Pulls from the Reading model
    (admin-editable). Hides archived entries; this_week sits above
    lingering."""
    from portfolio.models import Reading
    entries = Reading.objects.exclude(status='archived').order_by('order', '-created_at')
    this_week = [r for r in entries if r.status == 'this_week']
    lingering = [r for r in entries if r.status == 'lingering']
    return render(request, 'portfolio/reading.html', {
        'this_week': this_week,
        'lingering': lingering,
        'total': len(this_week) + len(lingering),
    })


def blog_experiment(request, name):
    """Local-preview variants of the blog landing page. Each experiment
    template at portfolio/blog_exp_<name>.html lets us A/B-feel a
    redesign before touching the canonical /blog/. Routed at
    /blog/exp/<name>/. Anyone can visit (we want to share the link
    around for feedback) but they're unindexed via robots noindex."""
    from django.http import Http404
    template = f'portfolio/blog_exp_{name}.html'
    from django.template.loader import select_template
    try:
        select_template([template])
    except Exception:
        raise Http404(f'Unknown blog experiment: {name}')
    return _blog_render(request, template=template, experiment=name)


_BLOG_EXPERIMENTS = [
    # Round 1
    ('garden', 'Garden', 'Maggie-Appleton-warm: voice up top, maturity badges, soft cards with cover banner, “last tended” ordering.'),
    ('notebook', 'Notebook', 'Calm-typographic: year-grouped flat list, square thumbnail at left of each row, no card chrome.'),
    ('magazine', 'Magazine', 'Stripe / Vercel blog pattern: hero card for newest post, smaller cards in a grid below.'),
    ('indexcard', 'Index Card', 'Letterboxd / library catalog: dense compact rows with square cover thumbnail at left.'),
    ('postcard', 'Postcard', 'Substack / newsletter rhythm: each post a single-column postcard, image banner up top.'),
    # Round 2 — 7 deeper directions
    ('numbered', 'Numbered Notes', 'Robin-Rendle "v19": running #NNNN counter spine, no cards, hero block for newest, mono dates.'),
    ('issue', 'Issue-Based', 'Asterisk / Works-in-Progress register: bundled into themed issues; current issue full, priors collapsed.'),
    ('labnotebook', 'Open Lab Notebook', 'Researcher-honest: status pill (open/iterating/parked/wrapped) + dual-dated entries, sticky `currently:` bar.'),
    ('reading', 'Reading-Log Hybrid', 'Papers I\'m chewing on, then the newest essay transcluded (real first paragraph + figure), then a quiet list.'),
    ('calendar', 'Calendar Block', 'One row per month; empty months show as `2026 / MAR · · ·`. Pace is honest, like a heartbeat strip.'),
    ('topographic', 'Topographic', 'Explicit `Foundations` zone (handpicked evergreens) above the chronological `Recent` feed.'),
    ('photo', 'Photo-Essay First', 'Image-led asymmetric grid; hover for title + date. Foregrounds the figures you already produce.'),
]


def blog_experiments_index(request):
    """Index page listing the available blog landing experiments."""
    return render(request, 'portfolio/blog_experiments.html', {
        'experiments': _BLOG_EXPERIMENTS,
    })


def _blog_render(request, *, template, experiment=None, kind=None, view='', extra=None):
    is_staff = request.user.is_authenticated and request.user.is_staff
    # Staff see drafts in the listing (so we don't lose track of WIP);
    # public listing excludes them entirely.
    posts = get_all_posts(include_drafts=is_staff)
    if kind:
        # Filter by kind. Posts that pre-date the field default to 'essay',
        # so /blog/ shows everything historical and /notebook/ starts empty
        # until the first lab_note is created.
        posts = [p for p in posts if (p.get('kind') or 'essay') == kind]
    tag = request.GET.get('tag')
    query = request.GET.get('q', '').strip()
    only_drafts = request.GET.get('drafts') == '1'

    if only_drafts and is_staff:
        posts = [p for p in posts if p.get('draft')]
    if tag:
        posts = [p for p in posts if tag in p['tags']]
    if query:
        q_lower = query.lower()
        posts = [p for p in posts if
                 q_lower in p['title'].lower() or
                 q_lower in p['excerpt'].lower() or
                 any(q_lower in t.lower() for t in p['tags'])]

    draft_count = sum(1 for p in posts if p.get('draft')) if is_staff else 0

    ctx = {
        'posts': posts,
        'active_tag': tag,
        'search_query': query,
        'is_staff': is_staff,
        'only_drafts': only_drafts,
        'draft_count': draft_count,
        'experiment': experiment,
        'kind': kind,
        'view': view,
    }
    if extra:
        ctx.update(extra)
    return render(request, template, ctx)


def _can_edit(request):
    """True if the request is authenticated as a staff/superuser. Used to
    gate the in-browser editor at /blog/<slug>/edit/ and /blog/new/."""
    return request.user.is_authenticated and request.user.is_staff


def blog_edit(request, slug):
    """In-browser WYSIWYG-ish editor for a single Post.
    Two-column layout: markdown source on the left, live server-rendered
    preview on the right. Auth: staff only."""
    from django.shortcuts import redirect
    from django.contrib.auth.decorators import login_required
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


def blog_autosave(request, slug):
    """Background autosave for the editor. Same field handling as
    blog_edit POST but returns JSON, doesn't redirect, and never fails
    loud (always 200 with {ok, saved_at})."""
    from django.http import JsonResponse
    from django.utils import timezone
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
        'desc': 'Embed an interactive demo + writeup explaining what it shows.',
        'title': 'Demo: <name>',
        'body': (
            '# Demo: <name>\n\n'
            'One sentence on what the demo shows.\n\n'
            '<aside class="callout"><strong>Try it →</strong> Move the slider and watch the boundary change.</aside>\n\n'
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
}


def blog_new(request):
    """Create a new draft post and redirect to its editor.
    GET without ?template=: show the template-picker page.
    GET with ?template=<key>: create a draft from that template.
    """
    from django.shortcuts import redirect
    from django.utils.text import slugify
    from datetime import date as date_cls
    if not _can_edit(request):
        return redirect('/admin/login/?next=/blog/new/')

    template_key = request.GET.get('template')
    if template_key not in _POST_TEMPLATES:
        return render(request, 'portfolio/blog_new.html', {
            'templates': [(k, v) for k, v in _POST_TEMPLATES.items()],
        })

    tmpl = _POST_TEMPLATES[template_key]
    from portfolio.models import Post
    base_title = request.GET.get('title') or tmpl['title']
    base_slug = slugify(base_title) or 'untitled-draft'
    slug = base_slug
    n = 1
    while Post.objects.filter(slug=slug).exists():
        n += 1
        slug = f'{base_slug}-{n}'
    p = Post.objects.create(
        slug=slug,
        title=base_title,
        body=tmpl['body'],
        date=date_cls.today(),
        draft=True,
        maturity=tmpl['maturity'],
        is_explainer=tmpl['is_explainer'],
        is_paper_companion=tmpl['is_paper_companion'],
    )
    return redirect('blog_edit', slug=p.slug)


def blog_preview(request):
    """Server-renders a markdown payload to HTML for the live-preview
    pane in the editor. POST {body, is_explainer} -> {html, toc}."""
    from django.http import JsonResponse
    if not _can_edit(request):
        return JsonResponse({'error': 'unauthorized'}, status=403)
    from portfolio.blog import render_markdown
    body = request.POST.get('body', '')
    is_explainer = request.POST.get('is_explainer') == 'true'
    html, toc = render_markdown(body, is_explainer=is_explainer)
    return JsonResponse({'html': html, 'toc': toc})


def _fetch_webmentions(target_url, limit=25):
    """Fetch incoming webmentions for a URL from the webmention.io public
    API. Cached locally. Returns a list of dicts:
    {author, content, url, type, published}. Empty list on any failure.

    Gated on settings.WEBMENTIONS_ENABLED (env: WEBMENTIONS_ENABLED=1).
    Until the domain is registered at webmention.io, keep this disabled —
    every blog-post view would otherwise eat a 1-2s external round-trip
    waiting for a 404. Flip the env var after registering.

    When enabled: 1s timeout (fast-fail on network hiccups), success
    cached 10 min, failure cached 24h (so one slow failure doesn't
    punish every subsequent visitor)."""
    from django.conf import settings as dj_settings
    if not getattr(dj_settings, 'WEBMENTIONS_ENABLED', False):
        return []

    from django.core.cache import cache
    import json
    import urllib.request
    import urllib.parse

    cache_key = f'webmentions:{target_url}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    api = (
        'https://webmention.io/api/mentions.jf2?'
        + urllib.parse.urlencode({'target': target_url, 'per-page': limit, 'sort-dir': 'down'})
    )
    items = []
    ok = False
    try:
        req = urllib.request.Request(api, headers={'User-Agent': 'dennisloevlie.com/webmentions'})
        with urllib.request.urlopen(req, timeout=1) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        for it in data.get('children', []):
            author = it.get('author') or {}
            items.append({
                'type': it.get('wm-property', 'mention'),
                'url': it.get('wm-source') or it.get('url'),
                'author_name': author.get('name', 'Anonymous'),
                'author_url': author.get('url', ''),
                'author_photo': author.get('photo', ''),
                'content': (it.get('content') or {}).get('text', '') if isinstance(it.get('content'), dict) else '',
                'published': it.get('published') or it.get('wm-received'),
            })
        ok = True
    except Exception:
        items = []
    # Hit-path TTL: 10 min. Miss-path TTL: 24h so a flaky/404 response
    # doesn't re-cost us on every visitor for the next 5 minutes.
    cache.set(cache_key, items, 600 if ok else 86400)
    return items


def blog_upload_image(request):
    """Editor image upload. POST a multipart `image` file; returns
    {url, markdown}. The editor inserts the markdown snippet at the
    cursor. Files land in MEDIA_ROOT/blog-images/YYYY/MM/<slug>-<n>.ext.

    Production caveat: ephemeral filesystems (Render free tier) lose
    these on every redeploy. Move MEDIA_ROOT to S3 or equivalent
    before relying on this in prod."""
    from django.conf import settings as dj_settings
    from django.core.files.storage import FileSystemStorage
    from django.http import JsonResponse
    from django.utils.text import slugify
    from datetime import date as date_cls
    import os, re

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
        location=os.path.join(dj_settings.MEDIA_ROOT, subdir),
        base_url=dj_settings.MEDIA_URL + subdir + '/',
    )
    saved_name = storage.save(fname, f)  # auto-suffixes on collisions
    url = storage.url(saved_name)
    alt = request.POST.get('alt', '') or safe_base.replace('-', ' ')
    return JsonResponse({
        'url': url,
        'markdown': f'![{alt}]({url})',
        'filename': saved_name,
    })


def blog_post(request, slug):
    is_staff = request.user.is_authenticated and request.user.is_staff
    post = get_post(slug, include_drafts=is_staff)
    if post is None:
        # Try again including drafts so anon visitors with the URL of a
        # draft post see a friendly "working on it" stub instead of 404.
        draft_post = get_post(slug, include_drafts=True)
        if draft_post is not None:
            return render(request, 'portfolio/blog_post_wip.html', {'post': draft_post})
        raise Http404("Post not found")
    all_posts = get_all_posts()
    # Get series posts if this post is part of a series
    series_posts = []
    if post.get('series'):
        series_posts = [p for p in all_posts if p.get('series') == post['series']]
        series_posts.sort(key=lambda p: p.get('series_order', 0))
    # Get related posts (others not in the series, max 3)
    related = [p for p in all_posts if p['slug'] != slug and p.get('series') != post.get('series')][:3]

    # Backlinks — "what links here". Other posts whose body contains a link
    # to this post's slug or absolute URL. Cheap O(N) substring scan over
    # body text; for a personal blog this is fine. Falls back to empty if
    # no body field is available.
    needles = (
        f'/blog/{slug}/',
        f'/blog/{slug}',
        f'](blog/{slug}',
        f'](/blog/{slug}',
    )
    backlinks = []
    for p in all_posts:
        if p['slug'] == slug:
            continue
        body = p.get('body') or ''
        if any(n in body for n in needles):
            backlinks.append({'slug': p['slug'], 'title': p['title'], 'date': p.get('date')})

    # Webmentions — public-API fetch (cached). Returns [] cleanly until
    # dennisloevlie.com is registered at webmention.io.
    target_url = request.build_absolute_uri()
    # Strip any query string (?stack=...) so all stacked variants share cache.
    if '?' in target_url:
        target_url = target_url.split('?', 1)[0]
    webmentions = _fetch_webmentions(target_url)

    return render(request, 'portfolio/blog_post.html', {
        'post': post,
        'series_posts': series_posts,
        'related_posts': related,
        'backlinks': backlinks,
        'webmentions': webmentions,
    })


def publications(request):
    return render(request, 'portfolio/publications.html')


def projects(request):
    return render(request, 'portfolio/projects.html')


def demos(request):
    """/demos/ listing. Public sees published demos; staff also see
    drafts (with a Draft pill on the card)."""
    is_staff = request.user.is_authenticated and request.user.is_staff
    visible = [d for d in DEMOS if is_staff or not d.get('draft')]
    demos_sorted = sorted(visible, key=lambda d: d['date'], reverse=True)
    return render(request, 'portfolio/demos.html', {
        'demos': demos_sorted,
        'is_staff': is_staff,
    })


def demo_detail(request, slug):
    """Standalone permalink page for a single demo. Includes the same
    `embed_<slug>.html` partial used on /demos/ but in a richer page
    chrome (own OG meta, reading-time chrome, related-post link).

    Drafts: anon visitors see a "Working on it" stub (same chrome as
    the blog WIP stub) so the URL stays alive; staff see the full
    interactive demo for preview."""
    demo = next((d for d in DEMOS if d['slug'] == slug), None)
    if demo is None:
        raise Http404("Demo not found")
    is_staff = request.user.is_authenticated and request.user.is_staff
    if demo.get('draft') and not is_staff:
        return render(request, 'portfolio/demo_detail_wip.html', {'demo': demo})
    # Find a related blog post (companion essay) by matching slug
    from portfolio.blog import get_post
    companion = get_post(slug, include_drafts=is_staff)
    return render(request, 'portfolio/demo_detail.html', {
        'demo': demo,
        'companion': companion,
        'is_staff': is_staff,
    })


def tag_index(request):
    """/tags/ — alphabetical list of all tags with post counts.
    Cheap O(N×T) over posts; for a personal blog this is fine."""
    posts = get_all_posts()
    counts = {}
    for p in posts:
        for t in p.get('tags', []):
            counts[t] = counts.get(t, 0) + 1
    tags = sorted(counts.items(), key=lambda x: (-x[1], x[0].lower()))
    return render(request, 'portfolio/tag_index.html', {
        'tags': tags,
        'total_posts': len(posts),
    })


def tag_detail(request, slug):
    """/tags/<slug>/ — posts with this tag. Slug match is exact (we
    don't slugify the tag — taggit stores the human form)."""
    posts = get_all_posts()
    matched = [p for p in posts if any(t.lower() == slug.lower() for t in p.get('tags', []))]
    if not matched:
        # Try fuzzy matching: hyphenated → spaces
        candidates = []
        for p in posts:
            for t in p.get('tags', []):
                if t.lower().replace(' ', '-').replace('_', '-') == slug.lower():
                    if p not in candidates:
                        candidates.append(p)
        matched = candidates
    if not matched:
        raise Http404(f'No posts tagged "{slug}"')
    # Resolve canonical tag display label from first match
    tag_label = next((t for p in matched for t in p.get('tags', [])
                      if t.lower().replace(' ', '-') == slug.lower()), slug)
    return render(request, 'portfolio/tag_detail.html', {
        'tag': tag_label,
        'tag_slug': slug,
        'posts': matched,
        'count': len(matched),
    })


def garden(request):
    """/garden/ — posts filtered by maturity badge. Digital-garden
    convention: Seedlings (half-formed) and Budding (being developed)
    up top, Evergreens (settled) below. Unmarked posts excluded."""
    posts = [p for p in get_all_posts() if p.get('maturity')]
    order = {'seedling': 0, 'budding': 1, 'evergreen': 2}
    buckets = {'seedling': [], 'budding': [], 'evergreen': []}
    for p in posts:
        m = p.get('maturity', '')
        if m in buckets:
            buckets[m].append(p)
    return render(request, 'portfolio/garden.html', {
        'buckets': [(k, buckets[k]) for k in ['seedling', 'budding', 'evergreen']],
        'total': len(posts),
    })


def now(request):
    """/now/ — Derek Sivers convention. What I'm doing in life and work
    right now. Updated quarterly. Strong taste signal for FAANG/ELLIS
    reviewers. The content is in NOW_PAGE in data.py so it's editable
    without touching templates."""
    from portfolio.data import NOW_PAGE
    return render(request, 'portfolio/now.html', {'now': NOW_PAGE})


def cv_page(request):
    """/cv/ — HTML page embedding the live PDF inline plus download
    + view-source links. The PDF lives at loevlie.github.io/cv/ and
    is rebuilt weekly by a launchd job. We render it via <object>
    with a download fallback so it works even if the upstream is
    momentarily unreachable."""
    upstream = 'https://loevlie.github.io/cv/loevlie-cv-latest.pdf'
    return render(request, 'portfolio/cv.html', {
        'upstream_url': upstream,
        'download_url': '/cv.pdf',
        'source_repo': 'https://github.com/loevlie/cv',
    })


def download_cv(request):
    """Proxy the latest CV from loevlie.github.io with Content-Disposition: attachment.
    Browsers ignore the `download` attribute on cross-origin links, so we have to
    fetch server-side and re-serve same-origin to actually trigger a download.
    Falls back to a redirect if the upstream is unreachable."""
    import urllib.request
    import urllib.error
    from django.http import HttpResponse, HttpResponseRedirect
    upstream = 'https://loevlie.github.io/cv/loevlie-cv-latest.pdf'
    try:
        req = urllib.request.Request(upstream, headers={'User-Agent': 'PhD-Website-CV-Proxy'})
        with urllib.request.urlopen(req, timeout=10) as r:
            pdf = r.read()
    except (urllib.error.URLError, TimeoutError):
        return HttpResponseRedirect(upstream)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="Dennis-Loevlie-CV.pdf"'
    response['Cache-Control'] = 'public, max-age=3600'  # 1 h client cache; upstream refreshes weekly
    return response


def presentation(request, slug):
    from pathlib import Path
    filepath = Path(__file__).parent.parent / 'presentations' / f'{slug}.html'
    if not filepath.exists():
        raise Http404("Presentation not found")
    from django.http import HttpResponse
    return HttpResponse(filepath.read_text(), content_type='text/html')


def google_verify(request):
    from django.http import HttpResponse
    return HttpResponse('google-site-verification: googled2e3ddb216daf4c4.html', content_type='text/html')


def robots_txt(request):
    from django.http import HttpResponse
    from django.template.loader import render_to_string
    content = render_to_string('portfolio/robots.txt', {
        'scheme': request.scheme,
        'host': request.get_host(),
    })
    return HttpResponse(content, content_type='text/plain')
