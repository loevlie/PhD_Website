"""SEO + AI-search surface: sitemap, robots, JSON-LD."""
import json
import re

from django.test import TestCase

from ._helpers import StaffClientMixin, make_post


def extract_json_ld(html):
    """Extract every <script type='application/ld+json'> block as parsed JSON."""
    blocks = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>',
        html, re.S,
    )
    return [json.loads(b.strip()) for b in blocks]


class SitemapTests(TestCase):
    def setUp(self):
        # Need at least one blog post + one tag for tag sitemap to populate
        make_post(slug='hello', title='Hello', tags=['ml', 'tabular'])

    def test_sitemap_returns_xml(self):
        r = self.client.get('/sitemap.xml')
        self.assertEqual(r.status_code, 200)
        self.assertIn('xml', r.headers.get('Content-Type', '').lower())

    def test_sitemap_contains_static_pages(self):
        r = self.client.get('/sitemap.xml')
        content = r.content.decode()
        for path in ('/', '/blog/', '/now/', '/garden/', '/cv/', '/tags/',
                     '/demos/', '/publications/', '/projects/', '/recipes/'):
            self.assertIn(f'{path}</loc>', content, msg=f'missing {path}')

    def test_sitemap_contains_blog_post(self):
        r = self.client.get('/sitemap.xml')
        self.assertIn('/blog/hello/', r.content.decode())

    def test_sitemap_contains_demo_detail(self):
        r = self.client.get('/sitemap.xml')
        # Frozen Forecaster ships in DEMOS
        self.assertIn('/demos/frozen-forecaster/', r.content.decode())

    def test_sitemap_contains_tag_detail(self):
        r = self.client.get('/sitemap.xml')
        self.assertIn('/tags/ml/', r.content.decode())

    def test_sitemap_excludes_admin_surfaces(self):
        r = self.client.get('/sitemap.xml')
        content = r.content.decode()
        for forbidden in ('/admin/', '/site/insights/', '/blog/new/',
                          '/blog/preview/', '/blog/upload-image/',
                          '/blog/hello/edit/', '/a/p', '/a/u'):
            self.assertNotIn(forbidden, content,
                             msg=f'sitemap leaked {forbidden}')


class RobotsTxtTests(TestCase):
    def test_robots_returns_text(self):
        r = self.client.get('/robots.txt')
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/plain', r.headers.get('Content-Type', ''))

    def test_robots_references_sitemap(self):
        r = self.client.get('/robots.txt')
        self.assertIn('Sitemap:', r.content.decode())


class JsonLdHomeTests(TestCase):
    def test_home_has_person_jsonld(self):
        r = self.client.get('/')
        blocks = extract_json_ld(r.content.decode())
        types = []
        for b in blocks:
            if isinstance(b, list):
                types.extend([x.get('@type') for x in b])
            else:
                types.append(b.get('@type'))
        self.assertIn('Person', types)

    def test_home_has_website_jsonld(self):
        r = self.client.get('/')
        blocks = extract_json_ld(r.content.decode())
        types = []
        for b in blocks:
            if isinstance(b, list):
                types.extend([x.get('@type') for x in b])
            else:
                types.append(b.get('@type'))
        self.assertIn('WebSite', types)

    def test_person_jsonld_has_sameas_links(self):
        r = self.client.get('/')
        blocks = extract_json_ld(r.content.decode())
        person = next((b for b in blocks if isinstance(b, dict) and b.get('@type') == 'Person'), None)
        self.assertIsNotNone(person)
        self.assertIsInstance(person.get('sameAs'), list)
        self.assertGreater(len(person['sameAs']), 0)
        # All sameAs values should be valid HTTPS URLs
        for url in person['sameAs']:
            self.assertTrue(url.startswith('http'), msg=f'bad sameAs: {url}')

    def test_person_jsonld_lists_affiliations(self):
        r = self.client.get('/')
        blocks = extract_json_ld(r.content.decode())
        person = next((b for b in blocks if isinstance(b, dict) and b.get('@type') == 'Person'), None)
        self.assertIsNotNone(person.get('affiliation'))


class JsonLdBlogPostTests(TestCase):
    def setUp(self):
        self.post = make_post(slug='jsonld-post', title='Test post', tags=['ml'])

    def test_blog_post_has_article_jsonld(self):
        r = self.client.get(f'/blog/{self.post.slug}/')
        blocks = extract_json_ld(r.content.decode())
        # Find the Article block
        article = None
        for b in blocks:
            if isinstance(b, list):
                for item in b:
                    if 'Article' in (item.get('@type') or []):
                        article = item
                        break
            elif 'Article' in (b.get('@type') or []):
                article = b
        self.assertIsNotNone(article)
        self.assertEqual(article['headline'], 'Test post')
        self.assertIn('author', article)
        self.assertIn('datePublished', article)

    def test_blog_post_has_breadcrumb_jsonld(self):
        r = self.client.get(f'/blog/{self.post.slug}/')
        blocks = extract_json_ld(r.content.decode())
        types = []
        for b in blocks:
            if isinstance(b, list):
                types.extend([x.get('@type') for x in b])
            else:
                types.append(b.get('@type'))
        self.assertIn('BreadcrumbList', types)

    def test_paper_companion_gets_scholarlyarticle_type(self):
        p = make_post(slug='paper-co', title='Paper companion test',
                      is_paper_companion=True)
        r = self.client.get(f'/blog/{p.slug}/')
        blocks = extract_json_ld(r.content.decode())
        for b in blocks:
            items = b if isinstance(b, list) else [b]
            for item in items:
                t = item.get('@type') or []
                if isinstance(t, list) and 'ScholarlyArticle' in t:
                    return  # found it
        self.fail('ScholarlyArticle type missing on is_paper_companion post')
