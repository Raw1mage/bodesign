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
    "reference (control group).\n\n"
    "FILE MODEL (docxmcp-style): upload a whole project tree as a tarball to POST /files "
    "(Content-Type application/x-tar or gzip) or call bodesign_stage_dir with an inline "
    "{relpath:{content,encoding}} map -> {token, doc_dir, files}. Pass `token` to any tool: its path "
    "args resolve inside the token's doc_dir and the result lists produced files as {rel, url}; fetch "
    "via GET /files/{token}/blob/{rel}. Tools also accept plain host paths (local same-host UDS).\n\n"
    "No send-to-fab output without deterministic validation + explicit approval."
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


def _h_simulate(a: dict) -> Any:
    from bodesign_eda_bridge import simulate_schematic
    return asdict(simulate_schematic(a["schematic_path"], a["out_dir"], simulator=a.get("simulator", "ngspice"), types=a.get("types")))


def _h_analyze_emc(a: dict) -> Any:
    from bodesign_eda_bridge import analyze_emc
    return asdict(analyze_emc(a["schematic_path"], a["pcb_path"], a["out_dir"], standard=a.get("standard", "fcc-class-b")))


def _h_analyze_thermal(a: dict) -> Any:
    from bodesign_eda_bridge import analyze_thermal
    return asdict(analyze_thermal(a["schematic_path"], a["pcb_path"], a["out_dir"], ambient=a.get("ambient", 25.0)))


def _h_export_bom(a: dict) -> Any:
    from bodesign_eda_bridge import export_bom
    return asdict(export_bom(a["schematic_path"], a["out_dir"], group_by=a.get("group_by", "Value"), xlsx=a.get("xlsx", False)))


def _h_export_netlist(a: dict) -> Any:
    from bodesign_eda_bridge import export_netlist
    return asdict(export_netlist(a["schematic_path"], a["out_dir"], fmt=a.get("format", "kicadsexpr")))


def _h_stage_dir(a: dict) -> Any:
    from token_store import default_store
    return default_store().stage_files(a["files"])


