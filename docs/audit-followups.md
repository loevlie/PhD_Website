# Staff-workflow audit — confirmed follow-ups (June 2026)

> **Status (2026-06-12): all 19 items closed.**
> Batch 1 (1–5): commit `015f605`
> Batch 2 (7–9): commit `00e84fc`
> Batch 3 (14–16): commit `653e58a`
> Batch 4 (17–19): commit `6a33685`
> Batch 5 (10–13): commit `6482c77`
> Item 6 (OG cards): commit `7894a31`
>
> Keep this doc as a historical record of the original audit + fix
> rationale — file-line pointers may have drifted since; rely on the
> commit diffs for the authoritative change.

Recovered from the adversarial audit of the studio → new-post → editor →
save workflow (run was stopped early; all finder/verifier results were
journaled). Every item below was independently verified against the
working tree, several with live reproductions. Deduplicated and ordered
by how much they matter. The June 2026 fixes already in the tree
(slug-autosave, cover clear/replace, autosave file payloads, create
nonces + double-submit guards, import ledger) are NOT listed — these are
the *remaining* items.

## High priority — correctness / data visibility

1. **Drafting or deleting a file-seeded post doesn't actually unpublish it.**
   `get_post()` (`portfolio/blog/__init__.py` ~1009-1027) falls back to the
   `.md` file on `Post.DoesNotExist` — and a `draft=True` row raises
   DoesNotExist through the `draft=False` filter, so the PUBLIC page serves
   the stale markdown version. Same for deleted/renamed file posts (the new
   ImportedPostLedger only guards `import_posts`, not this view fallback).
   Fix: only use the file fallback when `_has_db()` is False/table empty
   (mirror `_load_all_posts`), or consult the ledger and return None.

2. **A guest author with `add_post` permission can create a draft but then
   can't open it.** `blog_new` creates the Post without adding the creator
   as a collaborator; the redirect to `/blog/<slug>/edit/` bounces them via
   `_can_edit`. Fix in `blog_new` right after `Post.objects.create(...)`:
   `if not request.user.is_staff: PostCollaborator.objects.get_or_create(post=p, user=request.user, defaults={'order': 2})`
   (owner already holds order=1 via the signal).

3. **Explicit Save renders the whole post TWICE.** `blog_edit` POST calls
   bare `post.save()` (post_save signal does a full render) and then runs
   its own explicit render. On pyfig-heavy posts that doubles a
   multi-second save. Fix: `post._skip_render = True` before the
   `post.save()` in the blog_edit POST path (the view's explicit render is
   the authoritative one — it force-persists and handles `render_failed`).

4. **No slug validation on explicit Save.** The Details-drawer slug input is
   applied verbatim: empty string, arbitrary text ("my new title"), or a
   slug colliding with another post → IntegrityError 500 mid-save. Fix in
   `_apply_post_fields` (slug branch): `slugify(v)`; keep old slug if
   empty; uniqueness-suffix loop excluding `pk=post.pk` (same loop
   blog_new uses). Optionally `pattern=` on the input.

5. **Save can race the autosave/pagehide beacons.** Nothing stands down the
   autosave pipeline when the form submits: a debounced autosave or the
   pagehide flush can land around the multipart Save. Fix: submit listener
   on `#editor-form` → `clearTimeout(autosaveTimer); clearTimeout(retryTimer); dirty = false;`
   (the Save POST carries strictly more data than any beacon).

6. **OG cards are broken in production.** `regenerate_og_card` /
   `generate_og_cards` need Playwright (not in requirements.txt; never run
   by build.sh), write to a non-durable local dir, silently "succeed" for
   draft/unknown slugs, and nothing generates a card for new posts — so
   every post authored in the browser ships without its per-post OG image.
   Fix: rewrite generation with Pillow (already a dep) writing to
   `default_storage` (`og/<slug>.png`, survives deploys); command should
   use `include_drafts=True` for explicit slugs and raise `CommandError`
   on unknown; the view should verify the file exists and return the
   storage URL. (Or: add playwright+chromium to the build — heavy.)

## Medium — workflow weirdness

