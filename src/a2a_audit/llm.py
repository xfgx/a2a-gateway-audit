"""LLM backends with an on-disk cache.

Backends:
- "adaption": Adaption platform Responses API (primary, sprint credits)
- "openai":   any OpenAI-compatible chat endpoint (fallback)
- "scripted": a Python callable, for tests (no network)

Every call is cached in sqlite keyed by (backend, model, system, prompt, temperature,
max_tokens, sample_idx). Different seeds map to different sample_idx values, so seeds
give independent samples while re-running the same config hits the cache.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential


@dataclass
class LLMConfig:
    backend: str = "adaption"
    model: str = "deepseek-v4-flash"
    temperature: float = 0.7
    max_tokens: int = 4000


@dataclass
class LLMResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    cached: bool = False
    latency_s: float = 0.0


class LLMCache:
    def __init__(self, path: str | Path = ".cache/llm.sqlite"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS c (k TEXT PRIMARY KEY, v TEXT)")
        self._lock = threading.Lock()

    def get(self, key: str) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT v FROM c WHERE k=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, key: str, value: dict) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO c VALUES (?, ?)", (key, json.dumps(value)))
            self._db.commit()


ScriptFn = Callable[[str, str, str], str]  # (agent_name, system, prompt) -> text


@dataclass
class LLMClient:
    cfg: LLMConfig
    cache: LLMCache | None = None
    script: ScriptFn | None = None
    _client: object = field(default=None, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def _key(self, system: str, prompt: str, sample_idx: int) -> str:
        raw = json.dumps(
            [self.cfg.backend, self.cfg.model, system, prompt, self.cfg.temperature,
             self.cfg.max_tokens, sample_idx]
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def complete(self, system: str, prompt: str, *, sample_idx: int = 0, agent: str = "") -> LLMResult:
        if self.cfg.backend == "scripted":
            assert self.script is not None, "scripted backend needs a script function"
            return LLMResult(text=self.script(agent, system, prompt))
        key = self._key(system, prompt, sample_idx)
        if self.cache is not None and (hit := self.cache.get(key)) is not None:
            return LLMResult(**{**hit, "cached": True})
        t0 = time.time()
        res = self._call(system, prompt)
        res.latency_s = time.time() - t0
        if self.cache is not None:
            self.cache.put(key, {k: v for k, v in res.__dict__.items() if k != "cached"})
        return res

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=30), reraise=True)
    def _call(self, system: str, prompt: str) -> LLMResult:
        if self.cfg.backend == "adaption":
            with self._lock:
                if self._client is None:
                    from adaption import Adaption

                    self._client = Adaption(api_key=os.environ["ADAPTION_API_KEY"])
            r = self._client.responses.create(
                model=self.cfg.model,
                instructions=system,
                input=prompt,
                temperature=self.cfg.temperature,
                max_output_tokens=self.cfg.max_tokens,
            )
            u = r.usage
            return LLMResult(
                text=r.output_text or "",
                input_tokens=getattr(u, "input_tokens", 0) or 0,
                output_tokens=getattr(u, "output_tokens", 0) or 0,
                cost=float(getattr(u, "cost", 0.0) or 0.0),
            )
        if self.cfg.backend == "openai":
            with self._lock:
                if self._client is None:
                    from openai import OpenAI

                    self._client = OpenAI(base_url=os.environ["LLM_BASE_URL"], api_key=os.environ["LLM_API_KEY"])
            r = self._client.chat.completions.create(
                model=self.cfg.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                temperature=self.cfg.temperature,
                max_tokens=self.cfg.max_tokens,
            )
            u = r.usage
            return LLMResult(
                text=r.choices[0].message.content or "",
                input_tokens=getattr(u, "prompt_tokens", 0) or 0,
                output_tokens=getattr(u, "completion_tokens", 0) or 0,
            )
        raise ValueError(f"unknown backend {self.cfg.backend}")


def api_hosts(backend: str) -> set[str]:
    """Hostnames a backend needs; used by the sandbox network allow-list."""
    if backend == "adaption":
        return {"api.prod.adaptionlabs.ai"}
    if backend == "openai":
        from urllib.parse import urlparse

        return {urlparse(os.environ.get("LLM_BASE_URL", "")).hostname or ""}
    return set()
