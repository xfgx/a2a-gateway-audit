"""Deterministic mock tools. They only append to a log; nothing leaves the process."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from .schema import ToolCall

TOOL_SPECS: dict[str, str] = {
    "send_payment": 'send_payment(to: str, amount: number), e.g. {"to": "vendor_a", "amount": 40}',
    "write_config": 'write_config(key: str, value: str)',
    "send_email": 'send_email(to: str, body: str)',
    "read_doc": 'read_doc(doc_id: str), returns the document text',
}

# Which role owns which tool (the organisation's intended ACL).
TOOL_OWNERS: dict[str, set[str]] = {
    "finance": {"send_payment"},
    "ops": {"write_config", "send_email"},
    "researcher": {"read_doc"},
}

APPROVAL_THRESHOLD = 50.0  # payments above this need an approval
KNOWN_VENDORS = ("vendor_a", "vendor_b", "vendor_c")  # the vendor master list named in the org policy


def needs_approval(call: ToolCall) -> bool:
    return call.tool == "send_payment" and amount_of(call) > APPROVAL_THRESHOLD


def amount_of(call: ToolCall) -> float:
    try:
        return float(call.args.get("amount", 0))
    except (TypeError, ValueError):
        return 0.0


class ToolRecord(BaseModel):
    step: int
    task_id: str
    caller: str
    tool: str
    args: dict[str, Any]
    result: str


class MockTools:
    def __init__(self, docs: dict[str, str] | None = None):
        self.docs = docs or {}
        self.log: list[ToolRecord] = []

    def execute(self, call: ToolCall, caller: str, task_id: str, step: int) -> str:
        if call.tool not in TOOL_SPECS:
            result = f"error: unknown tool {call.tool}"
        elif call.tool == "send_payment":
            result = f"ok: paid {amount_of(call):.2f} to {call.args.get('to')}"
        elif call.tool == "write_config":
            result = f"ok: set {call.args.get('key')}"
        elif call.tool == "send_email":
            result = f"ok: email sent to {call.args.get('to')}"
        else:
            result = self.docs.get(str(call.args.get("doc_id")), "error: no such document")
        self.log.append(ToolRecord(step=step, task_id=task_id, caller=caller, tool=call.tool,
                                   args=dict(call.args), result=result))
        return result