_STR = {"type": "string"}
TOOLS: list[dict] = [
    {"name": "bodesign_stage_dir", "handler": _h_stage_dir,
     "description": "Stage an inline file tree {relpath:{content,encoding}} into a token namespace; returns {token, doc_dir, files}. Pass the token to other tools to operate inside that tree (docxmcp-style).",
     "schema": {"type": "object", "properties": {"files": {"type": "object"}}, "required": ["files"]}},
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
    {"name": "bodesign_simulate", "handler": _h_simulate,
     "description": "Simulate a schematic's analog subcircuits (dividers/filters/opamp/crystal) via the kicad analyzer + spice skill (ngspice); returns per-subcircuit pass/warn/fail. The analog-behaviour trust layer.",
     "schema": {"type": "object", "properties": {"schematic_path": _STR, "out_dir": _STR, "simulator": _STR, "types": _STR}, "required": ["schematic_path", "out_dir"]}},
    {"name": "bodesign_analyze_emc", "handler": _h_analyze_emc,
     "description": "EMC pre-compliance risk analysis on a schematic + .kicad_pcb (via kicad analyzers + emc skill): severity-bucketed findings (ground plane, decoupling, return paths, stitching, …). Pre-silicon risk, not certification.",
     "schema": {"type": "object", "properties": {"schematic_path": _STR, "pcb_path": _STR, "out_dir": _STR, "standard": _STR}, "required": ["schematic_path", "pcb_path", "out_dir"]}},
    {"name": "bodesign_analyze_thermal", "handler": _h_analyze_thermal,
     "description": "Thermal hotspot estimate on a schematic + .kicad_pcb (kicad analyze_thermal); per-component temps + thermal score.",
     "schema": {"type": "object", "properties": {"schematic_path": _STR, "pcb_path": _STR, "out_dir": _STR, "ambient": {"type": "number"}}, "required": ["schematic_path", "pcb_path", "out_dir"]}},
    {"name": "bodesign_export_bom", "handler": _h_export_bom,
     "description": "Export a grouped Bill of Materials (CSV, qty + MPN, DNP excluded) from a schematic; optional xlsx companion.",
     "schema": {"type": "object", "properties": {"schematic_path": _STR, "out_dir": _STR, "group_by": _STR, "xlsx": {"type": "boolean"}}, "required": ["schematic_path", "out_dir"]}},
    {"name": "bodesign_export_netlist", "handler": _h_export_netlist,
     "description": "Export a netlist from a schematic via kicad-cli.",
     "schema": {"type": "object", "properties": {"schematic_path": _STR, "out_dir": _STR, "format": _STR}, "required": ["schematic_path", "out_dir"]}},
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


# Path-like arg keys resolved inside a token's doc_dir when a tool call carries
# a `token` (docxmcp-style; G11b). Without a token they stay host paths (the
# local same-host UDS mode).
PATH_ARG_KEYS = ("folder", "out_dir", "path", "md_path", "board_path", "output_path", "corpus_dir", "schematic_path", "pcb_path")


def _snapshot(doc_dir: Path) -> dict:
    snap = {}
    for p in doc_dir.rglob("*"):
        if p.is_file():
            st = p.stat()
            snap[str(p.relative_to(doc_dir))] = (st.st_size, st.st_mtime_ns)
    return snap


def _produced(doc_dir: Path, before: dict) -> list[str]:
    out = []
    for p in doc_dir.rglob("*"):
        if p.is_file():
            rel = str(p.relative_to(doc_dir))
            st = p.stat()
            if before.get(rel) != (st.st_size, st.st_mtime_ns):
                out.append(rel)
    return sorted(out)


def run_tool(name: str, arguments: dict) -> dict:
    spec = TOOLS_BY_NAME.get(name)
    if spec is None:
        return {"error": f"unknown tool: {name}"}
    args = dict(arguments or {})
    token = args.pop("token", None)
    doc_dir = before = None
    if token:
        from token_store import TokenError, default_store
        try:
            doc_dir = default_store().resolve(token)
        except TokenError as error:
            return {"ok": False, "error": f"token: {error}"}
        for key in PATH_ARG_KEYS:
            if isinstance(args.get(key), str):
                args[key] = str((doc_dir / args[key].lstrip("/")).resolve())
        before = _snapshot(doc_dir)
    try:
        result = {"ok": True, "result": _jsonable(spec["handler"](args))}
    except Exception as error:  # surface tool errors as data, not transport failures
        return {"ok": False, "error": f"{type(error).__name__}: {error}"}
    if token:
        result["token"] = token
        result["doc_dir"] = str(doc_dir)
        result["produced"] = [{"rel": r, "url": f"/files/{token}/blob/{r}"} for r in _produced(doc_dir, before)]
    return result


# ── Self-documenting landing page ──────────────────────────────────────
# Orchestrated skills (run agent-side / on the server host; not bundled in the
# container image) that bodesign drives for analysis / docs / sim / sourcing / fab.
ORCHESTRATED_SKILLS = [
    ("kicad", "Schematic/PCB/Gerber analysis — ERC/DRC, netlist, power tree, subcircuit detection. Consumed by simulate/EMC."),
    ("kidoc", "Engineering doc packages — HDD, CE technical file, ICD, design-review, manufacturing-transfer; renders + diagrams."),
    ("spice", "ngspice simulation of detected subcircuits (filters, dividers, opamp, crystal). Driven by bodesign_simulate."),
    ("emc", "EMC pre-compliance risk analysis (FCC/CISPR). Driven by bodesign_analyze_emc."),
    ("datasheets", "Extract pinouts/specs from datasheet PDFs → feeds symbol generation (N7)."),
    ("bom / digikey / lcsc / element14 / mouser", "Part sourcing, pricing, stock, datasheet download."),
    ("jlcpcb / pcbway", "Fabrication + assembly ordering, DFM rules."),
]

WORKFLOW_STEPS = [
    ("1. Ingest", "Upload your project tree (tarball→token) or point at a folder; <code>bodesign_ingest_project</code> classifies files + flags non-readable ones."),
    ("2. Plan", "<code>bodesign_plan_design_intent</code> turns a natural-language spec into requirements, clarifying questions, and subsystems."),
    ("3. Source evidence", "<code>bodesign_evidence_manifest</code> grounds each part in a reference (local corpus first), so design = faithful reuse of known-good boards."),
    ("4. Symbols", "<code>bodesign_emit_symbol</code> turns a datasheet pinout into a KiCad symbol (harvest via the datasheets skill)."),
    ("5. Compose + ERC", "<code>bodesign_compose_schematic</code> auto-places components + nets → a kicad-cli-validated schematic (0 ERC)."),
    ("6. BOM + pins", "<code>bodesign_export_bom</code> (grouped, MPN) + <code>bodesign_pin_allocation</code> (the C03↔firmware interface)."),
    ("7. Layout", "<code>bodesign_emit_layout</code> places footprints via pcbnew + DRC + an SVG companion (a starting board to route)."),
    ("8. Fab", "<code>bodesign_emit_fab</code> exports gerbers/drill/pos/STEP/PDF for the factory."),
    ("9. Verify", "Four layers: ERC/DRC · <code>reference_crosscheck</code> vs a control group · <code>simulate</code> (SPICE) · <code>analyze_emc</code>/<code>analyze_thermal</code>."),
    ("10. Track", "<code>bodesign_package_readiness</code> recomputes the compass + next step until the package is factory-submittable."),
]


_CSS = """
:root{color-scheme:dark;--bg:#0e1116;--panel:#161b22;--panel2:#1c232c;--line:#30363d;--text:#e6edf3;--muted:#9aa7b4;--accent:#7ee787;--accent2:#79c0ff}
*{box-sizing:border-box}body{font-family:ui-sans-serif,system-ui,-apple-system,sans-serif;margin:0;background:var(--bg);color:var(--text);line-height:1.55}
main{max-width:1080px;margin:0 auto;padding:40px 22px 80px}
h1{font-size:2.2rem;margin:0 0 6px}h2{margin:34px 0 12px;font-size:1.3rem;border-bottom:1px solid var(--line);padding-bottom:6px}
.lead{color:var(--muted);font-size:1.05rem;max-width:760px}.crumb{color:var(--muted);font-size:.9rem;margin-bottom:18px}
code{background:var(--panel2);padding:1px 6px;border-radius:6px;font-family:ui-monospace,monospace;font-size:.9em}
pre{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:14px;overflow:auto;font-family:ui-monospace,monospace;font-size:.85rem}
a{color:var(--accent2);text-decoration:none}a:hover{text-decoration:underline}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:12px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.tool{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.tname{font-weight:700;font-family:ui-monospace,monospace}.tname a{color:var(--accent)}.tdesc{color:var(--text);font-size:.9rem;margin:5px 0}.treq{color:var(--muted);font-size:.8rem}
.step{display:flex;gap:14px;padding:9px 0;border-bottom:1px dashed var(--line)}.sh{flex:0 0 150px;color:var(--accent2);font-weight:600}.sb{color:var(--muted)}
ul{color:var(--muted)}.pill{display:inline-block;background:var(--panel2);border:1px solid var(--line);border-radius:999px;padding:2px 10px;margin:2px;font-size:.8rem;color:var(--accent)}
.warn{border-left:3px solid #d29922;padding-left:12px;color:var(--muted)}
table{width:100%;border-collapse:collapse;font-size:.9rem}td,th{border-bottom:1px solid var(--line);padding:8px 6px;text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600}.req{color:var(--accent2)}.opt{color:var(--muted)}
"""


def _base() -> str:
    """Public URL base for in-page links (e.g. '/bodesign' behind the gateway).

    The gateway strips the prefix for UDS routes, so the server's *routes* stay
    unprefixed, but browser-facing *links* must carry the prefix. Set via
    BODESIGN_HTTP_BASE; empty for direct access.
    """
    import os
    return os.environ.get("BODESIGN_HTTP_BASE", "").rstrip("/")


def _page(title: str, inner: str) -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>'
            f'<style>{_CSS}</style></head><body><main>{inner}</main></body></html>')


