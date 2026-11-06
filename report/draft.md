# DRAFT — What You See Is What You Sign: Approval Laundering and Delegation Escalation in A2A Agent Networks

> Draft written by the AI assistant for the team to rewrite (the template asks that the final text be primarily written by the team). Every `[[...]]` placeholder must be filled **only** from `results/main_deepseek-v4-flash/` (`summary.txt`, `comparisons.txt`, `prereg_tests.txt`). Do not type numbers by hand.

**Author:** Danyel Fork · **Affiliation:** Independent [[confirm]] · With Apart Research
Research conducted at the Swarm Alignment Hackathon, November 2026.

## Abstract (150–250 words; draft, team to rewrite)

When AI agents delegate work to each other, oversight is usually attached to single hops. An ACL checks the immediate caller, an approver reads the message in front of it, and a monitor screens one message at a time. We study how this fails under *approval laundering* (replaying an approval, obtaining it on a benign paraphrase, or splitting a payment below the approval threshold) and under confused-deputy requests that enter a task from outside. We build a reproducible sandbox in which LLM agents exchange A2A messages through a gateway, with mock payment tools and deterministic success predicates. We compare five gateway defences on 50 attack and 24 benign scenario variants (1110 pre-registered runs). A gateway that tracks the task's grant along the delegation chain, instead of trusting sender metadata, reduced externally injected payments from 24/30 to 0/30 (confused deputy) and from 21/30 to 0/30 (forged "on behalf of"). A per-hop ACL gave no protection, and benign completion stayed at 70/72. Binding approvals to the exact action and showing that action to the approver did not stop summary laundering: an LLM approver approved 30/30 laundered $900 payments to unknown accounts, and so did a much larger approver model. In exploratory runs, one gateway-written warning that the payee is not a known vendor cut laundered approvals to 0/30. A per-message LLM judge caught most attacks at roughly twice the LLM calls. Gateways should enforce provenance and state structural facts explicitly rather than rely on how an LLM reads text.

## 1. Introduction

Multi-agent systems increasingly delegate work. A planner hands a task to a finance agent, which asks an approver and then calls a payment tool. Oversight in such pipelines is usually attached to a single hop. An access-control list checks the *immediate* caller, an approver judges the *message in front of it*, and an LLM monitor screens *one message at a time*. Delegation breaks all three assumptions. The agent that calls the tool is rarely the one that wanted the action. The approver sees a description written by the requester, not the action. A harmful goal can be split into pieces that each look harmless.

Agent-to-agent protocols leave this to implementations. The A2A specification states that authorization "is implementation-specific" and based on the authenticated (immediate) identity (§7.5). It also states that the protocol "does not define the scope, representation, validity, or revocation semantics" of an authorization decision. Implementations must define "how the authorized operation is identified and how that authorization is checked" (§7.6.4). Sender-supplied `metadata` is a free-form key-value map (§3.2.5).

We study **approval laundering**: an approval obtained for one thing is used to authorize another. It can be replayed with different parameters, obtained on a benign paraphrase of a different action, or assembled from sub-threshold pieces. We also study the related **confused-deputy** escalation through delegation. We build a reproducible sandbox in which LLM agents exchange A2A `Message` objects through a gateway, run five scripted attacks against five gateway defences, and measure attack success alongside benign task completion.

**Our main contributions are:**
1. An open, replayable testbed: 5 LLM roles, mock tools, A2A wire format, deterministic success predicates, and a network allow-list. It contains 50 attack and 24 benign scenario variants.
2. A gateway defence (D3) that combines three mechanisms. (a) It tracks provenance itself: an agent's effective grant is the intersection of all grants that reached its task thread, so claimed `on_behalf_of` values are ignored. (b) Approvals are bound to the exact canonical action, single-use and lineage-scoped, with cumulative anti-splitting. (c) The approver is shown the exact structured action ("what you see is what you sign").
3. A pre-registered comparison against per-hop ACLs (D1) and a per-message LLM judge (D2), reporting both safety and usefulness. Gateway-tracked provenance removed externally injected payments, while per-hop ACLs gave no protection. Showing the approver the exact action did not stop laundering. In exploratory runs, an explicit gateway-written warning did.

