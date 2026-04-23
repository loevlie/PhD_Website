from django.db import models
from django.urls import reverse

from taggit.managers import TaggableManager


# ─── Content models (promoted from portfolio/content/*.py) ────────────
#
# These seven models replace the module-level Python constants in
# portfolio/content/. They keep the legacy data.py / content.* modules
# as the canonical seed (see `manage.py seed_content`) but the DB wins
# once any row exists — so the admin can edit without a redeploy.
#
# Design notes:
#   * `display_order` is the explicit manual sort; lower = higher up.
#     Ties broken by the model-specific secondary key (year/date).
#   * `draft=True` hides a row from the public surface. Staff still see
#     drafts with a "Draft" pill (same pattern as Post.draft).
#   * We do NOT mirror every Python field 1:1 — some (e.g. Project.tags
#     as a list) flatten into a CSV CharField so the admin list-view is
#     scannable. A future migration can promote to a M2M if needed.


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

    # Routes the post to the right surface:
    #   essay     → /blog/      (polished long-form)
    #   lab_note  → /notebook/  (open research log, status-tagged)
    # Garden is orthogonal (filters by `maturity`, not `kind`), so a post
    # can be both a lab_note AND seedling without conflict.
    KIND_CHOICES = [
        ('essay', 'Essay (long-form, /blog/)'),
        ('lab_note', 'Lab note (open log, /notebook/)'),
    ]
    kind = models.CharField(
        max_length=16, choices=KIND_CHOICES, default='essay',
        help_text="Which surface this post belongs to. Essays go to /blog/; lab notes go to /notebook/. Garden is orthogonal.",
    )
    # Per-post collaborators: authenticated non-staff users who can
    # edit this specific post (and only this one). Staff + superusers
    # can always edit any post; this M2M is the narrow grant we use
    # when handing a single post off to a guest contributor.
    #
    # The reverse accessor on User is `user.edit_posts` — used by the
    # editor helper endpoints that aren't slug-scoped (smart_paste,
    # check_word) to decide whether the caller has *any* editable post.
    collaborators = models.ManyToManyField(
        'auth.User', blank=True, related_name='edit_posts',
        help_text="Non-staff users who can edit this specific post.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    # Persisted render output. Updated by the post_save signal so a cold
    # dyno / fresh deploy serves blog posts without re-running pyfig
    # subprocesses on the first request. Stays NULL until the first
    # successful render; falls back to live render in get_post() when
    # missing or stale (modified_at > rendered_at).
    rendered_html = models.TextField(blank=True, default='')
    rendered_toc_html = models.TextField(blank=True, default='')
    rendered_at = models.DateTimeField(null=True, blank=True)

    tags = TaggableManager(blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('blog_post', args=[self.slug])


class Reading(models.Model):
    """A paper / essay / book Dennis is recommending. Drives the /reading/
    page. Independent from Post — these are external recommendations, not
    his own writing. Edit via the Django admin (no in-browser editor for
    these yet — they're rare enough that admin is fine)."""
    STATUS_CHOICES = [
        ('this_week', 'This week — actively reading'),
        ('lingering', 'Older but still lingering'),
        ('archived', 'Archived (hidden from /reading/)'),
    ]
    title = models.CharField(max_length=300)
    venue = models.CharField(
        max_length=200, blank=True,
        help_text="Where it was published — arXiv id, conference, journal, magazine, etc.",
    )
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    url = models.URLField(blank=True, help_text="Canonical link (arXiv, blog post, etc.)")
    annotation = models.TextField(
        blank=True,
        help_text="One-line note in your own voice — what makes it interesting to you right now.",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='this_week')
    # Manual sort within a status bucket so you can promote a particular
    # paper to the top without re-dating it.
    order = models.IntegerField(
        default=0,
        help_text="Lower = higher in the list within its status bucket. Ties broken by created_at desc.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    # If this entry was matched to a Mind Mapper note, the MM note id.
    # As of 2026-04 the sync NEVER creates Reading rows — it only decorates
    # manually-added rows with the MM note's annotation (see `mm_annotation`
    # below). The id is just a pointer so sync updates the same note's
    # annotation on re-run instead of attaching duplicates.
    mind_mapper_note_id = models.PositiveIntegerField(null=True, blank=True, unique=True, db_index=True)
    mm_annotation = models.TextField(
        blank=True,
        help_text="Optional annotation sourced from a matched Mind Mapper note. "
                  "Shown beneath your own annotation on /reading/. Overwritten "
                  "on every `sync_reading` run; edit in Mind Mapper, not here.",
    )

    class Meta:
        ordering = ['order', '-created_at']
        verbose_name = 'Reading entry'
        verbose_name_plural = 'Reading entries'

    def __str__(self):
        return self.title


# ─── Site content models ──────────────────────────────────────────────


class NewsItem(models.Model):
    """One bullet under /#news. `text` is HTML (links already embedded)."""
    date = models.CharField(
        max_length=40,
        help_text="Display string, e.g. '2026' or 'Apr 2026'. Stored as string so you can write '2026 —' or 'Spring 2025'.",
    )
    text = models.TextField(help_text="HTML allowed. Kept short: one bullet's worth.")
    highlight = models.BooleanField(
        default=False,
        help_text="Render with the accent left-rule treatment for top items.",
    )
    display_order = models.IntegerField(
        default=0,
        help_text="Lower = higher in the list.",
    )
    draft = models.BooleanField(default=False, help_text="Hidden from the public homepage.")
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', '-created_at']
        verbose_name = 'News item'
        verbose_name_plural = 'News items'

    def __str__(self):
        return f'{self.date}: {self.text[:60]}'


class Publication(models.Model):
    """One publication / poster. Child PublicationLink rows hold the
    Paper / Code / Poster URLs."""
    TYPE_CHOICES = [
        ('conference', 'Conference paper'),
        ('journal', 'Journal article'),
        ('poster', 'Poster'),
        ('preprint', 'Preprint'),
        ('thesis', 'Thesis'),
        ('workshop', 'Workshop paper'),
    ]
    title = models.CharField(max_length=500)
    authors = models.CharField(
        max_length=500,
        help_text="Comma-separated author list. Use the author's name as you'd like it shown.",
    )
    venue = models.CharField(max_length=300, blank=True)
    year = models.PositiveSmallIntegerField()
    pub_type = models.CharField(
        max_length=24, choices=TYPE_CHOICES, default='conference',
        help_text="Drives the 'Conference'/'Journal'/'Poster' pill on publication cards.",
    )
    selected = models.BooleanField(
        default=False,
        help_text="Promote to the homepage Selected Publications block.",
    )
    image = models.CharField(
        max_length=400, blank=True,
        help_text="Static-files path, e.g. 'portfolio/images/cover_acr.jpeg'. Required when selected=True.",
    )
    image_credit = models.CharField(max_length=300, blank=True)
    bibtex = models.TextField(blank=True)
    display_order = models.IntegerField(default=0, help_text="Lower = higher in the list.")
    draft = models.BooleanField(default=False, help_text="Hidden from public pages.")
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', '-year']

    def __str__(self):
        return f'{self.title} ({self.year})'

    @property
    def author_list(self):
        """Authors split back into a list — matches the legacy dict shape
        so the existing templates ({{ pub.authors }}) don't change."""
        return [a.strip() for a in self.authors.split(',') if a.strip()]


class PublicationLink(models.Model):
    """Paper / Code / Demo / Poster URL attached to a Publication."""
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE, related_name='link_set')
    label = models.CharField(max_length=40, help_text="e.g. 'Paper', 'Code', 'Poster'.")
    url = models.URLField()
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.label}: {self.url}'


class Project(models.Model):
    """One project card under /#projects and /projects/."""
    title = models.CharField(max_length=200)
    description = models.TextField(help_text="One-paragraph summary; 2–4 sentences is the sweet spot.")
    tags_csv = models.CharField(
        max_length=300, blank=True,
        help_text="Comma-separated tags shown as chips, e.g. 'LLM, Optimization, PyTorch'.",
    )
    github = models.CharField(
        max_length=200, blank=True,
        help_text="GitHub slug, e.g. 'loevlie/neuropt'. Used for star-count badge.",
    )
    language = models.CharField(max_length=40, blank=True)
    featured = models.BooleanField(
        default=False,
        help_text="Surface in the top 6 on /#projects (above the 'Show more' fold).",
    )
    display_order = models.IntegerField(default=0, help_text="Lower = higher in the list.")
    draft = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', '-modified_at']

    def __str__(self):
        return self.title

    @property
    def tags(self):
        return [t.strip() for t in self.tags_csv.split(',') if t.strip()]


class ProjectLink(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='link_set')
    label = models.CharField(max_length=40, help_text="e.g. 'Code', 'Demo', 'Paper'.")
    url = models.URLField()
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.label}: {self.url}'


