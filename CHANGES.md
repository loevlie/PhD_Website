# Design Pass — branch `design-pass-2026-04`

Started 2026-04-19. Working branch off `main` at `973b341`.

**Branch is pushed:** https://github.com/loevlie/PhD_Website/tree/design-pass-2026-04 — open a PR or just `git checkout` it locally to review.

**Revert everything:**
```bash
git checkout main
git branch -D design-pass-2026-04
git push origin --delete design-pass-2026-04   # if you want it gone from GH too
```

**See it live (locally):** dev server is running at http://127.0.0.1:8000/. Most interesting URLs:
- Homepage with new "What I'm thinking about" section: http://127.0.0.1:8000/
- Lab notebook (rewritten /demos/): http://127.0.0.1:8000/demos/
- Explainer template smoke test (sidenotes + citations + math): http://127.0.0.1:8000/blog/explainer-template-test/

This file is the running log. Each change has: **what**, **why**, **files touched**, **how to undo just that piece**.

---

## TL;DR — what changed

**Infrastructure (new capabilities):**
- Tufte-style sidenotes for explainer posts (auto-generated from standard markdown footnote syntax).
- Distill-style hover-citation popovers (one JSON manifest seeds every reference site-wide).
- `is_explainer` flag on `Post` model + migration → opts a post into the heavier chrome.
- Explainer template variant (collapsible top ToC, wider canvas, Explainer badge, sidenote-friendly layout).
- Demos page rewritten as a dated lab notebook driven by `DEMOS` list in `data.py`. Each entry: what / why / what I learned.
- New homepage section: "What I'm thinking about" — research-taste signal, three serif paragraphs, dated.

**Aesthetic / animation modernization:**
- OKLCH color tokens (perceptually uniform tints; replaced sRGB color-mix everywhere).
- New tokens: `--focus-ring`, `--sidenote-color`, `--sidenote-marker`.
- Native scroll-driven CSS animations expanded (`.section-reveal` utility, hero parallax).
- Named view-transition for the avatar (homepage ↔ blog page morph).
- Killed JS mousemove tilt + magnetic-cursor effects (Webflow tells); replaced with CSS-only hover lift.
- Fluid `clamp()` typography on the hero name (28 px → 56 px without breakpoint jumps).
- Trimmed top nav from 6 to 5 items, re-grouped children semantically.
- Global `prefers-reduced-motion` guard.

**Performance polish:**
- `content-visibility: auto` for below-the-fold sections (LCP/INP win on long pages).
- Async-load Google Fonts CSS + preload the two critical IBM Plex weights.

**Deferred (need user input):**
- 22 MB hero PNG → AVIF/WebP. Need lossless source. Tracked in Mind Mapper note 65.
- 3 MB hero avatar video. Same — needs source to re-encode.

## Numbers

Local Lighthouse on `127.0.0.1:8000/` after the design pass:

| | Before (live) | After (local) | Note |
|---|---|---|---|
| Performance | 56 | 59 | Local can't fix the 22 MB PNG; needs the source-file work to move materially |
| Accessibility | 94 | 94 | Unchanged |
| Best-Practices | 100 | 100 | Unchanged |
| SEO | 100 | 100 | Unchanged |
| FCP | 1.1 s | 0.8 s | Async-load fonts + preload helped |
| LCP | 19.1 s | 19.1 s | **Hero PNG still dominates** — re-encoding it is the only thing that moves this |
| CLS | 0.28 | 0.30 | Slightly worse — new sections shift layout. Sidenote: also dominated by the hero swap; needs the same fix |
| TBT | 0 ms | 0 ms | Unchanged (JS workload was never the issue) |

The performance story is unchanged because we deferred the dominant cost (the hero image). Once the lossless source is available, the deferred work in Mind Mapper note 65 will take Performance to 95+.

The **aesthetic and capability** story is the substantive change in this branch — see the per-item changelog below.



---

## Goals

1. Modernize animations using native 2025 CSS (scroll-driven animations, view transitions, OKLCH).
2. Add Tufte/Distill-style sidenote + hover-citation infrastructure.
3. Add `is_explainer` post type that opts into the heavier chrome.
4. Convert `/demos/` from hand-authored HTML to data-driven lab notebook.
5. Cut "Webflow template tell" effects (3D tilt, magnetic cursor).
6. Cheap perf wins (content-visibility, font preload, reduced-motion guards).
7. Trim navigation.

