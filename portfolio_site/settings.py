"""
Django settings for portfolio_site project.

Optional environment variables:
    ANTHROPIC_API_KEY   Enables the "Ask this post" reader chat
                        (see portfolio/views/ask.py). When unset, the
                        /blog/<slug>/ask/ endpoint returns HTTP 503
                        `{"error": "chat_offline"}` and the reader-side
                        UI falls back to a "chat offline" message. No
                        other part of the site depends on this key.
    WEBMENTIONS_ENABLED "1" / "true" / "yes" to enable the webmention.io
                        round-trip on every blog-post view. Defaults off
                        so uncached views stay fast.
    DATABASE_URL        Postgres connection string. Falls back to local
                        SQLite (db.sqlite3) when unset.
    SECRET_KEY          Django secret. Has a dev default baked in.
    DEBUG               "True"/"False". Defaults "True".
    ALLOWED_HOSTS       Comma-separated. Defaults to "*" for dev.
"""

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# SECRET_KEY MUST come from the environment in production. In dev
# (DEBUG=True, the default) we use a constant LOCAL-ONLY sentinel so
# `manage.py test` and `runserver` don't need any setup. The sentinel
# is deliberately *not* a valid-looking secret — GitGuardian scanners
# trip on `django-insecure-<random>` because many people ship that
# fallback to production by accident, and a leaked real-looking
# fallback is a cross-deployment replay risk.
#
# Generate a fresh production key with:
#     python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
# then set SECRET_KEY in the Render dashboard → Environment.
_DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'
if os.environ.get('SECRET_KEY'):
    SECRET_KEY = os.environ['SECRET_KEY']
elif _DEBUG:
    SECRET_KEY = 'local-dev-only-not-a-real-secret'
else:
    raise RuntimeError(
        'SECRET_KEY env var is required when DEBUG=False. '
        'Set it in the Render dashboard → Environment.'
    )

DEBUG = _DEBUG

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'taggit',
    'portfolio',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'portfolio_site.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # portfolio/templates is listed first so our admin/base_site.html
        # override wins over django.contrib.admin's default. Without this,
        # APP_DIRS order puts django.contrib.admin earlier in INSTALLED_APPS
        # and its templates win.
        'DIRS': [BASE_DIR / 'portfolio' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.messages.context_processors.messages',
                'django.contrib.auth.context_processors.auth',
                'portfolio.context_processors.portfolio_data',
            ],
        },
    },
]

WSGI_APPLICATION = 'portfolio_site.wsgi.application'

# Database: use DATABASE_URL env var (Neon PostgreSQL) or SQLite for local dev
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=60),
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# During tests, fall back to the basic static storage so {% static %}
# lookups don't need a pre-built manifest. Tests assert behavior, not
# the production storage backend.
import sys as _sys
if 'test' in _sys.argv or any('pytest' in a for a in _sys.argv):
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# Local in-memory cache. Per-process — Render's free tier runs a single
# gunicorn worker so this is fine; if/when we scale to multiple workers,
# swap in a shared backend (Redis, Memcached). Used by:
#   - blog.get_all_posts()      (10-min TTL, invalidated on Post save)
#   - analytics._fetch_webmentions  (5-min TTL)
#   - DailySalt.for_today        (DB-backed, but cheap)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'phd-website-locmem',
        'TIMEOUT': 600,
    }
}

# Webmentions: off by default. Every blog-post view would otherwise eat
# a 1-2s external round-trip to webmention.io before we got a cached
# miss. Flip WEBMENTIONS_ENABLED=1 on Render after registering the
# domain at webmention.io.
WEBMENTIONS_ENABLED = os.environ.get('WEBMENTIONS_ENABLED', '').lower() in ('1', 'true', 'yes')

# User-uploaded media (avatars, blog cover images, editor body images).
#
# Render's web service has an ephemeral filesystem — every deploy wipes
# whatever was written at runtime. To survive deploys we mirror the
# media tree into Cloudflare R2 (S3-compatible object storage) via
# django-storages, env-gated on R2_BUCKET_NAME so local dev still
# writes to disk.
#
# Minimum env to flip to R2 (set in Render):
#   R2_BUCKET_NAME         — bucket name, e.g. "dl-blog-media"
#   R2_ENDPOINT_URL        — https://<account-id>.r2.cloudflarestorage.com
#   R2_ACCESS_KEY_ID       — from an R2 API token
#   R2_SECRET_ACCESS_KEY   — from an R2 API token
# Optional:
#   R2_PUBLIC_DOMAIN       — public serving domain (r2.dev dev URL or a
#                            Cloudflare-proxied custom subdomain). If
#                            unset, django-storages falls back to signed
#                            URLs via the endpoint.
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

R2_BUCKET_NAME = os.environ.get('R2_BUCKET_NAME', '').strip()
if R2_BUCKET_NAME:
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    AWS_STORAGE_BUCKET_NAME = R2_BUCKET_NAME
    AWS_S3_ENDPOINT_URL = os.environ['R2_ENDPOINT_URL']
    AWS_ACCESS_KEY_ID = os.environ['R2_ACCESS_KEY_ID']
    AWS_SECRET_ACCESS_KEY = os.environ['R2_SECRET_ACCESS_KEY']
    AWS_S3_SIGNATURE_VERSION = 's3v4'
    AWS_S3_ADDRESSING_STYLE = 'virtual'
    # Public-read bucket: no per-object ACLs, no pre-signed URLs on the
    # reader-side — a post's cover image is just a static GET.
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = False
    AWS_S3_FILE_OVERWRITE = False
    _r2_public = os.environ.get('R2_PUBLIC_DOMAIN', '').strip()
    if _r2_public:
        AWS_S3_CUSTOM_DOMAIN = _r2_public
        MEDIA_URL = f'https://{_r2_public}/'

# Local scratch dir for pyfig's per-post dependency installs (pip
# --target). Never written by user uploads, so this can stay on the
# local ephemeral disk even when the rest of MEDIA lives in R2 — the
# worst case is a one-time re-install on the first pyfig render after
# a deploy. Explicitly not BASE_DIR-adjacent so Render's file watcher
# doesn't restart the worker when matplotlib's wheel lands.
PYFIG_CACHE_DIR = Path(os.environ.get('PYFIG_CACHE_DIR') or '/tmp/pyfig-cache')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

TAGGIT_CASE_INSENSITIVE = True

# Public auth routes (portfolio/urls.py wires `accounts/`):
#   /accounts/login/        login (Django built-in)
#   /accounts/logout/       logout
#   /accounts/signup/       custom public signup
#   /accounts/profile/      post-login landing
# After login or signup send users to the profile page, which lists
# any posts they've been granted edit access to.
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/accounts/profile/'
LOGOUT_REDIRECT_URL = '/'
