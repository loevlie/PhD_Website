from django.shortcuts import render
from django.http import Http404

from portfolio.data import RECIPES, DEMOS
from portfolio.blog import get_all_posts, get_post


def index(request):
    return render(request, 'portfolio/index.html')


def recipes(request):
    return render(request, 'portfolio/recipes.html')


def recipe_detail(request, slug):
    recipe = next((r for r in RECIPES if r['slug'] == slug), None)
    if recipe is None:
        raise Http404("Recipe not found")
    return render(request, 'portfolio/recipe_detail.html', {'recipe': recipe})


def blog(request):
    posts = get_all_posts()
    tag = request.GET.get('tag')
    query = request.GET.get('q', '').strip()

    if tag:
        posts = [p for p in posts if tag in p['tags']]
    if query:
        q_lower = query.lower()
        posts = [p for p in posts if
                 q_lower in p['title'].lower() or
                 q_lower in p['excerpt'].lower() or
                 any(q_lower in t.lower() for t in p['tags'])]

    return render(request, 'portfolio/blog.html', {
        'posts': posts,
        'active_tag': tag,
        'search_query': query,
    })


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
        for field in ('title', 'excerpt', 'body'):
            v = request.POST.get(field)
            if v is not None:
                setattr(post, field, v)
        post.is_explainer = request.POST.get('is_explainer') == 'on'
        post.draft = request.POST.get('draft') == 'on'
        post.save()
        if request.POST.get('action') == 'view':
            return redirect('blog_post', slug=post.slug)
        return redirect('blog_edit', slug=post.slug)

    return render(request, 'portfolio/blog_edit.html', {'post': post, 'is_new': False})


def blog_new(request):
    """Create a new draft post and redirect to its editor."""
    from django.shortcuts import redirect
    from django.utils.text import slugify
    from datetime import date as date_cls
    if not _can_edit(request):
        return redirect('/admin/login/?next=/blog/new/')

    from portfolio.models import Post
    base_slug = slugify(request.GET.get('title', 'untitled-draft'))
    slug = base_slug
    n = 1
    while Post.objects.filter(slug=slug).exists():
        n += 1
        slug = f'{base_slug}-{n}'
    p = Post.objects.create(
        slug=slug,
        title='Untitled draft',
        body='# Untitled\n\nStart writing…',
        date=date_cls.today(),
        draft=True,
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


def _fetch_webmentions(target_url, limit=25, cache_seconds=300):
    """Fetch incoming webmentions for a URL from the webmention.io public
    API. Cached locally for `cache_seconds`. Returns a list of dicts:
    {author, content, url, type, published}. Empty list on any failure.

    No API token required for the public read endpoint — webmention.io
    serves the JF2 feed for any registered domain at:
       /api/mentions.jf2?target=<url>

    Until the user registers dennisloevlie.com at webmention.io, this
    will return [] cleanly. After registration it just starts working."""
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
    try:
        req = urllib.request.Request(api, headers={'User-Agent': 'dennisloevlie.com/webmentions'})
        with urllib.request.urlopen(req, timeout=4) as resp:
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
    except Exception:
        items = []
    cache.set(cache_key, items, cache_seconds)
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
    post = get_post(slug)
    if post is None:
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
    # Newest first; date is an ISO string so a lexicographic sort is fine.
    demos_sorted = sorted(DEMOS, key=lambda d: d['date'], reverse=True)
    return render(request, 'portfolio/demos.html', {'demos': demos_sorted})


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
