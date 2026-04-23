"""Small public diagnostic surface for debugging deploy / persistence
weirdness without needing DevTools or admin access.

    GET /__dl/post/<slug>/          → JSON of a post's DB state
    GET /__dl/version/              → current commit + start time

These are intentionally minimal (no secrets, no bodies past a short
head/tail) so they can be hit anonymously via curl during debugging.
Returns 404 when the post doesn't exist, so scraping for existence is
bounded by the public sitemap anyway.
"""
import hashlib
import os
import time

from django.http import JsonResponse, Http404


_PROCESS_START = int(time.time())


def post_state(request, slug):
    """Return a compact JSON snapshot of a post's current DB state so
    an author can verify "is my save actually there?" via a plain
    `curl`."""
    from portfolio.models import Post
    try:
        p = Post.objects.only(
            'slug', 'title', 'body', 'rendered_html',
            'modified_at', 'rendered_at', 'draft',
        ).get(slug=slug)
    except Post.DoesNotExist:
        raise Http404()
    body = p.body or ''
    rendered = p.rendered_html or ''
    data = {
        'slug': p.slug,
        'title': p.title,
        'draft': p.draft,
        'modified_at': p.modified_at.isoformat() if p.modified_at else None,
        'rendered_at': p.rendered_at.isoformat() if p.rendered_at else None,
        'body_len': len(body),
        'rendered_len': len(rendered),
        'body_sha1': hashlib.sha1(body.encode('utf-8', 'replace')).hexdigest()[:12],
        'body_head': body[:120],
        'body_tail': body[-120:],
        # Easy presence check for anything the author just typed.
        'body_contains': request.GET.get('contains') and (
            request.GET.get('contains') in body
        ),
    }
    resp = JsonResponse(data)
    resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp


def version(request):
    """Confirm which git commit is actually serving a request."""
    return JsonResponse({
        'commit': os.environ.get('RENDER_GIT_COMMIT', '(unset)')[:12],
        'branch': os.environ.get('RENDER_GIT_BRANCH', '(unset)'),
        'worker_started_at': _PROCESS_START,
        'uptime_s': int(time.time()) - _PROCESS_START,
    })
