"""Aggregate run summaries into tables and figures. Numbers come only from results/.

Usage:
    uv run python -m a2a_audit.analyze results/<name>
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def load(results_dir: Path) -> pd.DataFrame:
    rows = [json.loads(p.read_text()) for p in results_dir.glob("*/summary.json")]
    return pd.DataFrame(rows)


def table(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["group"] = df["attack"].fillna("benign")
    out = []
    for (group, defence, model), g in df.groupby(["group", "defence", "model"]):
        valid = g[g["success"].notna()]
        n, k = len(valid), int(valid["success"].astype(bool).sum())
        lo, hi = wilson(k, n)
        blocked = int((valid["n_blocks"] > 0).sum())
        blo, bhi = wilson(blocked, n)
        out.append({"group": group, "defence": defence, "model": model, "n": n, "errors": len(g) - n,
                    "success_k": k, "success_rate": k / n if n else float("nan"), "ci_lo": lo, "ci_hi": hi,
                    "any_block_k": blocked, "any_block_rate": blocked / n if n else float("nan"),
                    "block_ci_lo": blo, "block_ci_hi": bhi, "cost_usd": g["cost_usd"].sum()})
    return pd.DataFrame(out)


def heatmap(t: pd.DataFrame, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    a = t[t["group"] != "benign"].pivot_table(index="group", columns="defence", values="success_rate")
    if a.empty:
        return
    fig, ax = plt.subplots(figsize=(1.2 * a.shape[1] + 2, 0.6 * a.shape[0] + 1.5))
    im = ax.imshow(a.values, vmin=0, vmax=1, cmap="Reds")
    ax.set_xticks(range(a.shape[1]), a.columns)
    ax.set_yticks(range(a.shape[0]), a.index)
    for i in range(a.shape[0]):
        for j in range(a.shape[1]):
            v = a.values[i, j]
            if not math.isnan(v):
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=10)
    ax.set_title("Attack success rate")
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    fig.savefig(path)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("results_dir")
    args = ap.parse_args(argv)
    d = Path(args.results_dir)
    df = load(d)
    if df.empty:
        print("no runs found")
        return
    t = table(df)
    t.to_csv(d / "summary.csv", index=False)
    (d / "summary.txt").write_text(t.to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    heatmap(t, d / "asr_heatmap.pdf")
    print(t.to_string(index=False, float_format=lambda x: f"{x:.2f}"))


if __name__ == "__main__":
    main()
