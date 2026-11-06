"""Approval records and capability grants (the state the gateway keeps)."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from pydantic import BaseModel, Field

from .schema import ToolCall
from .tools import amount_of


class ApprovalRecord(BaseModel):
    approval_id: str
    call: ToolCall  # the action attached to the approval request
    requester: str
    task_id: str
    lineage: frozenset[str]
    step: int
    shown_to_approver: str
    used: bool = False


class ApprovalService:
    """Issues approval ids. Ids are HMACs over the exact action, so they cannot be guessed."""

    def __init__(self, key: bytes = b"gateway-secret"):
        self._key = key
        self._n = 0
        self.records: dict[str, ApprovalRecord] = {}

    def issue(self, call: ToolCall, requester: str, task_id: str, lineage: frozenset[str],
              step: int, shown: str) -> ApprovalRecord:
        self._n += 1
        payload = f"{call.canonical()}|{task_id}|{sorted(lineage)}|{self._n}".encode()
        aid = "APR-" + hmac.new(self._key, payload, hashlib.sha256).hexdigest()[:10]
        rec = ApprovalRecord(approval_id=aid, call=call, requester=requester, task_id=task_id,
                             lineage=lineage, step=step, shown_to_approver=shown)
        self.records[aid] = rec
        return rec

    def get(self, approval_id: str | None) -> ApprovalRecord | None:
        return self.records.get(approval_id or "")


class Grant(BaseModel):
    """Capability grant. caps: tool -> {"args": {arg: [allowed values] | ["*"]},
    "max_total": {arg: limit}}. Grants only ever get narrower (intersection)."""

    caps: dict[str, dict[str, Any]] = Field(default_factory=dict)
    lineage: frozenset[str] = frozenset()

    def intersect(self, other: Grant) -> Grant:
        caps: dict[str, dict[str, Any]] = {}
        for tool in self.caps.keys() & other.caps.keys():
            a, b = self.caps[tool], other.caps[tool]
            args: dict[str, list] = {}
            for arg in set(a.get("args", {})) | set(b.get("args", {})):
                va, vb = a.get("args", {}).get(arg, ["*"]), b.get("args", {}).get(arg, ["*"])
                if va == ["*"]:
                    args[arg] = list(vb)
                elif vb == ["*"]:
                    args[arg] = list(va)
                else:
                    args[arg] = [v for v in va if v in vb]
            totals: dict[str, float] = {}
            for arg in set(a.get("max_total", {})) | set(b.get("max_total", {})):
                vals = [x["max_total"][arg] for x in (a, b) if arg in x.get("max_total", {})]
                totals[arg] = min(vals)
            caps[tool] = {"args": args, "max_total": totals}
        return Grant(caps=caps, lineage=self.lineage | other.lineage)

    def check(self, call: ToolCall, spent: dict[str, float]) -> tuple[bool, str]:
        """spent: lineage -> amount already spent with this tool in that lineage."""
        cap = self.caps.get(call.tool)
        if cap is None:
            return False, f"grant has no capability for {call.tool}"
        for arg, allowed in cap.get("args", {}).items():
            if allowed != ["*"] and call.args.get(arg) not in allowed:
                return False, f"{arg}={call.args.get(arg)!r} not in grant {allowed}"
        for arg, limit in cap.get("max_total", {}).items():
            amt = amount_of(call) if arg == "amount" else float(call.args.get(arg, 0) or 0)
            worst = max((spent.get(lin, 0.0) for lin in self.lineage), default=0.0)
            if worst + amt > limit:
                return False, f"cumulative {arg} {worst + amt:.2f} exceeds grant limit {limit}"
        return True, "within grant"
