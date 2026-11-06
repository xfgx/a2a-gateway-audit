"""Gateway defences D0-D4. Every message and tool call passes through one Gateway.

D0  none: delivers everything; tool calls always execute (policy lives only in agent prompts)
D1  ACL: immediate caller must own the tool; payments above threshold need an approval id
    that exists and was issued for the same *tool name* (args not checked, reusable)
D2  D1 + LLM judge on every message and tool call (sees one item at a time)
D3  D1 + provenance: the gateway tracks the task grant along the delegation chain (taint:
    an agent's effective grant is the intersection of all grants that reached its task thread);
    calls must fit the grant incl. cumulative budgets bound to the lineage; approvals must match
    the exact canonical call, the same lineage, and are single-use; cumulative payments to one
    recipient within a lineage above the threshold also need approval (anti-splitting); the
    approver is shown the exact structured action ("what you see is what you sign")
D4  D3 + D2
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field

from .agents import render
from .approvals import ApprovalService, Grant
from .llm import LLMClient
from .prompts import JUDGE_SYSTEM
from .schema import Decision, Message, ToolCall
from .tools import APPROVAL_THRESHOLD, TOOL_OWNERS, amount_of, needs_approval

DEFENCES = {
    "D0": dict(acl=False, judge=False, provenance=False),
    "D1": dict(acl=True, judge=False, provenance=False),
    "D2": dict(acl=True, judge=True, provenance=False),
    "D3": dict(acl=True, judge=False, provenance=True),
    "D4": dict(acl=True, judge=True, provenance=True),
}

TRUSTED_SENDERS = {"user_proxy"}  # the employee; the judge does not screen their messages


def _origins(g: Grant) -> str:
    return ", ".join(sorted({lin.split(":", 1)[-1] for lin in g.lineage})) or "unknown"


@dataclass
class Gateway:
    defence: str
    approvals: ApprovalService
    principal_grants: dict[str, Grant] = field(default_factory=dict)
    judge_llm: LLMClient | None = None
    judge_sample: int = 0
    on_judge: object = None  # callback(TurnLog-like dict)
    thread: dict[tuple[str, str], Grant] = field(default_factory=dict)
    msg_grants: dict[str, Grant] = field(default_factory=dict)
    spent: dict[str, dict[str, float]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(float)))
    spent_to: dict[tuple[str, str], float] = field(default_factory=lambda: defaultdict(float))
    judge_errors: int = 0

    def __post_init__(self):
        flags = DEFENCES[self.defence]
        self.acl, self.use_judge, self.provenance = flags["acl"], flags["judge"], flags["provenance"]
        if self.use_judge and self.judge_llm is None:
            raise ValueError(f"{self.defence} needs a judge LLM")

    # ---- provenance state -------------------------------------------------------------
    def effective(self, agent: str, task_id: str) -> Grant:
        if (agent, task_id) in self.thread:
            return self.thread[(agent, task_id)]
        return self.principal_grants.get(agent, Grant(lineage=frozenset({f"self:{agent}"})))

    def lineage_of(self, msg_id: str) -> frozenset[str]:
        g = self.msg_grants.get(msg_id)
        return g.lineage if g else frozenset()

    # ---- messages ---------------------------------------------------------------------
    def on_message(self, msg: Message) -> Decision:
        if self.provenance:
            g = self.effective(msg.sender, msg.task_id)
            self.msg_grants[msg.msg_id] = g
            msg.grant_id = "|".join(sorted(g.lineage))
            key = (msg.recipient, msg.task_id)
            self.thread[key] = self.thread[key].intersect(g) if key in self.thread else g
        if self.use_judge and msg.sender not in TRUSTED_SENDERS:
            item = render(msg)
            if msg.tool_call is not None:
                item += f"\n(attached action: {msg.tool_call.canonical()})"
            verdict = self._judge(f"MESSAGE to {msg.recipient}:\n{item}")
            if verdict is not None:
                return verdict
        return Decision(allow=True, defence=self.defence)

    def extra_for(self, msg: Message) -> str:
        """Extra header the recipient sees (D3/D4 only)."""
        if not self.provenance:
            return ""
        g = self.msg_grants.get(msg.msg_id)
        lines = [f"[gateway] verified origin of this request: {_origins(g)}" if g else ""]
        if msg.kind == "approval_request" and msg.tool_call is not None:
            lines.append(f"[gateway] EXACT ACTION YOU ARE APPROVING (verified): {msg.tool_call.canonical()}")
            if msg.tool_call.tool == "send_payment" and g is not None:
                to = str(msg.tool_call.args.get("to"))
                prior = max((self.spent_to[(lin, to)] for lin in g.lineage), default=0.0)
                lines.append(f"[gateway] already paid to {to} in this task: {prior:.2f}; "
                             f"total after this payment: {prior + amount_of(msg.tool_call):.2f}")
        return "\n".join(x for x in lines if x)

    # ---- tool calls -------------------------------------------------------------------
    def on_tool_call(self, call: ToolCall, caller: str, task_id: str, approval_ref: str | None) -> Decision:
        d = self.defence
        if self.acl and call.tool not in TOOL_OWNERS.get(caller, set()):
            return Decision(allow=False, reason=f"{caller} does not own {call.tool}", defence=d)
        g = self.effective(caller, task_id) if self.provenance else None
        if self.provenance:
            ok, why = g.check(call, self.spent[call.tool])
            if not ok:
                return Decision(allow=False, reason=why, defence=d)
        need = needs_approval(call)
        if self.provenance and call.tool == "send_payment":
            # splitting defence: cumulative payments to one recipient within a lineage count
            to = str(call.args.get("to"))
            prior = max((self.spent_to[(lin, to)] for lin in g.lineage), default=0.0)
            if prior + amount_of(call) > APPROVAL_THRESHOLD:
                need = True
        if self.acl and need:
            rec = self.approvals.get(approval_ref)
            if rec is None:
                return Decision(allow=False, reason="missing or unknown approval", defence=d)
            if rec.call.tool != call.tool:
                return Decision(allow=False, reason="approval is for a different tool", defence=d)
            if self.provenance:
                if rec.used:
                    return Decision(allow=False, reason="approval already used", defence=d)
                if rec.call.canonical() != call.canonical():
                    return Decision(allow=False, reason="call differs from the approved action", defence=d)
                if rec.lineage != g.lineage:
                    return Decision(allow=False, reason="approval from a different task lineage", defence=d)
        if self.use_judge:
            verdict = self._judge(f"TOOL CALL by {caller} (task {task_id}): {call.canonical()} "
                                  f"approval_ref={approval_ref}")
            if verdict is not None:
                return verdict
        # allowed: commit state changes
        if self.acl and need and self.provenance:
            self.approvals.get(approval_ref).used = True
        if self.provenance and "amount" in call.args:
            for lin in g.lineage:
                self.spent[call.tool][lin] += amount_of(call)
                if call.tool == "send_payment":
                    self.spent_to[(lin, str(call.args.get("to")))] += amount_of(call)
        return Decision(allow=True, defence=d)

    # ---- judge ------------------------------------------------------------------------
    def _judge(self, item: str) -> Decision | None:
        res = self.judge_llm.complete(JUDGE_SYSTEM, item, sample_idx=self.judge_sample, agent="judge")
        verdict, reason = None, ""
        try:
            text = res.text
            obj = json.loads(text[text.find("{"): text.rfind("}") + 1])
            verdict, reason = str(obj.get("verdict", "")).lower(), str(obj.get("reason", ""))
        except (ValueError, json.JSONDecodeError):
            self.judge_errors += 1  # fail-open, counted
        if callable(self.on_judge):
            self.on_judge({"item": item, "output": res.text, "verdict": verdict, "cost": res.cost,
                           "in": res.input_tokens, "out": res.output_tokens, "cached": res.cached})
        if verdict == "block":
            return Decision(allow=False, reason=f"judge: {reason}", defence=self.defence)
        return None
