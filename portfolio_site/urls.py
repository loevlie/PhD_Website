"""URL configuration for portfolio_site project."""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve as serve_static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('portfolio.urls')),
]

# Serve user-uploaded media (editor image uploads) and pyfig-generated
# PNGs from /media/ in BOTH dev and production. The Django static
# `serve` view is well-tested and fine for a low-traffic personal site.
# WhiteNoise handles /static/ separately (collected at deploy time);
# media is generated at runtime so collectstatic can't pre-process it.
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve_static,
            {'document_root': settings.MEDIA_ROOT}),
]
