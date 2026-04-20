from django.db import models
from django.urls import reverse

from taggit.managers import TaggableManager


class DailySalt(models.Model):
    """Per-day salt for IP hashing. New salt every day means yesterday's
    hashes can't be reversed even if today's salt leaks. Auto-generated
    on first lookup of a given date."""
    date = models.DateField(unique=True, db_index=True)
    salt = models.CharField(max_length=64)

    @classmethod
    def for_today(cls):
        from datetime import date as _date
        import secrets
        today = _date.today()
        obj, _ = cls.objects.get_or_create(date=today, defaults={'salt': secrets.token_hex(32)})
        return obj.salt

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f'salt({self.date})'


class Pageview(models.Model):
    """One row per pageview beacon. Privacy: no raw IP stored — only a
    daily-salted hash. No persistent fingerprint across days. Session
    cookie (sid) is per-browser-session (30 min idle TTL)."""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    path = models.CharField(max_length=500, db_index=True)
    referrer = models.CharField(max_length=500, blank=True)
    country = models.CharField(max_length=2, blank=True, db_index=True)  # ISO-2 from CF-IPCountry
    device = models.CharField(max_length=16, blank=True, db_index=True)  # phone/tablet/desktop
    browser = models.CharField(max_length=32, blank=True)  # Chrome/Safari/Firefox/Other
    viewport_w = models.PositiveSmallIntegerField(default=0)
    viewport_h = models.PositiveSmallIntegerField(default=0)
    session_id = models.CharField(max_length=32, db_index=True)
    ip_hash = models.CharField(max_length=64, blank=True, db_index=True)
    is_bot = models.BooleanField(default=False, db_index=True)
    # Updated by the unload beacon
    scroll_depth = models.PositiveSmallIntegerField(default=0)  # 0-100
    dwell_ms = models.PositiveIntegerField(default=0)
    # Soft join: if this view is on a blog post, store the slug for cheap aggregation.
    post_slug = models.CharField(max_length=200, blank=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at', 'path']),
            models.Index(fields=['created_at', 'session_id']),
        ]

    def __str__(self):
        return f'{self.created_at:%Y-%m-%d %H:%M} {self.path}'


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
    is_paper_companion = models.BooleanField(
        default=False,
        help_text="Render as a magazine-grade companion essay (Asterisk / Works in Progress register): single column, large serif body, drop cap, real footnotes at bottom, pull-quotes. Use for paper-companion essays where the prose is the artifact.",
    )
    MATURITY_CHOICES = [
        ('', 'Unmarked'),
        ('seedling', 'Seedling — half-formed'),
        ('budding', 'Budding — being developed'),
        ('evergreen', 'Evergreen — settled'),
    ]
    maturity = models.CharField(
        max_length=12, choices=MATURITY_CHOICES, blank=True, default='',
        help_text="Optional digital-garden maturity badge. Sets reader expectations and lets unfinished thinking ship without 'blog-post-as-final-statement' cost.",
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
