"""Admin Studio — the single-page starting point for all content work.

Route:
    /site/studio/             staff-only landing with tiled admin actions.

Intentionally lives at /site/ (same space as /site/insights/) so the
admin surface stays under one URL prefix and doesn't collide with
taggit / taggit-selectize's admin URL patterns.
"""
from django.shortcuts import redirect, render


def studio(request):
    if not (request.user.is_authenticated and request.user.is_staff):
        # Not authenticated: bounce through Django admin login so we
        # inherit Django's CSRF / rate limiting / audit log.
        return redirect(f'/admin/login/?next={request.path}')

    # Quick counts to make the tiles feel alive. Cheap queries; the
    # dashboard is expected to be visited rarely.
    from portfolio.models import Post, Reading
    from portfolio.content.demos import DEMOS
    essays = Post.objects.filter(kind='essay')
    lab_notes = Post.objects.filter(kind='lab_note')
    return render(request, 'portfolio/studio.html', {
        'counts': {
            'essays': essays.count(),
            'essay_drafts': essays.filter(draft=True).count(),
            'lab_notes': lab_notes.count(),
            'lab_note_drafts': lab_notes.filter(draft=True).count(),
            'reading_this_week': Reading.objects.filter(status='this_week').count(),
            'reading_lingering': Reading.objects.filter(status='lingering').count(),
        },
        'recent_essays': essays.order_by('-modified_at')[:5],
        'recent_lab_notes': lab_notes.order_by('-modified_at')[:5],
        'recent_reading': Reading.objects.exclude(status='archived').order_by('-modified_at')[:5],
        # Demo-writeup picker: one tile per demo in DEMOS that links
        # straight to `/blog/new/?template=demo&demo=<slug>` so the
        # new draft already embeds the live widget.
        'demos': DEMOS,
    })
