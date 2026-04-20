"""Admin-only analytics dashboard.

Aggregates Pageview rows into the visuals shown at /analytics/. All
queries run against the local DB; no external deps. Designed to be cheap
even at 100k+ pageviews — bounded ranges, indexed columns, COUNT(DISTINCT)
not subqueries.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from django.db.models import Count
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils import timezone


def _is_staff(request):
    return request.user.is_authenticated and request.user.is_staff


def dashboard(request):
    """/site/insights/ — staff-only stats dashboard."""
    if not _is_staff(request):
        return HttpResponseRedirect('/admin/login/?next=/site/insights/')

    from portfolio.models import Pageview

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=6)  # last 7 days inclusive
    month_start = today_start - timedelta(days=29)
    online_cutoff = now - timedelta(minutes=5)

    base = Pageview.objects.filter(is_bot=False)

    total_views = base.count()
    today_views = base.filter(created_at__gte=today_start).count()
    week_views = base.filter(created_at__gte=week_start).count()
    month_views = base.filter(created_at__gte=month_start).count()

    today_uniques = base.filter(created_at__gte=today_start).values('session_id').distinct().count()
    week_uniques = base.filter(created_at__gte=week_start).values('session_id').distinct().count()

    online = base.filter(created_at__gte=online_cutoff).values('session_id').distinct().count()

    # Hourly buckets for last 7 days (168 buckets)
    hourly_counts = defaultdict(int)
    hourly_qs = base.filter(created_at__gte=week_start).values('created_at')
    for row in hourly_qs.iterator():
        bucket = row['created_at'].replace(minute=0, second=0, microsecond=0)
        hourly_counts[bucket] += 1
    # Pad missing hours with 0 so the sparkline is uniform
    sparkline = []
    cursor = week_start.replace(minute=0, second=0, microsecond=0)
    while cursor <= now:
        sparkline.append({'ts': cursor.isoformat(), 'count': hourly_counts.get(cursor, 0)})
        cursor += timedelta(hours=1)

    # Daily buckets for last 30 days
    daily_counts = defaultdict(int)
    daily_qs = base.filter(created_at__gte=month_start).values('created_at')
    for row in daily_qs.iterator():
        bucket = row['created_at'].date()
        daily_counts[bucket] += 1
    daily = []
    cursor_d = month_start.date()
    today_d = today_start.date()
    while cursor_d <= today_d:
        daily.append({'date': cursor_d.isoformat(), 'count': daily_counts.get(cursor_d, 0)})
        cursor_d += timedelta(days=1)

    top_paths = list(
        base.filter(created_at__gte=week_start)
            .values('path')
            .annotate(c=Count('id'))
            .order_by('-c')[:15]
    )
    top_referrers = list(
        base.filter(created_at__gte=week_start)
            .exclude(referrer='')
            .values('referrer')
            .annotate(c=Count('id'))
            .order_by('-c')[:10]
    )
    countries = list(
        base.filter(created_at__gte=week_start)
            .exclude(country='')
            .values('country')
            .annotate(c=Count('id'))
            .order_by('-c')[:15]
    )
    devices = list(
        base.filter(created_at__gte=week_start)
            .values('device')
            .annotate(c=Count('id'))
            .order_by('-c')
    )
    browsers = list(
        base.filter(created_at__gte=week_start)
            .values('browser')
            .annotate(c=Count('id'))
            .order_by('-c')
    )

    # Per-post engagement (avg scroll depth + median dwell)
    post_engagement = list(
        base.filter(created_at__gte=month_start)
            .exclude(post_slug='')
            .values('post_slug')
            .annotate(c=Count('id'))
            .order_by('-c')[:10]
    )
    # Add avg scroll/dwell per slug
    for p in post_engagement:
        rows = base.filter(post_slug=p['post_slug'], created_at__gte=month_start) \
                   .values_list('scroll_depth', 'dwell_ms')
        scrolls = [r[0] for r in rows if r[0]]
        dwells = sorted([r[1] for r in rows if r[1]])
        p['avg_scroll'] = round(sum(scrolls) / len(scrolls)) if scrolls else 0
        p['median_dwell_s'] = round(dwells[len(dwells) // 2] / 1000) if dwells else 0

    return render(request, 'portfolio/analytics_dashboard.html', {
        'totals': {
            'all_time': total_views,
            'today': today_views,
            'today_uniques': today_uniques,
            'week': week_views,
            'week_uniques': week_uniques,
            'month': month_views,
            'online': online,
        },
        'sparkline': sparkline,
        'daily': daily,
        'top_paths': top_paths,
        'top_referrers': top_referrers,
        'countries': countries,
        'devices': devices,
        'browsers': browsers,
        'post_engagement': post_engagement,
    })
