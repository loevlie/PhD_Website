# Performance log — June 2026 speed pass

Measurements via `scripts/perf_snapshot.py` against local `runserver 8123`
(DEBUG dev server, hot locmem cache; absolute ms are local-only but
deltas are meaningful). Raw JSON in `docs/perf-snapshots/`.

- `html wire` = bytes on the wire with `Accept-Encoding: gzip` (shows GZipMiddleware win)
- `static refs` = summed size of all `/static/` scripts/styles/preloads referenced by the page,
  raw and gzip-compressed (gzip ≈ what WhiteNoise brotli serves in prod)

## Baseline (before any changes) — 2026-06-11

| Page | median | HTML wire | Encoding | Cache-Control | scripts/css | static refs raw | static refs gz |
|---|---|---|---|---|---|---|---|
| / (home) | 3.9ms | 77.5KB | identity | — | 5 / 8 | 179.8KB | 45.0KB |
| /blog/ | 2.4ms | 61.2KB | identity | — | 3 / 3 | 214.9KB | 88.1KB |
| /blog/perf-plain-post/ (no math/code) | 5.8ms | 76.2KB | identity | — | 11 / 6 | 638.1KB | 201.3KB |
| /blog/multiple-instance-learning/ (math+code) | 6.4ms | 87.2KB | identity | — | 14 / 6 | 674.5KB | 210.6KB |
| /blog/embed-showcase/ (math) | 5.6ms | 75.8KB | identity | — | 12 / 9 | 751.4KB | 227.3KB |
| /reading/ | 3.2ms | 38.7KB | identity | — | 3 / 3 | 214.9KB | 88.1KB |
| /demos/frozen-forecaster/ | 2.6ms | 30.5KB | identity | — | 4 / 8 | 198.6KB | 89.0KB |
| /tags/ | 2.9ms | 30.6KB | identity | — | 4 / 8 | 198.6KB | 89.0KB |
| /blog/embed-showcase/edit/ (editor, authed) | 5.1ms | 149.2KB | identity | — | — | — | — |

No page sends Cache-Control, ETag, or any Content-Encoding. The math-free
post still references 638KB of static assets (KaTeX et al. ungated).

### Key asset sizes (baseline)

| Asset | Size |
|---|---|
| images/og-cover.png | 2.74MB |
| images/hero-video.mp4 | 6.34MB |
| images/profile.png (unreferenced) | 897KB |
| data/frozen-forecaster/atlas.png | 4.05MB |
| data/frozen-forecaster/configs.json | 1.20MB |
| images/og/ per-post cards (dir) | 1.10MB |
| vendor/katex/katex.min.js + css | 271KB + 23KB |
| static/portfolio/images/ (dir total) | 14.40MB |
| static/portfolio/css/ (dir total) | 0.33MB |
| static/portfolio/fonts/ (dir total) | 0.98MB |

(Exact numbers in `docs/perf-snapshots/baseline.json`.)

## After (June 2026 pass complete) — wins table

HTML on the wire (with `Accept-Encoding: gzip`):

| Page | Before | After | Δ | Responsible change |
|---|---|---|---|---|
| / (home) | 77.5KB | 17.9KB | **−77%** | GZipMiddleware |
| /blog/ | 61.2KB | 14.1KB | **−77%** | GZipMiddleware |
| /blog/&lt;plain post&gt; | 76.2KB | 16.6KB | **−78%** | GZipMiddleware |
| /blog/&lt;math+code post&gt; | 87.2KB | 22.2KB | **−75%** | GZipMiddleware |
| /reading/ | 38.7KB | 9.2KB | **−76%** | GZipMiddleware |
| /tags/ | 30.6KB | 7.8KB | **−74%** | GZipMiddleware |
| editor (/blog/…/edit/) | 149.2KB | 40.9KB | **−73%** | GZipMiddleware |

Static assets referenced per page (raw bytes; brotli-compressed on the wire):

| Page | Before | After | Δ | Responsible change |
|---|---|---|---|---|
| math-free blog post | 638KB | 331KB | **−48%** | KaTeX + pygments gated on `has_math`/`has_code` |
| homepage | 180KB | 151KB | −16% | frozen-forecaster.js removed from base.html |

Cache behavior (was: nothing):

| Page class | Cache-Control now |
|---|---|
| anonymous pages | `public, max-age=120, stale-while-revalidate=600` + ETag/304 revalidation |
| logged-in pages | `private, no-cache` + ETag/304 |
| editor | `no-store` |
| sitemap/feed/presentations | `public, max-age=3600`; robots 24h |

One-time asset re-encodes:

| Asset | Before | After | Δ |
|---|---|---|---|
| images/og-cover (.png → .jpg, portrait kept) | 2.74MB | 254KB | **−91%** |
| images/hero-video.mp4 (1440² → 480², CRF26) | 6.34MB | 149KB | **−98%** |
| frozen-forecaster atlas (browser now fetches lossless .webp) | 4.05MB | 2.88MB | −29% |
| images/og/ per-post cards (256-color quantize) | 1.10MB | 0.53MB | −52% |
| images/profile.png (unreferenced — deleted) | 897KB | 0 | −100% |
| **static images dir total** | **14.40MB** | **4.26MB** | **−70%** |

(`data/frozen-forecaster/` grew on disk because atlas.webp ships alongside
the atlas.png fallback — but browsers download 2.88MB instead of 4.05MB,
and only when scrolling near the demo; hover-prerenders no longer fetch
it at all thanks to the `document.prerendering` guard.)

Also in this pass (not visible in the table): editor session-row lookups
served from locmem (`cached_db` sessions) for every 1.5s autosave;
`get_all_posts()` + 6 content lookups skipped on all blog/editor requests
(lazy context processor); DailySalt DB hit removed from every analytics
beacon; Neon connections reused 10 min with health checks.

Median local latency moved ~+1ms per page (gzip CPU on localhost, where
bandwidth is free) — on real networks the 70-80% byte reduction dominates.

To re-measure: `python3 manage.py runserver 8123` then
`python3 scripts/perf_snapshot.py <label>`. The `/blog/perf-plain-post/`
fixture and the `perfsnap` staff user exist only in the local dev
db.sqlite3 (git-ignored); recreate them if missing (see git history of
this file).
