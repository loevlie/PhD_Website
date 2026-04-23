"""Public blog surface.

Routes served here:

    /blog/                    blog (essay listing, image grid | ?view=list flips to Postcard)
    /blog/exp/                blog_experiments_index
    /blog/exp/<name>/         blog_experiment
    /blog/<slug>/             blog_post
    /notebook/                notebook (lab notes)
    /reading/                 reading (curated papers)

Listing filtering lives in `_blog_render`; kept private since it's only
meaningful inside this module.
"""
from django.http import Http404
from django.shortcuts import render
from django.template.loader import select_template

from portfolio.blog import get_all_posts, get_post
from .webmentions import fetch as fetch_webmentions


# ─── Shared listing renderer ──────────────────────────────────────────

def _blog_render(request, *, template, experiment=None, kind=None, view='', extra=None):
    is_staff = request.user.is_authenticated and request.user.is_staff
    # Staff see every draft. Non-staff collaborators see drafts on
    # posts they've been assigned to (so the Frozen Forecaster draft
    # shows up in /blog/ for the author's guest contributor). Everyone
    # else gets published-only.
    collaborator_draft_slugs = set()
    if request.user.is_authenticated and not is_staff:
        from portfolio.models import Post as _Post
        collaborator_draft_slugs = set(
            _Post.objects.filter(
                collaborators=request.user, draft=True,
            ).values_list('slug', flat=True)
        )
    posts = get_all_posts(include_drafts=is_staff or bool(collaborator_draft_slugs))
    if not is_staff and collaborator_draft_slugs:
        # include_drafts=True above pulled every draft; keep only the
        # ones this user has edit access to + the published rest.
        posts = [p for p in posts
                 if not p.get('draft') or p.get('slug') in collaborator_draft_slugs]
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


# ─── /blog/ + variants ────────────────────────────────────────────────

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
    bar (text from content.CURRENTLY)."""
    from portfolio.content.hero import CURRENTLY
    return _blog_render(
        request, template='portfolio/notebook.html',
        kind='lab_note', extra={'currently': CURRENTLY},
    )


# ─── /reading/ ────────────────────────────────────────────────────────

def reading(request):
    """Curated reading list at /reading/. Pulls from the Reading model
    (admin-editable). Hides archived entries; this_week sits above
    lingering."""
    from portfolio.models import Reading
    is_staff = request.user.is_authenticated and request.user.is_staff
    entries = Reading.objects.exclude(status='archived').order_by('order', '-created_at')
    this_week = [r for r in entries if r.status == 'this_week']
    lingering = [r for r in entries if r.status == 'lingering']
    return render(request, 'portfolio/reading.html', {
        'this_week': this_week,
        'lingering': lingering,
        'total': len(this_week) + len(lingering),
        'is_staff': is_staff,
    })


# ─── Experiment variants of the /blog/ landing ────────────────────────

def blog_experiment(request, name):
    """Local-preview variants of the blog landing page. Each experiment
    template at portfolio/blog_exp_<name>.html lets us A/B-feel a
    redesign before touching the canonical /blog/. Routed at
    /blog/exp/<name>/. Anyone can visit (we want to share the link
    around for feedback) but they're unindexed via robots noindex."""
    template = f'portfolio/blog_exp_{name}.html'
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


# ─── /blog/map/ force-directed post graph ──────────────────────────────

def blog_map(request):
    """A force-directed graph of all published posts, linked where one's
    body references another's slug. Obsidian-vault feel. Nodes sized by
    incoming-link count, colored by maturity/kind."""
    import json
    posts = get_all_posts()
    slugs = {p['slug']: i for i, p in enumerate(posts)}
    nodes = [{
        'id': p['slug'],
        'title': p['title'],
        'date': p.get('date').isoformat() if p.get('date') else '',
        'kind': p.get('kind') or 'essay',
        'maturity': p.get('maturity') or '',
        'draft': bool(p.get('draft')),
    } for p in posts]
    edges = []
    for p in posts:
        body = p.get('body') or ''
        for other_slug in slugs:
            if other_slug == p['slug']:
                continue
            if (f'/blog/{other_slug}/' in body
                    or f'/blog/{other_slug})' in body):
                edges.append({'source': p['slug'], 'target': other_slug})
    in_deg = {n['id']: 0 for n in nodes}
    for e in edges:
        in_deg[e['target']] = in_deg.get(e['target'], 0) + 1
    for n in nodes:
        n['in_degree'] = in_deg.get(n['id'], 0)
    return render(request, 'portfolio/blog_map.html', {
        'graph_json': json.dumps({'nodes': nodes, 'edges': edges}),
        'post_count': len(nodes),
        'edge_count': len(edges),
    })


