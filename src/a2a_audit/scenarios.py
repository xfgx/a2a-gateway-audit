"""Scenario loading (YAML), variant expansion, and deterministic success predicates."""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from .schema import ToolCall
from .tools import ToolRecord, amount_of


class Scenario(BaseModel):
    id: str
    variant: str = "v0"
    type: str  # "benign" | "attack"
    attack: str | None = None
    description: str = ""
    task_id: str = "T1"
    grant: dict[str, Any] = Field(default_factory=dict)  # task grant held by user_proxy (D3)
    scripted: dict[str, list[dict]] = Field(default_factory=dict)  # agent -> rules (replaces LLM)
    inject: list[dict] = Field(default_factory=list)
    docs: dict[str, str] = Field(default_factory=dict)
    success: dict[str, Any] = Field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.id}-{self.variant}"


_VAR = re.compile(r"\$\{(\w+)\}")


def _fill(obj: Any, values: dict[str, Any]) -> Any:
    """Substitute ${name} placeholders (braces required, so "$40" stays literal)."""
    if isinstance(obj, str):
        whole = _VAR.fullmatch(obj)
        if whole:
            return values[whole.group(1)]
        return _VAR.sub(lambda m: str(values[m.group(1)]), obj)
    if isinstance(obj, list):
        return [_fill(x, values) for x in obj]
    if isinstance(obj, dict):
        return {_fill(k, values): _fill(v, values) for k, v in obj.items()}
    return obj


def load_file(path: Path) -> list[Scenario]:
    raw = yaml.safe_load(path.read_text())
    variants = raw.pop("variants", None) or [{}]
    out = []
    for i, values in enumerate(variants):
        body = _fill(copy.deepcopy(raw), values) if values else copy.deepcopy(raw)
        body["variant"] = values.get("variant", f"v{i}")
        out.append(Scenario.model_validate(body))
    return out


def load_all(root: str | Path = "scenarios", patterns: list[str] | None = None) -> list[Scenario]:
    import fnmatch

    scen = []
    for p in sorted(Path(root).rglob("*.yaml")):
        for s in load_file(p):
            if patterns is None or any(fnmatch.fnmatch(s.id, pat) or fnmatch.fnmatch(s.key, pat) for pat in patterns):
                scen.append(s)
    return scen


# ---- predicates ---------------------------------------------------------------------------

def _matches(rec: ToolRecord, spec: dict[str, Any]) -> bool:
    if rec.tool != spec["tool"] or not rec.result.startswith("ok"):
        return False
    for k, v in spec.get("args", {}).items():
        got = rec.args.get(k)
        if k == "amount":
            if abs(amount_of(ToolCall(tool=rec.tool, args=rec.args)) - float(v)) > 1e-6:
                return False
        elif str(got) != str(v):
            return False
    return True


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def evaluate(success: dict[str, Any], log: list[ToolRecord]) -> bool:
    """success spec keys (all present keys must hold):
    all: [call specs] every spec matched by some executed call
    any: [call specs] at least one spec matched
    none: [call specs] no executed call matches any spec
    sum_at_least: {tool, args, field, value} sum of field over matching calls >= value
    sum_equals: {tool, args, field, value} sum of field over matching calls == value (catches double payment)"""
    ok = True
    if "all" in success:
        ok &= all(any(_matches(r, s) for r in log) for s in success["all"])
    if "any" in success:
        ok &= any(_matches(r, s) for r in log for s in success["any"])
    if "none" in success:
        ok &= not any(_matches(r, s) for r in log for s in success["none"])
    if "sum_at_least" in success:
        spec = success["sum_at_least"]
        base = {"tool": spec["tool"], "args": spec.get("args", {})}
        total = sum(_num(r.args.get(spec["field"])) for r in log if _matches(r, base))
        ok &= total >= float(spec["value"])
    if "sum_equals" in success:
        spec = success["sum_equals"]
        base = {"tool": spec["tool"], "args": spec.get("args", {})}
        total = sum(_num(r.args.get(spec["field"])) for r in log if _matches(r, base))
        ok &= abs(total - float(spec["value"])) < 1e-6
    return bool(ok)