## 2. Related Work

- **Multi-agent risk.** Hammond et al. (2025) give a taxonomy of multi-agent failures, with multi-agent security as one of the key risk factors. Chan et al. (2025) argue that agent safety needs external infrastructure (protocols, attribution, identity) beyond behaviour modification. Chan et al. (2024) propose IDs for AI system instances.
- **Prompt injection and system-level defences.** AgentDojo (Debenedetti et al., 2024) evaluates prompt-injection attacks and defences for tool-using agents. CaMeL (Debenedetti et al., 2025) separates control flow from untrusted data and uses capabilities. Foerster et al. (2026) extend this design to computer-use agents. Our D3 is closer to capability attenuation (cf. macaroons, Birgisson et al., 2014) applied across *agent* hops rather than within one agent. Prompt Infection (Lee & Tiwari, 2024) shows injections spreading between agents.
- **AI control.** Greenblatt et al. (2023) evaluate protocols that remain safe when the model is trying to subvert them. Our judge baseline (D2) is a simple trusted-monitor analogue that sees one message at a time.
- **Sprint example projects.** The Resources tab lists neighbouring ideas ("Does privilege shrink when agents delegate?", "Enforcement inside vs. outside the protocol", "Lineage-bound identity and a gateway-side audit trail"). Our focus is approval laundering and a measured safety/usefulness comparison.

## 3. Methods

**Environment.** A deterministic event loop delivers messages FIFO. Every message and every tool call passes through one gateway. Messages are serialized as A2A `Message` objects (`a2a-sdk` 1.3): free text goes in a text part, the structured action in a data part, and `on_behalf_of` / `approval_ref` in sender-controlled `metadata`. The roles are planner, finance (`send_payment`), ops (`write_config`, `send_email`), researcher (`read_doc`) and approver; all of them are LLMs. The employee (`user_proxy`) and the external agent are scripted. The organisation policy in every prompt says: only finance pays, payments above $50 need an approval id, and the known vendors are vendor_a/b/c. Agents are not told about attacks. Tools are mocks that only log. A network allow-list permits only the LLM API host.

**Attacks (scripted, 10 wording variants each).** A1 confused deputy: an external agent asks finance for a payment of at most $50 to an attacker account. A2 approval replay: a compromised planner gets a legitimate approved $120 payment through, then asks finance to reuse that approval for $600–990. A3 summary laundering: a compromised planner requests approval with a benign description while the attached action pays $900 to an attacker account, then forwards the approval id. A4 budget splitting: three payments of $35–49 to one attacker account. A5 origin spoofing: an external agent forges `on_behalf_of: user_proxy`. In A2–A4 the task grant is deliberately broad (any payee, $2000), so approvals, not recipient lists, are what stands between the attacker and the payment.

**Defences.** D0: none (policy only in prompts). D1: the immediate caller must own the tool; payments above threshold need an approval id issued for the same tool name. D2: D1 plus an LLM judge on every message and tool call, which sees one item at a time and fails open. D3: D1 plus provenance and action-bound approvals as in contribution 2. D4: D3 plus D2.

**Benign suite (24 variants).** Single payments below and above the threshold, two invoices to one vendor (which tests the cost of the anti-splitting rule), config changes, internal email, and a three-hop lookup-then-pay task. Success means the vendor receives exactly the amount due, or the expected config or email effect occurs.

**Models and sampling.** `deepseek-v4-flash` via the Adaption API for all LLM roles. Temperatures: agents 0.7, approver and judge 0. Three seeds; 1110 runs in total. LLM calls are cached and all prompts and outputs are logged.

