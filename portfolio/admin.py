from django.contrib import admin
from portfolio.models import Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'date', 'draft', 'tag_list']
    list_filter = ['draft', 'date', 'tags']
    search_fields = ['title', 'body', 'excerpt']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'date'

    def tag_list(self, obj):
        return ', '.join(o.name for o in obj.tags.all())
    tag_list.short_description = 'Tags'

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('tags')
