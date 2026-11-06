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


def fisher_exact(k1: int, n1: int, k2: int, n2: int) -> float:
    """Two-sided Fisher exact test p-value for the 2x2 table [[k1, n1-k1], [k2, n2-k2]]."""
    K, N = k1 + k2, n1 + n2

    def pmf(x: int) -> float:
        return math.comb(n1, x) * math.comb(n2, K - x) / math.comb(N, K)

    observed = pmf(k1)
    lo, hi = max(0, K - n2), min(K, n1)
    return min(1.0, sum(pmf(x) for x in range(lo, hi + 1) if pmf(x) <= observed * (1 + 1e-9)))


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


def compare(t: pd.DataFrame, pairs: list[tuple[str, str]]) -> pd.DataFrame:
    """Fisher exact tests between defences, per group (attack or benign) and model."""
    rows = []
    for (group, model), g in t.groupby(["group", "model"]):
        by = g.set_index("defence")
        for a, b in pairs:
            if a in by.index and b in by.index:
                ra, rb = by.loc[a], by.loc[b]
                p = fisher_exact(int(ra.success_k), int(ra.n), int(rb.success_k), int(rb.n))
                rows.append({"group": group, "model": model, "a": a, "b": b,
                             "rate_a": ra.success_rate, "rate_b": rb.success_rate, "p_fisher": p})
    return pd.DataFrame(rows)


def tradeoff(t: pd.DataFrame, path: Path) -> None:
    """Safety-usefulness plot: mean ASR over attacks vs benign completion, one point per defence."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    att = t[t["group"] != "benign"]
    ben = t[t["group"] == "benign"].set_index("defence")
    if att.empty or ben.empty:
        return
    # pool all attack runs per defence (each attack has the same n)
    pooled = att.groupby("defence")[["success_k", "n"]].sum()
    fig, ax = plt.subplots(figsize=(4.5, 3.6))
    for d, r in pooled.iterrows():
        if d not in ben.index:
            continue
        asr = r.success_k / r.n
        lo, hi = wilson(int(r.success_k), int(r.n))
        use = ben.loc[d, "success_rate"]
        ax.errorbar(use, asr, yerr=[[asr - lo], [hi - asr]],
                    xerr=[[use - ben.loc[d, "ci_lo"]], [ben.loc[d, "ci_hi"] - use]], fmt="o", capsize=3)
        ax.annotate(d, (use, asr), textcoords="offset points", xytext=(6, 4))
    ax.set_xlabel("benign task completion")
    ax.set_ylabel("attack success rate (pooled A1-A5)")
    ax.set_xlim(0, 1.05)
    ax.set_ylim(0, 1.05)
    ax.set_title("Safety vs usefulness")
    fig.tight_layout()
    fig.savefig(path)


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
    tradeoff(t, d / "tradeoff.pdf")
    c = compare(t, [("D0", "D1"), ("D1", "D2"), ("D1", "D3"), ("D2", "D3"), ("D3", "D4")])
    c.to_csv(d / "comparisons.csv", index=False)
    (d / "comparisons.txt").write_text(c.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print(t.to_string(index=False, float_format=lambda x: f"{x:.2f}"))


if __name__ == "__main__":
    main()
