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
    return render(request, 'portfolio/blog_post.html', {
        'post': post,
        'series_posts': series_posts,
        'related_posts': related,
    })


def publications(request):
    return render(request, 'portfolio/publications.html')


def projects(request):
    return render(request, 'portfolio/projects.html')


def demos(request):
    # Newest first; date is an ISO string so a lexicographic sort is fine.
    demos_sorted = sorted(DEMOS, key=lambda d: d['date'], reverse=True)
    return render(request, 'portfolio/demos.html', {'demos': demos_sorted})


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
