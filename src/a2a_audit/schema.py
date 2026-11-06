"""Core data model: messages, tool calls, agent actions, gateway decisions."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

Kind = Literal["task", "message", "approval_request", "approval", "refusal", "result"]


class ToolCall(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)

    def canonical(self) -> str:
        """Canonical form used to bind approvals: numbers (incl. numeric strings) as floats, strings stripped."""
        def norm(v: Any) -> Any:
            if isinstance(v, bool):
                return v
            if isinstance(v, (int, float)):
                return float(v)
            if isinstance(v, str):
                try:
                    return float(v)
                except ValueError:
                    return v.strip()
            return v

        args = {k: norm(v) for k, v in self.args.items()}
        return json.dumps({"tool": self.tool, "args": args}, sort_keys=True, separators=(",", ":"))


class Message(BaseModel):
    msg_id: str
    task_id: str
    step: int = 0
    sender: str
    recipient: str
    kind: Kind
    content: str = ""
    tool_call: ToolCall | None = None  # approval_request: the action to be approved
    parent_id: str | None = None
    on_behalf_of: str | None = None  # CLAIMED principal, sender-controlled
    approval_ref: str | None = None
    # Written by the gateway only; agents cannot set these.
    grant_id: str | None = None
    chain: list[str] = Field(default_factory=list)


ActionType = Literal["send", "tool", "request_approval", "approve", "deny", "done"]


class Action(BaseModel):
    """One action emitted by an agent in a turn."""

    type: ActionType
    to: str | None = None
    content: str = ""
    tool: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    approval_ref: str | None = None
    on_behalf_of: str | None = None
    request_id: str | None = None  # approve/deny: msg_id of the approval_request


class Decision(BaseModel):
    allow: bool
    reason: str = ""
    defence: str = ""