7. **Same-render nonce conflates different creations.** The Studio shares
   one `create_nonce` across its lab-note and demo forms, and the dedup
   key (`blog_new_nonce:<nonce>`) ignores template/demo — create a lab
   note, then a demo writeup within 10 min from the same Studio render and
   the second click silently redirects into the FIRST draft. Fix: scope
   the key `blog_new_nonce:{nonce}:{template_key}:{demo}`; ideally also
   `cache.add` first-writer-wins (the current get→set is check-then-act).

8. **bfcache restore leaves dead creation pages.** After creating from
   /blog/new/ or Studio, Back restores the page with all buttons disabled
   (`dataset.busy`) and a consumed nonce — clicks do nothing. Fix: add the
   editor's existing guard to both templates:
   `window.addEventListener('pageshow', e => { if (e.persisted) location.reload(); })`.

9. **The advertised `?demo=` / `?arxiv=` prefills are dropped.** The picker
   form POSTs to bare `/blog/new/` without carrying the GET params, so
   `?arxiv=<id>` (advertised in the card desc) does nothing. Fix: pass
   `arxiv`/`demo`/`title` from `request.GET` into hidden inputs in
   blog_new.html; also fix the leftover `request.GET.get('title')` →
   `request.POST.get('title')` in the demo branch (~blog_editor.py:705).

10. **Editor preview pane shows a stale render after autosave-only
    sessions.** On load, `lastRendered` is seeded with the CURRENT body
    while the pane shows the OLD persisted `rendered_html` — no re-render
    until the first keystroke. Fix: when
    `post.modified_at > post.rendered_at` (or no rendered_at), seed with a
    sentinel and `scheduleRender(0)` on init.

11. **Multi-file drag-drop inserts images at the same pinned offset**
    (reverse order, interleaved). Fix in the drop handler: pin only the
    first file, `pinnedPos = null` for the rest (they then follow the
    caret left by the previous insert).

12. **Upload completing while the tab is frozen (lock lost) claims
    "image inserted" but inserted nothing** (insertAtCursor's readOnly
    guard silently refuses; file IS in storage). Fix: make insertAtCursor
    return a bool; on refusal stash the markdown as a pending insert
    (flushed by "Take back") and show an error status instead.

13. **New posts ship with junk slugs** (`untitled-draft`, `lab-note-topic`)
    unless manually edited — title edits never re-derive the slug. Fix
    sketch: `slug_is_auto` flag set at creation; on explicit Save, while
    auto and untouched, re-derive from title with the uniqueness loop;
    clear the flag on manual edit or first publish.

## Reading quick-add (smaller)

14. **/reading/ page's own quick-add form** never got the nonce or the
    double-submit guard (only Studio did) — double-click still duplicates
    there. Mirror the Studio wiring (`reading()` view context + hidden
    input + guard script).
15. **Quick-add feedback is invisible on /reading/**: messages are queued
    but reading.html (unlike studio.html) has no `{% if messages %}`
    block — success/error/dedup notices silently vanish. Add the block
    (or put it in the base template).
16. **reading_quickadd auth is the odd one out**: anon → `/admin/login/`
    (site convention is `_staff_redirect` → `/accounts/login/`); GET →
    bare 400; an expired-session POST loses the typed entry and lands on
    the 400 after login. Fix: use `_staff_redirect(request, _safe_next(...))`
    and redirect GETs to the studio with a hint message.

## Cosmetic / low

17. **Studio tile counts call drafts "published"** — `counts.essays`
    includes drafts. Fix: `essays.filter(draft=False).count()` (same for
    lab notes).
18. **Cover replacement/deletion leaks the old file in storage** (no
    cleanup on reassign or post delete). Low priority: delete the old
    storage object on replace; post_delete receiver for cover_image.
19. **Lostlock rescue snapshot is keyed by slug only** — slug reuse after
    a delete could offer another post's rescued text. Gate the offer on
    `lost.ts >= post.created_at` epoch.

## Refuted (don't re-chase)

Three claims were refuted: they described pre-fix behavior (cover clear
on autosave), duplicated the ledger fix already in the tree, or couldn't
be reproduced.

## Suggested order of attack

1, 2, 3, 4, 5 (correctness, all small) → 7+8+9 as one "creation flow"
batch → 6 (og cards, the only meaty one) → 10-13 (editor polish) →
14-16 (reading) → 17-19. Add regression tests alongside each (the
verifiers' reasonings in the audit journal name exact repro sequences:
`.claude/projects/.../subagents/workflows/wf_56eafb78-5fd/journal.jsonl`).
