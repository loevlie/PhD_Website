"""Staff-only in-browser post editor.

Routes served here:

    /blog/new/                 blog_new       — template picker + draft create
    /blog/<slug>/edit/         blog_edit      — markdown / live-preview editor
    /blog/<slug>/autosave/     blog_autosave  — background JSON save
    /blog/preview/             blog_preview   — render markdown to HTML for the preview pane
    /blog/upload-image/        blog_upload_image

Auth: every endpoint requires request.user.is_staff (see `_can_edit`).
"""
from collections import OrderedDict
from datetime import date as date_cls
import hashlib
import os
import re
import time

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.text import slugify

from portfolio.data import DEMOS


# ─── Auth helper ─────────────────────────────────────────────────────
# Shared with the editor_assist endpoints so post-collaborator checks
# stay in exactly one place. Pass `post=<Post>` for slug-scoped views
# (editor, autosave, spellcheck, assist); omit it for slug-less helpers
# (preview, upload_image, smart_paste) — those fall back to "user has
# ANY collaborator post" which is fine because the damage a stray call
# can do is bounded by other slug-scoped views.

from portfolio.views.editor_assist import (
    _can_edit,
    _can_create_post,
    _staff_redirect,
)


# ─── POST-field → Post attribute adapter ─────────────────────────────