Big-rock perf items (22 MB hero PNG, 3 MB avatar video) are deferred — need lossless source files; tracked in Mind Mapper note 65.

---

## Changelog

### 1. OKLCH color tokens + new design tokens

**What:** Migrated `--accent-*` tint ramp from `color-mix(in srgb, ...)` to `color-mix(in oklch, ...)` so derived tints/hovers stay perceptually uniform. Expanded ramp from 4 stops to 6 (`--accent-05/10/20/50/80/95`). Kept `--accent-90` as a back-compat alias. Added two new tokens: `--focus-ring` (3px ring derived from accent for `:focus-visible`) and a sidenote-specific palette (`--sidenote-color`, `--sidenote-marker`, `--sidenote-bg`).

**Why:** OKLCH mixing produces cleaner tints than sRGB (no muddy mid-tones). New tokens unblock the sidenote and citation work.

**Files:** `portfolio/static/portfolio/css/variables.css`

**Undo just this:** `git checkout main -- portfolio/static/portfolio/css/variables.css`

### 2. Sidenote infrastructure (CSS + Python markdown post-processor)

**What:**
- New CSS section in `blog.css` for `.sidenote`, `.cite-popover`, `cite.ref`, `.explainer-badge`. Sidenotes are inline+italic on mobile, floated into the right margin (`margin-right: -240px`) on `≥1024px` viewports, only when the article has class `.is-explainer`.
- New Python helper `_transform_footnotes_to_sidenotes()` in `portfolio/blog/__init__.py` that for explainer posts converts `<sup class="footnote-ref">N</sup>` markers into adjacent `<aside class="sidenote">` blocks, sourced from the standard markdown `[^slug]: ...` footnote markup.
- `render_markdown(content, is_explainer=False)` now accepts the flag; `_post_to_dict` and `_parse_file_post` plumb it through from the model / frontmatter.
- Added `'footnotes'` to the markdown extension list so `[^slug]` syntax compiles.

**Why:** Authors write standard markdown footnotes — same source renders as classic numbered footnotes on regular posts and as Tufte/Distill margin notes on explainer posts. Zero new authoring vocabulary.

**Files:** `portfolio/static/portfolio/css/blog.css`, `portfolio/blog/__init__.py`

### 3. `is_explainer` flag on Post model + migration

**What:** Added `is_explainer = BooleanField(default=False)` to `portfolio/models.py` with help text; generated migration `portfolio/migrations/0004_post_is_explainer.py`; applied it. File-based posts opt in via frontmatter `is_explainer: true`.

**Why:** One canonical opt-in for the heavier chrome (sidenotes, hover citations, BibTeX export, wider canvas, ToC at top instead of side).

**Files:** `portfolio/models.py`, `portfolio/migrations/0004_post_is_explainer.py`

### 4. Hover-citation popovers

**What:**
- New `portfolio/static/portfolio/js/citations.js` (~140 LOC, vanilla, no deps) — listens for `cite.ref[data-key]`, fetches `citations.json`, shows positioned popover with title/authors/venue and a Copy BibTeX button. Mouse hover, keyboard focus, and click all work; Esc and outside-click dismiss.
- New `portfolio/static/portfolio/data/citations.json` seeded with all six current publications + BibTeX.
- Wired into `blog_post.html` `{% block scripts %}` via `<script defer>`.

**Why:** Distill-style refs without a heavy framework. The same JS works for any post (regular or explainer); the CSS pill style is in `blog.css` from change #2.

**Authoring syntax:** `<cite class="ref" data-key="harvey2026benchmark">[1]</cite>`

**Files:** `portfolio/static/portfolio/js/citations.js`, `portfolio/static/portfolio/data/citations.json`, `portfolio/templates/portfolio/blog_post.html`

### 5. Explainer template variant in `blog_post.html`

**What:**
- `<article>` adds class `is-explainer` and bumps `max-width` to `1200px` when `post.is_explainer` is true.
- Adds an "Explainer" pill badge above the H1.
- For explainer posts: ToC is rendered as a collapsible `<details>` block at the top instead of a sticky sidebar — frees the right margin for sidenotes.
- For explainer posts: the `lg:grid-cols-[1fr_220px]` 2-column wrapper is dropped (single-column prose; sidenotes float into the right gutter).

