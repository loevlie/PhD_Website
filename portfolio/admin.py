from django.contrib import admin
from django.utils.html import format_html

from portfolio.models import Post, Pageview, DailySalt, Reading


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['title', 'kind', 'date', 'draft', 'is_explainer', 'is_paper_companion', 'maturity', 'tag_list']
    list_filter = ['kind', 'draft', 'is_explainer', 'is_paper_companion', 'maturity', 'date', 'tags']
    list_editable = ['kind', 'draft', 'is_explainer', 'is_paper_companion', 'maturity']
    search_fields = ['title', 'body', 'excerpt']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'date'
    save_on_top = True

    fieldsets = (
        ('Post', {
            'fields': ('title', 'slug', 'date', 'updated', 'author'),
        }),
        ('Content', {
            'fields': ('excerpt', 'body'),
            'description': (
                'Body is Markdown. Supported extras on <code>is_explainer</code> '
                'posts: footnote syntax <code>word[^slug]</code> becomes Tufte '
                'sidenotes in the margin; citation pills via '
                '<code>&lt;cite class="ref" data-key="harvey2026benchmark"&gt;[1]&lt;/cite&gt;</code>. '
                'Math: <code>$inline$</code> and <code>$$display$$</code>.'
            ),
        }),
        ('Display', {
            'fields': ('kind', 'image', 'tags', 'is_explainer', 'is_paper_companion', 'maturity', 'draft'),
            'description': 'kind routes the post: essay → /blog/, lab_note → /notebook/. is_explainer = Distill register (sidenotes + citations + wide canvas). is_paper_companion = Asterisk/Works in Progress register (single column, drop cap, real footnotes, pull-quotes). Mutually exclusive in practice.',
        }),
        ('Series + external', {
            'fields': ('series', 'series_order', 'medium_url'),
            'classes': ('collapse',),
        }),
    )

    def tag_list(self, obj):
        return ', '.join(o.name for o in obj.tags.all())
    tag_list.short_description = 'Tags'

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('tags')


@admin.register(Pageview)
class PageviewAdmin(admin.ModelAdmin):
    """Browse raw analytics rows. Read-only — beacons are the only writers."""
    list_display = ['created_at', 'path_display', 'device', 'browser', 'country',
                    'scroll_depth', 'dwell_seconds', 'referrer_short', 'is_bot']
    list_filter = ['device', 'browser', 'country', 'is_bot', 'created_at', 'post_slug']
    search_fields = ['path', 'referrer', 'session_id', 'post_slug']
    readonly_fields = [f.name for f in Pageview._meta.fields]
    date_hierarchy = 'created_at'
    list_per_page = 50
    actions = ['mark_as_bot']

    def path_display(self, obj):
        return obj.path[:60] + ('…' if len(obj.path) > 60 else '')
    path_display.short_description = 'Path'

    def referrer_short(self, obj):
        if not obj.referrer:
            return '—'
        r = obj.referrer
        # Strip protocol for compact display
        for p in ('https://', 'http://'):
            if r.startswith(p):
                r = r[len(p):]
        return r[:50]
    referrer_short.short_description = 'Referrer'

    def dwell_seconds(self, obj):
        return f'{obj.dwell_ms / 1000:.1f}s' if obj.dwell_ms else '—'
    dwell_seconds.short_description = 'Dwell'

    def has_add_permission(self, request):
        return False

    def mark_as_bot(self, request, queryset):
        n = queryset.update(is_bot=True)
        self.message_user(request, f'Marked {n} pageview(s) as bot.')
    mark_as_bot.short_description = 'Mark selected as bot (excluded from dashboard)'


