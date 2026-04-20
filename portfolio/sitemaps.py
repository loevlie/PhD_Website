from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils.text import slugify

from portfolio.blog import get_all_posts
from portfolio.data import DEMOS


class StaticSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 1.0

    def items(self):
        return ['index']

    def location(self, item):
        return reverse(item)


class BlogSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.8

    def items(self):
        return get_all_posts()

    def location(self, item):
        return reverse('blog_post', args=[item['slug']])

    def lastmod(self, item):
        from datetime import datetime, timezone
        d = item.get('updated') or item['date']
        return datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)


class BlogListSitemap(Sitemap):
    """Static editorial pages. Excludes admin surfaces (/site/insights,
    editor) and dynamic ones that 302 (cv.pdf)."""
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return ['blog', 'publications', 'projects', 'recipes', 'demos',
                'now', 'garden', 'cv_page', 'tag_index']

    def location(self, item):
        return reverse(item)


class DemoDetailSitemap(Sitemap):
    """Each demo's standalone permalink page."""
    changefreq = 'monthly'
    priority = 0.6

    def items(self):
        return DEMOS

    def location(self, item):
        return reverse('demo_detail', args=[item['slug']])


class TagDetailSitemap(Sitemap):
    """Each tag's listing page. Tag slugs derived from the post tag set."""
    changefreq = 'weekly'
    priority = 0.5

    def items(self):
        seen = []
        seen_set = set()
        for p in get_all_posts():
            for t in p.get('tags', []):
                slug = slugify(t)
                if slug and slug not in seen_set:
                    seen_set.add(slug)
                    seen.append(slug)
        return sorted(seen)

    def location(self, slug):
        return reverse('tag_detail', args=[slug])
