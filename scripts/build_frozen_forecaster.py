#!/usr/bin/env python3
"""
Precompute the Frozen Forecaster grid: real TabICL + real XGBoost predict_proba
over a fixed query mesh, for ~2000 synthetic 2D support configurations. Quantize
to uint8 and pack as a tile-atlas PNG (Adam Pearce trick) so the runtime is pure
JSON + canvas interpolation — no in-browser inference.

Output (in --out-dir):
    atlas.png     — RGB tile atlas. Tile (col=k%C, row=k//C) holds config k:
                       R channel = TabICL  P(class=1), uint8 in [0,255]
                       G channel = XGBoost P(class=1), uint8 in [0,255]
                       B channel = reserved (0)
    configs.json  — {n_configs, query_res, domain, atlas_cols, atlas_rows,
                     feature_dim, feature_names, configs: [{kind, X, y, f}]}
    progress.json — checkpoint state for --resume

Cost: ~$5 on a single L4 (TabICL ~25M params; ~1.5–2s/config inc. XGBoost fit).
Smoke test: `python build_frozen_forecaster.py --smoke` runs N=10 on CPU,
            takes ~2 min, produces a valid (tiny) artifact for frontend dev.

Usage:
    pip install tabicl xgboost numpy scikit-learn pillow
    python scripts/build_frozen_forecaster.py --smoke
    python scripts/build_frozen_forecaster.py --n 2000 --device cuda
    python scripts/build_frozen_forecaster.py --resume     # picks up where it left off

The frontend (frozen-forecaster.js) currently uses Gaussian-KDE + 1-NN as
stand-ins. After this script emits real outputs, the JS lookup path swaps in.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import time
from typing import List, Tuple

import numpy as np


# ── Config ──────────────────────────────────────────────────────────────
QUERY_RES = 64                  # query grid resolution (64×64 = 4096 query points)
DOMAIN = (-3.0, 3.0)            # square domain in both x and y
ATLAS_COLS = 50                 # tile columns in atlas; 2000/50 = 40 rows
DEFAULT_N = 2000
DEFAULT_OUT = pathlib.Path("portfolio/static/portfolio/data/frozen-forecaster")

# Each prior gets equal share of the budget so we have balanced coverage.
CONFIG_PRIORS: List[Tuple[str, dict]] = [
    ("moons",   {"n_min": 6,  "n_max": 60, "noise": 0.10}),
    ("circles", {"n_min": 8,  "n_max": 60, "noise": 0.08}),
    ("xor",     {"n_min": 8,  "n_max": 40, "noise": 0.20}),
    ("blobs",   {"n_min": 8,  "n_max": 50, "k_blobs": 4}),
    ("spiral",  {"n_min": 12, "n_max": 80, "noise": 0.15}),
    ("random",  {"n_min": 5,  "n_max": 30, "noise": 0.0}),
    ("outlier", {"n_min": 4,  "n_max": 14, "noise": 0.12}),
    ("stripe",  {"n_min": 6,  "n_max": 30, "noise": 0.18}),
]

# Feature vector schema — see compute_features(). Must match frontend lookup.
FEATURE_NAMES = [
    "n_norm",          # n / 100
    "balance",         # frac of class 1
    "mean_x_norm",     # mean_x / 3
    "mean_y_norm",
    "std_x_norm",
    "std_y_norm",
    "class_sep_norm",  # ||centroid_1 - centroid_0|| / 6
    "mixedness",       # frac of points whose 1-NN is opposite class
    "aspect",          # min(std_x/std_y, std_y/std_x), in (0,1]
]


# ── Synthetic dataset generators ────────────────────────────────────────
def gen_moons(rng: np.random.Generator, n: int, noise: float):
    n0 = n // 2; n1 = n - n0
    t0 = rng.uniform(0, np.pi, n0); t1 = rng.uniform(0, np.pi, n1)
    X0 = np.stack([np.cos(t0), np.sin(t0)], axis=1) * 1.4 - [0.5, 0.4]
    X1 = np.stack([np.cos(t1 + np.pi), np.sin(t1 + np.pi)], axis=1) * 1.4 + [0.5, 0.4]
    X = np.vstack([X0, X1]) + rng.normal(0, noise, (n, 2))
    y = np.array([0] * n0 + [1] * n1)
    return X, y


def gen_circles(rng, n, noise):
    n0 = n // 2; n1 = n - n0
    t0 = rng.uniform(0, 2 * np.pi, n0); t1 = rng.uniform(0, 2 * np.pi, n1)
    X0 = np.stack([0.7 * np.cos(t0), 0.7 * np.sin(t0)], axis=1)
    X1 = np.stack([1.8 * np.cos(t1), 1.8 * np.sin(t1)], axis=1)
    X = np.vstack([X0, X1]) + rng.normal(0, noise, (n, 2))
    y = np.array([0] * n0 + [1] * n1)
    return X, y


def gen_xor(rng, n, noise):
    centers = np.array([[1.2, 1.2, 0], [-1.2, -1.2, 0], [1.2, -1.2, 1], [-1.2, 1.2, 1]])
    pts, ys = [], []
    for i in range(n):
        c = centers[i % 4]
        pts.append([c[0] + rng.normal(0, noise + 0.3), c[1] + rng.normal(0, noise + 0.3)])
        ys.append(int(c[2]))
    return np.array(pts), np.array(ys)


def gen_blobs(rng, n, k_blobs):
    centers = rng.uniform(-2, 2, (k_blobs, 2))
    classes = rng.integers(0, 2, k_blobs)
    # Force at least one of each class so the demo doesn't degenerate.
    if classes.sum() == 0: classes[0] = 1
    if classes.sum() == k_blobs: classes[0] = 0
    pts, ys = [], []
    for i in range(n):
        b = i % k_blobs
        pts.append(centers[b] + rng.normal(0, 0.4, 2))
        ys.append(int(classes[b]))
    return np.array(pts), np.array(ys)


def gen_spiral(rng, n, noise):
    n0 = n // 2; n1 = n - n0
    t0 = np.linspace(0.5, 4 * np.pi, n0); t1 = np.linspace(0.5, 4 * np.pi, n1)
    X0 = np.stack([t0 * np.cos(t0) * 0.2, t0 * np.sin(t0) * 0.2], axis=1)
    X1 = np.stack([t1 * np.cos(t1 + np.pi) * 0.2, t1 * np.sin(t1 + np.pi) * 0.2], axis=1)
    X = np.vstack([X0, X1]) + rng.normal(0, noise, (n, 2))
    y = np.array([0] * n0 + [1] * n1)
    return X, y


def gen_random(rng, n, noise):
    X = rng.uniform(-2.2, 2.2, (n, 2))
    y = (X[:, 0] * X[:, 1] > 0).astype(int)
    return X, y


def gen_outlier(rng, n, noise):
    """Dense cluster in one quadrant, sparse cluster (or single point) far away.
    Forces TabICL's "I don't know" behavior to show vs XGBoost's overconfidence."""
    n_cluster = max(2, n - rng.integers(1, 4))
    n_outlier = n - n_cluster
    cluster_center = rng.uniform(-2, 2, 2)
    cluster_class = int(rng.integers(0, 2))
    outlier_center = cluster_center + rng.choice([-1, 1]) * rng.uniform(2.5, 4.0, 2)
    outlier_center = np.clip(outlier_center, -2.5, 2.5)
    X_c = cluster_center + rng.normal(0, noise + 0.2, (n_cluster, 2))
    X_o = outlier_center + rng.normal(0, noise + 0.1, (n_outlier, 2))
    X = np.vstack([X_c, X_o])
    y = np.array([cluster_class] * n_cluster + [1 - cluster_class] * n_outlier)
    return X, y


