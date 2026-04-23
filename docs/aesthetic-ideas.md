# Aesthetic improvements — backlog

Captured 2026-04-22 from a visual analysis of
<https://flow-based-llms.github.io/> (a research post by Floor
Eijkelboom). Ordered by ROI. Not implemented yet; revisit when the
editor / analytics work is stable.

## Reference palette + fonts observed

- **Paper**: warm off-white `#FBFAF6` (bg), near-black ink `#1A1917`
- **Body prose muted**: warm grey `#6B6862`
- **Accent link**: navy `#1E3A5F`
- **Code background**: parchment tint `#F3F1EA`
- Fonts: Instrument Serif (display), Fraunces (body, weight 350),
  Inter Tight (UI / captions / ToC), JetBrains Mono (code).

---

## 1. Sticky left-gutter ToC with uppercase kickers + accent rail — HIGH ROI

We already ship `#sidebar-toc-left` on explainer posts. Upgrades:

- **Uppercase tracked kickers** for top-level items
  (`letter-spacing: 0.1em; font-variant: small-caps`), so sections read
  as "PHASE 1: LEARNING THE FLOW" rather than "Phase 1".
- **2px accent bar** (`var(--ctp-lavender)` / Catppuccin accent) pinned
  on the active item, sliding between items with a smooth transition.
- **Sub-items indented and quieter** — 0.85em, `color: var(--text-muted)`.
- Consider wrapping adjacent `<h2>…<h2>` spans into logical "chapters"
  so the kicker corresponds to a semantic block, not just a heading
  level.

**Cost**: CSS-only for the first two; a tiny JS upgrade for the sliding
accent bar via IntersectionObserver. ~1-2 hours.

## 2. Typography upgrade on explainer posts — HIGH-MED ROI

Current stack: IBM Plex Serif body, Inter UI. Solid but reads
"paper-companion," not "essay." Try:

- `Instrument Serif` (or `Fraunces` Variable) for **display** headings
  at weight 400, tight tracking, and mix roman + *italic* on the same
  line (e.g. `<h1>Part one: <em>what we tried</em></h1>`).
- `Fraunces` weight 350 for body prose — light but highly readable on
  off-white backgrounds.
- `Inter Tight` for small UI: TOC, captions, metadata.
- Keep Plex Serif as the `is-paper-companion` register (it's already
  tuned for that).
- Honor the existing Catppuccin palette — Latte flavor maps cleanly
  onto the warm-paper aesthetic.

**Cost**: font loading + a per-variant CSS override. ~2 hours.

## 3. TL;DR tinted card + between-section chapter interstitials — MEDIUM ROI

Two structural moves that break long explainer posts into acts:

- **TL;DR card** at the top of the post: a tinted
  `<aside class="tldr">` with serif italic copy, background
  `color-mix(in srgb, var(--accent-lavender) 8%, transparent)`,
  2-3 sentence summary. Surface the existing TL;DR from
  `post.excerpt`, or add a new optional `post.tldr_body` field for
  richer framing than the card-sized excerpt.
- **Chapter interstitials**: a centered, small-caps kicker between
  major sections — `<hr class="chapter-break" data-kicker="Phase 2: scaling up">`.
  Breaks 15-minute reads into digestible arcs.

**Cost**: new embed marker + CSS + one migration for the optional
field. ~3 hours.

## Low-priority but interesting

- **Interactive inline SVG** (e.g. a 1-D slider moving through a
  probability distribution). Infrastructure is already there via
  pyfig + pyodide cells — just needs a marker convention like
  `<div data-slider="…">`.
- **Mix roman + italic inside `<h1>`** (see typography note above).
  Zero code cost if heading tags allow `<em>` children — and they do.

## Non-goals / things NOT to adopt

- Right-hand sidenotes — flow-based-llms uses endnotes, but our
  Tufte-style sidenote system is a distinctive strength. Keep it.
- Abandoning dark mode — they don't ship one; we should. Catppuccin
  Mocha is already wired.
- Heavy animation on page load — at odds with fast preview +
  typographic feel.

## Ordering recommendation

1. Typography upgrade (small, visible, doesn't break anything).
2. Sticky-TOC polish (improves navigation on long posts).
3. TL;DR card + chapter interstitials (needs a model change, pair
   with a content pass).
