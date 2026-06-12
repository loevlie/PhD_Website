"""Pillow-based Open Graph card rendering.

Replaces the previous Playwright/HTML pipeline so cards can be generated
on Render (no chromium dep) AND survive deploys (writes to
default_storage — R2 in prod, local MEDIA_ROOT in dev — instead of the
ephemeral static tree).

Output: 1200×630 PNG written to default_storage at `og/<slug>.png`.
"""
from __future__ import annotations

import io
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


# Bundled TTFs (OFL-licensed) — see portfolio/fonts/.
FONTS_DIR = Path(settings.BASE_DIR) / 'portfolio' / 'fonts'
FONT_TITLE = str(FONTS_DIR / 'IBMPlexSerif-Bold.ttf')
FONT_META = str(FONTS_DIR / 'IBMPlexMono-Regular.ttf')
FONT_BODY = str(FONTS_DIR / 'IBMPlexSans-Medium.ttf')


CARD_W = 1200
CARD_H = 630
PAD_X = 72
PAD_Y = 60

# Brand colors lifted from the prior HTML card template.
COLOR_BG = (10, 37, 64)         # #0A2540 navy
COLOR_TITLE = (245, 245, 242)    # #F5F5F2 off-white
COLOR_META = (138, 163, 194)     # #8AA3C2 cool gray
COLOR_BODY = (201, 210, 220)     # #C9D2DC light slate
COLOR_GRID = (255, 255, 255, 12)  # ~4.7% white for subtle bg grid
COLOR_MATURITY = {
    'seedling': (166, 227, 161),   # #A6E3A1 green
    'budding': (249, 226, 175),    # #F9E2AF amber
    'evergreen': (138, 163, 194),  # #8AA3C2 cool gray
}


def _storage_key(slug: str) -> str:
    return f'og/{slug}.png'


def card_url_for(slug: str) -> str | None:
    """Return the public URL of the persisted card if it exists; else None.

    The fallback (site-wide og-cover.jpg) is the template tag's job —
    this helper sticks to the storage-state truth so callers can branch
    on existence cleanly."""
    key = _storage_key(slug)
    if not default_storage.exists(key):
        return None
    try:
        return default_storage.url(key)
    except Exception:
        return None


def card_exists(slug: str) -> bool:
    return default_storage.exists(_storage_key(slug))


def _kind_label(post: dict) -> str:
    if post.get('is_paper_companion'):
        return 'PAPER COMPANION'
    if post.get('is_explainer'):
        return 'EXPLAINER'
    if post.get('series'):
        return f'SERIES · {post["series"].upper()}'
    return 'NOTE'


def _date_str(post: dict) -> str:
    d = post.get('date')
    if d is None:
        return ''
    try:
        return d.strftime('%b %Y').upper()
    except AttributeError:
        return str(d)


