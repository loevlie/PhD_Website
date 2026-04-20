---
title: "Explainer template — sidenotes, citations, math"
date: 2026-04-19
author: "Dennis Loevlie"
tags: ["meta", "test"]
excerpt: "Smoke-test for the new explainer template: Tufte-style sidenotes in the right margin, hover citations, KaTeX, and code blocks."
draft: false
is_explainer: true
---

This post exercises the explainer chrome added in `design-pass-2026-04`. It is a draft so it never reaches the public listing — view it directly at `/blog/explainer-template-test/`.

## Sidenotes

Sidenotes are written as standard Markdown footnotes[^why-footnotes]. On regular posts they render as classic numbered footnotes at the bottom. On `is_explainer: true` posts they're transformed into Tufte-style margin notes that float into the right gutter on desktop[^mobile] and collapse inline on mobile.

[^why-footnotes]: Standard `[^slug]: content` markdown syntax means authors don't need to learn anything new — and the same source markdown renders correctly on platforms that don't have our sidenote CSS.

[^mobile]: Specifically: `.sidenote` is `display: block` with a left border and italic by default; `@media (min-width: 1024px)` floats it `right; margin-right: -240px;` so it hangs into the right margin.

You can put a few in the same paragraph[^a][^b]; they stack vertically in the margin, anchored near their markers.

[^a]: First note next to the same paragraph.
[^b]: Second note. They stack from the top of the floated context.

## Hover citations

Citations use a `<cite>` element with a `data-key` matching an entry in `citations.json`:

<cite class="ref" data-key="harvey2026benchmark">[1]</cite> — hover over the pill to see title, authors, venue, and a Copy BibTeX button.
<cite class="ref" data-key="harvey2025synthetic">[2]</cite>
<cite class="ref" data-key="loevlie2023demystifying">[3]</cite>

The popover positions itself below the pill, flips above if there's no room, clamps to viewport, and stays visible while the cursor moves into it.

## Math

KaTeX still works inline ($e^{i\pi} + 1 = 0$) and as display blocks:

$$
\mathcal{L}(\theta) = -\frac{1}{N} \sum_{i=1}^{N} y_i \log p_\theta(x_i) + (1-y_i) \log (1 - p_\theta(x_i))
$$

## Code

```python
def hello_explainer():
    return "sidenotes + citations + math"
```

That's it — if you're seeing margin notes on a wide screen, citation pills with hover popovers, and rendered math, the template is working.
