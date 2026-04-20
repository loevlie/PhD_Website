"""Generate per-post OG (Open Graph) social-share images.

Each blog post gets a 1200×630 PNG rendered from a branded HTML template
and screenshot via Playwright. Output lands in
portfolio/static/portfolio/images/og/<slug>.png and is referenced from
blog_post.html via the og_image_url template tag (with site-cover fallback).

Usage:
    python manage.py generate_og_cards            # all posts
    python manage.py generate_og_cards <slug>     # one post
    python manage.py generate_og_cards --check    # report which need regen

Requires Playwright. Already installed; if missing chromium, run
    python -m playwright install chromium

Brand: navy #0A2540 background, IBM Plex Serif title, IBM Plex Mono meta.
"""
from __future__ import annotations

import html
import os
from pathlib import Path

from django.core.management.base import BaseCommand
from django.conf import settings

from portfolio.blog import get_all_posts


OG_OUT_DIR = Path(settings.BASE_DIR) / 'portfolio' / 'static' / 'portfolio' / 'images' / 'og'


CARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Serif:wght@500;700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@600&display=swap" rel="stylesheet">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{
    width: 1200px; height: 630px;
    background: #0A2540;
    color: #F5F5F2;
    font-family: 'IBM Plex Sans', system-ui, sans-serif;
    overflow: hidden;
}}
.card {{
    width: 1200px; height: 630px;
    padding: 60px 72px;
    display: grid;
    grid-template-rows: auto 1fr auto;
    position: relative;
    overflow: hidden;
}}
/* Subtle decorative grid in the background — engineering taste */
.bg-grid {{
    position: absolute; inset: 0;
    background-image:
      linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px);
    background-size: 48px 48px;
    pointer-events: none;
}}
/* Accent gradient blob bottom-right */
.bg-blob {{
    position: absolute;
    right: -120px; bottom: -180px;
    width: 540px; height: 540px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(127, 200, 255, 0.42), rgba(127, 200, 255, 0) 70%);
    pointer-events: none;
}}
.eyebrow {{
    display: flex; align-items: center; gap: 14px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 18px;
    color: #8AA3C2;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    z-index: 1;
}}
.maturity {{
    display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 10px;
    border: 1px solid currentColor;
    border-radius: 4px;
    font-size: 14px;
    letter-spacing: 0.1em;
}}
.maturity.seedling {{ color: #A6E3A1; }}
.maturity.budding {{ color: #F9E2AF; }}
.maturity.evergreen {{ color: #8AA3C2; }}
.title {{
    font-family: 'IBM Plex Serif', Georgia, serif;
    font-weight: 700;
    line-height: 1.05;
    font-size: 64px;
    letter-spacing: -0.02em;
    color: #F5F5F2;
    align-self: center;
    z-index: 1;
}}
.title.long {{ font-size: 56px; }}
.title.xlong {{ font-size: 48px; }}
.excerpt {{
    margin-top: 18px;
    font-size: 22px;
    line-height: 1.4;
    color: #C9D2DC;
    max-width: 950px;
    z-index: 1;
}}
.footer {{
    display: flex; justify-content: space-between; align-items: end;
    z-index: 1;
}}
.author {{
    font-family: 'IBM Plex Serif', Georgia, serif;
    font-size: 24px;
    font-weight: 500;
}}
.author small {{
    display: block;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 14px;
    color: #8AA3C2;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    margin-top: 4px;
    font-weight: 400;
}}
.host {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 16px;
    color: #8AA3C2;
}}
.host b {{ color: #F5F5F2; font-weight: 500; }}
</style>
</head>
<body>
<div class="card">
    <div class="bg-grid"></div>
    <div class="bg-blob"></div>
    <div class="eyebrow">
        <span>{kind}</span>
        {maturity_tag}
        <span>· {date}</span>
        <span>· {reading_time}</span>
    </div>
    <h1 class="title {title_class}">{title}</h1>
    <div class="footer">
        <div class="author">
            Dennis Loevlie
            <small>ELLIS PhD · Tabular Foundation Models</small>
        </div>
        <div class="host">dennisloevlie.com<b>/blog/{slug}/</b></div>
    </div>
</div>
</body>
</html>
"""


def _title_class(title: str) -> str:
    n = len(title)
    if n > 90:
        return 'xlong'
    if n > 55:
        return 'long'
    return ''


def _kind_for(post: dict) -> str:
    if post.get('is_paper_companion'):
        return 'Paper companion'
    if post.get('is_explainer'):
        return 'Explainer'
    if post.get('series'):
        return f'Series · {post["series"]}'
    return 'Note'


def render_card_html(post: dict) -> str:
    title = post.get('title', 'Untitled')
    slug = post.get('slug', '')
    date = post.get('date')
    date_str = date.strftime('%b %Y') if hasattr(date, 'strftime') else str(date)
    reading_time = post.get('reading_time') or 1
    rt_str = f'{reading_time} min read'
    maturity = (post.get('maturity') or '').strip()
    maturity_tag = (
        f'<span class="maturity {maturity}">{maturity}</span>'
        if maturity in {'seedling', 'budding', 'evergreen'} else ''
    )
    return CARD_HTML.format(
        kind=html.escape(_kind_for(post)),
        maturity_tag=maturity_tag,
        date=html.escape(date_str),
        reading_time=html.escape(rt_str),
        title=html.escape(title),
        title_class=_title_class(title),
        slug=html.escape(slug),
    )


class Command(BaseCommand):
    help = 'Generate per-post Open Graph social-share PNGs (1200×630).'

    def add_arguments(self, parser):
        parser.add_argument('slug', nargs='?', help='Optional slug to regenerate one post.')
        parser.add_argument('--check', action='store_true', help='List which posts would be generated; do not write anything.')
        parser.add_argument('--force', action='store_true', help='Regenerate even if PNG already exists.')

    def handle(self, *args, slug=None, check=False, force=False, **opts):
        OG_OUT_DIR.mkdir(parents=True, exist_ok=True)
        posts = get_all_posts()
        if slug:
            posts = [p for p in posts if p.get('slug') == slug]
            if not posts:
                self.stderr.write(self.style.ERROR(f'No post with slug "{slug}"'))
                return

        to_render = []
        for p in posts:
            out = OG_OUT_DIR / f'{p["slug"]}.png'
            if out.exists() and not force:
                self.stdout.write(f'  [skip] {p["slug"]} ({out.name} exists)')
                continue
            to_render.append((p, out))

        self.stdout.write(self.style.MIGRATE_HEADING(f'\nWill generate {len(to_render)} of {len(posts)} cards.'))

        if check:
            for p, out in to_render:
                self.stdout.write(f'  [would] {p["slug"]} → {out.relative_to(settings.BASE_DIR)}')
            return
        if not to_render:
            return

        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            ctx = browser.new_context(viewport={'width': 1200, 'height': 630}, device_scale_factor=2)
            page = ctx.new_page()
            for p, out in to_render:
                page.set_content(render_card_html(p), wait_until='networkidle', timeout=15000)
                # Tiny delay to let webfonts settle even if networkidle fired
                page.wait_for_timeout(250)
                page.screenshot(path=str(out), full_page=False, omit_background=False)
                self.stdout.write(self.style.SUCCESS(f'  [ok]  {p["slug"]} → {out.name}'))
            browser.close()

        self.stdout.write(self.style.SUCCESS(f'\nDone. Wrote {len(to_render)} cards to {OG_OUT_DIR.relative_to(settings.BASE_DIR)}.'))
