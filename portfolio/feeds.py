from django.contrib.syndication.views import Feed
from django.urls import reverse

from portfolio.blog import get_all_posts


class BlogFeed(Feed):
    title = "Dennis Loevlie — Blog"
    link = "/blog/"
    description = "Thoughts on ML research, deep learning, and software engineering."

    def items(self):
        return get_all_posts()[:20]

    def item_title(self, item):
        return item['title']

    def item_description(self, item):
        return item['excerpt']

    def item_link(self, item):
        return reverse('blog_post', args=[item['slug']])

    def item_pubdate(self, item):
        from datetime import datetime, timezone
        return datetime.combine(item['date'], datetime.min.time(), tzinfo=timezone.utc)

    def item_updateddate(self, item):
        if item.get('updated'):
            from datetime import datetime, timezone
            return datetime.combine(item['updated'], datetime.min.time(), tzinfo=timezone.utc)
        return None