**Why:** Sidenote floats overlap a right-side sticky ToC, so explainer posts need a different layout. Distill solves this the same way (ToC at top, margin reserved for notes).

**Files:** `portfolio/templates/portfolio/blog_post.html`

### 6. Test/demo explainer post

**What:** New post `portfolio/blog/posts/explainer-template-test.md` exercising sidenotes, citations, math, and code. Visible at `/blog/explainer-template-test/`. Marked `is_explainer: true` and `draft: false` so it's reachable; it's also useful as live documentation of the new authoring conventions.

**Why:** Smoke test + reference for future authoring.

**Action item:** Decide whether to keep this published, mark draft, or delete after the design pass lands.

**Files:** `portfolio/blog/posts/explainer-template-test.md`

### 7. Killed JS mousemove effects (3D tilt, magnetic icons)

**What:** Removed the two `mousemove` IIFEs in `main.js`:
- 3D perspective rotate on `.tilt-card`
- Magnetic translate on `.social-icon`

Replaced `.tilt-card` styling in `animations.css` with a CSS-only subtle hover lift (`translate3d(0, -3px, 0)` + softer shadow + accent border ring), gated on `(hover: hover) and (prefers-reduced-motion: no-preference)`.

**Why:** Both effects were on the "Webflow template tell" list from the design research. They also burned the main thread on every mousemove event and conflicted with view-transitions. CSS hover reads as more confident; native compositor handles it for free.

**Files:** `portfolio/static/portfolio/js/main.js`, `portfolio/static/portfolio/css/animations.css`

### 8. Named view-transitions for the avatar

**What:** Added `view-transition-name: site-avatar` to the homepage hero avatar (`sections/hero.html`) and the blog post header headshot (`blog_post.html`). New `::view-transition-old/new(site-avatar)` rule in `animations.css` gives a 360 ms morph using the existing spring easing token.

**Why:** Cross-page navigation (homepage → blog post → back) now smoothly morphs the avatar between positions/sizes without any client-side routing. Browsers without View Transitions support fall through to the existing `root` cross-fade.

**Files:** `portfolio/templates/portfolio/sections/hero.html`, `portfolio/templates/portfolio/blog_post.html`, `portfolio/static/portfolio/css/animations.css`

### 9. Expanded scroll-driven CSS animations

**What:** Added two new native scroll-driven animation rules in `animations.css`, both inside `@supports (animation-timeline: view())` and `@media (prefers-reduced-motion: no-preference)`:
- `.section-reveal` — generic class any element can use to fade-rise on scroll, no JS
- `.hero-image.avatar-wrapper` — subtle parallax scale/translate as viewport scrolls past the hero

Also added a global `prefers-reduced-motion: reduce` rule that nullifies all animations and transitions site-wide (belt-and-braces over per-rule guards).

**Why:** Compositor-thread animations (zero JS, zero jank) replace what would otherwise need IntersectionObserver. The global reduced-motion guard ensures users with motion sensitivity get a fully static experience even if a future rule forgets the per-rule guard.

**Files:** `portfolio/static/portfolio/css/animations.css`

### 10. Demos page → dated lab notebook

**What:** Converted `/demos/` from hand-authored HTML to a data-driven editorial timeline.
- Added `DEMOS` list in `data.py` with: slug, title, date, updated, tags, summary, what / why / what-I-learned, embed snippet name. Two seeded entries (nanoparticle viewer, depth estimation) — easy to add more.
- New `views.demos` reads from `DEMOS` and sorts newest-first.
- New embed snippets: `templates/portfolio/demos/embed_nanoparticle.html` and `embed_depth.html`. Demos.html `{% include %}`s by name from the data record.
- Rewrote `templates/portfolio/demos.html` as a `<ol class="lab-notebook-list">` with sticky-side meta column (date + tags), title, embed, and the three muted "what / why / learned" notes.
- New CSS section in `sections.css` for `.lab-notebook`, `.lab-entry`, `.lab-note*`. Editorial register, mobile-friendly.