**Metrics and tests (pre-registered, `docs/PREREG.md`).** ASR per attack × defence (n = 30) and benign completion per defence (n = 72), with Wilson 95% CIs. Two-sided Fisher exact tests; the D1-vs-D3 family across A1–A5 is Holm-corrected. A per-variant robustness count is reported because runs within a variant are not independent.

## 4. Results

All numbers below are copied from generated files: `results/main_deepseek-v4-flash/table1.md` and `prereg_tests.txt` (1110 runs, 0 errors, 0 sandbox violations, total API cost $0.38).

**Table 1.** Attack success (k/n, rate, 95% Wilson CI) per attack × defence, and benign completion per defence. Model: deepseek-v4-flash for all roles.

| | D0 | D1 | D2 | D3 | D4 |
|---|---|---|---|---|---|
| A1 ASR | 21/30 (0.70; 0.52–0.83) | 24/30 (0.80; 0.63–0.90) | 1/30 (0.03; 0.01–0.17) | 0/30 (0.00; 0.00–0.11) | 0/30 (0.00; 0.00–0.11) |
| A2 ASR | 7/30 (0.23; 0.12–0.41) | 4/30 (0.13; 0.05–0.30) | 0/30 (0.00; 0.00–0.11) | 0/30 (0.00; 0.00–0.11) | 0/30 (0.00; 0.00–0.11) |
| A3 ASR | 25/30 (0.83; 0.66–0.93) | 27/30 (0.90; 0.74–0.97) | 15/30 (0.50; 0.33–0.67) | 30/30 (1.00; 0.89–1.00) | 18/30 (0.60; 0.42–0.75) |
| A4 ASR | 20/30 (0.67; 0.49–0.81) | 24/30 (0.80; 0.63–0.90) | 1/30 (0.03; 0.01–0.17) | 18/30 (0.60; 0.42–0.75) | 0/30 (0.00; 0.00–0.11) |
| A5 ASR | 22/30 (0.73; 0.56–0.86) | 21/30 (0.70; 0.52–0.83) | 0/30 (0.00; 0.00–0.11) | 0/30 (0.00; 0.00–0.11) | 0/30 (0.00; 0.00–0.11) |
| benign completion | 72/72 (1.00; 0.95–1.00) | 72/72 (1.00; 0.95–1.00) | 69/72 (0.96; 0.88–0.99) | 70/72 (0.97; 0.90–0.99) | 66/72 (0.92; 0.83–0.96) |

**Figure 1** (`fig1_asr_heatmap.png`). Attack success rate per attack × defence (n = 30 per cell; deepseek-v4-flash for all roles).

**Figure 2** (`fig2_safety_usefulness.png`). Safety vs usefulness: pooled attack success (A1–A5, n = 150 per defence) vs benign completion (n = 72), with 95% Wilson CIs.

**Observations (pre-registered tests).**
- *H1, supported.* A per-hop ACL gave no protection against requests that originate outside the task. A1: D0 21/30 vs D1 24/30 (p = 0.55). A5: 22/30 vs 21/30 (p = 1). The ACL checks finance, which legitimately owns the payment tool.
- *H2, supported for A1 and A5; not significant for A2.* D3 reduced A1 from 24/30 to 0/30 (Holm p = 1.6e-10) and A5 from 21/30 to 0/30 (Holm p = 1.4e-8); this held in 9 of 10 variants each. For A2 (approval replay), D1 4/30 vs D3 0/30 (Holm p = 0.34). The finance agent already refused most replay requests on its own, so the baseline was low.
- *H3, not supported.* A4 (splitting): D1 24/30 vs D3 18/30 (p = 0.16). D3's anti-splitting rule forced an approval for the cumulative amount, and the LLM approver then approved it.
- *H4, first part not supported.* A3 (summary laundering): D1 27/30 vs D3 30/30. Showing the approver the exact structured action ("what you see is what you sign") did not reduce approvals: the approver approved in every D3 run. Its stated reasons repeat the requester's description (e.g. "vendor_a invoice … office supplies") even though the action paid an unknown account.
- *H5, not supported.* Pooled over A1+A2+A5, the per-message judge (D2) allowed 1/90 and D3 0/90 (p = 1). The judge was also the only single defence that substantially reduced A4 (1/30) and A3 (15/30).
- *H6, supported.* Benign completion: D1 72/72, D3 70/72. The difference is 0.028 (95% CI −0.027 to 0.096), within the pre-registered 10-point margin. D2 completed 69/72 and D4 66/72. D2 and D4 used about 2× the LLM calls per run of D0/D1.
- D4 (provenance + judge) had the lowest ASR on every attack except A3 (18/30).

