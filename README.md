# a2a-gateway-audit

**Approval laundering and delegation privilege escalation in agent-to-agent (A2A) networks: attacks, a provenance-tracking gateway defence, and measurements.**

Submission for the [Swarm Alignment Hackathon 2026](https://apartresearch.com/sprints/swarm-alignment-2026) (Apart Research), **Track 3: Strengthening Agent Infrastructure** (cross-track with Track 4, oversight & control).

> **Status:** sprint starting. This repository has **planning documents and dependency configuration only, no implementation code yet**. See [Sprint disclosure](#sprint-disclosure).

## Question in one sentence

When agents delegate work to each other through a gateway, can an attacker get a harmful tool call executed by *laundering* it through approvals or higher-privileged agents? And how much does a gateway that tracks **who originally asked** and **what exactly was approved** reduce that, compared with per-hop ACLs and an LLM judge?

- Research plan: [`docs/RESEARCH_PLAN.md`](docs/RESEARCH_PLAN.md)
- Technical plan: [`docs/TECH_PLAN.md`](docs/TECH_PLAN.md)
- Integrity rules: [`CLAUDE.md`](CLAUDE.md)
- References (with verification status): [`docs/REFERENCES.md`](docs/REFERENCES.md)

## Setup

```bash
uv sync                      # Python 3.11 (exact pins: requirements.lock.txt)
cp .env.example .env         # add an OpenAI-compatible endpoint + key
uv run pytest                # (once code exists)
```

## Layout (planned)

```
src/a2a_audit/   schema, A2A wire adapter, LLM client, mock tools, agents, bus, gateway/ (D0–D4), harness, analysis
scenarios/       benign + attack suites (YAML)
experiments/     run configs
results/         raw JSONL logs + aggregated tables/figures
report/          report draft, tables, figures (final text goes into the official Google Doc template)
tests/
```

## Sprint disclosure

Only work done during the sprint is judged. Provenance:

| Item | When | Status |
|---|---|---|
| `README.md`, `CLAUDE.md`, `docs/*` (planning, no code) | 5–6 Nov 2026, before sprint start | **pre-sprint (planning)** |
| `pyproject.toml`, `requirements.lock.txt`, `.gitignore`, `.env.example` (dependency config, no logic) | 6 Nov 2026, before sprint start | **pre-sprint (config)** |
| Report template | [official Google Doc](https://docs.google.com/document/d/1_1_27EyZriMlc8n8EBE2YScaeyMjm-8xjR097nmHXAE/copy?usp=sharing) (not stored in repo) | third-party (Apart Research) |
| Everything in `src/`, `scenarios/`, `experiments/`, `results/`, `tests/`, report text | during the sprint | sprint work |

No code from other projects is reused. Third-party libraries are listed in `pyproject.toml` and [`docs/SPRINT_LOG.md`](docs/SPRINT_LOG.md).

## AI assistance

An AI assistant (Claude) is used for planning, coding and drafting. The team reviews and is responsible for all content. Every reported number comes from logged runs in `results/`. See [`CLAUDE.md`](CLAUDE.md) for the rules we follow.

## License

MIT (to be added).
