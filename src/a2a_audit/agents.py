"""Agents: LLM-driven roles and scripted (deterministic) roles."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from .llm import LLMClient
from .prompts import system_prompt
from .schema import Action, Message

MAX_ACTIONS = 3
MEMORY_LIMIT = 14


def render(msg: Message, extra: str = "") -> str:
    lines = [f"[{msg.msg_id}] FROM: {msg.sender} | KIND: {msg.kind} | TASK: {msg.task_id}"]
    if msg.on_behalf_of:
        lines.append(f"(sender says it acts on behalf of: {msg.on_behalf_of})")
    if msg.approval_ref:
        lines.append(f"(approval_ref: {msg.approval_ref})")
    if extra:
        lines.append(extra)
    lines.append(msg.content)
    return "\n".join(lines)


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def parse_actions(text: str) -> list[Action]:
    """Parse {"actions": [...]} (or a bare action / list), tolerating markdown fences."""
    m = _FENCE.search(text)
    raw = m.group(1) if m else text
    start = min([i for i in (raw.find("{"), raw.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise ValueError("no JSON found")
    obj: Any = json.JSONDecoder().raw_decode(raw[start:])[0]
    if isinstance(obj, dict) and "actions" in obj:
        obj = obj["actions"]
    if isinstance(obj, dict):
        obj = [obj]
    return [Action.model_validate(a) for a in obj][:MAX_ACTIONS]


@dataclass
class TurnLog:
    agent: str
    prompt: str
    output: str
    actions: list[dict]
    error: str | None
    usage: dict


@dataclass
class LLMAgent:
    name: str
    role: str
    tools: set[str]
    llm: LLMClient
    sample_idx: int = 0
    memory: dict[str, list[str]] = field(default_factory=dict)
    kind: str = "llm"

    def act(self, msg: Message, extra: str, on_turn: Callable[[TurnLog], None]) -> list[Action]:
        mem = self.memory.setdefault(msg.task_id, [])
        incoming = render(msg, extra)
        history = "\n\n".join(mem[-MEMORY_LIMIT:]) or "(nothing yet)"
        prompt = f"History of this task so far:\n{history}\n\nNEW MESSAGE:\n{incoming}\n\nReply with JSON only."
        return self._run(prompt, mem, incoming, on_turn)

    def observe(self, task_id: str, observation: str, on_turn: Callable[[TurnLog], None]) -> list[Action]:
        mem = self.memory.setdefault(task_id, [])
        history = "\n\n".join(mem[-MEMORY_LIMIT:])
        prompt = f"History of this task so far:\n{history}\n\nTOOL RESULTS:\n{observation}\n\nReply with JSON only."
        return self._run(prompt, mem, f"TOOL RESULTS:\n{observation}", on_turn)

    def _run(self, prompt: str, mem: list[str], incoming: str, on_turn) -> list[Action]:
        system = system_prompt(self.role, self.tools)
        actions: list[Action] = []
        error = None
        res = None
        for attempt in range(2):
            p = prompt if attempt == 0 else prompt + f"\n\nYour previous reply was invalid ({error}). Reply with valid JSON only."
            res = self.llm.complete(system, p, sample_idx=self.sample_idx * 10 + attempt, agent=self.name)
            try:
                actions = parse_actions(res.text)
                error = None
                break
            except (ValueError, ValidationError, json.JSONDecodeError) as e:
                error = f"{type(e).__name__}: {str(e)[:120]}"
        mem.append(incoming)
        mem.append("YOU REPLIED: " + json.dumps([a.model_dump(exclude_defaults=True) for a in actions]))
        on_turn(TurnLog(self.name, prompt, res.text if res else "", [a.model_dump() for a in actions], error,
                        {"in": res.input_tokens, "out": res.output_tokens, "cost": res.cost,
                         "cached": res.cached} if res else {}))
        return actions


@dataclass
class ScriptedAgent:
    """Deterministic agent driven by rules: [{"match": substring or None, "actions": [...]}].
    Each rule fires at most once, on the first incoming message whose content contains `match`.
    "{{approval_ref}}" in an action is replaced by the incoming message's approval_ref."""

    name: str
    rules: list[dict] = field(default_factory=list)
    fired: set[int] = field(default_factory=set)
    kind: str = "scripted"

    def act(self, msg: Message, extra: str, on_turn) -> list[Action]:
        for i, rule in enumerate(self.rules):
            if i in self.fired:
                continue
            match = rule.get("match")
            if match is None or match.lower() in msg.content.lower():
                self.fired.add(i)
                ref = msg.approval_ref or ""
                acts = [Action.model_validate(json.loads(json.dumps(a).replace("{{approval_ref}}", ref)))
                        for a in rule["actions"]]
                on_turn(TurnLog(self.name, render(msg, extra), "(scripted)", [a.model_dump() for a in acts], None, {}))
                return acts
        return []

    def observe(self, task_id: str, observation: str, on_turn) -> list[Action]:
        return []
