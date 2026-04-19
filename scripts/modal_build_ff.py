"""Modal launcher for build_frozen_forecaster.py.

Why two entry points:
- `smoke` runs N=10 on a fresh tmp dir, ~2 min, ~$0.10. Validates TabICL +
  XGBoost actually load on Modal's L4 and the atlas/JSON pipeline works
  end-to-end before committing to the real spend.
- `full` runs N=2000 backed by a persistent Modal Volume so a mid-run crash
  can resume from the last checkpoint instead of restarting from zero.

Usage (from /Users/dennisloevlie/PhD_Website):
    modal run scripts/modal_build_ff.py::smoke
    modal run scripts/modal_build_ff.py::full

Both auto-download the resulting atlas.png + configs.json into
portfolio/static/portfolio/data/frozen-forecaster/, replacing whatever's there.
"""
import pathlib
import modal

app = modal.App("frozen-forecaster")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch",
        "tabicl",
        "xgboost",
        "numpy",
        "scikit-learn",
        "pillow",
    )
    .add_local_file(
        local_path="scripts/build_frozen_forecaster.py",
        remote_path="/app/build_frozen_forecaster.py",
    )
)

# Volume persists between full-run invocations so --resume actually works.
vol = modal.Volume.from_name("ff-cache", create_if_missing=True)


def _read_artifacts(out_dir: str) -> dict:
    from pathlib import Path
    p = Path(out_dir)
    return {
        "atlas": (p / "atlas.png").read_bytes(),
        "configs": (p / "configs.json").read_bytes(),
    }


@app.function(image=image, gpu="L4", timeout=20 * 60)
def build_smoke() -> dict:
    """N=10, CPU-or-CUDA fallback, no volume — fully ephemeral."""
    import subprocess, sys
    out = "/tmp/ff_smoke_out"
    subprocess.run(
        [sys.executable, "/app/build_frozen_forecaster.py",
         "--n", "10", "--device", "cuda",
         "--out-dir", out, "--checkpoint-every", "5"],
        check=True,
    )
    return _read_artifacts(out)


@app.function(
    image=image,
    gpu="L4",
    timeout=2 * 60 * 60,            # 2 h max — well above the ~1 h estimate
    volumes={"/output": vol},
)
def build_full(n: int = 2000) -> dict:
    """Full run with checkpoint+resume backed by a Modal Volume."""
    import subprocess, sys
    subprocess.run(
        [sys.executable, "/app/build_frozen_forecaster.py",
         "--n", str(n), "--device", "cuda",
         "--out-dir", "/output", "--checkpoint-every", "100",
         "--resume"],
        check=True,
    )
    vol.commit()
    return _read_artifacts("/output")


def _save_locally(result: dict, label: str) -> None:
    out_dir = pathlib.Path("portfolio/static/portfolio/data/frozen-forecaster")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "atlas.png").write_bytes(result["atlas"])
    (out_dir / "configs.json").write_bytes(result["configs"])
    a_kb = (out_dir / "atlas.png").stat().st_size / 1024
    c_kb = (out_dir / "configs.json").stat().st_size / 1024
    print(f"[{label}] saved atlas.png ({a_kb:.1f} KB) + configs.json ({c_kb:.1f} KB) → {out_dir}")


@app.local_entrypoint()
def smoke():
    """Fast pipeline validation. ~2 min, ~$0.10."""
    print("[smoke] launching N=10 on Modal L4…")
    result = build_smoke.remote()
    _save_locally(result, "smoke")


@app.local_entrypoint()
def full(n: int = 2000):
    """Full run. ~1 hr, ~$5 on L4. Resumes from checkpoint if interrupted."""
    print(f"[full] launching N={n} on Modal L4 — ~1 hr, ~$5…")
    result = build_full.remote(n)
    _save_locally(result, "full")
