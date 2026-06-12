#!/usr/bin/env bash
set -o errexit

# Tailwind: blog-tw.css is pre-built and committed to the repo, so the
# deploy image doesn't need npm/node. To regenerate locally after
# adding new utility classes in a template, run:  npm run build:tw
# (input: portfolio/static/portfolio/css/blog-tw.input.css)

pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
python manage.py import_posts
# Backfill OG cards for every post missing one. The post_save signal
# auto-mints cards going forward; this catches the long tail of posts
# that pre-date the signal so they ship with their branded card too.
python manage.py generate_og_cards || true
