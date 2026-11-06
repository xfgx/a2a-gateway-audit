# Working rules for AI assistants (and humans) on this repo

This is a research project judged on honesty and rigor. These rules override speed.

## Research integrity — non-negotiable

1. **No invented results.** Every number in the report, README, slides, or chat must come from a script that reads logs in `results/`. Give the `run_id` and the command that produced it. If a number cannot be traced to a log, it does not get written.
2. **No invented references.** Cite only sources whose existence was verified by opening the URL/DOI. Track each in `docs/REFERENCES.md` with its verification status. If a source cannot be accessed, say so; never fill in authors, titles, years, or claims from memory.
3. **No silent filtering.** Never drop runs, seeds, or scenarios. Any exclusion is written down with the reason, ideally before looking at results.
4. **Pre-register before the main run.** Metrics, success predicates, and the experiment matrix are frozen in `docs/PREREG.md` before the main experiment. Later changes are allowed but must be labelled **post-hoc** in the report.
5. **Report what happened, including negative/null results.** If a defence does not help, or an attack fails, that is a finding.
6. **Do not overclaim.** Always give n and 95% CIs. Separate *observed* from *hypothesis* from *speculation*. Our setting is a small mock sandbox; claims stay scoped to it.
7. **Label what is scripted vs. LLM-driven.** Scripted adversaries and rule-based approvers must never be described as "LLM agents".
8. **Bugs that touch results:** fix, re-run, and record it in `docs/SPRINT_LOG.md`.
9. **Honest status to the user.** Never say "tests pass", "experiment done", or "verified" without having actually run it in this session. If something was not run or could not be accessed, say so explicitly.
10. **Success is decided by deterministic predicates over tool logs**, never by an LLM grading itself.

## Provenance / prior work

- Only work done during the sprint is judged. Everything is logged in `docs/SPRINT_LOG.md`.
- Anything written before the sprint start is marked **pre-sprint** (README table + report). Third-party code is listed with its license.
- AI assistance is disclosed in the README and in the report's **LLM Usage Statement**. Humans are the authors and are responsible for all content.
- The official template asks that the final report be **primarily written by the team**. The assistant drafts and checks; humans rewrite and own the final wording.

## Safety / dual-use

- Mock tools only. No real network, payment, email, or filesystem side effects. The harness enforces a network allow-list (LLM endpoint only).
- No real-world targets. Do not publish optimized jailbreak prompts beyond what reproduction needs.

## Engineering conventions

- Python 3.11, `uv` for env (`uv sync`, `uv run ...`). Code in `src/a2a_audit/`, tests in `tests/`.
- Every run is reproducible from `experiments/configs/*.yaml` + seed; all LLM calls are cached and logged (replay without API keys).
- Secrets only via `.env` / environment variables; never commit or print them.
- Keep it simple: the minimum code that answers the research questions in `docs/RESEARCH_PLAN.md`.
