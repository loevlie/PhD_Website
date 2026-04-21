"""/now/ page — Derek Sivers convention. Updated quarterly.

IMPORTANT: always update `updated` when you edit the rest — the field
is shown on the page so readers can tell if the content is stale.
"""

NOW_PAGE = {
    'updated': '2026-04-19',
    'location': 'Amsterdam (incoming)',
    'sections': [
        # ─────────────────────────────────────────────────────────────
        # Below: PhD-specific section bodies redacted from public view
        # 2026-04-19. The originals stay in this comment so they can be
        # re-instated quickly (just uncomment + delete the slim versions).
        # Reason: keeping ongoing PhD direction-search and unpublished
        # paper specifics off the public site until I'm ready to share.
        #
        # ORIGINAL — Research section:
        # 'body': (
        #     "Investigating **attention regularization** for transformer MIL, "
        #     "aiming to close the instance-level gap that our **centered-Gaussian "
        #     "(Gaussian-axial) baseline** opens up in our CHIL 2026 paper. "
        #     "Targeting NeurIPS 2026."
        # ),
        #
        # ORIGINAL — PhD direction search section:
        # 'heading': 'PhD direction search',
        # 'body': (
        #     "Picking the central thread on **tabular foundation models**. "
        #     "Top candidates:\n\n"
        #     "1. **Tabular world models** — V-JEPA-style SSL on table *dynamics*.\n"
        #     "2. **Contrastive table-language alignment** — \"CLIP for tables\" "
        #     "for task-driven pretraining-data selection.\n"
        #     "3. **Scaling-law theory** for tabular pretraining.\n"
        #     "4. **Causal structure** in TFMs — interventional distributions in-context.\n"
        #     "5. **Multimodal TFMs** — tables × text × images in one space.\n\n"
        #     "Direction 1 or 2 most likely; possibly merged."
        # ),
        # ─────────────────────────────────────────────────────────────
        {
            'heading': 'Research',
            'body': (
                "Wrapping up a CHIL 2026 paper with Ethan Harvey on multiple-instance "
                "learning baselines for neuroimaging. Drafting the next paper now; "
                "more details once it's submitted."
            ),
        },
        {
            'heading': 'PhD direction',
            'body': (
                "Currently interested in **tabular foundation models**. "
                "Happy to compare notes."
            ),
        },
        # ─────────────────────────────────────────────────────────────
        # ORIGINAL — Reading section (redacted 2026-04-19; titles signal
        # specific PhD directions I'd rather not flag publicly yet):
        # 'body': (
        #     "<a href=\"https://arxiv.org/abs/2506.09985\">V-JEPA 2</a>, "
        #     "<a href=\"https://arxiv.org/abs/2410.18164\">TabDPT</a>, "
        #     "<a href=\"https://arxiv.org/abs/2511.09665\">Ma et al.</a>, "
        #     "<a href=\"https://arxiv.org/abs/2506.10914\">PFN causal inference</a>, "
        #     "Anthropic's "
        #     "<a href=\"https://transformer-circuits.pub/2025/attribution-graphs/methods.html\">attribution-graphs</a>, "
        #     "and DeCLIP."
        # ),
        # ─────────────────────────────────────────────────────────────
        {
            'heading': 'Reading',
            'body': (
                "A mix of new tabular-foundation-model work, self-supervised "
                "learning papers, and a few interpretability pieces. Happy to "
                "share specific recommendations on request."
            ),
        },
        {
            'heading': 'Building',
            'body': (
                "This site. **Frozen Forecaster** (homepage demo) — real TabICL vs "
                "XGBoost inference cached from a Modal precompute. "
                "**[NeurOpt](https://github.com/loevlie/neuropt)** — LLM-guided "
                "ML optimization that reads training curves and proposes the next experiment."
            ),
        },
        # ─────────────────────────────────────────────────────────────
        # ORIGINAL — Applying section (removed 2026-04-20 per request;
        # commented for one-edit restore):
        # 'heading': 'Applying',
        # 'body': (
        #     "**ELLIS PhD 2026 cohort** — TRL Lab Amsterdam (Hulsebos + van de Meent). "
        #     "Open to FAANG / FAIR / DeepMind / Anthropic research internships for "
        #     "summer 2026 / 2027. [Get in touch](#contact)."
        # ),
        # ─────────────────────────────────────────────────────────────
        {
            'heading': 'Life',
            'body': (
                "Marrying **Cait Morrow** this year. Looking for **soccer leagues "
                "in Amsterdam** — recommendations welcome."
            ),
        },
    ],
    'inspired_by': [
        ('Derek Sivers', 'https://sivers.org/now'),
        ('Cal Newport', 'https://calnewport.com/now/'),
        ('nownownow.com', 'https://nownownow.com/'),
    ],
}
