"""Run experiments: scenarios x defences x seeds -> results/<name>/<run_id>/.

Usage:
    uv run python -m a2a_audit.harness experiments/configs/smoke.yaml
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from .bus import Environment
from .llm import LLMCache, LLMClient, LLMConfig, api_hosts
from .sandbox import network_allowlist, violations
from .scenarios import Scenario, evaluate, load_all


def _jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")


def run_one(s: Scenario, defence: str, seed: int, clients: dict[str, LLMClient | None],
            model_tag: str, out_root: Path, max_steps: int) -> dict[str, Any]:
    run_id = f"{s.key}__{defence}__{model_tag}__s{seed}"
    out = out_root / run_id
    if (out / "summary.json").exists():
        return json.loads((out / "summary.json").read_text())
    t0 = time.time()
    env = Environment(s, defence, clients["agent"], clients["approver"], clients["judge"], seed=seed,
                      max_steps=max_steps)
    error = None
    try:
        env.run()
    except Exception as e:  # recorded, never silently dropped
        error = f"{type(e).__name__}: {e}"
    llm_turns = [t for t in env.turns if t.get("usage") or t.get("agent") == "judge"]
    cost = sum((t.get("usage") or {}).get("cost", 0) or t.get("cost", 0) or 0 for t in llm_turns)
    blocks = [e for e in env.events if e["event"] == "block"]
    summary = {
        "run_id": run_id, "scenario": s.id, "variant": s.variant, "type": s.type, "attack": s.attack,
        "defence": defence, "model": model_tag, "seed": seed,
        "success": evaluate(s.success, env.tools.log) if error is None else None,
        "n_blocks": len(blocks), "n_tool_blocks": sum(b["where"] == "tool" for b in blocks),
        "steps": env.step, "llm_calls": len(llm_turns),
        "parse_errors": sum(1 for t in env.turns if t.get("error")),
        "judge_errors": env.gateway.judge_errors, "cost_usd": cost,
        "wall_s": round(time.time() - t0, 2), "error": error,
    }
    out.mkdir(parents=True, exist_ok=True)
    _jsonl(out / "events.jsonl", env.events)
    _jsonl(out / "turns.jsonl", env.turns)
    _jsonl(out / "tools.jsonl", [r.model_dump() for r in env.tools.log])
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    return summary


def code_hash() -> str:
    """SHA-256 over source, prompts and scenarios, so every result dir records the exact code it ran."""
    h = hashlib.sha256()
    for p in sorted([*Path(__file__).parent.glob("*.py"), *Path("scenarios").rglob("*.yaml")]):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def _client(spec: dict | None, cache: LLMCache) -> LLMClient | None:
    if not spec:
        return None
    return LLMClient(LLMConfig(**spec), cache=cache)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--limit", type=int, default=None, help="run only the first N jobs (pilot)")
    args = ap.parse_args(argv)
    load_dotenv(Path.cwd() / ".env")
    cfg = yaml.safe_load(Path(args.config).read_text())
    cache = LLMCache(cfg.get("cache", ".cache/llm.sqlite"))
    clients = {"agent": _client(cfg["agent_model"], cache),
               "approver": _client(cfg.get("approver_model", cfg["agent_model"]), cache),
               "judge": _client(cfg.get("judge_model"), cache)}
    model_tag = cfg.get("model_tag", cfg["agent_model"]["model"].replace(":", "_").replace("/", "_"))
    scen = load_all(cfg.get("scenario_root", "scenarios"), cfg.get("scenarios"))
    jobs = [(s, d, seed) for s in scen for d in cfg["defences"] for seed in cfg["seeds"]]
    if args.limit:
        jobs = jobs[: args.limit]
    out_root = Path("results") / cfg["name"]
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "config.json").write_text(json.dumps({**cfg, "code_hash": code_hash(), "n_jobs": len(jobs)}, indent=1))
    hosts = set().union(*(api_hosts(c.cfg.backend) for c in clients.values() if c))
    print(f"{len(jobs)} runs -> {out_root}", file=sys.stderr)
    rows = []
    with network_allowlist(hosts), ThreadPoolExecutor(cfg.get("workers", 4)) as pool:
        futs = [pool.submit(run_one, s, d, seed, clients, model_tag, out_root, cfg.get("max_steps", 30))
                for s, d, seed in jobs]
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result()
            rows.append(r)
            print(f"[{i}/{len(jobs)}] {r['run_id']} success={r['success']} blocks={r['n_blocks']} "
                  f"err={r['error']}", file=sys.stderr)
    _jsonl(out_root / "runs.jsonl", sorted(rows, key=lambda r: r["run_id"]))
    print(f"sandbox violations: {len(violations)}", file=sys.stderr)


if __name__ == "__main__":
    main()
