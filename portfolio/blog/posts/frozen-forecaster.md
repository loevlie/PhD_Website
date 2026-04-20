---
title: "The Frozen Forecaster: when does in-context learning beat XGBoost on tabular data?"
date: 2026-04-19
author: "Dennis Loevlie"
tags: ["tabular foundation models", "TabICL", "TabPFN", "XGBoost", "in-context learning"]
excerpt: "A hands-on look at TabICL versus XGBoost on small synthetic 2D distributions — and why the answer to 'which one wins?' isn't 'always TabICL' or 'always XGBoost,' but a regime question."
draft: false
is_explainer: true
maturity: budding
---

The slider on my homepage[^demo] is a lookup table. Two thousand synthetic 2D classification scenes were precomputed in a Modal job — for each, I asked a frozen [TabICL](https://arxiv.org/abs/2502.05564)[^tabicl] to predict the class probability over a 64×64 grid, and asked an [XGBoost](https://xgboost.ai)[^xgb] regressor trained on the same points to do the same. The result is a tile atlas; the live slider does a 4-nearest-neighbor lookup in feature space and blends the cached predictions. **No inference happens in your browser** — what you're seeing is real, but cached.

[^demo]: <cite class="ref" data-key="loevlie2023demystifying">[demo]</cite> The slider, the lookup mechanism, and the precompute job are all open. The atlas is a single PNG (~3 MB) packed by `scripts/build_frozen_forecaster.py`; the K-NN blend is in `frozen-forecaster.js`.
[^tabicl]: TabICL (Hooper et al., 2025) is a transformer-based tabular foundation model that does in-context learning over a small training set passed at inference time. It's a successor to TabPFN with a column-then-row attention pattern.
[^xgb]: XGBoost is the gradient-boosted-trees library that has been the empirical SOTA for tabular classification for the better part of a decade. It's the default benchmark every new tabular method has to beat.

The question this demo is gesturing at is: **when, exactly, does an in-context tabular foundation model out-predict a well-tuned gradient boosting model on small tabular data?** The honest answer is "it depends on the regime in ways the field is still pinning down." This post is a snapshot of what I've found so far playing with this on synthetic data, and the open questions I'm pulling on for my PhD.

## Why this matters

For most of the last ten years, the answer to "what should I throw at a small tabular dataset?" has been "XGBoost, then call it." Neural approaches kept losing to gradient boosting on small-N tabular benchmarks. The story changed in 2022 with TabPFN<cite class="ref" data-key="harvey2025synthetic">[1]</cite>: a transformer pretrained on a synthetic prior could match or beat XGBoost on small tabular tasks **without any per-dataset training**. You pass your training rows in-context, the model sees the support set, and it predicts on the test rows in a single forward pass.

That was the "tabular CLIP moment." Since then, several follow-ups have pushed the regime where in-context learning wins outward: [TabICL](https://arxiv.org/abs/2502.05564) extended to wider tables and longer contexts; [TabDPT](https://arxiv.org/abs/2410.18164) showed power-law scaling on real-data pretraining[^tabdpt]; [Ma et al.](https://arxiv.org/abs/2511.09665) showed a single wide table can transfer.

[^tabdpt]: TabDPT (2024) is interesting because it pretrains on *real* tables (millions of rows scraped from the web) rather than the synthetic-causal-model prior TabPFN/TabICL use. It found a power-law scaling on real-data pretraining quality — a phenomenology with no theory yet, which is one of the directions I'm thinking about for my PhD.

But "in-context learning beats gradient boosting" isn't a universal claim; it's a claim about a specific regime. The Frozen Forecaster lets you steer through the regime. Drag the divider to compare predictions on the same scene; click "Moons," "Circles," "XOR," "Outlier" to load presets; click on the canvas to drop your own points and see how each model adapts.

## What you can see in the demo

Three patterns recur as you play with it:

### 1. On smooth, separable distributions, both win — but XGBoost is sharper.

On the **Moons** preset, both models recover the moon-shaped decision boundary cleanly. XGBoost's boundary is harder-edged; TabICL's is smoother. For a downstream user who cares about confidence calibration, TabICL's smoother boundary is often *better* — it doesn't pretend to know more than it does near the gap.

### 2. On structured-but-tricky distributions (XOR, concentric circles), TabICL holds up where XGBoost fragments.

The **XOR** preset is the canonical "trees struggle here" case. XGBoost can solve XOR with deep enough trees and enough rounds, but with only ~50 training points it tends to over-fragment. TabICL handles XOR more gracefully with the same support set — the in-context attention seems to find the structure faster than the trees can split into it.

### 3. On outliers and class-imbalanced edges, TabICL is more conservative.

Drop a single point of the minority class far from any other points. XGBoost will happily carve out a small island of confident prediction around it. TabICL hedges — its predicted probability stays nearer 50% in the outlier neighborhood. Whether that's a feature or a bug depends on what you're optimizing for. For *medical* tabular data, where a single outlier could be a labeling error, the conservative response is usually right.

## The honest caveats

Three things worth being upfront about:

1. **This is synthetic 2D, which is not where the question actually lives.** The reason small medical-tabular benchmarks matter is that they have ~10–50 columns, structured semantics (this column is age in years, this one is binary indicator), and noisy labels. Synthetic 2D Gaussians have none of that. The Frozen Forecaster is good for *intuition*; the next move is to extend it to small medical-tabular benchmarks where TabICL's column-aware encoder might help more visibly.

2. **The XGBoost in the demo is *not* aggressively tuned.** It's a sensible default (n_estimators=100, max_depth=6, learning_rate=0.1). A tuning sweep — which is what XGBoost users actually do in production — would close some of the gap. TabICL's appeal is that it doesn't need a sweep, but the like-for-like comparison should acknowledge that XGBoost has a leash to pull on.

3. **No-training is half the story; *zero per-task hyperparameter tuning* is the other half.** TabICL's promise isn't just "no fit step" — it's "no validation-set sweep." For a researcher iterating across many small datasets, that's a much bigger time-saver than the inference cost would suggest.

## What I'm pulling on for my PhD

The bigger question — which is one of the threads I'm chasing for my PhD on [tabular foundation models](/now/) — is whether we can predict, *before training*, which regime a new dataset is in. Right now you have to run both models and see. There should be a cheap diagnostic — something like a ratio of within-cluster to between-cluster variance, or a measure of column interaction structure — that tells you in advance whether the in-context learner will be worth the inference cost.

Two papers I keep coming back to point in slightly different directions on this:

- TabDPT<cite class="ref" data-key="loevlie2023demystifying">[2]</cite> argues real-data pretraining quality is the lever — better priors come from larger and more diverse real corpora.
- Ma et al. argues *features* matter more than *instances* — a single wide table with the right columns can transfer to many tasks.

> The diagnostic might not need to be smart. It might just need to count something the model couldn't have seen during pretraining.

That's the seedling; the budding follow-up is figuring out what to count. Reach me on [Bluesky](https://bsky.app/profile/dennisloevlie.bsky.social) or [email](mailto:Loevliedenny@gmail.com) if you have ideas — I'd love to hear from anyone who's poked at this from a different angle.

## Going further

- The TabPFN paper: [Hollmann et al., 2022](https://arxiv.org/abs/2207.01848)
- TabICL: [Hooper et al., 2025](https://arxiv.org/abs/2502.05564)
- TabDPT: [arxiv 2410.18164](https://arxiv.org/abs/2410.18164)
- Ma et al. on single-table transfer: [arxiv 2511.09665](https://arxiv.org/abs/2511.09665)
- The Frozen Forecaster code (precompute + JS lookup): on the [homepage](/) under "Interactive demo"