def _landing_html(uds_path: str | None = None, tcp_port: int | None = None) -> str:
    import html

    def esc(x):
        return html.escape(str(x))

    uds = uds_path or "<server>.run/bodesign.sock"
    port = tcp_port or 8077
    b = _base()

    tool_cards = []
    for t in TOOLS:
        req = ", ".join(f"<code>{esc(r)}</code>" for r in (t["schema"].get("required") or [])) or "—"
        tool_cards.append(
            f'<div class="tool"><div class="tname"><a href="{b}/tools/{esc(t["name"])}">{esc(t["name"])}</a></div>'
            f'<div class="tdesc">{esc(t["description"])}</div>'
            f'<div class="treq">required: {req}</div></div>'
        )
    skills = "".join(f"<li><b>{esc(n)}</b> — {esc(d)}</li>" for n, d in ORCHESTRATED_SKILLS)
    workflow = "".join(f'<div class="step"><div class="sh">{esc(h)}</div><div class="sb">{b}</div></div>' for h, b in WORKFLOW_STEPS)

    inner = f"""
<h1>bodesign <span style="color:var(--accent)">MCP</span></h1>
<p class="lead">An AI PCB-design copilot, delivered as an MCP server (docxmcp-style). Drive the full KiCad lifecycle — schematic → layout → fab — by conversation + raw data: ingest a project tree, plan, generate symbols/schematics, lay out, export fab files, and verify, all validated against KiCad and a known-good reference.</p>
<p><span class="pill">{len(TOOLS)} tools</span><span class="pill">v{esc(SERVER_VERSION)}</span><span class="pill">MCP Streamable HTTP</span><span class="pill">UDS + TCP</span><span class="pill">token file API</span></p>

<h2>Endpoints</h2>
<div class="card">
<p>MCP: <code>POST /mcp/</code> · Files: <code>POST /files</code>, <code>GET /files/{{token}}/blob/{{rel}}</code> · Health: <code>GET /healthz</code></p>
<p><b>Local (UDS):</b> <code>unix://{esc(uds)}:/mcp/</code><br><b>External (TCP):</b> <code>http://&lt;host&gt;:{port}/mcp/</code></p>
</div>

<h2>Install &amp; run</h2>
<div class="card">
<p><b>Docker (portable, recommended)</b> — bundles KiCad 9 + LibreOffice + pygerber + the mcp SDK:</p>
<pre>./mcpctl.sh start        # build image + start container (UDS + TCP :{port})
./mcpctl.sh status       # health + socket
./mcpctl.sh log          # follow logs
./mcpctl.sh stop</pre>
<p><b>Host (no Docker)</b> — needs kicad-cli + pcbnew + soffice + ngspice on PATH:</p>
<pre>pip install -r services/mcp/requirements.txt
python services/mcp/server.py --transport http --uds .run/bodesign.sock --port {port}</pre>
<p><b>Register in an MCP client</b> (see <code>mcp.json</code>): transport <code>streamable-http</code>, url <code>unix://…/bodesign.sock:/mcp/</code> (local) or <code>http://&lt;host&gt;:{port}/mcp/</code> (TCP).</p>
</div>

<h2>File model (docxmcp-style)</h2>
<div class="card">
<p>Upload your whole project tree as a tarball → a <b>token</b> whose <code>doc_dir</code> is your tree; pass <code>token</code> to any tool (its path args resolve inside it) and download produced files by token. No host bind mount needed.</p>
<pre>tar -C myproject -cf - . | curl --unix-socket .run/bodesign.sock \\
     -X POST -H 'Content-Type: application/x-tar' --data-binary @- http://bd/files
# → {{"token":"tok_…","doc_dir":"…","files":[…]}}
curl --unix-socket .run/bodesign.sock http://bd/files/{{token}}/blob/{{rel}}</pre>
<p>Or stage inline with the <a href="{b}/tools/bodesign_stage_dir"><code>bodesign_stage_dir</code></a> tool. Tools also accept plain host paths for the local same-host case.</p>
</div>

<h2>Circuit-design workflow</h2>
<div class="card">{workflow}</div>
<p class="warn">Reliability is <b>shown, not asserted</b>: bodesign cross-checks against a known-good shipped board (control group) and runs SPICE/EMC. These are pre-silicon risk layers — they do not replace accredited EMC / EVT / DVT at the lab/factory, and no send-to-fab output is emitted without validation + explicit approval.</p>

<h2>Skill packages it orchestrates</h2>
<div class="card"><p>bodesign generates; mature skills verify/source/document. These run agent-side (or on the server host via <code>BODESIGN_*_SKILL</code> / <code>~/.claude/skills</code>); install the ones you need:</p>
<ul>{skills}</ul></div>

<h2>Tools ({len(TOOLS)}) — <a href="{b}/tools">full call schemas →</a></h2>
<div class="grid">{''.join(tool_cards)}</div>
"""
    return _page("bodesign MCP", inner)


