"""Editor-assist features. One package per sub-feature so additions
don't cross-pollinate.

    spellcheck  — pure-Python spell-checker with ML-term tolerance.
                  Input: markdown body text. Output: list of
                  potential misspellings with suggestions. View
                  layer in portfolio/views/editor_assist.py calls
                  this module; tests live in
                  portfolio/tests/test_spellcheck.py.

Future submodules will slot in here:
    smart_paste — URL-shape detection for paste events (Tier 1).
    ai_assists  — Tighten / TL;DR / title suggestions (Tier 2).
    research    — notation glossary extract, reproducibility block,
                  `\\cite{}` expansion (Tier 3).
"""