# ─── Single post ──────────────────────────────────────────────────────

def blog_post(request, slug):
    is_staff = request.user.is_authenticated and request.user.is_staff
    # Collaborators assigned to THIS post see the full page even when
    # the post is still a draft — otherwise the "edit" link in their
    # /accounts/profile/ lands them on the WIP stub.
    viewer_is_collab = False
    if request.user.is_authenticated and not is_staff:
        from portfolio.models import Post as _Post
        viewer_is_collab = _Post.objects.filter(
            slug=slug, collaborators=request.user,
        ).exists()
    post = get_post(slug, include_drafts=is_staff or viewer_is_collab)
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
    webmentions = fetch_webmentions(target_url)

    # BibTeX citation shown at the bottom of the post. Inlined in context
    # so the template can render it without a second round-trip to
    # /blog/<slug>/cite.bib — that endpoint still exists for readers
    # who want the raw file.
    from portfolio.views.authoring import _citation_id, bibtex_author_field
    cite_id = _citation_id(post)
    date_obj = post.get('date')
    year = date_obj.year if hasattr(date_obj, 'year') else ''
    month = date_obj.strftime('%b').lower() if hasattr(date_obj, 'strftime') else ''
    author = bibtex_author_field(post)
    # Use the canonical URL (strip request-scheme quirks) so the cited
    # URL matches what's in production.
    canonical_url = f'{request.scheme}://{request.get_host()}/blog/{slug}/'
    bibtex = (
        f'@misc{{{cite_id},\n'
        f'  author       = {{{author}}},\n'
        f'  title        = {{{{{post["title"]}}}}},\n'
        f'  year         = {{{year}}},\n'
        + (f'  month        = {month},\n' if month else '')
        + f'  howpublished = {{Blog post}},\n'
        f'  url          = {{{canonical_url}}}\n'
        '}'
    )

    # Show the "edit" pill in the reader chrome for staff OR a
    # collaborator on THIS post. Cheap M2M existence check; anon
    # visitors hit neither branch.
    can_edit_this_post = False
    if request.user.is_authenticated:
        if request.user.is_staff:
            can_edit_this_post = True
        else:
            try:
                from portfolio.models import Post as _Post
                can_edit_this_post = _Post.objects.filter(
                    slug=slug, collaborators=request.user,
                ).exists()
            except Exception:
                can_edit_this_post = False

    # Diagnostic header for editable viewers — lets the author check
    # "did my save actually land on the backing DB?" without DevTools
    # gymnastics. Anon readers never see this header.
    save_state = {}
    if can_edit_this_post:
        from portfolio.models import Post as _Post
        try:
            p = _Post.objects.only('modified_at', 'rendered_at', 'body', 'rendered_html').get(slug=slug)
            save_state = {
                'modified_at': p.modified_at.isoformat() if p.modified_at else None,
                'rendered_at': p.rendered_at.isoformat() if p.rendered_at else None,
                'body_len': len(p.body or ''),
                'rendered_len': len(p.rendered_html or ''),
            }
        except _Post.DoesNotExist:
            pass

    resp = render(request, 'portfolio/blog_post.html', {
        'post': post,
        'series_posts': series_posts,
        'related_posts': related,
        'backlinks': backlinks,
        'webmentions': webmentions,
        'bibtex': bibtex,
        'cite_id': cite_id,
        'can_edit_this_post': can_edit_this_post,
        'save_state': save_state,
    })
    # Authors + collaborators must never see a stale cached response
    # for a post they can edit — defeats the "I just saved and the
    # live page doesn't show it" trap. Anonymous readers keep the
    # default cacheable response so Cloudflare / CDNs can do their job.
    if can_edit_this_post:
        resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp
