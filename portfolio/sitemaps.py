from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from portfolio.blog import get_all_posts


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
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return ['blog', 'publications', 'projects', 'recipes']

    def location(self, item):
        return reverse(item)
