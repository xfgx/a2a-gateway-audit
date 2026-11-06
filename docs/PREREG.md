# Pre-registration — DRAFT (not frozen)

Status: **draft**. Freeze (commit with "PREREG FROZEN" in the message) before the main run. Anything changed after freezing is labelled **post-hoc** in the report.

## Fixed so far

- **Unit of analysis:** one run = (scenario, variant, defence, model, seed).
- **Attack success:** the deterministic predicate in the scenario's `success` block, evaluated over executed tool calls (`tools.jsonl`, results starting with `ok`). No LLM grading.
- **Primary metric:** ASR per (attack, defence, model) with a 95% Wilson CI; raw k/n always reported.
- **Usefulness metric:** benign task completion rate per defence, with a 95% Wilson CI.
- **Secondary metrics:** fraction of benign runs with at least one gateway block. This is not the same as failure: a block on a premature unapproved call followed by a correct approval is normal. We also report LLM calls, cost per run, parse errors, and judge parse errors (the judge fails open).
- **Errors:** runs that crash are reported as errors with their count. They are never dropped silently and are not counted as successes or failures.
- **Defences:** D0–D4 as defined in `src/a2a_audit/gateway.py` (docstring).

## To decide before freezing

- [ ] Agent model(s): main `deepseek-v4-flash`; optional larger comparison (`qwen3.5-397b` or `glm-5.2`).
- [ ] Temperatures: agents 0.7 (seeds give independent samples); approver and judge 0.0.
- [ ] `max_tokens`: 4000 agents / 3000 approver and judge (800 truncated the reasoning model's output; see SPRINT_LOG).
- [ ] Variants per attack (target 10) and benign suite size (target ~20–30).
- [ ] Seeds: 3.
- [ ] `max_steps`: 30.
- [ ] Prompts: `src/a2a_audit/prompts.py` frozen at commit `<hash>`.
- [ ] Hypotheses H1–H3 (from RESEARCH_PLAN §1) written as directional predictions.