class TimelineEntry(models.Model):
    """Education + work history row for /#experience."""
    year = models.CharField(max_length=24, help_text="Display range, e.g. '2026 —' or '2021 — 2023'.")
    title = models.CharField(max_length=200)
    org = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    link = models.URLField(blank=True)
    link_label = models.CharField(max_length=80, blank=True)
    display_order = models.IntegerField(default=0, help_text="Lower = higher; newest first.")
    draft = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', '-created_at']
        verbose_name = 'Timeline entry'
        verbose_name_plural = 'Timeline entries'

    def __str__(self):
        return f'{self.year}: {self.title}'


class OpenSourceItem(models.Model):
    """One contribution tile under /#opensource."""
    name = models.CharField(max_length=100)
    description = models.TextField()
    url = models.URLField()
    role = models.CharField(max_length=80, blank=True, help_text="e.g. 'Contributor', 'Maintainer'.")
    display_order = models.IntegerField(default=0)
    draft = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', '-created_at']
        verbose_name = 'Open-source contribution'
        verbose_name_plural = 'Open-source contributions'

    def __str__(self):
        return self.name


class SocialLink(models.Model):
    """A social-profile link shown in the hero/contact block and used
    to build the site-wide Person JSON-LD `sameAs` array."""
    ICON_CHOICES = [
        ('github', 'GitHub'),
        ('scholar', 'Google Scholar'),
        ('linkedin', 'LinkedIn'),
        ('bluesky', 'Bluesky'),
        ('medium', 'Medium'),
        ('twitter', 'Twitter / X'),
        ('email', 'Email'),
    ]
    name = models.CharField(max_length=40)
    url = models.CharField(max_length=400, help_text="Full URL or mailto: link.")
    icon = models.CharField(max_length=24, choices=ICON_CHOICES)
    display_order = models.IntegerField(default=0)
    draft = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'id']

    def __str__(self):
        return self.name


class NowPage(models.Model):
    """Singleton — the content of /now/. Exactly one row should exist;
    `seed_content` upserts it. Sections live in `NowSection` children."""
    updated = models.DateField(help_text="Displayed on the page so readers know how stale it is.")
    location = models.CharField(max_length=120, blank=True)
    draft = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Now page'
        verbose_name_plural = 'Now page'

    def __str__(self):
        return f'/now/ — last updated {self.updated}'

    @classmethod
    def current(cls):
        """Return the singleton or None if never seeded."""
        return cls.objects.order_by('-modified_at').first()


class NowSection(models.Model):
    """One heading+body pair on /now/."""
    now_page = models.ForeignKey(NowPage, on_delete=models.CASCADE, related_name='section_set')
    heading = models.CharField(max_length=100)
    body = models.TextField(help_text="Markdown allowed — rendered at view time.")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.heading} (/now/)'
