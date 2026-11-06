"""Deterministic event loop. Every message and every tool call goes through the gateway."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict
from typing import Any

from .a2a_wire import to_dict
from .agents import LLMAgent, ScriptedAgent, TurnLog, render
from .approvals import ApprovalService, Grant
from .gateway import Gateway
from .llm import LLMClient
from .scenarios import Scenario
from .schema import Action, Message, ToolCall
from .tools import TOOL_OWNERS, MockTools

LLM_ROLES = ("planner", "finance", "ops", "researcher", "approver")


class Environment:
    def __init__(self, scenario: Scenario, defence: str, agent_llm: LLMClient, approver_llm: LLMClient,
                 judge_llm: LLMClient | None, seed: int = 0, max_steps: int = 30):
        self.s = scenario
        self.max_steps = max_steps
        self.events: list[dict[str, Any]] = []
        self.turns: list[dict[str, Any]] = []
        self.step = 0
        self._n = 0
        self.tools = MockTools(scenario.docs)
        self.approvals = ApprovalService()
        grants = {"user_proxy": Grant(caps=scenario.grant, lineage=frozenset({f"{scenario.task_id}:user_proxy"}))}
        self.gateway = Gateway(defence, self.approvals, grants, judge_llm=judge_llm, judge_sample=seed,
                               on_judge=lambda d: self.turns.append({"agent": "judge", **d}))
        self.agents: dict[str, LLMAgent | ScriptedAgent] = {}
        for role in LLM_ROLES:
            if role in scenario.scripted:
                self.agents[role] = ScriptedAgent(role, scenario.scripted[role])
            else:
                llm = approver_llm if role == "approver" else agent_llm
                self.agents[role] = LLMAgent(role, role, TOOL_OWNERS.get(role, set()), llm, sample_idx=seed)
        for name in ("user_proxy", "external"):
            self.agents[name] = ScriptedAgent(name, scenario.scripted.get(name, []))
        self.queue: deque[Message] = deque()
        self.pending = sorted(scenario.inject, key=lambda m: m.get("at_step", 0))
        self.requests: dict[str, Message] = {}

    # ---- helpers ----------------------------------------------------------------------
    def _id(self) -> str:
        self._n += 1
        return f"m{self._n:03d}"

    def _log(self, kind: str, **kw) -> None:
        self.events.append({"step": self.step, "event": kind, **kw})

    def _on_turn(self, t: TurnLog) -> None:
        self.turns.append(asdict(t))

    def _enqueue(self, **kw) -> Message:
        msg = Message(msg_id=self._id(), step=self.step, **kw)
        self.queue.append(msg)
        return msg

    def _inject(self, spec: dict) -> None:
        spec = dict(spec)
        spec.pop("at_step", None)
        tc = spec.pop("tool_call", None)
        self._enqueue(task_id=spec.pop("task_id", self.s.task_id), kind=spec.pop("kind", "message"),
                      tool_call=ToolCall(**tc) if tc else None, **spec)

    # ---- main loop --------------------------------------------------------------------
    def run(self) -> None:
        while self.step < self.max_steps:
            while self.pending and (self.pending[0].get("at_step", 0) <= self.step or not self.queue):
                self._inject(self.pending.pop(0))
            if not self.queue:
                break
            msg = self.queue.popleft()
            self.step += 1
            msg.step = self.step
            self._deliver(msg)
        self._log("end", reason="max_steps" if self.step >= self.max_steps else "quiescent")

    def _deliver(self, msg: Message) -> None:
        if msg.sender == "gateway":
            decision = None
        else:
            decision = self.gateway.on_message(msg)
        self._log("message", a2a=to_dict(msg, context_id=self.s.key), grant=msg.grant_id,
                  decision=decision.model_dump() if decision else None)
        if decision is not None and not decision.allow:
            self._log("block", where="message", reason=decision.reason, sender=msg.sender, recipient=msg.recipient)
            if msg.sender in self.agents:
                self._enqueue(task_id=msg.task_id, sender="gateway", recipient=msg.sender, kind="refusal",
                              content=f"Your message to {msg.recipient} was blocked by the gateway: {decision.reason}")
            return
        agent = self.agents.get(msg.recipient)
        if agent is None:
            self._log("undeliverable", recipient=msg.recipient)
            return
        if msg.kind == "approval_request":
            self.requests[msg.msg_id] = msg
        extra = self.gateway.extra_for(msg)
        actions = agent.act(msg, extra, self._on_turn)
        self._handle(agent, msg, actions, depth=0)

    def _handle(self, agent, incoming: Message, actions: list[Action], depth: int) -> None:
        task_id, me = incoming.task_id, agent.name
        observations = []
        for a in actions:
            if a.type == "send" and a.to:
                self._enqueue(task_id=task_id, sender=me, recipient=a.to,
                              kind="result" if a.to == "user_proxy" else "message", content=a.content,
                              parent_id=incoming.msg_id, on_behalf_of=a.on_behalf_of, approval_ref=a.approval_ref)
            elif a.type == "done":
                self._enqueue(task_id=task_id, sender=me, recipient="user_proxy", kind="result",
                              content=a.content, parent_id=incoming.msg_id)
            elif a.type == "request_approval" and a.tool:
                self._enqueue(task_id=task_id, sender=me, recipient="approver", kind="approval_request",
                              content=a.content, tool_call=ToolCall(tool=a.tool, args=a.args),
                              parent_id=incoming.msg_id, on_behalf_of=a.on_behalf_of)
            elif a.type == "tool" and a.tool:
                call = ToolCall(tool=a.tool, args=a.args)
                d = self.gateway.on_tool_call(call, me, task_id, a.approval_ref)
                self._log("tool_call", caller=me, task_id=task_id, call=call.model_dump(),
                          approval_ref=a.approval_ref, decision=d.model_dump())
                if d.allow:
                    result = self.tools.execute(call, me, task_id, self.step)
                else:
                    self._log("block", where="tool", reason=d.reason, caller=me, call=call.model_dump())
                    result = f"BLOCKED by gateway: {d.reason}"
                observations.append(f"{call.canonical()} -> {result}")
            elif a.type in ("approve", "deny"):
                self._decide_approval(agent, incoming, a)
            else:
                self._log("invalid_action", agent=me, action=a.model_dump())
        if observations and depth == 0:
            follow = agent.observe(task_id, "\n".join(observations), self._on_turn)
            self._handle(agent, incoming, follow, depth=1)

    def _decide_approval(self, agent, incoming: Message, a: Action) -> None:
        req = self.requests.get(a.request_id or "") or (incoming if incoming.kind == "approval_request" else None)
        if agent.name != "approver" or req is None or req.tool_call is None:
            self._log("invalid_action", agent=agent.name, action=a.model_dump())
            if agent.name == "approver" and incoming.sender in self.agents:
                # environment notice (same under every defence): approvals need a structured request
                self._enqueue(task_id=incoming.task_id, sender="gateway", recipient=incoming.sender, kind="refusal",
                              content="The approver can only issue approvals for structured requests. "
                                      "Use a request_approval action with the exact tool and args.")
            return
        self.requests.pop(req.msg_id, None)
        if a.type == "approve":
            rec = self.approvals.issue(req.tool_call, req.sender, req.task_id, self.gateway.lineage_of(req.msg_id),
                                       self.step, shown=render(req, self.gateway.extra_for(req)))
            self._log("approval_issued", approval=rec.model_dump(mode="json"))
            self._enqueue(task_id=req.task_id, sender="approver", recipient=req.sender, kind="approval",
                          approval_ref=rec.approval_id, parent_id=req.msg_id,
                          content=f"APPROVED request {req.msg_id}; approval id {rec.approval_id}. {a.content}")
        else:
            self._log("approval_denied", request=req.msg_id, reason=a.content)
            self._enqueue(task_id=req.task_id, sender="approver", recipient=req.sender, kind="approval",
                          parent_id=req.msg_id, content=f"DENIED request {req.msg_id}. {a.content}")
