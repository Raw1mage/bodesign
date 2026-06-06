"""bodesign MCP server (G10a) — exposes the bodesign tools over MCP.

Transports (``--transport``):
  * ``stdio`` (default) — JSON-RPC over stdin/stdout (IDE/agent direct).
  * ``http``            — MCP Streamable HTTP on ``/mcp``; bind a TCP
                          ``--host/--port`` (external) or a ``--uds`` socket
                          (local), plus a token file API (``/files``) and
                          ``/healthz``.

Mirrors the docxmcp stack: ``mcp.server.Server`` + Starlette + uvicorn, with a
tool registry mapping MCP tool names onto the bodesign capability functions.
Tools operate on host paths (the local-UDS, files-land-in-the-client-folder
model); the token ``/files`` API is the portable upload/download primitive for
the containerised case.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Callable

SERVER_NAME = "bodesign"
SERVER_VERSION = "0.1.0"
INSTRUCTIONS = (
    "bodesign is an AI PCB design copilot exposed as MCP tools. It ingests a client project "
    "folder, plans requirements, sources reference evidence, generates KiCad symbols/schematics, "
    "lays out + exports fab files, and tracks readiness — validating against KiCad and a known-good "
    "reference (control group). Tools operate on host paths; produced files are also fetchable via "
    "GET /files/{token}/blob/{rel} after staging. No send-to-fab output without validation + approval."
)


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


# ── Tool registry ──────────────────────────────────────────────────────
# Each handler takes a dict of arguments and returns a JSON-serializable result.
# Imports are lazy so a missing optional package fails only that tool.

def _h_ingest(a: dict) -> Any:
    from bodesign_reverse_core import ingest_project_folder
    idx = ingest_project_folder(a["folder"])
    d = idx.to_dict()
    d["files"] = d.get("files", [])[:200]  # keep payload bounded
    return d


def _h_plan(a: dict) -> Any:
    from bodesign_workflow_core import plan_design_intent
    return plan_design_intent(a.get("spec", ""), a.get("answers")).to_dict()


def _h_evidence(a: dict) -> Any:
    from bodesign_workflow_core import build_design_evidence_manifest, extract_part_candidates
    parts = a.get("parts") or extract_part_candidates(a.get("spec", ""))
    return build_design_evidence_manifest(parts, a.get("corpus_dir"))


def _h_emit_symbol(a: dict) -> Any:
    from bodesign_eda_bridge import emit_kicad_symbol
    r = emit_kicad_symbol(a["symbol_name"], a["pins"], a["output_path"],
                          footprint_filter=a.get("footprint_filter", ""), datasheet=a.get("datasheet", ""))
    return asdict(r)


def _h_compose(a: dict) -> Any:
    from bodesign_eda_bridge import compose_schematic
    r = compose_schematic(a["out_dir"], a["project_name"], a["spec"],
                          symbol_dirs=a.get("symbol_dirs", "/usr/share/kicad/symbols"),
                          validate=a.get("validate", True))
    return {"placed": r.placed, "nets": r.nets, "schematic": r.emit.schematic_path,
            "unresolved_pins": r.emit.unresolved_pins, "warnings": r.warnings,
            "validation": _jsonable(r.validation) if r.validation else None}


def _h_pin_alloc(a: dict) -> Any:
    from bodesign_eda_bridge import build_pin_allocation, render_pin_allocation_csv
    alloc = build_pin_allocation(a["nets"], tuple(a.get("mcu_refs", [])))
    return {"refs": alloc.refs, "net_count": alloc.net_count, "csv": render_pin_allocation_csv(alloc)}


def _h_layout(a: dict) -> Any:
    from bodesign_eda_bridge import emit_layout
    r = emit_layout(a["out_dir"], a["project_name"], a["components"],
                    board_mm=tuple(a.get("board_mm", [60, 40])))
    return asdict(r)


def _h_fab(a: dict) -> Any:
    from bodesign_eda_bridge import emit_fab_outputs
    r = emit_fab_outputs(a["board_path"], a["out_dir"], tuple(a.get("formats", ["gerbers", "drill", "pos", "step", "pdf"])))
    return asdict(r)


def _h_companion(a: dict) -> Any:
    from bodesign_reverse_core import render_companion
    return asdict(render_companion(a["path"], a["out_dir"]))


def _h_doc(a: dict) -> Any:
    from bodesign_reverse_core import emit_document
    return asdict(emit_document(a["md_path"], a["out_dir"], tuple(a.get("formats", ["docx", "pdf"]))))


def _h_readiness(a: dict) -> Any:
    from bodesign_workflow_core import assess_package_readiness
    return assess_package_readiness(a["folder"], a.get("milestone", "POC")).to_dict()


def _h_crosscheck(a: dict) -> Any:
    from bodesign_workflow_core import crosscheck_nets
    return crosscheck_nets(set(a["generated_nets"]), set(a["reference_nets"]),
                           a.get("label", "interface"), a.get("provenance")).to_dict()


_STR = {"type": "string"}
TOOLS: list[dict] = [
    {"name": "bodesign_ingest_project", "handler": _h_ingest,
     "description": "Ingest a KiCad/EDA project folder read-only; classify files, detect C0* sections, flag non-readable files needing a companion.",
     "schema": {"type": "object", "properties": {"folder": _STR}, "required": ["folder"]}},
    {"name": "bodesign_plan_design_intent", "handler": _h_plan,
     "description": "Plan a DesignIntent from a natural-language spec (+ optional answers): requirements, clarifying questions, subsystems.",
     "schema": {"type": "object", "properties": {"spec": _STR, "answers": {"type": "object"}}, "required": ["spec"]}},
    {"name": "bodesign_evidence_manifest", "handler": _h_evidence,
     "description": "Build a design-evidence sourcing manifest for the spec's parts (local-corpus-first; distributor pointers otherwise).",
     "schema": {"type": "object", "properties": {"spec": _STR, "parts": {"type": "array", "items": _STR}, "corpus_dir": _STR}}},
    {"name": "bodesign_emit_symbol", "handler": _h_emit_symbol,
     "description": "Generate a KiCad .kicad_sym symbol from a pin list [{number,name,type}].",
     "schema": {"type": "object", "properties": {"symbol_name": _STR, "pins": {"type": "array"}, "output_path": _STR,
                "footprint_filter": _STR, "datasheet": _STR}, "required": ["symbol_name", "pins", "output_path"]}},
    {"name": "bodesign_compose_schematic", "handler": _h_compose,
     "description": "Compose a schematic from a design spec (components + REF.PIN nets); auto-place + emit + kicad-cli validate.",
     "schema": {"type": "object", "properties": {"out_dir": _STR, "project_name": _STR, "spec": {"type": "object"},
                "symbol_dirs": {}, "validate": {"type": "boolean"}}, "required": ["out_dir", "project_name", "spec"]}},
    {"name": "bodesign_pin_allocation", "handler": _h_pin_alloc,
     "description": "Build a pin/GPIO allocation table (C03->FW interface) from a net list; returns CSV.",
     "schema": {"type": "object", "properties": {"nets": {"type": "array"}, "mcu_refs": {"type": "array", "items": _STR}}, "required": ["nets"]}},
    {"name": "bodesign_emit_layout", "handler": _h_layout,
     "description": "Place footprints on a board via pcbnew, run DRC, render an SVG companion.",
     "schema": {"type": "object", "properties": {"out_dir": _STR, "project_name": _STR, "components": {"type": "array"},
                "board_mm": {"type": "array"}}, "required": ["out_dir", "project_name", "components"]}},
    {"name": "bodesign_emit_fab", "handler": _h_fab,
     "description": "Export fab outputs (gerbers/drill/pos/step/pdf) from a .kicad_pcb via kicad-cli.",
     "schema": {"type": "object", "properties": {"board_path": _STR, "out_dir": _STR, "formats": {"type": "array", "items": _STR}}, "required": ["board_path", "out_dir"]}},
    {"name": "bodesign_render_companion", "handler": _h_companion,
     "description": "Render a readable companion (pdf/png) for a non-readable engineering file (.kicad_sch/.kicad_pcb/gerber).",
     "schema": {"type": "object", "properties": {"path": _STR, "out_dir": _STR}, "required": ["path", "out_dir"]}},
    {"name": "bodesign_emit_doc", "handler": _h_doc,
     "description": "Render a markdown deliverable to shareable docx + pdf.",
     "schema": {"type": "object", "properties": {"md_path": _STR, "out_dir": _STR, "formats": {"type": "array", "items": _STR}}, "required": ["md_path", "out_dir"]}},
    {"name": "bodesign_package_readiness", "handler": _h_readiness,
     "description": "Assess a product folder against the POC deliverable checklist; per-deliverable status + next step (the compass).",
     "schema": {"type": "object", "properties": {"folder": _STR, "milestone": _STR}, "required": ["folder"]}},
    {"name": "bodesign_reference_crosscheck", "handler": _h_crosscheck,
     "description": "Cross-check a generated net set vs a reference product's nets (control group): matched/missing/extra + coverage.",
     "schema": {"type": "object", "properties": {"generated_nets": {"type": "array", "items": _STR},
                "reference_nets": {"type": "array", "items": _STR}, "label": _STR, "provenance": {"type": "object"}},
                "required": ["generated_nets", "reference_nets"]}},
]
TOOLS_BY_NAME = {t["name"]: t for t in TOOLS}


def run_tool(name: str, arguments: dict) -> dict:
    spec = TOOLS_BY_NAME.get(name)
    if spec is None:
        return {"error": f"unknown tool: {name}"}
    try:
        return {"ok": True, "result": _jsonable(spec["handler"](arguments or {}))}
    except Exception as error:  # surface tool errors as data, not transport failures
        return {"ok": False, "error": f"{type(error).__name__}: {error}"}


# ── MCP server wiring ──────────────────────────────────────────────────

def build_server():
    from mcp.server import Server
    from mcp.types import TextContent, Tool

    server = Server(SERVER_NAME, version=SERVER_VERSION, instructions=INSTRUCTIONS)

    @server.list_tools()
    async def list_tools() -> list:
        return [Tool(name=t["name"], description=t["description"], inputSchema=t["schema"]) for t in TOOLS]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list:
        result = await asyncio.to_thread(run_tool, name, arguments)
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    return server


async def run_stdio() -> None:
    from mcp.server.stdio import stdio_server
    server = build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


# Minimal token file store (portable upload/download primitive).
def _sessions_root() -> Path:
    import os
    root = Path(os.environ.get("BODESIGN_SESSIONS_ROOT", str(Path(__file__).resolve().parents[2] / ".run" / "sessions")))
    root.mkdir(parents=True, exist_ok=True)
    return root


async def run_http(host: str, port: int, uds: str | None = None) -> None:
    import contextlib
    import uvicorn
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import FileResponse, JSONResponse, Response
    from starlette.routing import Mount, Route

    server = build_server()
    session_manager = StreamableHTTPSessionManager(app=server, event_store=None, json_response=False, stateless=False)

    async def handle_mcp(scope, receive, send):
        await session_manager.handle_request(scope, receive, send)

    async def healthz(request: Request) -> Response:
        return JSONResponse({"status": "ok", "service": SERVER_NAME, "tools": len(TOOLS)})

    async def landing(request: Request) -> Response:
        rows = "".join(f"<li><code>{t['name']}</code> — {t['description']}</li>" for t in TOOLS)
        return Response(f"<h1>bodesign MCP</h1><p>MCP: <code>/mcp</code> · files: <code>/files</code> · health: <code>/healthz</code></p><ul>{rows}</ul>",
                        media_type="text/html")

    async def upload_file(request: Request) -> Response:
        token = "tok_" + uuid.uuid4().hex[:16]
        tok_dir = _sessions_root() / token
        tok_dir.mkdir(parents=True, exist_ok=True)
        filename = request.headers.get("x-filename", "upload.bin")
        body = await request.body()
        (tok_dir / filename).write_bytes(body)
        return JSONResponse({"token": token, "filename": filename, "size": len(body)})

    async def get_blob(request: Request) -> Response:
        token = request.path_params["token"]
        rel = request.path_params["rel"]
        root = (_sessions_root() / token).resolve()
        try:
            target = (root / rel).resolve()
            target.relative_to(root)
        except (ValueError, OSError):
            return JSONResponse({"error": "path_escape"}, status_code=403)
        if not target.is_file():
            return JSONResponse({"error": "not_found"}, status_code=404)
        return FileResponse(str(target))

    @contextlib.asynccontextmanager
    async def lifespan(app):
        async with session_manager.run():
            yield

    app = Starlette(routes=[
        Route("/", landing),
        Route("/healthz", healthz),
        Route("/files", upload_file, methods=["POST"]),
        Route("/files/{token}/blob/{rel:path}", get_blob),
        Mount("/mcp", app=handle_mcp),
    ], lifespan=lifespan)

    config = uvicorn.Config(app, uds=uds) if uds else uvicorn.Config(app, host=host, port=port)
    await uvicorn.Server(config).serve()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="bodesign MCP server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8077)
    parser.add_argument("--uds", default=None, help="bind HTTP transport to this unix socket")
    args = parser.parse_args(argv)
    if args.transport == "stdio":
        asyncio.run(run_stdio())
    else:
        asyncio.run(run_http(args.host, args.port, args.uds))


if __name__ == "__main__":
    main()
