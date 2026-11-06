"""Containment: during experiments the process may only resolve allow-listed hostnames.

Mock tools never touch the network or filesystem; this guard makes that checkable and
catches anything (a bug, a library) that tries to reach a non-allow-listed host.
Violations raise SandboxViolation and are counted.
"""

from __future__ import annotations

import socket
import threading
from contextlib import contextmanager

LOCAL = {"localhost", "127.0.0.1", "::1"}


class SandboxViolation(RuntimeError):
    pass


violations: list[str] = []
_lock = threading.Lock()


@contextmanager
def network_allowlist(hosts: set[str]):
    allowed = {h for h in hosts if h} | LOCAL
    original = socket.getaddrinfo

    def guarded(host, *args, **kwargs):
        h = host.decode() if isinstance(host, bytes) else str(host)
        if h not in allowed:
            with _lock:
                violations.append(h)
            raise SandboxViolation(f"network access to {h!r} is not allowed in the sandbox")
        return original(host, *args, **kwargs)

    socket.getaddrinfo = guarded
    try:
        yield
    finally:
        socket.getaddrinfo = original