def _tools_index_html() -> str:
    import html

    def esc(x):
        return html.escape(str(x))

    b = _base()
    rows = []
    for t in TOOLS:
        req = ", ".join(f"<code>{esc(r)}</code>" for r in (t["schema"].get("required") or [])) or "—"
        rows.append(f'<tr><td><a href="{b}/tools/{esc(t["name"])}">{esc(t["name"])}</a></td>'
                    f'<td>{esc(t["description"])}</td><td>{req}</td></tr>')
    inner = (f'<p class="crumb"><a href="{b}/">bodesign MCP</a> / tools</p>'
             f'<h1>Tool catalog <span style="color:var(--muted);font-size:1rem">({len(TOOLS)})</span></h1>'
             f'<p class="lead">Click a tool for its full MCP <code>inputSchema</code> and a ready-to-send <code>tools/call</code> payload.</p>'
             f'<div class="card"><table><tr><th>Tool</th><th>Description</th><th>Required</th></tr>{"".join(rows)}</table></div>')
    return _page("bodesign MCP — tools", inner)


def _tool_detail_html(name: str) -> str:
    import html

    def esc(x):
        return html.escape(str(x))

    b = _base()
    spec = TOOLS_BY_NAME.get(name)
    if spec is None:
        inner = (f'<p class="crumb"><a href="{b}/">bodesign MCP</a> / <a href="{b}/tools">tools</a> / {esc(name)}</p>'
                 f'<h1>Unknown tool</h1><p class="lead"><code>{esc(name)}</code> is not registered. '
                 f'<a href="{b}/tools">See the catalog →</a></p>')
        return _page("bodesign MCP — unknown tool", inner)

    schema = spec["schema"]
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    prop_rows = []
    for pname, pdef in props.items():
        typ = pdef.get("type", "any") if isinstance(pdef, dict) else "any"
        tag = '<span class="req">required</span>' if pname in required else '<span class="opt">optional</span>'
        prop_rows.append(f"<tr><td><code>{esc(pname)}</code></td><td>{esc(typ)}</td><td>{tag}</td></tr>")
    schema_json = esc(json.dumps(schema, indent=2, ensure_ascii=False))
    example_args = {p: ("…" if p in required else "…") for p in list(required)[:4]} or {"…": "…"}
    call_payload = esc(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                   "params": {"name": name, "arguments": example_args}}, indent=2, ensure_ascii=False))
    inner = (f'<p class="crumb"><a href="{b}/">bodesign MCP</a> / <a href="{b}/tools">tools</a> / {esc(name)}</p>'
             f'<h1 style="font-family:ui-monospace,monospace;color:var(--accent)">{esc(name)}</h1>'
             f'<p class="lead">{esc(spec["description"])}</p>'
             f'<h2>Parameters</h2><div class="card"><table><tr><th>Name</th><th>Type</th><th></th></tr>{"".join(prop_rows) or "<tr><td>—</td></tr>"}</table></div>'
             f'<h2>inputSchema (JSON Schema)</h2><pre>{schema_json}</pre>'
             f'<h2>tools/call payload</h2><pre>{call_payload}</pre>'
             f'<p class="crumb"><a href="{b}/tools">← back to catalog</a></p>')
    return _page(f"bodesign MCP — {name}", inner)


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
        return Response(_landing_html(uds, port), media_type="text/html; charset=utf-8")

    async def tools_index(request: Request) -> Response:
        return Response(_tools_index_html(), media_type="text/html; charset=utf-8")

    async def tool_detail(request: Request) -> Response:
        return Response(_tool_detail_html(request.path_params["name"]), media_type="text/html; charset=utf-8")

    async def upload_file(request: Request) -> Response:
        """POST /files — ingest a file tree into a fresh token namespace.

        Content-Type discriminates: application/x-tar / application/gzip = a
        directory tarball (the docxmcp client-tree path); else raw single file
        (set x-filename). Returns {token, doc_dir, files}.
        """
        from token_store import TokenError, default_store
        store = default_store()
        ctype = request.headers.get("content-type", "")
        body = await request.body()
        try:
            if ctype.startswith("application/x-tar") or ctype.startswith("application/gzip"):
                result = store.stage_tarball(body, gz=ctype.startswith("application/gzip"))
            else:
                result = store.stage_raw(body, request.headers.get("x-filename", "upload.bin"))
        except TokenError as error:
            return JSONResponse({"error": "stage_failed", "message": str(error)}, status_code=400)
        return JSONResponse(result)

    async def get_blob(request: Request) -> Response:
        from token_store import TokenNotFoundError, default_store
        store = default_store()
        token = request.path_params["token"]
        rel = request.path_params["rel"]
        try:
            doc_dir = store.resolve(token)
            target = store.safe_join(doc_dir, rel)
        except TokenNotFoundError:
            return JSONResponse({"error": "token_not_found"}, status_code=404)
        except (ValueError, OSError):
            return JSONResponse({"error": "path_escape"}, status_code=403)
        if not target.is_file():
            return JSONResponse({"error": "not_found"}, status_code=404)
        return FileResponse(str(target))

    app = Starlette(routes=[
        Route("/", landing),
        Route("/tools", tools_index),
        Route("/tools/{name}", tool_detail),
        Route("/healthz", healthz),
        Route("/files", upload_file, methods=["POST"]),
        Route("/files/{token}/blob/{rel:path}", get_blob),
        Mount("/mcp", app=handle_mcp),
    ])

    # Serve UDS (local) and/or TCP (external) concurrently from one process,
    # sharing a single session manager + app. session_manager.run() is entered
    # once and held open while both uvicorn binds serve.
    binds = []
    if uds:
        binds.append(uvicorn.Server(uvicorn.Config(app, uds=uds)).serve())
    if port is not None:
        binds.append(uvicorn.Server(uvicorn.Config(app, host=host, port=port)).serve())
    if not binds:
        raise ValueError("run_http needs at least one of --uds / --port")
    async with session_manager.run():
        await asyncio.gather(*binds)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="bodesign MCP server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=None, help="serve HTTP on this TCP port (external)")
    parser.add_argument("--uds", default=None, help="serve HTTP on this unix socket (local)")
    args = parser.parse_args(argv)
    if args.transport == "stdio":
        asyncio.run(run_stdio())
    else:
        # UDS and TCP can run together; default to TCP 8077 if neither is given.
        port = args.port
        if not args.uds and port is None:
            port = 8077
        asyncio.run(run_http(args.host, port, args.uds))


if __name__ == "__main__":
    main()