@admin.register(Reading)
class ReadingAdmin(admin.ModelAdmin):
    """Curated reading list shown at /reading/. Stored in the DB so you
    can edit on the go from /admin/ without a redeploy.

    Source of truth: a Mind Mapper "Reading" project (one note per
    paper). The "Sync from Mind Mapper" button at the top of the
    changelist runs `python manage.py sync_reading` from the admin so
    you don't need the Render shell."""
    list_display = ['title_with_mm_link', 'venue', 'year', 'status', 'order', 'source', 'modified_at']
    list_display_links = ['title_with_mm_link']
    list_filter = ['status', 'year']
    list_editable = ['status', 'order']
    search_fields = ['title', 'venue', 'annotation']
    save_on_top = True
    actions = ['mark_this_week', 'mark_lingering', 'mark_archived']
    change_list_template = 'admin/portfolio/reading/change_list.html'
    fieldsets = (
        ('Reference', {
            'fields': ('title', 'venue', 'year', 'url'),
        }),
        ('Annotation', {
            'fields': ('annotation',),
            'description': 'One-line note in your own voice. Italic on the page; keep it short. Will be overwritten by the next Mind Mapper sync if mind_mapper_note_id is set, so prefer editing in MM for synced rows.',
        }),
        ('Surface', {
            'fields': ('status', 'order'),
            'description': 'this_week shows top, lingering shows below, archived hides from /reading/. Lower order = higher in its bucket.',
        }),
        ('Provenance', {
            'fields': ('mind_mapper_note_id',),
            'classes': ('collapse',),
            'description': 'NULL = manually-added (never touched by sync). An integer = synced from this Mind Mapper note id; sync will update fields from MM on each run.',
        }),
    )

    def source(self, obj):
        if obj.mind_mapper_note_id:
            return format_html(
                '<span style="color:#7287fd">MM #{}</span>',
                obj.mind_mapper_note_id,
            )
        return format_html('<span style="color:#888">manual</span>')
    source.short_description = 'Source'

    def title_with_mm_link(self, obj):
        edit_url = f'/admin/portfolio/reading/{obj.pk}/change/'
        if obj.mind_mapper_note_id:
            mm_url = f'https://mind-mapper-x1zt.onrender.com/notes/{obj.mind_mapper_note_id}/'
            return format_html(
                '<a href="{}">{}</a> '
                '<a href="{}" target="_blank" rel="noopener" '
                'title="Open in Mind Mapper" '
                'style="margin-left:6px;font-size:0.75em;color:#7287fd;text-decoration:none">↗ MM</a>',
                edit_url, obj.title, mm_url,
            )
        return format_html('<a href="{}">{}</a>', edit_url, obj.title)
    title_with_mm_link.short_description = 'Title'
    title_with_mm_link.admin_order_field = 'title'

    def mark_this_week(self, request, queryset):
        n = queryset.update(status='this_week')
        self.message_user(request, f'Moved {n} entry(ies) to "This week".')
    mark_this_week.short_description = 'Move to "This week"'

    def mark_lingering(self, request, queryset):
        n = queryset.update(status='lingering')
        self.message_user(request, f'Moved {n} entry(ies) to "Lingering".')
    mark_lingering.short_description = 'Move to "Lingering"'

    def mark_archived(self, request, queryset):
        n = queryset.update(status='archived')
        self.message_user(request, f'Archived {n} entry(ies) (hidden from /reading/).')
    mark_archived.short_description = 'Archive (hide from /reading/)'

    # ── Sync-from-MM admin action wired as a custom URL + button ──
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        return [
            path('sync-mm/', self.admin_site.admin_view(self.sync_from_mm),
                 name='portfolio_reading_sync_mm'),
        ] + urls

    def sync_from_mm(self, request):
        """Admin endpoint: runs `sync_reading` and redirects back with a
        flash message summarizing what changed. POST-only to avoid
        accidental double-syncs from a bookmark.

        Pass ?prune=1 in the form to also delete local rows whose MM
        source has been removed (used when you delete a paper in MM and
        want it gone from /reading/ on the next sync)."""
        from django.shortcuts import redirect
        from django.urls import reverse
        from django.contrib import messages
        from django.core.management import call_command
        from io import StringIO

        if request.method != 'POST':
            return redirect(reverse('admin:portfolio_reading_changelist'))

        prune = request.POST.get('prune') == '1'
        out = StringIO()
        try:
            kwargs = {'stdout': out, 'stderr': out}
            if prune:
                kwargs['prune'] = True
            call_command('sync_reading', **kwargs)
            output = out.getvalue()
            last_line = next((ln for ln in reversed(output.splitlines()) if ln.strip()), 'sync ran')
            verb = 'Mind Mapper sync (with prune)' if prune else 'Mind Mapper sync'
            messages.success(request, f'{verb}: {last_line.strip()}')
        except Exception as e:
            messages.error(request, f'Mind Mapper sync failed: {e}')
        return redirect(reverse('admin:portfolio_reading_changelist'))


@admin.register(DailySalt)
class DailySaltAdmin(admin.ModelAdmin):
    list_display = ['date', 'salt_preview']
    readonly_fields = ['date', 'salt']
    ordering = ['-date']

    def salt_preview(self, obj):
        return obj.salt[:8] + '…'
    salt_preview.short_description = 'Salt (preview)'

    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
