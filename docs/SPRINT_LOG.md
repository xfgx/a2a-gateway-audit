# Sprint log & provenance

Purpose: make it trivially checkable what was done when, as required by the sprint rules on prior work.

## Pre-sprint (5–6 Nov 2026)

- Created repository.
- Planning docs: `README.md`, `CLAUDE.md`, `docs/RESEARCH_PLAN.md`, `docs/TECH_PLAN.md`, `docs/REFERENCES.md`, this file. **No code.**
- Dependency config: `pyproject.toml`, `requirements.lock.txt`, `.env.example`, `.gitignore`. **No logic.**
- Located the official Apart report template (Google Doc, linked from the Guidelines tab).

## Sprint (from Fri 6 Nov 2026, first official sprint day)

- **2026-11-06 13:10 UTC** (file birth times) started implementation: `src/a2a_audit/` (schema, A2A wire adapter, LLM client with Adaption/OpenAI/scripted backends + sqlite cache, mock tools, approvals and grants, agents, gateway D0-D4, event loop, scenarios and predicates, network sandbox, harness, analysis), 9 scenario files (4 benign, 5 attack; 2-3 variants each), offline tests (17, scripted test doubles, no network).
- **2026-11-06 13:17 UTC** first real-model smoke run (`experiments/configs/smoke.yaml`, deepseek-v4-flash, 1 variant x 1 seed). Pipeline check only, **not a result** (not committed; `results/smoke*` is git-ignored). Issues found and fixed:
  - `max_tokens: 800` truncated the reasoning model's output (empty replies: 14/121 turns). Raised to 4000/3000; re-run had 0/155 parse errors.
  - The approver sometimes "approved" a plain message with no structured request; the run then stalled. Fixed: the environment now replies with a notice telling the sender to use `request_approval`. This behaves the same under every defence.
  - D3: the approval view now also shows the cumulative amount already paid to the same recipient in the task lineage. Without it the approver approved each split payment on its own.
- Design change: the analysis reports benign *completion* as the usefulness metric; "any gateway block" is secondary (see PREREG).
- **2026-11-06 ~13:30 UTC** scenario suite extended to 10 variants per attack (A1–A5) and 24 benign variants (B01–B06, new: B05 email, B06 three-hop lookup-then-pay). Added Fisher exact tests and a safety–usefulness plot to `analyze.py`.
- **2026-11-06 13:39–13:48 UTC** pilot (`experiments/configs/pilot.yaml`, seed 9, 370 runs, ~$0.12). Seed 9 is **not used in the main run**. The pilot was a bug check only; its numbers are not results. Findings:
  - 0 crashed runs and 6 parse errors. Mechanics checked by reading transcripts of D3 blocks, approvals and the anti-splitting rule.
  - Measurement fix: the benign payment predicates required separate payments per invoice, so a correct single payment for the total (B04) counted as a failure and double payments were not caught. All benign payment scenarios now use `sum_equals` (vendor receives exactly the amount due). Re-scoring the pilot benign runs with the new predicate: 6 runs flipped fail→success and 1 flipped success→fail.
  - **No attack prompts, agent prompts or defences were changed after the pilot.**
- **2026-11-06 ~13:51 UTC** PREREG frozen (`docs/PREREG.md`, code_hash `ddcfa9730b96019c`), then the main run started.
- **2026-11-06 13:52–14:09 UTC** main run (`results/main_deepseek-v4-flash`, 1110 runs, 0 errors, 0 sandbox violations, 14 parse errors, 1 judge parse error, $0.38). The code_hash in `config.json` matches the PREREG.
- **2026-11-06 ~14:10 UTC** analysis additions (no effect on runs): Holm correction, Newcombe CI for H6, per-variant robustness, generated `table1.md` and `runs.csv`, PNG/SVG figures.
- **2026-11-06 14:12–14:22 UTC** **exploratory, post-hoc** run (`experiments/configs/explore_strong_approver.yaml`): approver swapped to qwen3.5-397b; D1/D3 × A3, A4, B02, B04, B06 × 3 seeds = 192 runs. Motivated by the main-run result on A3; not pre-registered. Its code_hash (`4abb809f8e89c561`) differs from the main run only because `analyze.py` changed in between; the run code is identical.
- **2026-11-06 ~17:40–18:05 UTC** **exploratory, post-hoc**: added D5 (gateway warns the approver when the payee is not on the vendor master list) and D6 (hard vendor allowlist) to `gateway.py`, plus `scenarios_explore/` (A1L/A3L/A4L with vendor-lookalike payees). Runs: `explore_d5_d6` (D3/D5/D6 × main suite × 3 seeds = 666 runs, $0.29) and `explore_lookalike` (D0–D6 × 15 lookalike variants × 3 seeds = 315 runs, $0.14). 0 errors. One lookalike run hung on an API call; the harness was restarted and resumed only that job (its `config.json` therefore shows code_hash `133ff0cf4cf84487`, which differs from `a3f4d05005d8f191` only by an `analyze.py` edit). Afterwards a docstring-only edit was made to `gateway.py`. D0–D4 code paths are unchanged (offline tests pass). Reproducibility note: the D3 re-run was served from the LLM cache for 1195/1212 calls, but 9/360 runs differed from the main run. Cause: the cache is keyed by prompt only, so D3 and D4 runs with identical prompts share a cache key, and concurrent misses overwrite each other (last write wins). D5/D6 are therefore compared with the D3 re-run from the same batch.
- Raw per-run logs (~29 MB) are not in git; they are archived as `a2a-gateway-audit_raw_logs_2026-11-06.tar.gz` (sha256 `33e09b52698357085226af5af186b6597134815f881eebc6877bc5696dbfb0a0`; contains main, pilot and all exploratory runs). Aggregated files are committed (the 1110-row `runs.csv` of the main run is in the archive and regenerated by `analyze`).

## Third-party / preexisting code

| Component | Source | License | Preexisting? |
|---|---|---|---|
| Python libraries in `pyproject.toml` (openai, adaption, pydantic, a2a-sdk, pyyaml, tenacity, python-dotenv, tqdm, pandas, matplotlib, pytest, ruff) | PyPI | their respective OSS licenses | third-party, used as dependencies |
| Report template | Apart Research (Guidelines tab) | provided for submissions | third-party |
