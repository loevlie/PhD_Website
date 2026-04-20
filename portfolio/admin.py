from django.contrib import admin

from portfolio.models import Post


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
