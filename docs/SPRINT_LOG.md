# Sprint log & provenance

Purpose: make it trivially checkable what was done when, as required by the sprint rules on prior work.

## Pre-sprint (5–6 Nov 2026)

- Created repository.
- Planning docs: `README.md`, `CLAUDE.md`, `docs/RESEARCH_PLAN.md`, `docs/TECH_PLAN.md`, `docs/REFERENCES.md`, this file. **No code.**
- Dependency config: `pyproject.toml`, `requirements.lock.txt`, `.env.example`, `.gitignore`. **No logic.**
- Located the official Apart report template (Google Doc, linked from the Guidelines tab).

## Sprint (from Fri 6 Nov 2026, first official sprint day)

- **2026-11-06 ~13:10 UTC** started implementation: `src/a2a_audit/` (schema, A2A wire adapter, LLM client with Adaption/OpenAI/scripted backends + sqlite cache, mock tools, approvals and grants, agents, gateway D0-D4, event loop, scenarios and predicates, network sandbox, harness, analysis), 9 scenario files (4 benign, 5 attack; 2-3 variants each), offline tests (17, scripted test doubles, no network).
- **2026-11-06 ~14:00 UTC** first real-model smoke run (`experiments/configs/smoke.yaml`, deepseek-v4-flash, 1 variant x 1 seed). Pipeline check only, **not a result** (not committed; `results/smoke*` is git-ignored). Issues found and fixed:
  - `max_tokens: 800` truncated the reasoning model's output (empty replies: 14/121 turns). Raised to 4000/3000; re-run had 0/155 parse errors.
  - The approver sometimes "approved" a plain message with no structured request; the run then stalled. Fixed: the environment now replies with a notice telling the sender to use `request_approval`. This behaves the same under every defence.
  - D3: the approval view now also shows the cumulative amount already paid to the same recipient in the task lineage. Without it the approver approved each split payment on its own.
- Design change: the analysis reports benign *completion* as the usefulness metric; "any gateway block" is secondary (see PREREG).

## Third-party / preexisting code

| Component | Source | License | Preexisting? |
|---|---|---|---|
| Python libraries in `pyproject.toml` (openai, adaption, pydantic, a2a-sdk, pyyaml, tenacity, python-dotenv, tqdm, pandas, matplotlib, pytest, ruff) | PyPI | their respective OSS licenses | third-party, used as dependencies |
| Report template | Apart Research (Guidelines tab) | provided for submissions | third-party |