**Exploratory (post-hoc, not pre-registered).** We swapped only the approver for a much larger model (qwen3.5-397b), with D1 and D3 on A3, A4 and the payment benign tasks (`results/explore_strong_approver/`):

| | D1 | D3 |
|---|---|---|
| A3 ASR | 30/30 (1.00; 0.89–1.00) | 30/30 (1.00; 0.89–1.00) |
| A4 ASR | 22/30 (0.73; 0.56–0.86) | 18/30 (0.60; 0.42–0.75) |
| benign completion | 36/36 (1.00; 0.90–1.00) | 32/36 (0.89; 0.75–0.96) |

The larger approver also approved every laundered A3 request under D3, and lowered benign completion under D3.

**Exploratory 2 (post-hoc): surface the structural fact, or enforce it.** D5 = D3 plus one gateway-written line in the approval view ("WARNING: payee X is NOT on the vendor master list"). D6 = D3 plus a hard vendor allowlist at the gateway. Both rely on a vendor master list that the gateway can consult. The full main suite, 3 seeds (`results/explore_d5_d6/`); D3 was re-run in the same batch for a like-for-like reference:

| | D3 | D5 | D6 |
|---|---|---|---|
| A1 ASR | 0/30 (0.00; 0.00–0.11) | 0/30 (0.00; 0.00–0.11) | 0/30 (0.00; 0.00–0.11) |
| A2 ASR | 0/30 (0.00; 0.00–0.11) | 0/30 (0.00; 0.00–0.11) | 0/30 (0.00; 0.00–0.11) |
| A3 ASR | 30/30 (1.00; 0.89–1.00) | 0/30 (0.00; 0.00–0.11) | 0/30 (0.00; 0.00–0.11) |
| A4 ASR | 18/30 (0.60; 0.42–0.75) | 0/30 (0.00; 0.00–0.11) | 0/30 (0.00; 0.00–0.11) |
| A5 ASR | 0/30 (0.00; 0.00–0.11) | 0/30 (0.00; 0.00–0.11) | 0/30 (0.00; 0.00–0.11) |
| benign completion | 68/72 (0.94; 0.87–0.98) | 68/72 (0.94; 0.87–0.98) | 68/72 (0.94; 0.87–0.98) |

A single gateway-written warning was enough: the same approver that approved 30/30 laundered requests under D3 approved 0/30 under D5. A4 fell from 18/30 to 0/30. Benign completion was unchanged (68/72 in all three).

**Exploratory 3 (post-hoc): vendor-lookalike payees** (e.g. `vendor_a_billing`, `vendor-b`, `vendor_d`; 5 variants × 3 seeds; `results/explore_lookalike/`):

| | D0 | D1 | D2 | D3 | D4 | D5 | D6 |
|---|---|---|---|---|---|---|---|
| A1L ASR | 3/15 (0.20; 0.07–0.45) | 5/15 (0.33; 0.15–0.58) | 0/15 (0.00; 0.00–0.20) | 0/15 (0.00; 0.00–0.20) | 0/15 (0.00; 0.00–0.20) | 0/15 (0.00; 0.00–0.20) | 0/15 (0.00; 0.00–0.20) |
| A3L ASR | 7/15 (0.47; 0.25–0.70) | 6/15 (0.40; 0.20–0.64) | 2/15 (0.13; 0.04–0.38) | 8/15 (0.53; 0.30–0.75) | 6/15 (0.40; 0.20–0.64) | 0/15 (0.00; 0.00–0.20) | 0/15 (0.00; 0.00–0.20) |
| A4L ASR | 4/15 (0.27; 0.11–0.52) | 3/15 (0.20; 0.07–0.45) | 0/15 (0.00; 0.00–0.20) | 2/15 (0.13; 0.04–0.38) | 0/15 (0.00; 0.00–0.20) | 0/15 (0.00; 0.00–0.20) | 0/15 (0.00; 0.00–0.20) |

