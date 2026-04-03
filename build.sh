#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

# Build Tailwind CSS for blog
npm install
npx @tailwindcss/cli -i portfolio/static/portfolio/css/blog-input.css -o portfolio/static/portfolio/css/blog-tw.css --minify

python manage.py collectstatic --noinput
python manage.py migrate --noinput
python manage.py import_posts
