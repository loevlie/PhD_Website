"""Top-nav structure. Trimmed 2026-04 to ≤4 primary items (Apple /
Linear / Vercel pattern: keep the top bar identity-first). Secondary
pages live under dropdown children."""

NAV_LINKS = [
    {'label': 'About', 'href': '#about'},
    {'label': 'Research', 'href': '#publications', 'children': [
        {'label': 'Selected', 'href': '#publications'},
        {'label': 'Full List', 'href': '/publications/'},
        {'label': 'Experience', 'href': '#experience'},
        {'label': 'News', 'href': '#news'},
    ]},
    {'label': 'Writing', 'href': '/blog/', 'children': [
        {'label': 'Blog (essays)', 'href': '/blog/'},
        {'label': 'Notebook (open lab notes)', 'href': '/notebook/'},
        {'label': 'Reading (papers I am chewing on)', 'href': '/reading/'},
        {'label': 'Garden (notes by maturity)', 'href': '/garden/'},
        {'label': 'Featured Projects', 'href': '#projects'},
        {'label': 'All Projects', 'href': '/projects/'},
    ]},
    {'label': 'Demos', 'href': '/demos/', 'children': [
        # Removed the static "Frozen Forecaster → #demos" anchor: the
        # homepage section is hidden when the demo is draft, leaving a
        # dead anchor. Lab Notebook is the canonical entry point.
        {'label': 'Lab Notebook', 'href': '/demos/'},
        {'label': 'Recipes', 'href': '/recipes/'},
    ]},
    {'label': 'Contact', 'href': '#contact'},
]
