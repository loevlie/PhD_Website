"""Fast "Add a paper to /reading/" endpoint for staff.

POST /site/reading/add/  with form fields:
    title       (required)
    url         (optional)
    venue       (optional)
    year        (optional)
    status      (optional, default `this_week`; one of the Reading statuses)
    annotation  (optional)

Redirects back to ?next (if provided and local) or to /admin/portfolio/reading/.

Designed to be embeddable on any staff-facing page (the Studio
dashboard, the /reading/ page itself) so adding an entry doesn't
require a Django admin round-trip.
"""
from urllib.parse import urlparse

from django.contrib import messages
from django.shortcuts import redirect

from portfolio.views.editor_assist import _staff_redirect


_STATUS_VALUES = {'this_week', 'lingering', 'archived'}


def _safe_next(request, fallback='/admin/portfolio/reading/'):
    """Only honor `next` if it's same-host. Stops an open-redirect via the form."""
    candidate = request.POST.get('next') or request.GET.get('next') or fallback
    parsed = urlparse(candidate)
    if parsed.netloc and parsed.netloc != request.get_host():
        return fallback
    return candidate


def reading_quickadd(request):
    if not (request.user.is_authenticated and request.user.is_staff):
        # Site convention is /accounts/login/ via _staff_redirect — the
        # bare /admin/login/ redirect here was the odd one out, and
        # rejected non-staff Django logins with the misleading
        # "invalid credentials" error instead of routing them to their
        # profile page.
        return _staff_redirect(request, _safe_next(request, fallback='/site/studio/'))
    if request.method != 'POST':
        # A GET hits when an expired-session POST bounces through login
        # and re-lands here — bare 400 lost the typed entry without a
        # breadcrumb. Send the user to the Studio quick-add form with
        # a note so they can re-type without hunting for the surface.
        messages.info(request, 'Use the quick-add form below to log a paper.')
        return redirect('/site/studio/')

    from portfolio.models import Reading

    title = (request.POST.get('title') or '').strip()
    if not title:
        messages.error(request, 'Title is required.')
        return redirect(_safe_next(request))

    # One entry per rendered form: a double-click re-submits the same
    # nonce; cache.add is first-writer-wins, so the duplicate becomes a
    # friendly no-op instead of a second identical row.
    nonce = (request.POST.get('create_nonce') or '').strip()
    if nonce:
        from django.core.cache import cache
        if not cache.add(f'reading_nonce:{nonce}', '1', 600):
            messages.info(request, f'“{title[:60]}” was already added — skipped the duplicate submit.')
            return redirect(_safe_next(request))

    status = (request.POST.get('status') or 'this_week').strip()
    if status not in _STATUS_VALUES:
        status = 'this_week'

    year_raw = (request.POST.get('year') or '').strip()
    year = None
    if year_raw:
        try:
            year = int(year_raw)
        except ValueError:
            year = None

    Reading.objects.create(
        title=title[:300],
        url=(request.POST.get('url') or '').strip()[:500],
        venue=(request.POST.get('venue') or '').strip()[:200],
        year=year,
        status=status,
        annotation=(request.POST.get('annotation') or '').strip(),
    )
    messages.success(request, f'Added “{title[:60]}” to /reading/.')
    return redirect(_safe_next(request))
