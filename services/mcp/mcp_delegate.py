"""MCP-to-MCP targeted delegation (Batch F, design: mcp_collaboration.md).

A thin MCP *client* so a bodesign tool / the C00 spine can call a specific external
MCP server's tool (docxmcp, drawmiat, future) with graceful degradation. No new
dependency — uses the `mcp` SDK client already present.

Registry (config): an external server is resolved by name from
  - BODESIGN_MCP_SERVERS = JSON {"<name>": {"url": "...", "headers_env": "ENV_NAME"}}
  - or per-name BODESIGN_MCP_<NAME>_URL  (+ optional BODESIGN_MCP_<NAME>_HEADERS = JSON)

Degradation reuses the worker semantics: an unconfigured server is permanent
`worker_unavailable` (don't retry); a configured-but-unreachable server is retryable
`worker_starting`. A real tool error from the external server is returned verbatim.
Never fabricates a result.

The MCP client is async and `run_tool` is sync (inside the server's async handler), so
the call runs in a worker thread with its own event loop — robust regardless of the
outer loop.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from typing import Any

_CONNECT_TIMEOUT = float(os.environ.get("BODESIGN_MCP_CONNECT_TIMEOUT", "10") or 10)
_RETRY_AFTER = int(os.environ.get("BODESIGN_WORKER_RETRY_AFTER", "5") or 5)
_JOIN_TIMEOUT = 330.0  # > the client sse_read_timeout (300) so a live slow tool isn't cut off


def resolve_mcp_server(name: str) -> dict[str, Any] | None:
    """Return {url, headers} for a configured external MCP server, or None."""
    raw = os.environ.get("BODESIGN_MCP_SERVERS")
    if raw:
        try:
            servers = json.loads(raw)
            entry = servers.get(name)
            if isinstance(entry, dict) and entry.get("url"):
                headers = None
                hdr_env = entry.get("headers_env")
                if hdr_env and os.environ.get(hdr_env):
                    headers = json.loads(os.environ[hdr_env])
                return {"url": entry["url"], "headers": headers}
        except (json.JSONDecodeError, AttributeError):
            pass
    url = os.environ.get(f"BODESIGN_MCP_{name.upper()}_URL")
    if url:
        headers = None
        hraw = os.environ.get(f"BODESIGN_MCP_{name.upper()}_HEADERS")
        if hraw:
            try:
                headers = json.loads(hraw)
            except json.JSONDecodeError:
                headers = None
        return {"url": url, "headers": headers}
    return None


def _normalize(res: Any) -> dict[str, Any]:
    """Normalize an mcp CallToolResult into bodesign's {ok, result} shape."""
    is_error = bool(getattr(res, "isError", False))
    structured = getattr(res, "structuredContent", None)
    if structured is not None:
        return {"ok": not is_error, "result": structured, "is_error": is_error}
    text = None
    for block in (getattr(res, "content", None) or []):
        if getattr(block, "type", None) == "text":
            text = block.text
            break
    parsed: Any = None
    if text is not None:
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            parsed = text
    return {"ok": not is_error, "result": parsed, "is_error": is_error}


async def _acall(url: str, headers: dict[str, str] | None, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    # Connect/initialize errors propagate (server down -> worker_starting). A tool
    # error from a connected server is returned verbatim (not "starting").
    async with streamablehttp_client(url, headers=headers, timeout=_CONNECT_TIMEOUT) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            try:
                res = await session.call_tool(tool, arguments or {})
            except Exception as error:  # connected, but the call failed
                return {"ok": False, "error": f"external tool error: {type(error).__name__}: {error}", "is_error": True}
            return _normalize(res)


def call_external_mcp_tool(server: str, tool: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call `tool` on the external MCP server registered as `server`. Degrades cleanly."""
    cfg = resolve_mcp_server(server)
    if not cfg:
        return {"ok": False, "status": "worker_unavailable", "worker_unavailable": True, "server": server,
                "error": f"external MCP server '{server}' is not configured "
                         f"(set BODESIGN_MCP_SERVERS or BODESIGN_MCP_{server.upper()}_URL)"}
    out: dict[str, Any] = {}

    def runner() -> None:
        try:
            out["value"] = asyncio.run(_acall(cfg["url"], cfg.get("headers"), tool, arguments or {}))
        except Exception as error:  # connect/initialize/transport failure
            out["error"] = error

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join(timeout=_JOIN_TIMEOUT)

    if thread.is_alive() or "error" in out:
        err = out.get("error")
        reason = f"{type(err).__name__}: {err}" if err else "timed out"
        return {"ok": False, "status": "worker_starting", "worker_starting": True,
                "retry_after_seconds": _RETRY_AFTER, "server": server,
                "error": f"external MCP '{server}' tool '{tool}' not reachable yet ({reason}); "
                         f"it may be starting — retry in {_RETRY_AFTER}s"}
    return out["value"]
