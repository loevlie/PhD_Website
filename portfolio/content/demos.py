"""Interactive demos at /demos/ and /demos/<slug>/.

Schema:
  slug          str   — anchor + element id
  title         str
  date          ISO date the demo was first published
  updated       ISO date the demo last meaningfully changed (optional)
  tags          list[str]
  summary       short (1-line) blurb shown above the embed
  what          markdown — what this demo is + how to use it
  why           markdown — why I built it; what I was trying to learn
  learned       markdown — what I now know that I didn't before
  embed         template-snippet name in `portfolio/demos/embed_<slug>.html`
  draft         bool   — anon visitors see a WIP stub; staff see the full demo
"""

DEMOS = [
    {
        'slug': 'frozen-forecaster',
        'title': 'The Frozen Forecaster',
        'date': '2026-04-18',
        'updated': '',
        'draft': True,  # standalone /demos/frozen-forecaster/ hidden from public; homepage embed stays visible
        'tags': ['tabular', 'in-context-learning', 'tabicl', 'xgboost'],
        'summary': 'TabICL vs XGBoost on the same 2D scene — drag the divider to '
                   'sweep the boundary. Click to drop points, drag the probe to '
                   'inspect P(class). Real precomputed TabICL grids on common '
                   'preset scenes.',
        'what': "Interactive split-screen comparing a frozen tabular foundation "
                "model (TabICL) against XGBoost on the same five canonical 2D "
                "datasets. Cached lookup tables, not live inference, but the "
                "precomputed surfaces are the actual TabICL outputs.",
        'why':  "Wanted a way to make the 'frozen weights as prior' framing tactile. "
                "Two minutes with the slider beats reading the abstract. The split "
                "view forces direct comparison rather than two side-by-side static "
                "decision-boundary figures, which never line up perfectly.",
        'learned': "The boundary differences land hardest on outliers and on the "
                   "XOR scene — TabICL's smoother prior absorbs noise where XGBoost "
                   "carves around it. Caching the precomputed grids pushed the "
                   "interactive feel from 'laggy and academic' to 'fluent.'",
        'embed': 'embed_frozen_forecaster.html',
    },
    {
        'slug': 'nanoparticle-viewer',
        'title': 'AuPd Nanoparticle Viewer',
        'date': '2024-08-12',
        'updated': '',
        'tags': ['three.js', 'chemistry', 'visualization'],
        'summary': '55-atom Mackay icosahedron — the structure studied in '
                   'Loevlie et al., Acc. Chem. Res. (2023). Drag to rotate, '
                   'scroll to zoom, toggle Au-core ↔ Pd-core.',
        'what': "Real-time WebGL viewer of a 55-atom bimetallic Mackay icosahedron "
                "with a single-button core-swap and live cohesive-energy readout.",
        'why':  "Wanted a way to *see* the structure that the entire chemical-ordering "
                "argument in the paper hinges on, without forcing a reader to install "
                "ASE + NGLView. WebGL via three.js was the cheapest path to a "
                "frame-rate-locked rotation that doesn't fall over on a phone.",
        'learned': "Three.js's instanced meshes are fine for a few hundred atoms "
                   "but the per-atom material updates on core-swap are the real "
                   "cost — batch them or you drop frames on every toggle.",
        'embed': 'embed_nanoparticle.html',
    },
    {
        'slug': 'depth-estimation',
        'title': 'Client-Side Depth Estimation',
        'date': '2024-07-20',
        'updated': '',
        'tags': ['onnx', 'transformers.js', 'ml'],
        'summary': 'Drop an image, get a monocular depth map computed in your '
                   'browser via Depth Anything V2 (~27 MB ONNX, loads on first use).',
        'what': "Single-page upload that runs Depth Anything V2 entirely client-side "
                "via transformers.js + ONNX Runtime Web. Slide the divider to compare "
                "input ↔ predicted depth.",
        'why':  "Curious how far client-side ML had come for non-trivial vision "
                "models. Goal was zero server cost — the model is fetched from a "
                "Hugging Face Space and cached in IndexedDB after first run.",
        'learned': "WebGPU backend speeds inference 4–8× over WASM but adoption is "
                   "still spotty (Safari 26 in 2025 helped). The model fetch is "
                   "what users actually feel — service-worker prefetch is the "
                   "lever, not the inference itself.",
        'embed': 'embed_depth.html',
    },
]