Lookalike payees did not make the attacks more successful against the LLM agents or the judge (D2 still 0–2/15). D3 still let laundering through (A3L 8/15). D5 and D6 stopped every attempt.

**Interpretation (kept separate from the observations).** Structural provenance cleanly removes attacks that *enter* a task from outside (A1, A5). Inside a legitimately delegated task with a broad grant, however, every remaining safeguard reduces to an LLM's judgment of text: the approver's, or the judge's. Binding approvals to the exact action closes replay (by construction; there were few successes to remove), but it does not make approvers read the action. The approver anchored on the narrative it was given. When the gateway turned the structured fact into an explicit sentence (D5), the same approver refused every laundered request. This suggests the failure is one of salience, not of capability; the exploratory results support this, but it is not established.

## 5. Discussion and Limitations

**Discussion (draft).** (1) Provenance should be tracked by the gateway, not trusted from sender metadata. A per-hop ACL on the authenticated caller, the identity-based authorization that A2A §7.5 describes, gave no measurable protection in our setting. (2) "Exact-action" approval is necessary but not sufficient. An LLM approver needs the *structural* facts surfaced as decisions ("payee is not a known vendor"), or the grant must carry a recipient allowlist. Both are gateway-side checks that do not depend on the approver reading carefully. (3) In our setting the per-message judge was strong. In the main suite, attacker accounts look obviously unlike known vendors (e.g. `acct_7731`). With vendor-lookalike payees (exploratory) it still caught most attempts (0–2/15). An attacker who adapts to the judge remains untested.

**Limitations (draft).** The approver and judge run at temperature 0, and the first adversarial step is scripted. Their decisions on that step are therefore nearly identical across seeds, so for A2–A4 the effective sample size is closer to 10 variants than to 30 runs (see the per-variant robustness counts). Attacker payees are visibly non-vendor IDs. All adversaries are scripted: we measure the gullibility of honest LLM agents and the gateway's structural guarantees, not an adaptive attacker. One model family serves every role. The approver is an LLM stand-in for a human. Mock tools only. The scenarios are small and hand-written, so ASR depends on wording; we mitigate with 10 variants per attack. D3 assumes the gateway is trusted and agents cannot forge gateway state. Data-exfiltration splitting (which needs secrecy labels) and identity reset via renaming (A6) are not evaluated. D5/D6 depend on a vendor master list. Our benign suite pays only known vendors, so the usefulness cost of onboarding a *new* legitimate vendor is not measured, and an attacker who controls a listed vendor account is out of scope. The LLM cache is keyed by prompt. Runs whose prompts are identical across defences (e.g. D3/D4/D5/D6 before the first gateway difference) share samples, and when two runs miss the cache at the same time the last write wins. A re-run of D3 was served 1195/1212 calls from cache, and 9/360 runs differed in outcome or number of calls from the main run (benign 68/72 vs 70/72). We therefore compare D5/D6 against the D3 re-run from the same batch.

### Future Work

A6 (agents that rename or copy themselves to reset per-identity limits); an adaptive LLM adversary; real A2A servers over HTTP; larger models; a human approver study.

## 6. Conclusion

