from django.contrib import admin
from django.utils.html import format_html

from portfolio.models import Post, Pageview, DailySalt


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['title', 'date', 'draft', 'is_explainer', 'is_paper_companion', 'maturity', 'tag_list']
    list_filter = ['draft', 'is_explainer', 'is_paper_companion', 'maturity', 'date', 'tags']
    list_editable = ['draft', 'is_explainer', 'is_paper_companion', 'maturity']
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
            'fields': ('image', 'tags', 'is_explainer', 'is_paper_companion', 'maturity', 'draft'),
            'description': 'is_explainer = Distill register (sidenotes + citations + wide canvas). is_paper_companion = Asterisk/Works in Progress register (single column, drop cap, real footnotes, pull-quotes). Mutually exclusive in practice.',
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