**Why:** The Karpathy / Ciechanowski / Red Blob Games model — "things I'm currently exploring" reads as research-thinking; "card grid of polished demos" reads as portfolio. Public-thinking with a "what I learned" section per entry signals taste + curiosity, which is the FAANG/ELLIS reviewer signal.

**Files:** `portfolio/data.py`, `portfolio/views.py`, `portfolio/templates/portfolio/demos.html`, `portfolio/templates/portfolio/demos/embed_*.html`, `portfolio/static/portfolio/css/sections.css`

### 11. Trimmed top navigation

**What:** Reduced top nav from 6 primary items (`About`, `News`, `Experience`, `Publications`, `Explore`, `Contact`) to 5 (`About`, `Research`, `Writing`, `Demos`, `Contact`). Re-grouped children:
- `Research` → Selected pubs · Full list · Experience · News
- `Writing` → Blog · Featured projects · All projects
- `Demos` → Frozen Forecaster · Lab notebook · Recipes

**Why:** Apple/Linear/Vercel pattern: ≤4 primary items so the eye lands on page identity, not the menu. News + Experience are now under Research where they actually belong; Recipes is demoted to a Demos child rather than being a top-level peer of academic content.

**Files:** `portfolio/data.py`

### 12. Below-the-fold paint optimization (`content-visibility: auto`)

**What:** Added a `.cv-auto` utility class in `base.css` with `content-visibility: auto` and tuned `contain-intrinsic-size` defaults. Per-element overrides for `.lab-entry`, `.timeline-item`, `.blog-card`. Applied to `.lab-entry` in the new demos template.

**Why:** Browser skips layout/paint for elements outside the viewport until they're near it — free LCP/INP win on long pages. Tuned intrinsic sizes prevent CLS when sections eventually render. Spec: https://web.dev/articles/content-visibility

**Files:** `portfolio/static/portfolio/css/base.css`, `portfolio/templates/portfolio/demos.html`

### 13. Async-load Google Fonts CSS + preload critical weights

**What:** Replaced the render-blocking `<link rel="stylesheet" href="...googleapis.com...">` with the print-media swap pattern:
```html
<link rel="stylesheet" media="print" onload="this.media='all'" href="...">
<noscript><link rel="stylesheet" href="..."></noscript>
```
Added two `<link rel="preload" as="font" type="font/woff2" crossorigin>` tags for the most-used IBM Plex Sans + Serif weights so they begin downloading immediately and don't wait for the CSS round-trip.

**Why:** Lighthouse flagged the googleapis CSS as render-blocking. Async-loading shaves the FCP wait; preloading the LCP weights covers the visible-fold typography without FOUT.

**Files:** `portfolio/templates/portfolio/personal_base.html`

### 14. New homepage section: "What I'm thinking about"

**What:** New `sections/thinking.html` injected between Hero and News on the homepage. Three short paragraphs in serif editorial register, with a dated "Last updated" line linking to social. Currently seeded with: CHIL benchmark insight (mean-pooling vs attention MIL), the "predict the regime before training" follow-up question, and the tabular-foundation-models thread (TabPFN/TabICL).

**Why:** Per the design research synthesis, this is the single cheapest credibility signal for FAANG/ELLIS reviewers — the Lilian Weng / Sasha Rush / Cal Newport pattern. Almost no one does it well, and it can't be faked. Recruiters explicitly look for "evidence of taste and curiosity in public."

**Maintenance:** Update ~quarterly. Stale dates kill the signal. Edit `sections/thinking.html` directly.

**Files:** `portfolio/templates/portfolio/sections/thinking.html`, `portfolio/templates/portfolio/index.html`, `portfolio/static/portfolio/css/sections.css`

### 15. Fluid hero typography

**What:** Replaced fixed `--h2-size` on `.hero-name` with `clamp(1.75rem, 1.4rem + 1.8vw, 3.5rem)` — fluid scaling between 28 px on phones and 56 px on widescreens with no breakpoint jumps. Tightened line-height to 1.05 for the bigger sizes.

**Why:** Modern type-scaling pattern; removes need for per-breakpoint font-size overrides; reads more confident at large sizes (Apple/Linear/Vercel pattern).

**Files:** `portfolio/static/portfolio/css/sections.css`