def _apply_post_fields(post, data, files=None):
    """Apply editor POST fields onto a Post instance. Shared by full-save
    and autosave so behavior stays identical. `files` (request.FILES)
    is optional — autosave never sends files, only the explicit Save
    carries the multipart payload with a fresh cover image."""
    for field in ('title', 'excerpt', 'body', 'slug', 'series', 'image', 'medium_url'):
        v = data.get(field)
        if v is not None:
            setattr(post, field, v)
    # Cover image upload — arrives in request.FILES on explicit Save.
    if files is not None:
        uploaded = files.get('cover_image')
        if uploaded is not None:
            post.cover_image = uploaded
    # Explicit clear — an empty `cover_image_clear` checkbox on the
    # editor form removes the existing upload without re-uploading.
    if data.get('cover_image_clear') == '1':
        if post.cover_image:
            post.cover_image.delete(save=False)
        post.cover_image = None
    # Notation glossary — JSON-encoded list of {term, definition, kind}
    # entries. Silently ignore malformed input; the editor's JS always
    # submits valid JSON, and the admin still accepts direct JSONField
    # edits.
    if 'notation' in data:
        import json as _json
        try:
            val = _json.loads(data.get('notation') or '[]')
            if isinstance(val, list):
                # Normalize shape; drop blank rows.
                cleaned = []
                for e in val:
                    if not isinstance(e, dict):
                        continue
                    term = (e.get('term') or '').strip()
                    defn = (e.get('definition') or '').strip()
                    if not term or not defn:
                        continue
                    kind = e.get('kind', 'text')
                    if kind not in ('text', 'latex'):
                        kind = 'text'
                    cleaned.append({'term': term, 'definition': defn, 'kind': kind})
                post.notation = cleaned
        except (ValueError, TypeError):
            pass
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

    Concurrency model: click-through lock. When user A has the editor
    open, user B clicking "edit" on the same post lands on a read-only
    "A is editing now" screen with a Take-over button. The lock NEVER
    gates a POST save — once A gets past the lock and into the editor,
    every Save they click commits unconditionally (last write wins).
    This keeps two users from stepping on each other's fresh work while
    making the "why isn't my Save landing?" failure mode impossible.

    Auth: staff, or a user listed in `post.collaborators`.
    """
    from portfolio.models import Post
    try:
        post = Post.objects.get(slug=slug)
    except Post.DoesNotExist:
        raise Http404("Post not found")

    if not _can_edit(request, post=post):
        return redirect(f'/accounts/login/?next=/blog/{slug}/edit/')

    # Per-tab token so the same user in two tabs counts as two editors
    # (split-window scenario). Session-scoped so it persists across
    # reloads within a tab.
    tab_token = request.session.get('editor_tab_token')
    if not tab_token:
        import secrets
        tab_token = secrets.token_urlsafe(10)
        request.session['editor_tab_token'] = tab_token

    # Lock check applies to GET only — POST saves always proceed.
    if request.method == 'GET':
        holder = _read_edit_lock(slug)
        mine = holder and _lock_is_ours(holder, request, tab_token)
        taking_over = request.GET.get('takeover') == '1'
        if holder and not mine and not taking_over:
            return render(request, 'portfolio/blog_edit_locked.html', {
                'post': post,
                'lock': holder,
                'age_s': max(0, int(timezone.now().timestamp() - holder['acquired_at'])),
            })
        # Either free, ours, or taking over — claim it and render.
        _write_edit_lock(slug, request, tab_token, fresh=not mine)

    if request.method == 'POST':
        _apply_post_fields(post, request.POST, files=request.FILES)
        post.save()
        if request.POST.get('tags') is not None:
            tag_str = request.POST.get('tags', '').strip()
            tag_list = [t.strip() for t in tag_str.split(',') if t.strip()] if tag_str else []
            post.tags.set(tag_list)

        # Force-refresh the persisted render. The post_save signal
        # (signals._render_and_persist) silently SKIPS the update if
        # any pyfig errors, which left `rendered_html` frozen at stale
        # content even when the body was saving correctly. An explicit
        # Save click is unambiguous user intent — overwrite the
        # rendered HTML regardless of pyfig status, so the live page
        # reflects what the author just typed. Errors in individual
        # pyfig blocks still render as inline error banners — the
        # surrounding prose still gets through.
        try:
            from portfolio.blog import render_markdown
            from portfolio.models import Post as _Post
            errors_out = []
            html, toc = render_markdown(
                post.body or '',
                is_explainer=getattr(post, 'is_explainer', False),
                post_slug=post.slug,
                errors_out=errors_out,
                notation_entries=getattr(post, 'notation', None) or [],
            )
            _Post.objects.filter(pk=post.pk).update(
                rendered_html=html,
                rendered_toc_html=toc,
                rendered_at=timezone.now(),
            )
        except Exception:
            # Save of `post.body` already committed above; a render
            # failure here shouldn't block the redirect. Live-render
            # fallback in get_post() picks up the slack.
            pass

        # Bust the get_all_posts listing cache so the listing
        # surfaces the fresh post immediately. Idempotent; cheap.
        from portfolio.blog import invalidate_post_cache
        invalidate_post_cache()

        if request.POST.get('action') == 'view':
            # Cache-bust the redirect target so a mid-session browser
            # cache doesn't serve the old rendered version.
            from django.http import HttpResponseRedirect
            from django.urls import reverse
            t = int(timezone.now().timestamp())
            resp = HttpResponseRedirect(f'{reverse("blog_post", args=[post.slug])}?_r={t}')
            # Belt-and-braces: tell the browser NOT to cache either
            # the redirect or the target. If your browser was holding
            # an old copy of /blog/<slug>/, this kills it.
            resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            return resp
        return redirect('blog_edit', slug=post.slug)

    return render(request, 'portfolio/blog_edit.html', _edit_context(
        post, tag_csv=', '.join(t.name for t in post.tags.all()),
    ))


# ── Edit-lock helpers ───────────────────────────────────────────────
# CLICK-THROUGH lock: prevents TWO people from opening the editor on
# the same post at the same time. Does NOT gate POST saves — so once
# you're inside the editor, your Save click always persists, no matter
# what the lock state has drifted to in the meantime.
#
# Lives in Django cache with a 120s TTL, refreshed every 60s by a
# client heartbeat. Closed tabs auto-free the lock within 2 minutes;
# the locked page also has an instant "Take over" button.

_LOCK_TTL_SECONDS = 120


def _lock_key(slug: str) -> str:
    return f'edit_lock:{slug}'


def _read_edit_lock(slug: str):
    from django.core.cache import cache
    return cache.get(_lock_key(slug))


def _lock_is_ours(lock: dict, request, tab_token: str) -> bool:
    """A lock is 'ours' if the same authed user holds it AND it's the
    same browser tab (tab_token). Two tabs of the same user count as
    two sessions — split-window reality."""
    return (
        lock.get('user_id') == request.user.pk
        and lock.get('tab_token') == tab_token
    )


def _write_edit_lock(slug: str, request, tab_token: str, fresh=False):
    """Claim or refresh the lock. `fresh=True` resets `acquired_at` —
    used when the caller is taking over from someone else."""
    from django.core.cache import cache
    now_ts = timezone.now().timestamp()
    existing = cache.get(_lock_key(slug))
    if not fresh and existing and _lock_is_ours(existing, request, tab_token):
        acquired_at = existing.get('acquired_at', now_ts)
    else:
        acquired_at = now_ts
    cache.set(_lock_key(slug), {
        'user_id': request.user.pk,
        'username': request.user.username,
        'tab_token': tab_token,
        'acquired_at': acquired_at,
        'last_heartbeat': now_ts,
    }, timeout=_LOCK_TTL_SECONDS)


def _release_edit_lock(slug: str, request, tab_token: str):
    from django.core.cache import cache
    existing = cache.get(_lock_key(slug))
    if existing and _lock_is_ours(existing, request, tab_token):
        cache.delete(_lock_key(slug))


def blog_edit_heartbeat(request, slug):
    """POST /blog/<slug>/edit/heartbeat/ — client pings every 60s to
    refresh the TTL. Also used to release on unload (body
    {action: 'release'}). Silent no-op if someone else holds the lock."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    from portfolio.models import Post
    try:
        post = Post.objects.get(slug=slug)
    except Post.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'not found'}, status=404)
    if not _can_edit(request, post=post):
        return JsonResponse({'ok': False, 'error': 'unauthorized'}, status=403)
    tab_token = request.session.get('editor_tab_token')
    if not tab_token:
        return JsonResponse({'ok': False, 'error': 'no session token'}, status=400)
    if request.POST.get('action') == 'release':
        _release_edit_lock(slug, request, tab_token)
        return JsonResponse({'ok': True, 'released': True})
    # Refresh the TTL but don't STEAL if someone else is the holder.
    holder = _read_edit_lock(slug)
    if holder and not _lock_is_ours(holder, request, tab_token):
        return JsonResponse({'ok': True, 'note': 'not lock holder — skipping refresh'})
    _write_edit_lock(slug, request, tab_token)
    return JsonResponse({'ok': True})


