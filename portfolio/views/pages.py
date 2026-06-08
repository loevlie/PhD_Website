"""Portfolio-side page views (everything that is NOT the blog surface).

Routes served from here (see portfolio/urls.py):

    /                         index
    /recipes/                 recipes listing
    /recipes/<slug>/          recipe_detail
    /projects/                projects
    /publications/            publications
    /demos/                   demos listing
    /demos/<slug>/            demo_detail
    /now/                     now
    /garden/                  garden
    /tags/                    tag_index
    /tags/<slug>/             tag_detail
    /cv/                      cv_page (embedded PDF + download links)
    /cv.pdf                   download_cv (server-side proxy for download)
    /presentations/<slug>/    presentation (static HTML proxy)
    /robots.txt               robots_txt
    /googled2e3ddb…html       google_verify
"""
from pathlib import Path

from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string

from portfolio.data import RECIPES, DEMOS
from portfolio.blog import get_all_posts, get_post


# ─── Homepage ────────────────────────────────────────────────────────

def index(request):
    # `featured_demo` (None when Frozen Forecaster is a draft) is provided
    # by portfolio.context_processors.portfolio_data so all templates —
    # the homepage section, Cmd+K palette, and nav dropdown — hide together.
    return render(request, 'portfolio/index.html')


# ─── Recipes ─────────────────────────────────────────────────────────

def recipes(request):
    return render(request, 'portfolio/recipes.html')


def recipe_detail(request, slug):
    recipe = next((r for r in RECIPES if r['slug'] == slug), None)
    if recipe is None:
        raise Http404("Recipe not found")
    return render(request, 'portfolio/recipe_detail.html', {'recipe': recipe})


# ─── Publications / Projects ─────────────────────────────────────────

def publications(request):
    return render(request, 'portfolio/publications.html')


def projects(request):
    return render(request, 'portfolio/projects.html')


# ─── Demos ────────────────────────────────────────────────────────────

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
    companion = get_post(slug, include_drafts=is_staff)
    return render(request, 'portfolio/demo_detail.html', {
        'demo': demo,
        'companion': companion,
        'is_staff': is_staff,
    })


# ─── Tags ─────────────────────────────────────────────────────────────

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


# ─── /garden/ (posts by maturity) ─────────────────────────────────────

def garden(request):
    """/garden/ — posts filtered by maturity badge. Digital-garden
    convention: Seedlings (half-formed) and Budding (being developed)
    up top, Evergreens (settled) below. Unmarked posts excluded."""
    posts = [p for p in get_all_posts() if p.get('maturity')]
    buckets = {'seedling': [], 'budding': [], 'evergreen': []}
    for p in posts:
        m = p.get('maturity', '')
        if m in buckets:
            buckets[m].append(p)
    return render(request, 'portfolio/garden.html', {
        'buckets': [(k, buckets[k]) for k in ['seedling', 'budding', 'evergreen']],
        'total': len(posts),
    })


# ─── /now/ ────────────────────────────────────────────────────────────

def now(request):
    """/now/ — Derek Sivers convention. What I'm doing in life and work
    right now. Updated quarterly. Strong taste signal for FAANG/ELLIS
    reviewers. Content is DB-backed (NowPage / NowSection), with a
    data.py fallback when empty — see portfolio.content.live."""
    from portfolio.content import live
    return render(request, 'portfolio/now.html', {'now': live.now_page()})


# ─── Denny's Rules ─────────────────────────────────────────────────────
# `/rules/` — host a rendered view of the DENNYS_RULES.md file that
# lives in the ml-research-template cookiecutter repo. The source is
# the cookiecutter template path (literal `{% if … %}` braces in the
# filename), so we fetch the raw GitHub URL with that exact name and
# pipe it through the existing render_markdown pipeline. Cached for
# 1 hour so we don't hammer GitHub on every visit.

_DENNYS_RULES_RAW_URL = (
    'https://raw.githubusercontent.com/loevlie/ml-research-template/main/template/'
    '%7B%25%20if%20include_dennys_rules%20%25%7D'
    'DENNYS_RULES.md'
    '%7B%25%20endif%20%25%7D'
)


def dennys_rules(request):
    """GET /rules/ — render the canonical Denny's Rules markdown from
    GitHub into a styled page. Cached for an hour; stale-while-error
    on a fetch failure so a GitHub blip doesn't 500."""
    from django.core.cache import cache
    from urllib.request import urlopen, Request
    from urllib.error import URLError
    from portfolio.blog import render_markdown

    cache_key = 'dennys_rules:html_v1'
    cached = cache.get(cache_key)
    if cached:
        html, fetched_at = cached
    else:
        html, fetched_at = None, None
        try:
            req = Request(_DENNYS_RULES_RAW_URL, headers={'User-Agent': 'dennisloevlie.com'})
            with urlopen(req, timeout=8) as r:
                md = r.read().decode('utf-8')
            html, _ = render_markdown(md, is_explainer=False, post_slug='rules')
            from django.utils import timezone as _tz
            fetched_at = _tz.now()
            cache.set(cache_key, (html, fetched_at), 60 * 60)
        except (URLError, TimeoutError, OSError):
            # Network blip — fall back to a stale copy from the long-
            # lived "stale" key (1-day TTL) if we have one.
            stale = cache.get(cache_key + ':stale')
            if stale:
                html, fetched_at = stale
        if html is not None and fetched_at is not None:
            cache.set(cache_key + ':stale', (html, fetched_at), 60 * 60 * 24)

    if html is None:
        # First load with GitHub down + no stale copy. Surface the
        # source so the visitor can read it there instead of seeing a
        # 500 page.
        return render(request, 'portfolio/dennys_rules.html', {
            'rendered_html': None,
            'source_url': 'https://github.com/loevlie/ml-research-template',
            'fetched_at': None,
        })

    return render(request, 'portfolio/dennys_rules.html', {
        'rendered_html': html,
        'source_url': 'https://github.com/loevlie/ml-research-template',
        'fetched_at': fetched_at,
    })


# ─── CV ────────────────────────────────────────────────────────────────

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
    """Proxy the latest CV from loevlie.github.io with
    Content-Disposition: attachment. Browsers ignore the `download`
    attribute on cross-origin links, so we have to fetch server-side
    and re-serve same-origin to actually trigger a download.
    Falls back to a redirect if the upstream is unreachable."""
    import urllib.request
    import urllib.error
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


# ─── Static passthroughs + tooling endpoints ──────────────────────────

def presentation(request, slug):
    filepath = Path(__file__).parent.parent.parent / 'presentations' / f'{slug}.html'
    if not filepath.exists():
        raise Http404("Presentation not found")
    return HttpResponse(filepath.read_text(), content_type='text/html')


def google_verify(request):
    return HttpResponse('google-site-verification: googled2e3ddb216daf4c4.html', content_type='text/html')


def robots_txt(request):
    content = render_to_string('portfolio/robots.txt', {
        'scheme': request.scheme,
        'host': request.get_host(),
    })
    return HttpResponse(content, content_type='text/plain')
