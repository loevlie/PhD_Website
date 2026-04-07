from django.contrib.sitemaps.views import sitemap
from django.urls import path

from . import views
from .feeds import BlogFeed
from .sitemaps import StaticSitemap, BlogSitemap, BlogListSitemap

sitemaps = {
    'static': StaticSitemap,
    'blog': BlogSitemap,
    'pages': BlogListSitemap,
}

urlpatterns = [
    path('', views.index, name='index'),
    path('recipes/', views.recipes, name='recipes'),
    path('recipes/<slug:slug>/', views.recipe_detail, name='recipe_detail'),
    path('blog/', views.blog, name='blog'),
    path('blog/feed/', BlogFeed(), name='blog_feed'),
    path('blog/<slug:slug>/', views.blog_post, name='blog_post'),
    path('publications/', views.publications, name='publications'),
    path('projects/', views.projects, name='projects'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('presentations/<slug:slug>/', views.presentation, name='presentation'),
    path('googled2e3ddb216daf4c4.html', views.google_verify, name='google_verify'),
]