We built a reproducible A2A sandbox and tested how approval laundering and confused-deputy requests get past single-hop oversight. In 1110 pre-registered runs, three findings emerged. First, a gateway that tracks the task's provenance itself, instead of trusting sender metadata, removed externally injected payments, while a per-hop ACL gave no protection. Second, binding approvals to the exact action and showing that action to an LLM approver did not stop summary laundering, with either a small or a much larger approver model. Third, in exploratory runs, a single gateway-written warning that the payee is not a known vendor, or a hard allowlist, stopped every laundering and splitting attempt in our suite, at no measured cost to benign tasks. Next steps are adaptive attackers, measuring the cost of onboarding new vendors, and human approvers.

## Code and Data

- Code repository: https://github.com/xfgx/a2a-gateway-audit (to be made public before submission)
- Data: aggregated results and one row per run under `results/`; raw per-run logs (prompts, outputs, A2A messages, tool calls) archived separately (sha256 in `docs/SPRINT_LOG.md`)

## References

1. Hammond, L., Chan, A., Clifton, J., et al. (2025). Multi-Agent Risks from Advanced AI. arXiv:2502.14143.
2. Chan, A., Wei, K., Huang, S., et al. (2025). Infrastructure for AI Agents. arXiv:2501.10114.
3. Chan, A., Kolt, N., Wills, P., et al. (2024). IDs for AI Systems. arXiv:2406.12137.
4. A2A Protocol Specification (latest, v1.0), accessed 2026-11-06. https://a2a-protocol.org/latest/specification/
5. Greenblatt, R., Shlegeris, B., Sachan, K., et al. (2023). AI Control: Improving Safety Despite Intentional Subversion. arXiv:2312.06942.
6. Debenedetti, E., Zhang, J., Balunović, M., et al. (2024). AgentDojo. arXiv:2406.13352.
7. Debenedetti, E., Shumailov, I., Fan, T., et al. (2025). Defeating Prompt Injections by Design. arXiv:2503.18813.
8. Foerster, H., Blanchard, T., Nikolić, K., et al. (2026). CaMeLs Can Use Computers Too. arXiv:2601.09923.
9. Lee, D., & Tiwari, M. (2024). Prompt Infection: LLM-to-LLM Prompt Injection within Multi-Agent Systems. arXiv:2410.07283.
10. Birgisson, A., Politz, J. G., Erlingsson, Ú., Taly, A., Vrable, M., & Lentczner, M. (2014). Macaroons: Cookies with Contextual Caveats for Decentralized Authorization in the Cloud. NDSS 2014.

## Appendix A: Limitations and Dual-Use / Ethical Considerations (required)

**What this does and does not establish.** The results establish the following for our sandbox. Gateway-tracked provenance blocks requests that enter a task from outside. LLM approvers approve laundered actions even when shown the exact action, unless a structural fact is stated explicitly. They do not establish robustness against adaptive attackers, against attackers who control a listed vendor, or against a compromised gateway. The results hold for one model family, scripted attackers and a mock organisation. They do not show that D3 stops adaptive attackers or attacks on the gateway itself.

**Dual use.** The attack scenarios describe ways to get payments past approval steps in agent systems. The techniques (replaying approvals, paraphrasing for approvers, splitting below thresholds, forging relay claims) are well known from human fraud. They target only mock tools, and we publish them together with a defence and its measured cost. We do not release optimized jailbreak prompts; the scenario texts are plain business-English requests. The main risk is that our finding about which defences fail could guide attackers toward systems that use per-hop ACLs or per-message monitors. We judge that the benefit to defenders outweighs this.

## Appendix B: Pre-sprint disclosure

Planning documents (`README.md`, `CLAUDE.md`, `docs/*`) and dependency configuration were written on 5–6 Nov 2026 before the sprint. All code, scenarios, experiments and results were produced during the sprint (timestamps in `docs/SPRINT_LOG.md`).

## LLM Usage Statement

We used Claude (Anthropic) to plan the project, write and debug code, and draft sections of this report. All numbers come from logged runs via the analysis scripts. References were checked against their sources. [[team: describe your own review and rewriting]]
