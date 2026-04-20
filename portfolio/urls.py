from django.contrib.sitemaps.views import sitemap
from django.urls import path

from . import views, analytics, analytics_dashboard
from .feeds import BlogFeed
from .sitemaps import StaticSitemap, BlogSitemap, BlogListSitemap, DemoDetailSitemap, TagDetailSitemap

sitemaps = {
    'static': StaticSitemap,
    'blog': BlogSitemap,
    'pages': BlogListSitemap,
    'demos': DemoDetailSitemap,
    'tags': TagDetailSitemap,
}

urlpatterns = [
    path('', views.index, name='index'),
    path('recipes/', views.recipes, name='recipes'),
    path('recipes/<slug:slug>/', views.recipe_detail, name='recipe_detail'),
    path('blog/', views.blog, name='blog'),
    path('blog/feed/', BlogFeed(), name='blog_feed'),
    path('blog/new/', views.blog_new, name='blog_new'),
    path('blog/preview/', views.blog_preview, name='blog_preview'),
    path('blog/upload-image/', views.blog_upload_image, name='blog_upload_image'),
    path('blog/<slug:slug>/', views.blog_post, name='blog_post'),
    path('blog/<slug:slug>/edit/', views.blog_edit, name='blog_edit'),
    path('blog/<slug:slug>/autosave/', views.blog_autosave, name='blog_autosave'),
    path('publications/', views.publications, name='publications'),
    path('projects/', views.projects, name='projects'),
    path('demos/', views.demos, name='demos'),
    path('demos/<slug:slug>/', views.demo_detail, name='demo_detail'),
    path('now/', views.now, name='now'),
    path('garden/', views.garden, name='garden'),
    path('tags/', views.tag_index, name='tag_index'),
    path('tags/<slug:slug>/', views.tag_detail, name='tag_detail'),
    path('cv/', views.cv_page, name='cv_page'),
    path('cv.pdf', views.download_cv, name='download_cv'),
    # First-party privacy analytics. /a/p posts pageviews, /a/u updates
    # scroll/dwell on unload. Both are CSRF-exempt and respect DNT.
    # Dashboard lives under /site/insights/ — staff-only, kept off the
    # public-looking part of the URL space.
    path('a/p', analytics.beacon_pageview, name='analytics_beacon_pageview'),
    path('a/u', analytics.beacon_update, name='analytics_beacon_update'),
    path('site/insights/', analytics_dashboard.dashboard, name='analytics_dashboard'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('presentations/<slug:slug>/', views.presentation, name='presentation'),
    path('googled2e3ddb216daf4c4.html', views.google_verify, name='google_verify'),
]