def _edit_context(post, tag_csv=''):
    """Shared context builder for the editor template."""
    import json as _json
    return {
        'post': post,
        'is_new': False,
        'tag_csv': tag_csv,
        'demos': DEMOS,
        'notation_json': _json.dumps(post.notation or []),
    }


# ─── /blog/<slug>/autosave/ ──────────────────────────────────────────

def blog_autosave(request, slug):
    """Background autosave for the editor. Same field handling as
    blog_edit POST but returns JSON, doesn't redirect, and never fails
    loud (always 200 with {ok, saved_at})."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    from portfolio.models import Post
    try:
        post = Post.objects.get(slug=slug)
    except Post.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'not found'}, status=404)
    if not _can_edit(request, post=post):
        return JsonResponse({'ok': False, 'error': 'unauthorized'}, status=403)

    # Conflict detection intentionally OMITTED on autosave. Autosave
    # fires every ~1.5s and even a single editor tripped false-positive
    # conflicts (microsecond-precision modified_at round-trips,
    # beforeunload beacons with stale base_version, etc.). The explicit
    # Save path still checks (see blog_edit), which is where
    # conflict-detection actually has teeth — autosave is a best-effort
    # safety net, not a place to block work.

    try:
        _apply_post_fields(post, request.POST)
        # Autosave runs every 1.5s. The full render pipeline (pyfig
        # execution, arxiv/github/wiki fetches, demo template renders)
        # takes tens of seconds on a complex post; if we ran it on
        # every autosave we'd block the web worker and queue the
        # user's next preview request behind it. The explicit Save
        # path still renders — published HTML stays in sync there.
        post._skip_render = True
        post.save()
        if request.POST.get('tags') is not None:
            tag_str = request.POST.get('tags', '').strip()
            tag_list = [t.strip() for t in tag_str.split(',') if t.strip()] if tag_str else []
            post.tags.set(tag_list)
        return JsonResponse({
            'ok': True,
            'saved_at': timezone.now().isoformat(),
        })
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
    'deepdive': {
        'label': 'Deep-dive',
        'desc': 'Hero figure + TL;DR callout + chapters. For long explainer posts.',
        'title': 'Deep dive: <topic>',
        'body': (
            '# Deep dive: <topic>\n\n'
            '<aside class="callout"><strong>TL;DR</strong> — one-paragraph version.</aside>\n\n'
            '<blockquote class="pullquote"><p>"A pull-quote from the post itself."</p></blockquote>\n\n'
            '## The setup\n\nTwo or three sentences establishing the problem.\n\n'
            '## What the field does today\n\nPrior art:\n\n<div data-arxiv="2502.05564"></div>\n\n'
            '## The idea\n\n<div data-equation data-explain="theta=model parameters; x=input">\n$$\\hat{y} = f_{\\theta}(x)$$\n</div>\n\n'
            '## What I found\n\nResults, caveats, surprises.\n\n'
            '## Check yourself\n\n<div data-quiz>\nq: Anchor question.\noptions:\n  - First option\n  - Right answer\n  - Wrong answer\nanswer: 1\nexplain: Why.\n</div>\n\n'
            '## Where this goes\n\nNext steps.\n'
        ),
        'maturity': 'budding',
        'is_explainer': True,
        'is_paper_companion': False,
    },
    'livenotes': {
        'label': 'Live notes',
        'desc': 'Gwern-style append-only log that grows over time with dated entries.',
        'title': 'Live notes: <topic>',
        'body': (
            '# Live notes: <topic>\n\n'
            '**Opened:** today. **Status:** thinking. Living document; I add as I learn.\n\n'
            '---\n\n## Why keep a live note\n\nOne paragraph on the scope.\n\n'
            '---\n\n### {{YYYY-MM-DD}} — first pass\n\nToday\'s observation.\n\n'
            '### {{YYYY-MM-DD}} — second pass\n\nFollow-up thought.\n'
        ),
        'maturity': 'seedling',
        'is_explainer': False,
        'is_paper_companion': False,
    },
    'thread': {
        'label': 'Thread',
        'desc': 'Tweet-thread-style atomic paragraphs. Cross-posts cleanly.',
        'title': 'Thread: <topic>',
        'body': (
            '# Thread: <topic>\n\n'
            '**1/** Single-sentence hook.\n\n'
            '**2/** Second beat — the non-obvious move.\n\n'
            '**3/** Supporting fact:\n\n<div data-arxiv="2502.05564"></div>\n\n'
            '**4/** What this means for the reader.\n\n'
            '**5/** Caveat + link to the long version.\n'
        ),
        'maturity': 'seedling',
        'is_explainer': False,
        'is_paper_companion': False,
    },
    'arxiv': {
        'label': 'arXiv companion',
        'desc': 'Paper-companion with metadata pre-filled. Append ?arxiv=<id> to auto-fetch.',
        'title': 'Paper companion: <title>',
        'body': (
            '# Paper companion: <title>\n\n'
            '<div data-arxiv="<id>"></div>\n\n'
            '## The problem\n\nWhy this paper exists.\n\n'
            '## What we did\n\nOne-paragraph method.\n\n'
            '## What we found\n\nThe result. Caveats.\n\n'
            '## Where this goes\n\nOpen questions.\n'
        ),
        'maturity': 'evergreen',
        'is_explainer': False,
        'is_paper_companion': True,
    },
}


def blog_new(request):
    """Create a new draft post and redirect to its editor.
    GET without ?template=: show the template-picker page.
    GET with ?template=<key>: create a draft from that template.

    Access: staff by default. Non-staff users need the explicit
    `portfolio.add_post` permission (granted in /admin/ on the user
    detail page) — a plain collaborator assignment is NOT enough, by
    design. Otherwise assigning a guest author to one post would
    silently let them create more.
    """
    if not _can_create_post(request):
        return _staff_redirect(request, '/blog/new/')

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

    # For the `arxiv` template, a ?arxiv=<id> param pre-fills title + marker.
    if template_key == 'arxiv':
        arxiv_id = (request.GET.get('arxiv') or '').strip()
        if arxiv_id:
            try:
                from portfolio.blog.embeds.arxiv import _fetch as fetch_arxiv
                meta = fetch_arxiv(arxiv_id)
            except Exception:
                meta = None
            paper_title = meta['title'] if meta else f'arXiv:{arxiv_id}'
            base_title = request.GET.get('title') or f'Paper companion: {paper_title}'
            body = (
                f'# Paper companion: {paper_title}\n\n'
                f'<div data-arxiv="{arxiv_id}"></div>\n\n'
                '## The problem\n\nWhy this paper exists.\n\n'
                '## What we did\n\nOne-paragraph method.\n\n'
                '## What we found\n\nThe result. Caveats.\n\n'
                '## Where this goes\n\nOpen questions.\n'
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

# Each tuple: (regex, replacement-template). Groups in the regex feed
# into the placeholder so the author can see WHICH embed the placeholder
# stands for. Every heavy embed handler (network fetch, matplotlib exec,
# demo template render, GitHub file fetch) is short-circuited here so
# the preview round-trip measures in tens of ms instead of seconds.
_PREVIEW_SUBS = [
    # pyfig blocks: full matplotlib execution per render is the biggest
    # single cost; a 5-figure post can run >5s. Show one line instead.
    (re.compile(r'```python\s+pyfig[^\n]*\n[\s\S]*?\n```', re.MULTILINE),
     '<div class="preview-placeholder preview-pyfig">pyfig block · renders at save</div>'),
    # Demo embeds: the template render itself is cheap but we swap to a
    # placeholder client-side anyway — doing it server-side is strictly
    # faster (no demo template I/O at all).
    (re.compile(r'<div\s+data-demo=["\']([a-z0-9\-]+)["\'][^>]*>\s*</div>', re.IGNORECASE),
     '<div class="preview-placeholder">Demo: <code>\\1</code> · runs on published page</div>'),
    (re.compile(r'<div\b(?=[^>]*\bclass=["\']demo-embed["\'])(?=[^>]*\bdata-slug=["\']([a-z0-9\-]+)["\'])[^>]*>\s*</div>', re.IGNORECASE),
     '<div class="preview-placeholder">Demo: <code>\\1</code> · runs on published page</div>'),
    # Network-fetching embeds (arxiv / github / github-snippet / wiki):
    # each hits the internet on a cold cache. Placeholders keep the
    # author in flow; the real card renders when they save & view.
    (re.compile(r'<div\s+data-arxiv=["\']([\w\./\-]+)["\'][^>]*>\s*</div>', re.IGNORECASE),
     '<div class="preview-placeholder">arXiv: <code>\\1</code></div>'),
    (re.compile(r'<div\s+data-github=["\']([\w\.\-/]+)["\'][^>]*>\s*</div>', re.IGNORECASE),
     '<div class="preview-placeholder">GitHub: <code>\\1</code></div>'),
    (re.compile(r'<div\s+data-github-snippet=["\']([^"\']+)["\'][^>]*>\s*</div>', re.IGNORECASE),
     '<div class="preview-placeholder">GitHub snippet: <code>\\1</code></div>'),
    (re.compile(r'<div\s+data-wiki=["\']([^"\']+)["\'][^>]*>\s*</div>', re.IGNORECASE),
     '<div class="preview-placeholder">Wikipedia: <code>\\1</code></div>'),
]


def _strip_heavy_markers(body: str) -> str:
    """Substitute expensive embed markers with compact placeholders so
    the preview render never hits the network or runs matplotlib. The
    author's source text is untouched — this transforms only the copy
    that gets fed to `render_markdown`."""
    for pat, repl in _PREVIEW_SUBS:
        body = pat.sub(repl, body)
    return body


# Per-process preview render cache. The editor is staff-only + single-
# author so cross-user isolation isn't a concern. Key on (sha1(body),
# is_explainer). Typing "." then backspacing is free; toggling between
# two drafts you bounce between is free. LRU-ish: evict oldest entry
# past capacity. 16 × ~30 KB html = ~0.5 MB RSS worst case.
_PREVIEW_CACHE_MAX = 16
_preview_cache: "OrderedDict[tuple[str, bool], tuple[str, str]]" = OrderedDict()


def _preview_render(body: str, is_explainer: bool) -> tuple[str, str]:
    from portfolio.blog import render_markdown
    key = (
        hashlib.sha1(body.encode('utf-8', errors='replace')).hexdigest(),
        is_explainer,
    )
    hit = _preview_cache.get(key)
    if hit is not None:
        _preview_cache.move_to_end(key)
        return hit
    html, toc = render_markdown(body, is_explainer=is_explainer, preview=True)
    _preview_cache[key] = (html, toc)
    while len(_preview_cache) > _PREVIEW_CACHE_MAX:
        _preview_cache.popitem(last=False)
    return html, toc


def blog_preview(request):
    """Server-renders a markdown payload to HTML for the live-preview
    pane in the editor. POST {body, is_explainer, slug?} -> {html, toc}.

    `slug` is optional but the editor always sends it when available —
    the auth gate uses it to decide whether a collaborator can run a
    preview for *this* post (vs. any post), which lets staff keep the
    slug-less behaviour for ad-hoc previews.

    Hot-path: heavy markers stripped, cosmetic passes skipped, result
    memoised per (body_hash, is_explainer). A Server-Timing header
    reports render milliseconds (view it in DevTools → Network)."""
    slug = request.POST.get('slug', '').strip()
    post = None
    if slug:
        from portfolio.models import Post
        try:
            post = Post.objects.get(slug=slug)
        except Post.DoesNotExist:
            post = None
    if not _can_edit(request, post=post):
        return JsonResponse({'error': 'unauthorized'}, status=403)
    body = request.POST.get('body', '')
    is_explainer = request.POST.get('is_explainer') == 'true'
    body = _strip_heavy_markers(body)
    t0 = time.perf_counter()
    html, toc = _preview_render(body, is_explainer)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    resp = JsonResponse({'html': html, 'toc': toc})
    resp['Server-Timing'] = f'render;dur={elapsed_ms}'
    return resp


# ─── /blog/upload-image/ ─────────────────────────────────────────────

def blog_upload_image(request):
    """Editor image upload. POST a multipart `image` file; returns
    {url, markdown}. The editor inserts the markdown snippet at the
    cursor. Files land in MEDIA_ROOT/blog-images/YYYY/MM/<slug>-<n>.ext.

    Production caveat: ephemeral filesystems (Render free tier) lose
    these on every redeploy. Move MEDIA_ROOT to S3 or equivalent
    before relying on this in prod."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    slug = request.POST.get('slug', '').strip()
    post = None
    if slug:
        from portfolio.models import Post
        try:
            post = Post.objects.get(slug=slug)
        except Post.DoesNotExist:
            post = None
    if not _can_edit(request, post=post):
        return JsonResponse({'error': 'unauthorized'}, status=403)
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
