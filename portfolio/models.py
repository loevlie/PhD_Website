from django.db import models
from django.urls import reverse

from taggit.managers import TaggableManager


class Post(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    excerpt = models.TextField(blank=True, help_text="Short description for cards and meta tags")
    body = models.TextField(help_text="Markdown content")
    date = models.DateField(help_text="Original publication date")
    updated = models.DateField(blank=True, null=True)
    author = models.CharField(max_length=100, default='Dennis Loevlie')
    image = models.CharField(max_length=300, blank=True, help_text="Static path for cover image, e.g. portfolio/images/blog/cover.jpg")
    series = models.CharField(max_length=100, blank=True, help_text="Series name, e.g. 'Deep Dive: Multiple Instance Learning'")
    series_order = models.PositiveIntegerField(default=0, help_text="Order within the series (1, 2, 3...)")
    medium_url = models.URLField(blank=True, help_text="Canonical URL if originally published elsewhere")
    draft = models.BooleanField(default=False)
    is_explainer = models.BooleanField(
        default=False,
        help_text="Render with explainer chrome: Tufte sidenotes, hover citations, BibTeX export, wider figure canvas.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    tags = TaggableManager(blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('blog_post', args=[self.slug])