def _wrap_title(draw, text: str, font, max_width: int) -> list[str]:
    """Greedy word-wrap to fit within max_width pixels. Falls back to a
    character-level break for single words that exceed the width."""
    words = (text or '').split()
    if not words:
        return ['']
    lines: list[str] = []
    cur = words[0]
    for w in words[1:]:
        trial = cur + ' ' + w
        bbox = draw.textbbox((0, 0), trial, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def _title_font_for(text: str) -> 'ImageFont.FreeTypeFont':
    """Pick a title size that keeps the visible title to ~3 lines max.

    The old HTML version used 64/56/48 based on length; this mirrors
    that with conservative thresholds."""
    from PIL import ImageFont
    n = len(text or '')
    if n > 90:
        size = 48
    elif n > 55:
        size = 56
    else:
        size = 64
    return ImageFont.truetype(FONT_TITLE, size)


def render_card_png(post: dict) -> bytes:
    """Render a single post's OG card to PNG bytes."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new('RGB', (CARD_W, CARD_H), COLOR_BG)
    overlay = Image.new('RGBA', (CARD_W, CARD_H), (0, 0, 0, 0))
    draw_o = ImageDraw.Draw(overlay)
    # Subtle 48px grid — same as the HTML template.
    for x in range(0, CARD_W, 48):
        draw_o.line([(x, 0), (x, CARD_H)], fill=COLOR_GRID, width=1)
    for y in range(0, CARD_H, 48):
        draw_o.line([(0, y), (CARD_W, y)], fill=COLOR_GRID, width=1)
    img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')

    draw = ImageDraw.Draw(img)
    meta_font = ImageFont.truetype(FONT_META, 20)
    body_font = ImageFont.truetype(FONT_BODY, 22)
    body_small = ImageFont.truetype(FONT_META, 14)
    footer_serif = ImageFont.truetype(FONT_TITLE, 26)
    footer_host = ImageFont.truetype(FONT_META, 16)

    # ── Eyebrow row ─────────────────────────────────────────────────
    kind = _kind_label(post)
    date_str = _date_str(post)
    rt = post.get('reading_time') or 1
    rt_str = f'{rt} MIN READ'
    parts = [kind, date_str, rt_str]
    parts = [p for p in parts if p]
    eyebrow = '  ·  '.join(parts)
    draw.text((PAD_X, PAD_Y), eyebrow, font=meta_font, fill=COLOR_META)

    # Maturity pill — positioned to the right of the eyebrow row.
    maturity = (post.get('maturity') or '').strip()
    if maturity in COLOR_MATURITY:
        color = COLOR_MATURITY[maturity]
        eb_bbox = draw.textbbox((PAD_X, PAD_Y), eyebrow, font=meta_font)
        pill_x = eb_bbox[2] + 20
        pill_y = PAD_Y - 2
        pill_text = maturity.upper()
        pill_pad = (12, 6)
        pt_bbox = draw.textbbox((0, 0), pill_text, font=meta_font)
        pw = (pt_bbox[2] - pt_bbox[0]) + pill_pad[0] * 2
        ph = (pt_bbox[3] - pt_bbox[1]) + pill_pad[1] * 2
        draw.rectangle(
            [pill_x, pill_y, pill_x + pw, pill_y + ph],
            outline=color, width=2,
        )
        draw.text((pill_x + pill_pad[0], pill_y + pill_pad[1] - 4),
                  pill_text, font=meta_font, fill=color)

    # ── Title (vertically centered in the middle band) ──────────────
    title = post.get('title') or 'Untitled'
    title_font = _title_font_for(title)
    max_title_width = CARD_W - PAD_X * 2
    lines = _wrap_title(draw, title, title_font, max_title_width)
    # Cap at 3 lines so the footer always has room — truncate with an
    # ellipsis if a long title overruns.
    if len(lines) > 3:
        lines = lines[:3]
        # Try to give the last line a visible truncation cue.
        last = lines[-1]
        while last:
            trial = last + '…'
            bb = draw.textbbox((0, 0), trial, font=title_font)
            if (bb[2] - bb[0]) <= max_title_width:
                lines[-1] = trial
                break
            last = last[:-1]
    # Vertical center: figure out total height of the block.
    line_metrics = [draw.textbbox((0, 0), ln, font=title_font) for ln in lines]
    line_heights = [bb[3] - bb[1] for bb in line_metrics]
    total_h = sum(line_heights) + 14 * (len(lines) - 1)
    y = (CARD_H - total_h) // 2 - 10  # nudge slightly above true center
    for ln, h in zip(lines, line_heights):
        draw.text((PAD_X, y), ln, font=title_font, fill=COLOR_TITLE)
        y += h + 14

    # ── Footer ──────────────────────────────────────────────────────
    footer_y = CARD_H - PAD_Y - 60
    draw.text((PAD_X, footer_y), 'Dennis Loevlie', font=footer_serif, fill=COLOR_TITLE)
    draw.text((PAD_X, footer_y + 38), 'ELLIS PhD · TABULAR FOUNDATION MODELS',
              font=body_small, fill=COLOR_META)

    slug = (post.get('slug') or '').strip()
    host_text = f'dennisloevlie.com/blog/{slug}/'
    host_bbox = draw.textbbox((0, 0), host_text, font=footer_host)
    host_x = CARD_W - PAD_X - (host_bbox[2] - host_bbox[0])
    draw.text((host_x, footer_y + 38), host_text,
              font=footer_host, fill=COLOR_META)

    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    return buf.getvalue()


def generate_card(post: dict) -> str:
    """Render + persist a card for `post`. Returns the storage key.

    Overwrites any existing card; callers gate on `card_exists` when
    they want a no-op fallback."""
    png = render_card_png(post)
    key = _storage_key(post.get('slug') or '')
    if default_storage.exists(key):
        default_storage.delete(key)
    default_storage.save(key, ContentFile(png))
    return key


def delete_card(slug: str) -> bool:
    """Drop the persisted card for `slug`. Returns True if a file was
    removed (idempotent — missing key returns False)."""
    key = _storage_key(slug)
    if not default_storage.exists(key):
        return False
    try:
        default_storage.delete(key)
        return True
    except Exception:
        return False
