"""External-MCP adapters (F-5) — the per-MCP argument-mapping layer.

When a C0x layer declares `backend.kind = external_mcp` in the architecture template,
the C00 orchestration spine dispatches it by invoking the named adapter here. An
adapter is a PURE mapping: it takes the dispatched work packet (+ the project root)
and returns `{"server", "tool", "arguments"}` describing the external MCP call — it
does NOT perform the call (the transport is injected by the caller, keeping
workflow-core free of any services/MCP-transport dependency).

This is the only hand-wired part of external delegation, and it is an *interface*
concern (each external MCP — docxmcp's decompose/assemble, drawmiat's diagram schema —
has its own API), not a *decision*. Adapters are registered by name; the registry
ships empty and a concrete adapter is added when a real external-MCP-backed layer is
introduced (e.g. F-4 emit_doc→docxmcp). Tests register their own.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

# adapter(work_packet: dict, *, root: Path) -> {"server","tool","arguments"}
Adapter = Callable[..., dict[str, Any]]


class AdapterError(ValueError):
    """Raised when an external-MCP adapter name is not registered."""


_ADAPTERS: dict[str, Adapter] = {}


def register_adapter(name: str, fn: Adapter) -> None:
    _ADAPTERS[name] = fn


def resolve_adapter(name: str) -> Adapter:
    fn = _ADAPTERS.get(name)
    if fn is None:
        raise AdapterError(f"no external-MCP adapter registered as {name!r}")
    return fn


def list_adapters() -> list[str]:
    return sorted(_ADAPTERS)


def build_external_call(adapter_name: str, work_packet: dict[str, Any], root: str | Path) -> dict[str, Any]:
    """Resolve `adapter_name` and map the work packet to an external MCP call spec."""
    call = resolve_adapter(adapter_name)(work_packet, root=Path(root))
    if not isinstance(call, dict) or not call.get("server") or not call.get("tool"):
        raise AdapterError(f"adapter {adapter_name!r} returned an invalid call spec: {call!r}")
    return {"server": call["server"], "tool": call["tool"], "arguments": call.get("arguments") or {}}
