"""Citation API — backing the explainer-post `<cite data-key=...>` markers.

Three endpoints:

* `GET /blog/citations.json` — public manifest, consumed by
  `portfolio/static/portfolio/js/citations.js` to resolve data-keys
  into popover content. Replaces the static JSON file.
* `POST /blog/citations/create/` — editor-authenticated endpoint:
  accepts a pasted BibTeX entry, parses it, upserts a Citation row,
  returns `{key}` so the editor JS can insert the `<cite>` pill at
  the cursor.
* `GET /blog/citations/search/?q=...` — editor-authenticated search
  for reusing existing citations (typeahead in the cite dialog).

POST is gated behind `_can_edit_any_post`: staff + any user who
has at least one Post.collaborators assignment. Plain signed-up
users without a post assignment can't spam the citations table.
"""
from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import (
    HttpRequest,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    JsonResponse,
)
from django.views.decorators.http import require_GET, require_POST

from portfolio.citations import bibtex_to_fields


def _can_edit_any_post(user) -> bool:
    """Staff always; otherwise must have at least one collaborator
    assignment. Matches the `smart_paste` / `check_word` gating."""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return user.edit_posts.exists()


@require_GET
def manifest(request: HttpRequest) -> JsonResponse:
    """Return the citation manifest in the legacy citations.js shape:
    `{key: {title, authors, venue, url, bibtex}, ...}`. Cached for 5
    minutes; on-save invalidation handled by a post_save signal."""
    from django.core.cache import cache
    from portfolio.models import Citation

    cached = cache.get('citations:manifest')
    if cached is not None:
        return JsonResponse(cached, json_dumps_params={'ensure_ascii': False})

    data = {c.key: c.to_manifest_entry() for c in Citation.objects.all()}
    cache.set('citations:manifest', data, 300)
    return JsonResponse(data, json_dumps_params={'ensure_ascii': False})


@login_required
@require_POST
def create_from_bibtex(request: HttpRequest) -> JsonResponse:
    """Parse a pasted BibTeX entry, upsert a Citation row, return
    `{key, created, ...}`. Body: JSON `{bibtex: "..."}`."""
    if not _can_edit_any_post(request.user):
        return HttpResponseForbidden('Citation create requires editor access.')

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON body.')

    bibtex = (payload.get('bibtex') or '').strip()
    if not bibtex:
        return HttpResponseBadRequest('Missing `bibtex` field.')

    try:
        fields = bibtex_to_fields(bibtex)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    from portfolio.models import Citation
    # Dedupe priority: existing key (same string) > arxiv_id > doi.
    obj = None
    if fields.get('key'):
        obj = Citation.objects.filter(key=fields['key']).first()
    if obj is None and fields.get('arxiv_id'):
        obj = Citation.objects.filter(arxiv_id=fields['arxiv_id']).first()
    if obj is None and fields.get('doi'):
        obj = Citation.objects.filter(doi=fields['doi']).first()

    created = False
    if obj is None:
        obj = Citation.objects.create(
            created_by=request.user if request.user.is_authenticated else None,
            **{k: v for k, v in fields.items() if v},
        )
        created = True
    else:
        # Update any fields that were empty on the existing row —
        # later pastes can enrich an earlier one without overwriting
        # hand-curated values.
        changed = False
        for k, v in fields.items():
            if v and not getattr(obj, k, None):
                setattr(obj, k, v)
                changed = True
        if changed:
            obj.save()

    return JsonResponse({
        'key': obj.key,
        'created': created,
        'title': obj.title,
        'authors': obj.authors,
    })


@login_required
@require_GET
def search(request: HttpRequest) -> JsonResponse:
    """Typeahead search over existing citations by key, title, or
    authors. Used by the cite dialog's "reuse existing" list."""
    if not _can_edit_any_post(request.user):
        return HttpResponseForbidden('Citation search requires editor access.')

    q = (request.GET.get('q') or '').strip()
    from django.db.models import Q
    from portfolio.models import Citation
    qs = Citation.objects.all()
    if q:
        qs = qs.filter(Q(key__icontains=q) | Q(title__icontains=q) | Q(authors__icontains=q))
    qs = qs[:15]
    return JsonResponse({
        'results': [{
            'key': c.key, 'title': c.title, 'authors': c.authors,
            'venue': c.venue, 'year': c.year,
        } for c in qs],
    })
