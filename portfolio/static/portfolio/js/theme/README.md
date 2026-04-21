# Theme handling

Two distinct theme systems coexist on the site. They intentionally don't
share code — they have different state spaces — but do share vocabulary
for `localStorage` keys so a future unified toggle is easy.

## 1. Portfolio surface (base.html + personal_base.html)

Two states: **light** (default) and **dark**.

- **Pre-paint script:** inline in the `<head>` of `base.html` /
  `personal_base.html`. Reads `localStorage.theme`. If anything other
  than `"light"` is stored, adds `dark-mode` to `<html>` before the CSS
  loads — avoids a flash of wrong theme.
- **Runtime:** `js/theme/portfolio.js` handles clicks on
  `.theme-toggle`, flips `html.classList.dark-mode`, persists, swaps
  the moon/sun icon visibility, and fires a `themechange` event so
  other widgets can react.
- **CSS:** every variable in `css/variables.css` is keyed off
  `html.dark-mode` so nothing else needs to opt in.

**localStorage keys:** `theme`  (`"light"` | `"dark"`), plus optional
`tod` override for the time-of-day accent shift
(`auto` | `dawn` | `day` | `dusk` | `night`).

## 2. Blog surface (blog_base.html)

Four states: Catppuccin **latte**, **frappe**, **macchiato**, **mocha**.
Inline in `blog_base.html` because the Catppuccin CSS variables all
live there too.

- **Pre-paint script:** inline; reads `localStorage['ctp-flavor']`,
  falls back to `prefers-color-scheme` (`mocha` for dark,
  `latte` for light), adds the flavor as a class on `<html>`.
- **Runtime:** Alpine.js x-data on the `<html>` tag exposes a `flavor`
  reactive variable; `:class="{ latte: flavor==='latte', … }"` (object
  form — string form caused a subtle stacking bug; see 2026-04 fix
  in git history). Each flavor button mutates `flavor`.
- **CSS:** four CSS-variable blocks (`.latte`, `.frappe`, `.macchiato`,
  `.mocha`) each defining the full Catppuccin palette.

**localStorage key:** `ctp-flavor`
(`"latte"` | `"frappe"` | `"macchiato"` | `"mocha"`).

## Why keep them separate?

The portfolio uses a brand-specific accent system (time-of-day hue
shift on dusk/dawn, etc.) that doesn't map onto Catppuccin. The blog
uses Catppuccin so reading surfaces match the syntax-highlighter
palette inside code blocks. Merging would require picking one and
losing part of the design.

## If you need both states

Both keys persist independently, so a user can be on latte for the
blog and light-mode for the portfolio without conflict. If you ever
want a "follow system" meta-toggle, wire it to update both
(`localStorage.theme` + `localStorage['ctp-flavor']`) from the same
event handler.
