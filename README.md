# a2a-gateway-audit

**Approval laundering and delegation privilege escalation in agent-to-agent (A2A) networks — attacks, a provenance-tracking gateway defence, and measurements.**

Submission for the [Swarm Alignment Hackathon 2026](https://apartresearch.com/sprints/swarm-alignment-2026) (Apart Research), **Track 3 — Strengthening Agent Infrastructure** (cross-track: Track 4, oversight & control).

> **Status:** pre-sprint planning. This repository currently contains **only planning documents, no code**. See [Sprint disclosure](#sprint-disclosure).

## Question in one sentence

When agents delegate work to each other through a gateway, can an attacker get a harmful tool call executed by *laundering* it through approvals or higher-privileged agents — and how much does a gateway that tracks **who originally asked** and **what exactly was approved** reduce that, compared with per-hop ACLs and an LLM judge?

Full plan: [`docs/RESEARCH_PLAN.md`](docs/RESEARCH_PLAN.md).

## Repository layout (planned)

```
docs/          research plan, threat model, sprint log
env/           multi-agent sandbox: agents, mock tools, message bus      (sprint)
gateway/       defences D1–D4                                             (sprint)
attacks/       attack scenarios A1–A5                                     (sprint)
scenarios/     benign + attack task suites (JSON)                         (sprint)
experiments/   run configs, scripts, analysis notebooks                   (sprint)
results/       raw JSONL logs + aggregated tables/figures                 (sprint)
report/        PDF report on the official Apart template                  (sprint)
```

## Reproducibility (target)

- Every message, tool call, gateway decision and model response is logged as JSONL with a run seed.
- Mock tools are deterministic; no real network, filesystem or payment side effects (sandbox containment is part of the evaluation).
- One command re-runs any experiment from its config.

## Sprint disclosure

Only work done during the sprint is judged. We track provenance explicitly:

| Item | When | Status |
|---|---|---|
| `README.md`, `docs/RESEARCH_PLAN.md`, `docs/SPRINT_LOG.md` (planning only, no code) | Thu 5 Nov 2026, before sprint start | **pre-sprint (planning)** |
| All code in `env/`, `gateway/`, `attacks/`, `scenarios/`, `experiments/`, `results/`, `report/` | during the sprint | sprint work |

No code from other projects is reused. If any third-party library or preexisting code is used, it will be listed in [`docs/SPRINT_LOG.md`](docs/SPRINT_LOG.md) and marked **preexisting** here and in the report.

## AI assistance

AI tools were used for planning and will be used for coding and writing. The team reviewed and is responsible for all content; all reported numbers come from logged runs in `results/`.

## License

TBD (MIT planned) — to be added during the sprint.
