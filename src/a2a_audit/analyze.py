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
    xmin = 1.0
    for i, (d, r) in enumerate(pooled.iterrows()):
        if d not in ben.index:
            continue
        asr = r.success_k / r.n
        lo, hi = wilson(int(r.success_k), int(r.n))
        use = ben.loc[d, "success_rate"]
        ax.errorbar(use, asr, yerr=[[asr - lo], [hi - asr]],
                    xerr=[[use - ben.loc[d, "ci_lo"]], [ben.loc[d, "ci_hi"] - use]], fmt="o", capsize=3)
        ax.annotate(d, (use, asr), textcoords="offset points", xytext=(-18 if i % 2 else 6, 6))
        xmin = min(xmin, ben.loc[d, "ci_lo"])
    ax.set_xlabel("benign task completion (95% CI)")
    ax.set_ylabel("attack success rate, pooled A1-A5")
    ax.set_xlim(max(0.0, xmin - 0.05), 1.02)
    ax.set_ylim(0, 1.05)
    ax.set_title("Safety vs usefulness")
    fig.tight_layout()
    for ext in (".pdf", ".png", ".svg"):
        fig.savefig(path.with_suffix(ext), dpi=200)


def holm(pvals: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values (same order as input)."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj, running = [0.0] * m, 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        adj[i] = running
    return adj


def newcombe_diff(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float, float]:
    """Difference p1 - p2 with Newcombe's hybrid-score 95% CI (method 10)."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = p1 - p2
    lo = d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return d, lo, hi


def prereg_tests(df: pd.DataFrame) -> str:
    """The tests pre-registered in docs/PREREG.md, computed from run summaries only."""
    v = df[df["success"].notna()].copy()
    v["success"] = v["success"].astype(bool)

    def counts(mask) -> tuple[int, int]:
        sub = v[mask]
        return int(sub["success"].sum()), len(sub)

    def cell(attack, defence):
        return counts((v["attack"] == attack) & (v["defence"] == defence))

    out = [f"runs with a valid outcome: {len(v)} / {len(df)} (errors: {len(df) - len(v)})", ""]
    out.append("PRIMARY FAMILY: D1 vs D3 per attack, two-sided Fisher exact, Holm-corrected")
    attacks = ["A1", "A2", "A3", "A4", "A5"]
    raw = []
    for a in attacks:
        (k1, n1), (k3, n3) = cell(a, "D1"), cell(a, "D3")
        raw.append(fisher_exact(k1, n1, k3, n3) if n1 and n3 else float("nan"))
    adj = holm(raw)
    for a, p, pa in zip(attacks, raw, adj):
        (k1, n1), (k3, n3) = cell(a, "D1"), cell(a, "D3")
        out.append(f"  {a}: D1 {k1}/{n1}  D3 {k3}/{n3}  p={p:.4g}  p_holm={pa:.4g}")
    out += ["", "H1: A1, A5: D0 vs D1 (prediction: D1 not lower)"]
    for a in ("A1", "A5"):
        (k0, n0), (k1, n1) = cell(a, "D0"), cell(a, "D1")
        out.append(f"  {a}: D0 {k0}/{n0}  D1 {k1}/{n1}  p={fisher_exact(k0, n0, k1, n1):.4g}")
    k3, n3 = cell("A3", "D3")
    lo, hi = wilson(k3, n3)
    out += ["", f"H4: A3 under D3: {k3}/{n3} = {k3 / n3:.3f} (95% CI {lo:.3f}-{hi:.3f}); prediction: > 0"]
    m2 = (v["attack"].isin(["A1", "A2", "A5"])) & (v["defence"] == "D2")
    m3 = (v["attack"].isin(["A1", "A2", "A5"])) & (v["defence"] == "D3")
    (k2, n2), (k3, n3) = counts(m2), counts(m3)
    out += ["", f"H5: pooled A1+A2+A5: D2 {k2}/{n2}  D3 {k3}/{n3}  p={fisher_exact(k2, n2, k3, n3):.4g} (prediction: D2 higher)"]
    (b1, m1), (b3, mm3) = counts((v["type"] == "benign") & (v["defence"] == "D1")), counts(
        (v["type"] == "benign") & (v["defence"] == "D3"))
    d, dlo, dhi = newcombe_diff(b1, m1, b3, mm3)
    out += ["", f"H6: benign completion D1 {b1}/{m1}  D3 {b3}/{mm3}; D1-D3 = {d:.3f} (95% CI {dlo:.3f} to {dhi:.3f}); "
                "prediction: difference <= 0.10"]
    out += ["", "ROBUSTNESS: per variant (pooled over seeds), D3 ASR lower / equal / higher than D1"]
    for a in attacks:
        sub = v[v["attack"] == a]
        r = sub.groupby(["variant", "defence"])["success"].mean().unstack()
        if {"D1", "D3"} <= set(r.columns):
            lower = int((r["D3"] < r["D1"]).sum())
            equal = int((r["D3"] == r["D1"]).sum())
            higher = int((r["D3"] > r["D1"]).sum())
            out.append(f"  {a}: lower {lower}, equal {equal}, higher {higher} (of {len(r)} variants)")
    return "\n".join(out)


def markdown_table(t: pd.DataFrame) -> str:
    """Table 1 for the report: k/n (rate, 95% CI) per group x defence. Generated, never typed by hand."""
    defences = sorted(t["defence"].unique())
    groups = [g for g in sorted(t["group"].unique()) if g != "benign"] + ["benign"]
    lines = ["| | " + " | ".join(defences) + " |", "|---|" + "---|" * len(defences)]
    for g in groups:
        cells = []
        for d in defences:
            r = t[(t["group"] == g) & (t["defence"] == d)]
            if r.empty:
                cells.append("")
                continue
            r = r.iloc[0]
            cells.append(f"{int(r.success_k)}/{int(r.n)} ({r.success_rate:.2f}; {r.ci_lo:.2f}–{r.ci_hi:.2f})")
        label = "benign completion" if g == "benign" else f"{g} ASR"
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def heatmap(t: pd.DataFrame, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    a = t[t["group"] != "benign"].pivot_table(index="group", columns="defence", values="success_rate")
    if a.empty:
        return
    fig, ax = plt.subplots(figsize=(0.9 * a.shape[1] + 1.6, 0.5 * a.shape[0] + 1.2))
    im = ax.imshow(a.values, vmin=0, vmax=1, cmap="Reds", aspect="auto")
    ax.set_xticks(range(a.shape[1]), a.columns)
    ax.set_yticks(range(a.shape[0]), a.index)
    for i in range(a.shape[0]):
        for j in range(a.shape[1]):
            v = a.values[i, j]
            if not math.isnan(v):
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=10,
                        color="white" if v > 0.6 else "black")
    ax.set_title("Attack success rate (n=30 per cell)")
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    for ext in (".pdf", ".png", ".svg"):
        fig.savefig(path.with_suffix(ext), dpi=200)


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
    runs = df.sort_values("run_id")[["scenario", "variant", "defence", "seed", "success", "n_blocks", "llm_calls",
                                      "cost_usd", "error"]].copy()
    runs["success"] = runs["success"].map({True: 1, False: 0})
    runs.to_csv(d / "runs.csv", index=False, float_format="%.3g")  # one row per run, committed to git
    (d / "summary.txt").write_text(t.to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    heatmap(t, d / "asr_heatmap.pdf")
    tradeoff(t, d / "tradeoff.pdf")
    c = compare(t, [("D0", "D1"), ("D1", "D2"), ("D1", "D3"), ("D2", "D3"), ("D3", "D4")])
    c.to_csv(d / "comparisons.csv", index=False)
    (d / "comparisons.txt").write_text(c.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    (d / "table1.md").write_text(markdown_table(t) + "\n")
    if {"A1", "D1", "D3"} <= set(df["attack"].dropna()) | set(df["defence"]):
        (d / "prereg_tests.txt").write_text(prereg_tests(df))
    print(t.to_string(index=False, float_format=lambda x: f"{x:.2f}"))


if __name__ == "__main__":
    main()
