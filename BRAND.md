# Brand & Design Tokens

Single source of truth for the visual brand across **CV PDF**, **personal
website**, **slide decks**, **cover letters**, and any future surfaces.

The website CSS in `portfolio/static/portfolio/css/variables.css` is the
operational copy of these tokens; the LaTeX CV in
[`loevlie/cv`](https://github.com/loevlie/cv) mirrors the same values
in its preamble. When you change a token, change it in both.

---

## Colors

| Token | Hex | Use |
|---|---|---|
| **Accent** (light mode) | `#0A2540` | Stripe-tier deep navy. Primary brand color. Section headers, links, rules, name in CV header. |
| Accent (dark mode) | `#6FA8FF` | Same navy, lifted for legibility on dark backgrounds. |
| Accent light | `#2563A8` | Hyperlinks (lighter so they're visibly clickable but not shouting). |
| Accent hover | `#1B4F84` | Hover state for accent-colored interactives. |
| Body ink | `#1A1A1A` | Body text. Bringhurst near-black, never pure `#000`. |
| Meta gray | `#6B6B6B` | Secondary text, metadata, dates, captions. |
| Rule / border | `#E5E2DA` (light) / `#2a3a4a` (dark) | Hairlines under section headers, card borders. |
| Paper (light) | `#FCFCFA` | Warm off-white background. Never pure `#FFFFFF`. |
| Ink-bg (dark) | `#0f1923` | Dark slate background. Inherited from the website's pre-rebrand palette. |

### Tint ramp

Derived from `--accent` via `color-mix(in srgb, var(--accent) X%, white)`
(or `black` in dark mode). Available as `--accent-90 / -50 / -20 / -10`
on the website; mirrored as `\colorlet{accent80}{accent!80!white}` in
the LaTeX CV.

---

## Typography

Single typeface family across all surfaces: **IBM Plex** (Bold Monday for IBM).

| Role | Family | Where it lands |
|---|---|---|
| **Body / prose** | IBM Plex Serif | Hero subtitle, news entries, publication titles + authors, longform copy. Renders as "academic." |
| **UI / nav / buttons** | IBM Plex Sans | Navigation, buttons, dates, section titles, CV headers. |
| **Code / URLs** | IBM Plex Mono | Code blocks, inline `code`, URLs in CV. |
| Fallback sans | Inter, then system sans | Catch any glyph Plex doesn't render. |
| Fallback serif | Georgia | Catch any glyph Plex Serif doesn't render. |

### OpenType features always-on

- `kern` — proper kerning
- `liga` — standard ligatures (`fi`, `fl`)
- `onum` — old-style proportional figures in body prose (numbers sit at x-height)

### Selective features

- `lnum` + `tnum` — lining tabular figures for **dates**, **years**, **timeline**, **page numbers**, **venue names**. Numbers align column-perfect across rows.
- `smcp` — **NOT in IBM Plex** (it ships no real small caps). Workaround: `text-transform: uppercase; letter-spacing: 0.08–0.12em;` on venue names and section headers. CV uses the same workaround via `\textls[120]{\MakeUppercase{...}}`.

---

## Section header treatment

Spaced uppercase Plex Sans, accent-colored, with a thin rule under.
Tracking ~12% (Butterick range for all-caps).

```css
.section-title {
  font-family: var(--font-family);
  font-size: 0.8125rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent);
  border-bottom: 1px solid var(--accent-bg-subtle);
}
```

LaTeX equivalent (CV):

```latex
\titleformat{\section}
  {\sansfam\footnotesize\bfseries\color{accent}}
  {}{0em}{\textls[120]{\MakeUppercase{#1}}}
  [\vspace{1pt}{\color{rule}\titlerule[0.4pt]}]
```

---

## Spacing & rhythm

| Token | Value |
|---|---|
| Section padding | `64px` |
| Container max-width | `900px` |
| Card padding | `24px` |
| Card radius | `12px` |
| Body line-height | `1.7` |
| Heading line-height | `1.3` |
| CV linespread | `1.06` (Plex Serif at 10pt) |
| CV section-spacing before | `0.6\baselineskip` (Bringhurst grid) |

---

## Anti-patterns we don't use

Documented in the [Elite CV Typography KB](../Scratch/notes/Personal_Vault/01-Projects/Elite_CV_Typography_KB/wiki/anti_patterns.md):

- ❌ Multiple accent colors
- ❌ Saturated primaries (`#FF0000`, `#0000FF`)
- ❌ Skill-rating bars (`Python ████████░░ 80%`)
- ❌ Carousel of "featured" anything
- ❌ Typewriter intro animation
- ❌ AI-generated profile photo
- ❌ Pure `#FFFFFF` backgrounds (use warm off-white) or pure `#000000` text (use `#1A1A1A`)
- ❌ Default Inter / Helvetica / Times alone — generic
- ❌ Photo on academic homepage / CV
- ❌ Per-paper inline citation counts (gauche pre-tenure)
- ❌ "References available upon request"

---

## Cross-surface consistency

| Surface | Repo | Notes |
|---|---|---|
| Personal website | this repo | Django + custom CSS + Tailwind for blog |
| Academic CV PDF | [`loevlie/cv`](https://github.com/loevlie/cv) | LaTeX (pdflatex + biblatex+publist + IBM Plex) |
| Industry CV PDF | [`loevlie/cv`](https://github.com/loevlie/cv) | `industry.tex`, two-column variant |
| Slide deck | [`loevlie/cv`](https://github.com/loevlie/cv/tree/main/slides) | Touying (Typst) primary, Beamer/Metropolis fallback |
| Cover letters | [`loevlie/cv`](https://github.com/loevlie/cv/tree/main/letter) | Same Plex stack, same navy footer |

When a recruiter or collaborator opens any one of these, they see the
same name, same color, same font family, same hierarchy. The brand
is the consistency.
