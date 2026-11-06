"""Serialize our Message to/from the official A2A protocol Message type (a2a-sdk).

Our protocol-level fields travel the way they would in A2A: free text in a text part,
the structured action in a data part, and everything else (claimed principal, approval
reference) in sender-controlled `metadata`. Gateway-only fields (grant, chain) are not
part of the wire message.
"""

from __future__ import annotations

from typing import Any

import a2a.types as a2a
from google.protobuf import json_format

from .schema import Message, ToolCall

_META_KEYS = ("sender", "recipient", "kind", "step", "on_behalf_of", "approval_ref")


def to_a2a(msg: Message, context_id: str) -> a2a.Message:
    out = a2a.Message(
        message_id=msg.msg_id,
        context_id=context_id,
        task_id=msg.task_id,
        role=a2a.Role.Value("ROLE_AGENT"),
    )
    if msg.parent_id:
        out.reference_task_ids.append(msg.parent_id)
    out.parts.append(a2a.Part(text=msg.content))
    if msg.tool_call is not None:
        part = a2a.Part()
        json_format.ParseDict(msg.tool_call.model_dump(), part.data)
        out.parts.append(part)
    meta = {k: getattr(msg, k) for k in _META_KEYS if getattr(msg, k) is not None}
    out.metadata.update(meta)
    return out


def to_dict(msg: Message, context_id: str) -> dict[str, Any]:
    return json_format.MessageToDict(to_a2a(msg, context_id))


def from_a2a(wire: a2a.Message) -> Message:
    meta = json_format.MessageToDict(wire.metadata) if wire.HasField("metadata") else {}
    text, tool_call = "", None
    for part in wire.parts:
        if part.HasField("data"):
            tool_call = ToolCall.model_validate(json_format.MessageToDict(part.data))
        elif part.text:
            text = part.text
    return Message(
        msg_id=wire.message_id,
        task_id=wire.task_id,
        step=int(meta.get("step", 0)),
        sender=meta["sender"],
        recipient=meta["recipient"],
        kind=meta["kind"],
        content=text,
        tool_call=tool_call,
        parent_id=wire.reference_task_ids[0] if wire.reference_task_ids else None,
        on_behalf_of=meta.get("on_behalf_of"),
        approval_ref=meta.get("approval_ref"),
    )
