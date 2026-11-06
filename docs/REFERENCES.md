# References — verification log

**Verified** means the URL resolved and the title matched (checked on 2026-11-06). "Read" records what we actually read; we cite only claims from what we read.

| # | Reference | URL | Exists | Read |
|---|---|---|---|---|
| 1 | Hammond et al. (2025). *Multi-Agent Risks from Advanced AI* | https://arxiv.org/abs/2502.14143 | ✅ | abstract (arXiv API, 2026-11-06) |
| 2 | Chan et al. (2025). *Infrastructure for AI Agents* | https://arxiv.org/abs/2501.10114 | ✅ | abstract |
| 3 | Chan et al. (2024). *IDs for AI Systems* | https://arxiv.org/abs/2406.12137 | ✅ | abstract |
| 4 | Google (2025). *A2A: A new era of agent interoperability* (blog) | https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/ | ✅ | ☐ |
| 5 | A2A Protocol specification ("latest", v1.0, accessed 2026-11-06) | https://a2a-protocol.org/latest/specification/ | ✅ | §3.2.5 Metadata, §7.5 Server Authorization, §7.6.3–7.6.4 In-Task Authorization |
| 6 | Greenblatt et al. *AI Control: Improving Safety Despite Intentional Subversion* | https://arxiv.org/abs/2312.06942 | ✅ | abstract |
| 7 | Debenedetti et al. (2024). *AgentDojo* | https://arxiv.org/abs/2406.13352 | ✅ | abstract |
| 8 | Debenedetti et al. (2025). *Defeating Prompt Injections by Design* (CaMeL) | https://arxiv.org/abs/2503.18813 | ✅ | abstract |
| 9 | Foerster et al. (2026). *CaMeLs Can Use Computers Too* | https://arxiv.org/abs/2601.09923 | ✅ | abstract |
| 10 | Lee & Tiwari (2024). *Prompt Infection* | https://arxiv.org/abs/2410.07283 | ✅ | abstract |
| 11 | Birgisson, Politz, Erlingsson, Taly, Vrable, Lentczner (2014, NDSS). *Macaroons: Cookies with Contextual Caveats…* | https://research.google/pubs/macaroons-cookies-with-contextual-caveats-for-decentralized-authorization-in-the-cloud/ | ✅ | abstract |
| 12 | Jones et al. (2025). Splitting tasks to evade per-agent safety filters | https://openreview.net/forum?id=GCkhEPE1FG | ⚠️ link resolves, title not confirmed (bot check) | ☐ |
| 13 | Zhang et al. (2025). Attributing failures in multi-agent systems | https://openreview.net/forum?id=GazlTYxZss | ⚠️ link resolves, title not confirmed (bot check) | ☐ |
| 14 | Swarm Traces (2026) | https://swarmtraces.org/ | ✅ | ☐ |
| 15 | METR (2026). Hugging Face incident report | https://metr.org/hugging-face-incident-report-aug-2026.pdf | ✅ (PDF) | ☐ |
| 16 | Hardy (1988). *The Confused Deputy* | https://doi.org/10.1145/54289.871709 | ⚠️ DOI blocked (403), not confirmed | ☐ |

Items 1–4, 6, 9, 10, 12–15 are listed in the sprint's Resources tab.

## Notes from the A2A specification (§ numbers of the version accessed 2026-11-06)

- §3.2.5: metadata is "a flexible key-value map for passing additional context or parameters with operations". It is free-form and set by the sender.
- §7.5: once authenticated, a server "authorizes requests based on the authenticated identity and its own policies"; authorization logic "is implementation-specific". This is the immediate caller, which is what our D1 models.
- §7.6.3: for in-band credentials passed along chains of agents, credentials "SHOULD be bound to the agent which originated the request".
- §7.6.4: "The A2A protocol does not define the scope, representation, validity, or revocation semantics of the authorization decision or credential". An implementation "is responsible for defining how the authorized operation is identified and how that authorization is checked before the operation is performed". This is exactly the gap that D3's action-bound approvals fill.
