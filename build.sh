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
