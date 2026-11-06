"""Offline test doubles: a deterministic 'obedient' policy standing in for LLM agents.

These are NOT a model of LLM behaviour; they only exercise the plumbing so that gateway
logic can be tested without network access.
"""

from __future__ import annotations

import json
import re

import pytest

from a2a_audit.llm import LLMClient, LLMConfig

PAY = re.compile(r"(\d+)\s*(?:usd|dollars?)?\s*(?:\w+\s+){0,3}?(?:to|for)?\s*\b((?:vendor|acct|ext_pay)_\w+)", re.IGNORECASE)
PAY2 = re.compile(r"\b((?:vendor|acct|ext_pay)_\w+)\b[^\d]{0,40}?(\d+)", re.IGNORECASE)


def _new_message(prompt: str) -> str:
    return prompt.split("NEW MESSAGE:", 1)[-1] if "NEW MESSAGE:" in prompt else prompt


def obedient(agent: str, system: str, prompt: str) -> str:
    if "TOOL RESULTS:" in prompt and "NEW MESSAGE:" not in prompt:
        return json.dumps({"actions": [{"type": "done", "content": "done"}]})
    msg = _new_message(prompt)
    if agent == "planner":
        target = "ops" if "config" in msg.lower() else "finance"
        body = msg.split("\n", 1)[-1]
        return json.dumps({"actions": [{"type": "send", "to": target, "content": body}]})
    if agent == "approver":
        rid = re.search(r"\[(m\d+)\]", msg).group(1)
        return json.dumps({"actions": [{"type": "approve", "request_id": rid, "content": "ok"}]})
    if agent == "ops":
        m = re.search(r"key (\w+) to (\w+)", msg)
        return json.dumps({"actions": [{"type": "tool", "tool": "write_config",
                                        "args": {"key": m.group(1), "value": m.group(2)}}]})
    if agent == "finance":
        ref = None
        refs = re.findall(r"approval id (APR-\w+)", prompt) + re.findall(r"approval_ref: (APR-\w+)", prompt)
        if refs:
            ref = refs[-1]
        if "APPROVED" in msg and ref:  # approval arrived: pay what was requested earlier
            last = [json.loads(x.split("YOU REPLIED: ", 1)[1]) for x in prompt.split("\n\n") if x.startswith("YOU REPLIED: ")]
            for acts in reversed(last):
                for a in acts:
                    if a.get("type") == "request_approval":
                        return json.dumps({"actions": [{"type": "tool", "tool": "send_payment",
                                                        "args": a["args"], "approval_ref": ref}]})
        pays = [(int(a), t) for t, a in PAY2.findall(msg)] or [(int(a), t) for a, t in PAY.findall(msg)]
        pays = [(a, t) for a, t in pays if not t.lower().startswith("inv")]
        if not pays:
            return json.dumps({"actions": [{"type": "done", "content": "nothing to do"}]})
        amt, to = pays[0]
        if re.search(r"three|3 separate|separate payments|invoices:", msg, re.IGNORECASE):
            nums = [int(x) for x in re.findall(r"\b(\d{2})\b", msg)]
            return json.dumps({"actions": [{"type": "tool", "tool": "send_payment", "args": {"to": to, "amount": n}}
                                           for n in nums[:3]]})
        if amt > 50 and not ref:
            return json.dumps({"actions": [{"type": "request_approval", "tool": "send_payment",
                                            "args": {"to": to, "amount": amt}, "content": "invoice"}]})
        return json.dumps({"actions": [{"type": "tool", "tool": "send_payment", "args": {"to": to, "amount": amt},
                                        "approval_ref": ref}]})
    return json.dumps({"actions": [{"type": "done", "content": ""}]})


def allow_judge(agent: str, system: str, prompt: str) -> str:
    return '{"verdict": "allow", "reason": "test"}'


@pytest.fixture
def clients():
    agent = LLMClient(LLMConfig(backend="scripted"), script=obedient)
    judge = LLMClient(LLMConfig(backend="scripted"), script=allow_judge)
    return agent, judge
