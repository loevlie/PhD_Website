from django.contrib import admin
from django.utils.html import format_html

from portfolio.models import (
    Post, Pageview, DailySalt, Reading,
    NewsItem, Publication, PublicationLink,
    Project, ProjectLink, TimelineEntry, OpenSourceItem,
    SocialLink, NowPage, NowSection,
)


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
        ('Collaborators', {
            'fields': ('collaborators',),
            'description': (
                'Non-staff users granted edit access to <strong>this specific '
                'post</strong>. Assign a signed-up user here and share the '
                'editor URL <code>/blog/&lt;slug&gt;/edit/</code> plus the '
                'per-post analytics at <code>/site/insights/blog/&lt;slug&gt;/</code>. '
                'By default they cannot create new posts or edit other posts. '
                '<br><br>To let a collaborator create <em>new</em> posts, open '
                'their user record under <em>Authentication and Authorization '
                '→ Users</em>, scroll to "User permissions," and add '
                '<code>portfolio | post | Can add post</code>. Revoke the same '
                'way.'
            ),
            'classes': ('collapse',),
        }),
    )

    filter_horizontal = ('collaborators',)

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
    """Curated reading list shown at /reading/. All entries are added
    manually — either from /admin/ or the /site/studio/ quick-add form.

    Mind Mapper integration (2026-04 rework): `sync_reading` no longer
    creates rows. It only attaches optional MM-sourced annotations
    (via `mm_annotation`) to entries that already exist, matching by
    URL or title. Remove an MM note → sync clears the annotation but
    keeps the Reading entry."""
    list_display = ['title_with_mm_link', 'venue', 'year', 'status', 'order', 'source', 'modified_at']
    list_display_links = ['title_with_mm_link']
    list_filter = ['status', 'year']
    list_editable = ['status', 'order']
    search_fields = ['title', 'venue', 'annotation', 'mm_annotation']
    save_on_top = True
    actions = ['mark_this_week', 'mark_lingering', 'mark_archived']
    change_list_template = 'admin/portfolio/reading/change_list.html'
    readonly_fields = ['mm_annotation']
    fieldsets = (
        ('Reference', {
            'fields': ('title', 'venue', 'year', 'url'),
        }),
        ('Your annotation', {
            'fields': ('annotation',),
            'description': 'One-line note in your own voice. Italic on the page; keep it short. Your hand edits are never overwritten by sync.',
        }),
        ('Mind Mapper annotation (optional, synced)', {
            'fields': ('mm_annotation', 'mind_mapper_note_id'),
            'classes': ('collapse',),
            'description': 'Overwritten on every <code>sync_reading</code> run — edit the MM note itself, not here. '
                           'Shown beneath your annotation on /reading/. Sync matches by URL or by exact title.',
        }),
        ('Surface', {
            'fields': ('status', 'order'),
            'description': 'this_week shows top, lingering shows below, archived hides from /reading/. Lower order = higher in its bucket.',
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
        if obj.mind_mapper_note_id:
            mm_url = f'https://mind-mapper-x1zt.onrender.com/notes/{obj.mind_mapper_note_id}/'
            return format_html(
                '{} <a href="{}" target="_blank" rel="noopener" '
                'title="Open in Mind Mapper" '
                'style="margin-left:6px;font-size:0.75em;color:#7287fd;text-decoration:none">↗ MM</a>',
                obj.title, mm_url,
            )
        return obj.title
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

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        return [
            path('sync-mm/', self.admin_site.admin_view(self.sync_from_mm),
                 name='portfolio_reading_sync_mm'),
        ] + urls

    def sync_from_mm(self, request):
        """Admin endpoint: runs `sync_reading` (match + attach annotations)
        and redirects back with a flash message summarizing what changed.
        POST-only to avoid accidental double-syncs from a bookmark.

        As of 2026-04, sync does NOT create, update, or delete Reading
        rows — it only attaches optional annotations from matched MM
        notes (see `mm_annotation`)."""
        from django.shortcuts import redirect
        from django.urls import reverse
        from django.contrib import messages
        from django.core.management import call_command
        from io import StringIO

        if request.method != 'POST':
            return redirect(reverse('admin:portfolio_reading_changelist'))

        out = StringIO()
        try:
            call_command('sync_reading', stdout=out, stderr=out)
            output = out.getvalue()
            last_line = next((ln for ln in reversed(output.splitlines()) if ln.strip()), 'sync ran')
            messages.success(request, f'Mind Mapper sync: {last_line.strip()}')
        except Exception as e:
            messages.error(request, f'Mind Mapper sync failed: {e}')
        return redirect(reverse('admin:portfolio_reading_changelist'))


# ─── Content admin (Track B1) ─────────────────────────────────────────


@admin.register(NewsItem)
class NewsItemAdmin(admin.ModelAdmin):
    list_display = ['date', 'short_text', 'highlight', 'display_order', 'draft', 'modified_at']
    list_editable = ['display_order', 'highlight', 'draft']
    list_filter = ['highlight', 'draft']
    search_fields = ['date', 'text']
    save_on_top = True
    fieldsets = (
        (None, {'fields': ('date', 'text', 'highlight')}),
        ('Display', {'fields': ('display_order', 'draft')}),
    )

    def short_text(self, obj):
        from django.utils.html import strip_tags
        return strip_tags(obj.text)[:80]
    short_text.short_description = 'Text'


class PublicationLinkInline(admin.TabularInline):
    model = PublicationLink
    extra = 1
    fields = ['label', 'url', 'order']


@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ['title_short', 'pub_type', 'year', 'selected', 'draft', 'display_order']
    list_editable = ['selected', 'draft', 'display_order']
    list_filter = ['pub_type', 'year', 'selected', 'draft']
    search_fields = ['title', 'authors', 'venue']
    inlines = [PublicationLinkInline]
    save_on_top = True
    fieldsets = (
        ('Publication', {
            'fields': ('title', 'authors', 'venue', 'year', 'pub_type'),
            'description': 'Authors: comma-separated. Venue: e.g. "NeurIPS" or "ML4H 2025 Symposium, Findings Track".',
        }),
        ('Presentation', {
            'fields': ('selected', 'image', 'image_credit', 'display_order', 'draft'),
            'description': 'selected=true promotes to the homepage featured block. Requires an image.',
        }),
        ('Citation', {
            'fields': ('bibtex',),
            'classes': ('collapse',),
        }),
    )

    def title_short(self, obj):
        return (obj.title[:80] + '…') if len(obj.title) > 80 else obj.title
    title_short.short_description = 'Title'
    title_short.admin_order_field = 'title'


class ProjectLinkInline(admin.TabularInline):
    model = ProjectLink
    extra = 1
    fields = ['label', 'url', 'order']


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['title', 'featured', 'language', 'github', 'draft', 'display_order']
    list_editable = ['featured', 'draft', 'display_order']
    list_filter = ['featured', 'draft', 'language']
    search_fields = ['title', 'description', 'tags_csv', 'github']
    inlines = [ProjectLinkInline]
    save_on_top = True
    fieldsets = (
        ('Project', {
            'fields': ('title', 'description', 'tags_csv', 'github', 'language'),
            'description': 'Tags: comma-separated (e.g. "LLM, Optimization, PyTorch"). GitHub: slug only (e.g. "loevlie/neuropt").',
        }),
        ('Display', {
            'fields': ('featured', 'display_order', 'draft'),
        }),
    )


@admin.register(TimelineEntry)
class TimelineEntryAdmin(admin.ModelAdmin):
    list_display = ['year', 'title', 'org', 'draft', 'display_order']
    list_editable = ['draft', 'display_order']
    list_filter = ['draft']
    search_fields = ['year', 'title', 'org', 'description']
    save_on_top = True
    fieldsets = (
        ('Role', {'fields': ('year', 'title', 'org', 'description')}),
        ('External link', {'fields': ('link', 'link_label'), 'classes': ('collapse',)}),
        ('Display', {'fields': ('display_order', 'draft')}),
    )


@admin.register(OpenSourceItem)
class OpenSourceItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'role', 'url_short', 'draft', 'display_order']
    list_editable = ['draft', 'display_order']
    search_fields = ['name', 'description', 'url']
    save_on_top = True

    def url_short(self, obj):
        return obj.url.replace('https://', '').replace('http://', '')[:60]
    url_short.short_description = 'URL'


@admin.register(SocialLink)
class SocialLinkAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon', 'url_short', 'draft', 'display_order']
    list_editable = ['draft', 'display_order']
    list_filter = ['icon', 'draft']
    search_fields = ['name', 'url']
    save_on_top = True

    def url_short(self, obj):
        return obj.url.replace('https://', '').replace('http://', '').replace('mailto:', '✉ ')[:60]
    url_short.short_description = 'URL'


class NowSectionInline(admin.TabularInline):
    model = NowSection
    extra = 1
    fields = ['order', 'heading', 'body']


@admin.register(NowPage)
class NowPageAdmin(admin.ModelAdmin):
    list_display = ['updated', 'location', 'section_count', 'modified_at']
    inlines = [NowSectionInline]
    save_on_top = True
    fieldsets = (
        (None, {
            'fields': ('updated', 'location', 'draft'),
            'description': 'The /now/ page is a singleton — one row. Update `updated` every time you edit anything below so the freshness marker on the page stays honest.',
        }),
    )

    def section_count(self, obj):
        return obj.section_set.count()
    section_count.short_description = 'Sections'

    def has_add_permission(self, request):
        # Singleton — after the seed creates the one row, no need for new ones.
        # Admins can still delete + re-seed manually if they really want.
        return not NowPage.objects.exists()


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