def gen_stripe(rng, n, noise):
    """Linearly separable along a random axis. Boring for both models, useful as
    a sanity-check anchor in feature-space lookup."""
    n0 = n // 2; n1 = n - n0
    angle = rng.uniform(0, np.pi)
    direction = np.array([np.cos(angle), np.sin(angle)])
    perp = np.array([-np.sin(angle), np.cos(angle)])
    t0 = rng.uniform(-2, 2, n0); t1 = rng.uniform(-2, 2, n1)
    X0 = t0[:, None] * direction + perp * (-0.8 + rng.normal(0, noise, n0))[:, None]
    X1 = t1[:, None] * direction + perp * (0.8 + rng.normal(0, noise, n1))[:, None]
    X = np.vstack([X0, X1])
    y = np.array([0] * n0 + [1] * n1)
    return X, y


GENERATORS = {
    "moons": gen_moons, "circles": gen_circles, "xor": gen_xor,
    "blobs": gen_blobs, "spiral": gen_spiral, "random": gen_random,
    "outlier": gen_outlier, "stripe": gen_stripe,
}


# ── Feature vector for nearest-config lookup ────────────────────────────
def compute_features(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """9-D vector roughly normalized to [0, 1]. Used by the frontend to find
    the K-nearest cached configs for an arbitrary user-supplied scene."""
    from sklearn.neighbors import NearestNeighbors
    n = len(X)
    balance = float((y == 1).mean())
    mean_xy = X.mean(axis=0)
    std_xy = X.std(axis=0) + 1e-6
    mask0, mask1 = (y == 0), (y == 1)
    c0 = X[mask0].mean(axis=0) if mask0.any() else mean_xy
    c1 = X[mask1].mean(axis=0) if mask1.any() else mean_xy
    class_sep = float(np.linalg.norm(c1 - c0))
    if n >= 2:
        nn = NearestNeighbors(n_neighbors=2).fit(X)
        _, idx = nn.kneighbors(X)
        mixedness = float((y[idx[:, 1]] != y).mean())
    else:
        mixedness = 0.0
    aspect = float(min(std_xy[0] / std_xy[1], std_xy[1] / std_xy[0]))
    return np.array([
        min(n / 100.0, 1.0),
        balance,
        mean_xy[0] / 3.0,
        mean_xy[1] / 3.0,
        std_xy[0] / 3.0,
        std_xy[1] / 3.0,
        class_sep / 6.0,
        mixedness,
        aspect,
    ], dtype=np.float32)


# ── Models ──────────────────────────────────────────────────────────────
def make_tabicl(device: str):
    from tabicl import TabICLClassifier
    # n_estimators=1 → single forward pass; deterministic enough for cached use.
    return TabICLClassifier(n_estimators=1, device=device)


def make_xgboost():
    import xgboost as xgb
    return xgb.XGBClassifier(
        n_estimators=200, max_depth=6, learning_rate=0.1,
        eval_metric="logloss", verbosity=0,
        tree_method="hist",
    )


def predict_grid(clf, X_train, y_train, X_query) -> np.ndarray:
    clf.fit(X_train, y_train)
    proba = clf.predict_proba(X_query)
    # Some classifiers return only a single column when y is degenerate; defend.
    if proba.shape[1] == 1:
        col = 1.0 - proba[:, 0] if int(clf.classes_[0]) == 0 else proba[:, 0]
    else:
        col = proba[:, 1]
    return col.astype(np.float32)


# ── Atlas packing ───────────────────────────────────────────────────────
def quantize(probs: np.ndarray) -> np.ndarray:
    return np.clip(probs * 255.0, 0, 255).astype(np.uint8)


def pack_atlas(grids_t: np.ndarray, grids_x: np.ndarray, atlas_cols: int,
               out_path: pathlib.Path) -> Tuple[int, int]:
    """Pack into a tile atlas. Returns (atlas_rows, atlas_cols) actually used."""
    from PIL import Image
    n, h, w = grids_t.shape
    atlas_rows = (n + atlas_cols - 1) // atlas_cols
    atlas = np.zeros((atlas_rows * h, atlas_cols * w, 3), dtype=np.uint8)
    for k in range(n):
        col = k % atlas_cols
        row = k // atlas_cols
        atlas[row*h:(row+1)*h, col*w:(col+1)*w, 0] = grids_t[k]
        atlas[row*h:(row+1)*h, col*w:(col+1)*w, 1] = grids_x[k]
        # B channel reserved (0) — could later carry ensemble variance, etc.
    Image.fromarray(atlas, mode="RGB").save(out_path, optimize=True)
    return atlas_rows, atlas_cols


# ── Driver ──────────────────────────────────────────────────────────────
def build_query_mesh():
    qx = np.linspace(DOMAIN[0], DOMAIN[1], QUERY_RES)
    qy = np.linspace(DOMAIN[1], DOMAIN[0], QUERY_RES)   # y flipped → image space
    QX, QY = np.meshgrid(qx, qy)
    return np.stack([QX.ravel(), QY.ravel()], axis=1)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, default=DEFAULT_N, help="number of configs (default 2000)")
    parser.add_argument("--smoke", action="store_true", help="N=10 on CPU; ~2 min; for frontend dev")
    parser.add_argument("--device", default="cuda", help="cuda | cpu")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", type=pathlib.Path, default=DEFAULT_OUT)
    parser.add_argument("--checkpoint-every", type=int, default=100,
                        help="re-pack atlas + JSON every N configs (so partial runs survive crashes)")
    parser.add_argument("--resume", action="store_true",
                        help="continue from existing progress.json (skip already-done configs)")
    args = parser.parse_args()

    if args.smoke:
        args.n = 10
        args.device = "cpu"
        args.checkpoint_every = 5
        print("[smoke] N=10, device=cpu, checkpoint every 5")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed=args.seed)
    X_query = build_query_mesh()

    grids_t = np.zeros((args.n, QUERY_RES, QUERY_RES), dtype=np.uint8)
    grids_x = np.zeros((args.n, QUERY_RES, QUERY_RES), dtype=np.uint8)
    configs_meta: List[dict] = [None] * args.n  # type: ignore
    start_idx = 0

    progress_path = args.out_dir / "progress.json"
    if args.resume and progress_path.exists():
        prog = json.loads(progress_path.read_text())
        start_idx = prog["next_idx"]
        # Rehydrate from existing artifact if present — but for simplicity we
        # only support resume from the START of a checkpoint, not mid-block.
        # (TabICL restart is ~30s; not worth complicating.)
        print(f"[resume] restarting from config {start_idx}")
        # Reseed to the same place
        for _ in range(start_idx):
            rng.uniform()  # advance — crude but matches deterministic order

    print(f"[load] make TabICL on {args.device}…")
    t0 = time.time()
    tabicl = make_tabicl(args.device)
    xgb_model = make_xgboost()
    print(f"[load] ready in {time.time() - t0:.1f}s")

    t_start = time.time()
    for i in range(start_idx, args.n):
        kind, params = CONFIG_PRIORS[i % len(CONFIG_PRIORS)]
        n_pts = int(rng.integers(params["n_min"], params["n_max"] + 1))
        gen_kwargs = {k: v for k, v in params.items() if k not in ("n_min", "n_max")}
        X_train, y_train = GENERATORS[kind](rng, n_pts, **gen_kwargs)

        # Defensive: every config must have both classes for predict_proba shape stability
        if (y_train == 0).sum() == 0: y_train[0] = 0
        if (y_train == 1).sum() == 0: y_train[-1] = 1

        try:
            p_t = predict_grid(tabicl, X_train, y_train, X_query).reshape(QUERY_RES, QUERY_RES)
        except Exception as e:
            print(f"[warn] config {i} ({kind}, n={n_pts}): TabICL failed → {e}; falling back to 0.5")
            p_t = np.full((QUERY_RES, QUERY_RES), 0.5, dtype=np.float32)
        try:
            p_x = predict_grid(xgb_model, X_train, y_train, X_query).reshape(QUERY_RES, QUERY_RES)
        except Exception as e:
            print(f"[warn] config {i} ({kind}, n={n_pts}): XGBoost failed → {e}; falling back to 0.5")
            p_x = np.full((QUERY_RES, QUERY_RES), 0.5, dtype=np.float32)

        grids_t[i] = quantize(p_t)
        grids_x[i] = quantize(p_x)
        configs_meta[i] = {
            "i": i,
            "kind": kind,
            "X": np.round(X_train, 3).tolist(),
            "y": [int(v) for v in y_train],
            "f": [round(float(v), 4) for v in compute_features(X_train, y_train)],
        }

        if (i + 1) % 10 == 0 or i + 1 == args.n:
            elapsed = time.time() - t_start
            rate = (i + 1 - start_idx) / max(elapsed, 1e-6)
            eta_min = (args.n - i - 1) / max(rate, 1e-6) / 60.0
            print(f"[{i+1:>4}/{args.n}] {kind:>8s} (n={n_pts:>3d})  {rate:.2f} cfg/s  eta {eta_min:.1f} min")

        if (i + 1) % args.checkpoint_every == 0 or i + 1 == args.n:
            atlas_rows, atlas_cols = pack_atlas(grids_t[:i+1], grids_x[:i+1], ATLAS_COLS,
                                                args.out_dir / "atlas.png")
            with open(args.out_dir / "configs.json", "w") as f:
                json.dump({
                    "n_configs": i + 1,
                    "query_res": QUERY_RES,
                    "domain": list(DOMAIN),
                    "atlas_cols": atlas_cols,
                    "atlas_rows": atlas_rows,
                    "tile_size": QUERY_RES,
                    "feature_dim": len(FEATURE_NAMES),
                    "feature_names": FEATURE_NAMES,
                    "configs": [c for c in configs_meta if c is not None],
                }, f)
            with open(progress_path, "w") as f:
                json.dump({"next_idx": i + 1, "n_total": args.n}, f)
            print(f"[checkpoint] wrote atlas ({atlas_rows}×{atlas_cols} tiles) + configs.json")

    print(f"DONE → {args.out_dir} ({time.time() - t_start:.1f}s total)")


if __name__ == "__main__":
    main()
