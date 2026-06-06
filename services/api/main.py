from dataclasses import asdict
from html import escape
import base64
import json
from pathlib import Path
import sys
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOTS = [
    REPO_ROOT / "packages" / "shared",
    REPO_ROOT / "packages" / "component-kb",
    REPO_ROOT / "packages" / "design-ir",
    REPO_ROOT / "packages" / "doc-core",
    REPO_ROOT / "packages" / "eda-bridge",
    REPO_ROOT / "packages" / "reverse-core",
    REPO_ROOT / "packages" / "source-core",
    REPO_ROOT / "packages" / "gerber-core",
    REPO_ROOT / "packages" / "storage-core",
    REPO_ROOT / "packages" / "workflow-core",
]

for package_root in PACKAGE_ROOTS:
    package_path = str(package_root)
    if package_path not in sys.path:
        sys.path.append(package_path)

try:
    from bodesign_component_kb import build_component_knowledge_queue, ingest_datasheet_knowledge, reuse_component_knowledge
    from bodesign_doc_core import plan_openmv_document_ingestion
    from bodesign_eda_bridge import build_kicad_native_extension_contract, plan_kicad_bridge
    from bodesign_gerber_core import focus_svg_viewbox, parse_drill_file, parse_gerber_file, render_gerber_raster_with_pygerber, render_gerber_with_pygerber, render_geometry_svg, validate_gerber_export_placeholder
    from bodesign_shared import JobSummary, ProjectSummary, detect_input_artifact
    from bodesign_reverse_core import build_rockbox_input_manifest, reconstruct_rockbox_placeholder
    from bodesign_source_core import plan_gerber_export, produce_design_report
    from bodesign_storage_core import build_default_storage_share_manifest, build_kicad_happy_cache_mapping, build_project_tree_browse_contract, classify_project_folder_taxonomy, validate_storage_share_manifest
    from bodesign_workflow_core import build_generated_design_candidate_workspace, plan_reference_board_workflow
except ImportError:
    ingest_datasheet_knowledge = None
    build_component_knowledge_queue = None
    reuse_component_knowledge = None
    plan_openmv_document_ingestion = None
    build_kicad_native_extension_contract = None
    plan_kicad_bridge = None
    parse_drill_file = None
    parse_gerber_file = None
    focus_svg_viewbox = None
    render_gerber_raster_with_pygerber = None
    render_gerber_with_pygerber = None
    render_geometry_svg = None
    validate_gerber_export_placeholder = None
    JobSummary = None
    ProjectSummary = None
    detect_input_artifact = None
    build_rockbox_input_manifest = None
    reconstruct_rockbox_placeholder = None
    plan_gerber_export = None
    produce_design_report = None
    build_default_storage_share_manifest = None
    build_kicad_happy_cache_mapping = None
    build_project_tree_browse_contract = None
    classify_project_folder_taxonomy = None
    validate_storage_share_manifest = None
    build_generated_design_candidate_workspace = None
    plan_reference_board_workflow = None

app = FastAPI(title="bodesign API", version="0.1.0")

PROJECTS: dict[str, dict[str, Any]] = {}
JOBS: list[dict[str, Any]] = []


BODESIGN_WEB_ROUTES = [
    {"method": "GET", "path": "/", "purpose": "Redirect to the bodesign viewer."},
    {"method": "GET", "path": "/bodesign", "purpose": "Redirect to the canonical bodesign viewer path."},
    {"method": "GET", "path": "/bodesign/", "purpose": "Render the bodesign project browser and default Rockbox workspace."},
    {"method": "GET", "path": "/bodesign/projects/{project_id}", "purpose": "Open a specific bodesign project workspace."},
    {"method": "GET", "path": "/bodesign/projects/{project_id}/artifacts/{artifact_id}", "purpose": "Browse a specific project artifact."},
    {"method": "GET", "path": "/bodesign/routes", "purpose": "Show visible bodesign web/API routes."},
    {"method": "GET", "path": "/bodesign/health", "purpose": "Health check for host/gateway routing."},
    {"method": "GET", "path": "/bodesign/api/routes", "purpose": "Return visible bodesign web/API routes as JSON."},
    {"method": "GET", "path": "/bodesign/api/projects", "purpose": "List bodesign projects."},
    {"method": "POST", "path": "/bodesign/api/projects", "purpose": "Create a bodesign project."},
    {"method": "GET", "path": "/bodesign/api/projects/{project_id}/artifacts", "purpose": "List project artifacts."},
    {"method": "GET", "path": "/bodesign/api/projects/{project_id}/artifacts/{artifact_id}", "purpose": "Return artifact metadata and preview."},
    {"method": "GET", "path": "/bodesign/api/projects/{project_id}/geometry", "purpose": "Return parsed Gerber/drill geometry summary for the board view."},
    {"method": "GET", "path": "/bodesign/api/projects/{project_id}/storage-share", "purpose": "Return client-owned project folder storage-share manifest."},
    {"method": "GET", "path": "/bodesign/api/projects/{project_id}/project-tree", "purpose": "Return read-only client-owned folder tree evidence summary."},
    {"method": "GET", "path": "/bodesign/api/projects/{project_id}/kicad-foundation", "purpose": "Return KiCad-native companion foundation status and blockers."},
    {"method": "GET", "path": "/bodesign/api/projects/{project_id}/kicad-native-extension", "purpose": "Return KiCad Action Plugin / sidecar extension contract."},
    {"method": "GET", "path": "/bodesign/api/projects/{project_id}/kicad-plugin-handshake", "purpose": "Return KiCad plugin sidecar handshake status without running native tools."},
    {"method": "POST", "path": "/bodesign/api/artifacts/detect", "purpose": "Detect artifact types before ingestion."},
    {"method": "GET", "path": "/bodesign/api/projects/{project_id}/board-design", "purpose": "Return a BoardDesign IR summary."},
    {"method": "POST", "path": "/bodesign/api/projects/{project_id}/rockbox/reconstruct", "purpose": "Reconstruct Rockbox into BoardDesign IR summary."},
    {"method": "POST", "path": "/bodesign/api/projects/{project_id}/knowledge/datasheets", "purpose": "Ingest datasheet knowledge."},
    {"method": "GET", "path": "/bodesign/api/projects/{project_id}/knowledge/queue", "purpose": "List reusable component knowledge candidates."},
    {"method": "POST", "path": "/bodesign/api/projects/{project_id}/knowledge/external-fetch", "purpose": "Policy gate for external datasheet fetching."},
    {"method": "POST", "path": "/bodesign/api/projects/{project_id}/eda/kicad/bridge-plan", "purpose": "Plan KiCad adapter/plugin bridge outputs."},
    {"method": "POST", "path": "/bodesign/api/projects/{project_id}/workflow/reference-board", "purpose": "Plan the AI reference-board reconstruction workflow."},
    {"method": "GET", "path": "/bodesign/api/projects/{project_id}/candidates/generated-design", "purpose": "Show generated design candidate diff/evidence/approval workspace."},
]

BUILTIN_PROJECT_ID = "rockbox"



@app.get("/health")
@app.get("/bodesign/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "bodesign-api"}


@app.get("/", include_in_schema=False)
def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/bodesign/")


@app.get("/bodesign", include_in_schema=False)
def bodesign_viewer_redirect() -> RedirectResponse:
    return RedirectResponse(url="/bodesign/")


@app.get("/bodesign/routes", response_class=HTMLResponse)
def bodesign_route_index() -> str:
    route_rows = "".join(
        f"<tr><td><code>{escape(route['method'])}</code></td><td><a href=\"{escape(route['path'])}\"><code>{escape(route['path'])}</code></a></td><td>{escape(route['purpose'])}</td></tr>"
        for route in BODESIGN_WEB_ROUTES
    )
    return """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>bodesign routes</title>
        <style>
          body { margin: 0; padding: 32px; font-family: ui-sans-serif, system-ui, sans-serif; background: #101418; color: #e8f0f2; }
          a { color: #8ef6d2; }
          table { border-collapse: collapse; width: 100%; margin-top: 20px; }
          th, td { border-bottom: 1px solid #26323a; padding: 10px 8px; text-align: left; vertical-align: top; }
          code { color: #8ef6d2; }
        </style>
      </head>
      <body>
        <h1>bodesign visible routes</h1>
        <p>The primary viewer is <a href="/bodesign/"><code>/bodesign/</code></a>.</p>
        <table>
          <thead><tr><th>Method</th><th>Path</th><th>Purpose</th></tr></thead>
          <tbody>""" + route_rows + """</tbody>
        </table>
      </body>
    </html>
    """


@app.get("/bodesign/api/routes")
def bodesign_route_registry() -> dict[str, object]:
    return {"service": "bodesign-api", "routes": BODESIGN_WEB_ROUTES}


@app.get("/bodesign/", response_class=HTMLResponse)
def bodesign_viewer() -> str:
    return _render_project_workspace(BUILTIN_PROJECT_ID)


@app.get("/bodesign/projects/{project_id}", response_class=HTMLResponse)
def bodesign_project_workspace(project_id: str) -> str:
    return _render_project_workspace(project_id)


@app.get("/bodesign/projects/{project_id}/artifacts/{artifact_id}", response_class=HTMLResponse)
def bodesign_artifact_viewer(project_id: str, artifact_id: str) -> str:
    artifact = _find_project_artifact(project_id, artifact_id)
    if artifact is None:
        return _render_not_found(f"Artifact not found: {project_id}/{artifact_id}")
    return _render_artifact_viewer(project_id, artifact)


def _render_project_workspace(project_id: str) -> str:
    projects = _list_visible_projects()
    project_markup = "".join(_project_card(project) for project in projects)
    board_design = _project_board_design(project_id)
    confidence = board_design["confidence_summary"]
    components = board_design.get("components", [])
    nets = board_design.get("nets", [])
    layers = board_design.get("layers", [])
    artifact_paths = _project_artifact_paths(project_id)
    artifact_groups = _group_artifacts(artifact_paths)
    geometry = _project_geometry(project_id)
    fusion_summary = geometry.get("fusion_summary") if isinstance(geometry.get("fusion_summary"), dict) else {}
    board_image = geometry.get("image_data_uri", "")
    raster_renderer = geometry.get("raster_renderer") if isinstance(geometry.get("raster_renderer"), dict) else {}
    board_visual = _board_raster_visual(board_image, raster_renderer)
    gerber_geometry = geometry.get("gerber") or {}
    drill_geometry = geometry.get("drill") or {}
    overlay_components = _board_overlay_components(components, nets)
    overlay_markup = "".join(_component_overlay_marker(component) for component in overlay_components)
    overlay_data = _js_string_literal(json.dumps({component["refdes"]: component for component in overlay_components}, ensure_ascii=False))
    layer_markup = "".join(_layer_row(layer) for layer in layers) or '<p class="muted">No copper layers parsed.</p>'
    document_markup = _artifact_group_markup(artifact_groups)
    artifact_table = "".join(_artifact_row(project_id, artifact) for artifact in _project_artifact_records(project_id))
    if not artifact_table:
        artifact_table = '<tr><td colspan="5">No artifacts are attached to this project yet.</td></tr>'
    component_table = "".join(_component_row(project_id, component) for component in components[:80])
    if not component_table:
        component_table = '<tr><td colspan="5">No placement/BOM components parsed.</td></tr>'
    net_markup = "".join(
        f'<tr><td><a href="/bodesign/api/projects/{escape(project_id)}/cross-probe/{escape_url(str(net.get("name", "net")))}"><code>{escape(str(net.get("name", "net")))}</code></a></td><td>{len(net.get("connected_pads", []))}</td><td>{escape(", ".join(str(pad) for pad in net.get("connected_pads", [])[:8]))}</td></tr>'
        for net in nets[:80]
    )
    if not net_markup:
        net_markup = '<tr><td colspan="3">No IPC nets parsed yet.</td></tr>'
    fusion_components = fusion_summary.get("components") if isinstance(fusion_summary.get("components"), list) else []
    fusion_markup = "".join(_component_fusion_row(component) for component in fusion_components[:80])
    if not fusion_markup:
        fusion_markup = '<tr><td colspan="5">No component↔net fusion evidence yet.</td></tr>'
    kicad_foundation = get_project_kicad_foundation(project_id)
    project_tree = get_project_tree(project_id)
    kicad_native_extension = get_project_kicad_native_extension(project_id)
    kicad_source_markup = _kicad_source_markup(kicad_foundation)
    kicad_taxonomy_markup = _kicad_taxonomy_markup(kicad_foundation)
    kicad_analysis_markup = _kicad_analysis_markup(kicad_foundation)
    kicad_blocker_markup = _kicad_blocker_markup(kicad_foundation)
    kicad_native_markup = _kicad_native_extension_markup(kicad_native_extension)
    candidate_workspace = get_generated_design_candidate_workspace(project_id)
    candidate_markup = _candidate_workspace_markup(candidate_workspace)
    ir_json = escape(json.dumps(_compact_board_design(board_design), indent=2, ensure_ascii=False))
    return """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>bodesign Workspace</title>
        <style>
          :root { color-scheme: dark; --bg: #0b0f12; --panel: #111a20; --panel2: #162229; --line: #293943; --text: #e8f0f2; --muted: #9aacb4; --accent: #5de4c7; --accent2: #ffc857; }
          * { box-sizing: border-box; }
          body { margin: 0; font-family: ui-sans-serif, system-ui, sans-serif; background: var(--bg); color: var(--text); }
          .shell { display: grid; grid-template-columns: 300px minmax(0, 1fr); min-height: 100vh; max-width: 100vw; overflow-x: hidden; }
          .sidebar { padding: 24px; border-right: 1px solid var(--line); background: #0f171c; min-width: 0; }
          .workspace { padding: 22px; min-width: 0; }
          h1, h2, h3 { margin-top: 0; }
          h1 { font-size: 26px; letter-spacing: -0.03em; }
          h2 { font-size: 18px; }
          h3 { font-size: 15px; color: #d8e8ec; }
          .muted { color: var(--muted); }
          .metric { display: flex; justify-content: space-between; gap: 16px; margin: 8px 0; color: #cbd6d9; }
          .button { display: inline-block; padding: 8px 11px; border-radius: 10px; background: var(--accent); color: #07100d; text-decoration: none; font-weight: 700; }
          .button.secondary { background: transparent; color: var(--accent); border: 1px solid var(--line); }
          .pill { display: inline-block; margin: 4px 4px 4px 0; padding: 5px 9px; border: 1px solid #39515b; border-radius: 999px; color: #9bd8ff; background: #0c151a; }
          .tabs { display: flex; flex-wrap: wrap; align-items: flex-start; gap: 8px; margin-bottom: 16px; position: sticky; top: 0; z-index: 1; padding: 8px 0 14px; background: linear-gradient(#0b0f12 76%, #0b0f1200); min-width: 0; }
          .tabs input { display: none; }
          .tabs label { cursor: pointer; padding: 9px 12px; border: 1px solid var(--line); border-radius: 12px; color: var(--muted); background: var(--panel); }
          #tab-overview:checked ~ label[for="tab-overview"], #tab-schematic:checked ~ label[for="tab-schematic"], #tab-pcb:checked ~ label[for="tab-pcb"], #tab-libraries:checked ~ label[for="tab-libraries"], #tab-datasheets:checked ~ label[for="tab-datasheets"], #tab-analysis:checked ~ label[for="tab-analysis"], #tab-manufacturing:checked ~ label[for="tab-manufacturing"], #tab-reports:checked ~ label[for="tab-reports"], #tab-candidates:checked ~ label[for="tab-candidates"] { color: #07100d; background: var(--accent); border-color: var(--accent); }
          .panels { flex: 0 0 100%; width: 100%; min-width: 0; }
          .panel { display: none; border: 1px solid var(--line); border-radius: 18px; background: var(--panel); padding: 20px; min-height: calc(100vh - 96px); max-width: 100%; overflow: hidden; }
          #tab-overview:checked ~ .panels #overview, #tab-schematic:checked ~ .panels #schematic, #tab-pcb:checked ~ .panels #pcb, #tab-libraries:checked ~ .panels #libraries, #tab-datasheets:checked ~ .panels #datasheets, #tab-analysis:checked ~ .panels #analysis, #tab-manufacturing:checked ~ .panels #manufacturing, #tab-reports:checked ~ .panels #reports, #tab-candidates:checked ~ .panels #candidates { display: block; }
          .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; min-width: 0; }
          .card { border: 1px solid var(--line); border-radius: 16px; padding: 16px; background: var(--panel2); min-width: 0; overflow-wrap: anywhere; }
          .project-card { border-color: #3e635b; }
          .viewer-toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 14px 0 10px; }
          .control-button { cursor: pointer; padding: 7px 10px; border-radius: 10px; border: 1px solid var(--line); background: #0f171c; color: var(--text); font-weight: 650; }
          .control-button:hover { border-color: var(--accent); color: var(--accent); }
          .geometry-viewer { height: min(68vh, 760px); border: 1px solid #3b5560; border-radius: 16px; background: #07100d; overflow: hidden; padding: 12px; user-select: none; touch-action: none; }
          .geometry-canvas { width: 100%; height: 100%; position: relative; }
          .raster-view { width: 100%; height: 100%; object-fit: contain; display: block; image-rendering: auto; }
          .render-error { height: 100%; display: grid; place-content: center; text-align: center; color: #ffb4a8; border: 1px dashed #74443e; border-radius: 12px; padding: 20px; }
          .component-overlay { position: absolute; inset: 0; pointer-events: none; }
          .component-marker { position: absolute; transform: translate(-50%, -50%); pointer-events: auto; cursor: pointer; border: 1px solid #ffed9a; border-radius: 8px; background: #ffc857d9; color: #12170f; font-size: 11px; font-weight: 800; padding: 3px 5px; box-shadow: 0 0 0 2px #0008; white-space: nowrap; }
          .component-marker[data-side="bottom"] { background: #9bd8ffd9; border-color: #cfefff; }
          .geometry-canvas:not(.show-components) .component-marker { display: none; }
          .component-marker[data-category="passive"], .component-marker[data-category="testpoint"] { display: none; }
          .geometry-canvas.show-components.show-passives .component-marker[data-category="passive"], .geometry-canvas.show-components.show-testpoints .component-marker[data-category="testpoint"] { display: block; }
          .geometry-canvas.show-components .component-marker[data-category="major"], .geometry-canvas.show-components .component-marker[data-category="active"], .geometry-canvas.show-components .component-marker[data-category="other"] { display: block; }
          .component-marker[data-category="testpoint"] { font-size: 9px; padding: 2px 4px; opacity: 0.72; }
          .component-marker.is-selected { background: #ff6b6b; border-color: #ffd0d0; color: white; }
          .inspector { margin-top: 12px; border: 1px solid var(--line); border-radius: 14px; background: #0f171c; padding: 14px; }
          .pin-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
          table { border-collapse: collapse; width: 100%; table-layout: fixed; }
          th, td { border-bottom: 1px solid var(--line); padding: 9px 8px; text-align: left; vertical-align: top; }
          th { color: #bcd0d7; font-weight: 650; }
          td, th, code { overflow-wrap: anywhere; }
          .scroll { max-height: 540px; overflow: auto; max-width: 100%; }
          pre { margin: 0; white-space: pre-wrap; color: #d6e3e7; max-width: 100%; overflow: auto; }
          code { color: #8ef6d2; }
          @media (max-width: 900px) { .shell { grid-template-columns: 1fr; } .sidebar { border-right: 0; border-bottom: 1px solid var(--line); } }
        </style>
      </head>
      <body>
        <main class="shell">
          <aside class="sidebar">
            <h1>bodesign</h1>
             <p class="muted">KiCad companion dashboard for client-owned folders and fixture-backed hardware evidence. Native KiCad remains the schematic/PCB editor.</p>
            <h2>Project</h2>
            <div class="metric"><span>project</span><code>""" + escape(project_id) + """</code></div>
            <div class="metric"><span>IR</span><code>""" + escape(str(board_design["id"])) + """</code></div>
            <div class="metric"><span>status</span><code>""" + escape(str(confidence["status"])) + """</code></div>
            <div class="metric"><span>confidence</span><code>""" + escape(str(confidence["overall"])) + """</code></div>
             <p><a class="button" href="#overview">Open companion dashboard</a></p>
            <h2>Parsed Summary</h2>
            <div class="metric"><span>components</span><code>""" + str(int(confidence.get("components", 0))) + """</code></div>
            <div class="metric"><span>nets</span><code>""" + str(int(confidence.get("nets", 0))) + """</code></div>
            <div class="metric"><span>IPC pads</span><code>""" + str(int(confidence.get("ipc_pads", 0))) + """</code></div>
            <div class="metric"><span>IPC vias</span><code>""" + str(int(confidence.get("ipc_vias", 0))) + """</code></div>
            <h2>Source Groups</h2>
            <div class="metric"><span>Gerber</span><code>""" + str(len(artifact_groups["gerber"])) + """</code></div>
            <div class="metric"><span>Drill</span><code>""" + str(len(artifact_groups["drill"])) + """</code></div>
            <div class="metric"><span>IPC</span><code>""" + str(len(artifact_groups["ipc356"])) + """</code></div>
            <div class="metric"><span>BOM/placement</span><code>""" + str(len(artifact_groups["bom_placement"])) + """</code></div>
          </aside>
          <section class="workspace">
            <div class="tabs">
              <input checked id="tab-overview" name="workspace-tab" type="radio" />
              <input id="tab-schematic" name="workspace-tab" type="radio" />
              <input id="tab-pcb" name="workspace-tab" type="radio" />
              <input id="tab-libraries" name="workspace-tab" type="radio" />
              <input id="tab-datasheets" name="workspace-tab" type="radio" />
              <input id="tab-analysis" name="workspace-tab" type="radio" />
              <input id="tab-manufacturing" name="workspace-tab" type="radio" />
              <input id="tab-reports" name="workspace-tab" type="radio" />
              <input id="tab-candidates" name="workspace-tab" type="radio" />
              <label for="tab-overview">Project Overview</label>
              <label for="tab-schematic">Schematic Status</label>
              <label for="tab-pcb">PCB Layout Status</label>
              <label for="tab-libraries">Libraries</label>
              <label for="tab-datasheets">Datasheets/Docs</label>
              <label for="tab-analysis">Analysis</label>
              <label for="tab-manufacturing">Manufacturing Outputs</label>
              <label for="tab-reports">Reports</label>
              <label for="tab-candidates">Candidate Review</label>
              <div class="panels">
                <article class="panel" id="overview">
                  <h2>Project Overview</h2>
                  <p class="muted">Open or import client-owned KiCad projects. bodesign is a companion dashboard; native KiCad owns editing, canvas, libraries, DRC, and ERC.</p>
                   <div class="grid">""" + project_markup + """
                     <div class="card">
                        <h3>Connect native KiCad project</h3>
                        <p class="muted">Folder sharing is not wired yet. The target flow indexes KiCad files from a client-owned folder and hands edit/canvas actions to a KiCad Action Plugin or sidecar.</p>
                       <p><a class="button secondary" href="/bodesign/routes">View available API routes</a></p>
                     </div>
                     <div class="card">
                        <h3>KiCad native foundation status</h3>
                       <p><code>""" + escape(str(kicad_foundation.get("status", "unknown"))) + """</code></p>
                       <p>storage owner: <code>""" + escape(str(kicad_foundation.get("storage_owner", "unknown"))) + """</code></p>
                       <p>save-back: <code>""" + escape(str(kicad_foundation.get("safe_save_back", {}).get("mode", "unknown"))) + """</code></p>
                     </div>
                   </div>
                     <h3>KiCad source detection</h3>
                     <div class="grid">""" + kicad_source_markup + """</div>
                     <h3>Client-owned project tree</h3>
                     """ + _project_tree_markup(project_tree) + """
                     <h3>Native KiCad extension boundary</h3>
                    """ + kicad_native_markup + """
                    <h3>Foundation blockers</h3>
                    <ul>""" + kicad_blocker_markup + """</ul>
                  </article>
                 <article class="panel" id="schematic">
                  <h2>Schematic Status</h2>
                  <p class="muted">Native KiCad schematic editor is the primary circuit design surface. This panel shows evidence/status only; it is not a browser schematic editor.</p>
                  <div class="card"><h3>Schematic evidence status</h3><p>No <code>.kicad_sch</code> is attached yet. IPC nets and placement tables below are evidence inputs, not a schematic source.</p></div>
                  <h3>IPC / Nets evidence</h3>
                  <div class="scroll"><table><thead><tr><th>Net</th><th>Connected pads</th><th>Sample pads</th></tr></thead><tbody>""" + net_markup + """</tbody></table></div>
                </article>
                <article class="panel" id="pcb">
                  <h2>PCB Layout Status</h2>
                  <p class="muted">Native KiCad PCB editor owns board layout, canvas interaction, DRC, and ERC. This fixture shows third-party raster Gerber evidence until a <code>.kicad_pcb</code> source is attached.</p>
                  <h3>Board View evidence</h3>
                  <p class="muted">Third-party raster Gerber render. This view uses pygerber's raster backend instead of hand-written SVG geometry; net-aware coloring and multi-layer compositing are still pending.</p>
                  <div class="grid">
                    <div class="card"><h3>Default view</h3><p><code>pygerber-raster</code></p><p>status: <b>""" + escape(str((geometry.get("raster_renderer") or {}).get("status", "not-run"))) + """</b></p></div>
                    <div class="card"><h3>Gerber source</h3><p><code>""" + escape(str(gerber_geometry.get("filename", "none"))) + """</code></p><p>draws: <b>""" + escape(str(gerber_geometry.get("draw_count", 0))) + """</b> · flashes: <b>""" + escape(str(gerber_geometry.get("flash_count", 0))) + """</b></p></div>
                    <div class="card"><h3>Drill source</h3><p><code>""" + escape(str(drill_geometry.get("filename", "none"))) + """</code></p><p>hits: <b>""" + escape(str(drill_geometry.get("hit_count", 0))) + """</b> · tools: <b>""" + escape(str(drill_geometry.get("tool_count", 0))) + """</b></p></div>
                    <div class="card"><h3>Component-Net fusion preview</h3><p>coverage: <b>""" + escape(str(fusion_summary.get("coverage_ratio", 0.0))) + """</b></p><p>mapped components: <b>""" + escape(str(fusion_summary.get("mapped_components", 0))) + """</b> / """ + escape(str(fusion_summary.get("total_components", 0))) + """</p></div>
                  </div>
                  <div class="viewer-toolbar" aria-label="Board view controls">
                      <button class="control-button" type="button" data-overlay-toggle="components">Toggle placement overlay</button>
                      <button class="control-button" type="button" data-overlay-toggle="passives">Toggle passives</button>
                      <button class="control-button" type="button" data-overlay-toggle="testpoints">Toggle test points</button>
                      <span class="muted">Raster view is the default. It is generated by pygerber; Browser-level zoom is intentionally left to the image viewer for now, and hand-written SVG pan/zoom fallback has been removed.</span>
                  </div>
                  <div class="geometry-viewer">
                    <div class="geometry-canvas" id="geometry-canvas">""" + board_visual + """<div class="component-overlay" id="component-overlay">""" + overlay_markup + """</div></div>
                  </div>
                  <div class="inspector" id="component-inspector">
                    <h3>Component / pinout inspector</h3>
                    <p class="muted">Click a component marker to see placement, package, and IPC-derived pin/net evidence. Exact footprint pin geometry is pending datasheet/footprint normalization.</p>
                  </div>
                </article>
                 <article class="panel" id="libraries">
                   <h2>Libraries</h2>
                   <p class="muted">Project-local symbols, footprints, 3D models, and vendor libraries will be indexed here when a KiCad folder is shared.</p>
                   <h3>Human-facing folder taxonomy</h3>
                   <div class="grid">""" + kicad_taxonomy_markup + """</div>
                   <div class="scroll"><table><thead><tr><th>Refdes</th><th>Part/value</th><th>Footprint</th><th>Side</th><th>XY mil</th></tr></thead><tbody>""" + component_table + """</tbody></table></div>
                 </article>
                <article class="panel" id="datasheets">
                  <h2>Datasheets/Docs</h2>
                  <p class="muted">Human-facing docs and datasheets stay in client-owned folders. Manufacturing artifacts remain evidence inputs below until native KiCad sources are attached.</p>
                  <div class="scroll"><table><thead><tr><th>File</th><th>Type</th><th>Format</th><th>Size</th><th>Open</th></tr></thead><tbody>""" + artifact_table + """</tbody></table></div>
                  <h3>Grouped by type</h3>
                  <div class="grid">""" + document_markup + """</div>
                </article>
                <article class="panel" id="analysis">
                  <h2>Analysis</h2>
                   <p class="muted">KiCad Happy analyzer output, trust summaries, DRC/ERC/DFM evidence, and reconstruction previews appear here as evidence/cache views.</p>
                   <h3>KiCad Happy hidden analysis cache</h3>
                   """ + kicad_analysis_markup + """
                   <h3>Component-Net fusion evidence</h3>
                  <div class="scroll"><table><thead><tr><th>Refdes</th><th>Part/value</th><th>Pins</th><th>Nets</th><th>Sample nets</th></tr></thead><tbody>""" + fusion_markup + """</tbody></table></div>
                  <h3>BoardDesign IR</h3>
                  <pre>""" + ir_json + """</pre>
                </article>
                <article class="panel" id="manufacturing">
                  <h2>Manufacturing Outputs</h2>
                   <p class="muted">Gerber, drill, IPC, BOM, placement, and routing reports are manufacturing evidence panels for the KiCad companion dashboard.</p>
                   <h3>Detected manufacturing outputs</h3>
                   """ + _kicad_output_markup(kicad_foundation) + """
                   <h3>Gerber Layers</h3>
                  <table><thead><tr><th>Layer</th><th>Source file</th><th>Status</th></tr></thead><tbody>""" + layer_markup + """</tbody></table>
                  <h2>IPC-356 Nets</h2>
                  <p class="muted">Connectivity evidence parsed from IPC records. This is the closest current view to circuit topology.</p>
                  <div class="scroll"><table><thead><tr><th>Net</th><th>Connected pads</th><th>Sample pads</th></tr></thead><tbody>""" + net_markup + """</tbody></table></div>
                </article>
                <article class="panel" id="candidates">
                  <h2>Candidate Review</h2>
                  <p class="muted">Candidate workspace for diff, evidence and approval review. This does not create send-to-fab output.</p>
                  """ + candidate_markup + """
                </article>
                <article class="panel" id="reports">
                  <h2>Reports</h2>
                  <div class="grid">
                    <div class="card"><h3>Current capability</h3><p>Rockbox placement and IPC summaries are parsed into BoardDesign IR.</p></div>
                    <div class="card"><h3>Not yet correct</h3><p>True schematic drawing, Gerber geometry rendering, routing topology and datasheet-derived semantics are still pending.</p></div>
                    <div class="card"><h3>Next viewer layer</h3><p>Render each original file type visually: PDFs as documents, Gerber as layer canvas, IPC as net graph, BOM as component table.</p></div>
                  </div>
                </article>
              </div>
            </div>
          </section>
        </main>
        <script>
          (() => {
            const canvas = document.getElementById('geometry-canvas');
            const viewer = canvas ? canvas.closest('.geometry-viewer') : null;
            if (!canvas || !viewer) return;
            const inspector = document.getElementById('component-inspector');
            const components = JSON.parse('""" + overlay_data + """');
            document.querySelectorAll('[data-overlay-toggle]').forEach((button) => {
              button.addEventListener('click', () => {
                const category = button.getAttribute('data-overlay-toggle');
                if (category === 'components') canvas.classList.toggle('show-components');
                if (category === 'passives') canvas.classList.toggle('show-passives');
                if (category === 'testpoints') canvas.classList.toggle('show-testpoints');
              });
            });
            document.querySelectorAll('.component-marker').forEach((marker) => {
              marker.addEventListener('click', (event) => {
                event.stopPropagation();
                document.querySelectorAll('.component-marker').forEach((item) => item.classList.remove('is-selected'));
                marker.classList.add('is-selected');
                const component = components[marker.dataset.refdes];
                if (!component || !inspector) return;
                const pins = component.pins.length ? component.pins.map((pin) => `<span class="pill">${pin}</span>`).join('') : '<span class="muted">No IPC pin/net evidence linked yet.</span>';
                inspector.innerHTML = `<h3>${component.refdes} ${component.part_number || ''}</h3><div class="grid"><div class="card"><strong>footprint</strong><br><code>${component.footprint || 'unknown'}</code></div><div class="card"><strong>side</strong><br><code>${component.side}</code></div><div class="card"><strong>XY mil</strong><br><code>${component.x_mil}, ${component.y_mil}</code></div></div><h3>IPC pin/net evidence</h3><div class="pin-list">${pins}</div>`;
              });
            });
          })();
        </script>
      </body>
    </html>
    """


@app.get("/api/projects")
@app.get("/bodesign/api/projects")
def list_projects() -> list[dict[str, object]]:
    return _list_visible_projects()


@app.get("/api/projects/{project_id}/artifacts")
@app.get("/bodesign/api/projects/{project_id}/artifacts")
def list_project_artifacts(project_id: str) -> list[dict[str, object]]:
    return _project_artifact_records(project_id)


@app.get("/api/projects/{project_id}/artifacts/{artifact_id}")
@app.get("/bodesign/api/projects/{project_id}/artifacts/{artifact_id}")
def get_project_artifact(project_id: str, artifact_id: str) -> dict[str, object]:
    artifact = _find_project_artifact(project_id, artifact_id)
    if artifact is None:
        return {"project_id": project_id, "artifact_id": artifact_id, "status": "not-found"}
    return {**artifact, "preview": _artifact_preview(Path(str(artifact["path"])), str(artifact["artifact_type"]))}


@app.get("/api/projects/{project_id}/geometry")
@app.get("/bodesign/api/projects/{project_id}/geometry")
def get_project_geometry(project_id: str) -> dict[str, object]:
    geometry = _project_geometry(project_id)
    return {key: value for key, value in geometry.items() if key != "svg"}


@app.get("/api/projects/{project_id}/storage-share")
@app.get("/bodesign/api/projects/{project_id}/storage-share")
def get_project_storage_share(project_id: str) -> dict[str, object]:
    if build_default_storage_share_manifest is None or validate_storage_share_manifest is None:
        return {
            "project_id": project_id,
            "status": "storage-core package import failed",
            "durable_owner": "client",
            "storage_model": "client-owned-local-folder",
            "hidden_workspace": ".bodesign",
            "warnings": ["Storage-share manifest contract could not be built."],
        }
    manifest = build_default_storage_share_manifest(project_id)
    taxonomy = classify_project_folder_taxonomy(_project_taxonomy_paths(project_id), manifest.hidden_workspace) if classify_project_folder_taxonomy is not None else None
    kicad_happy_cache = build_kicad_happy_cache_mapping(manifest.hidden_workspace) if build_kicad_happy_cache_mapping is not None else None
    return {
        **asdict(manifest),
        "status": "ready",
        "validation_errors": validate_storage_share_manifest(manifest),
        "folder_taxonomy": asdict(taxonomy) if taxonomy is not None else {"warnings": ["Storage folder taxonomy classifier is unavailable."]},
        "kicad_happy_cache": asdict(kicad_happy_cache) if kicad_happy_cache is not None else {"warnings": ["KiCad Happy cache mapping is unavailable."]},
    }


@app.get("/api/projects/{project_id}/project-tree")
@app.get("/bodesign/api/projects/{project_id}/project-tree")
def get_project_tree(project_id: str) -> dict[str, object]:
    if build_default_storage_share_manifest is None or build_project_tree_browse_contract is None:
        return {
            "project_id": project_id,
            "status": "storage-core package import failed",
            "durable_owner": "client",
            "access_mode": "read-only-fixture-backed",
            "folder_nodes": [],
            "hidden_workspace": {"path": ".bodesign", "visibility": "hidden-system-summary", "source_count": 0},
            "blockers": ["Project tree contract could not be built."],
        }
    manifest = build_default_storage_share_manifest(project_id)
    tree = build_project_tree_browse_contract(project_id, _project_taxonomy_paths(project_id), manifest)
    return {
        **asdict(tree),
        "status": "project-tree-fixture-ready",
        "mutation_capabilities": [],
        "read_scope": "storage-share-manifest-derived",
    }


@app.get("/api/projects/{project_id}/kicad-foundation")
@app.get("/bodesign/api/projects/{project_id}/kicad-foundation")
def get_project_kicad_foundation(project_id: str) -> dict[str, object]:
    storage_share = get_project_storage_share(project_id)
    taxonomy = storage_share.get("folder_taxonomy") if isinstance(storage_share.get("folder_taxonomy"), dict) else {}
    kicad_sources = taxonomy.get("kicad_sources") if isinstance(taxonomy.get("kicad_sources"), dict) else {}
    roles = taxonomy.get("roles") if isinstance(taxonomy.get("roles"), dict) else {}
    output_artifacts = taxonomy.get("output_artifacts") if isinstance(taxonomy.get("output_artifacts"), list) else []
    kicad_happy_cache = storage_share.get("kicad_happy_cache") if isinstance(storage_share.get("kicad_happy_cache"), dict) else {}
    blockers = [
        "Real client folder browsing is not wired yet; this fixture uses deterministic manifest paths.",
        "Safe save-back is limited to scoped client-approved writes or client-applied patches.",
        "Gerber→design-source and datasheet/reference→design-source remain blocked until native KiCad plugin/sidecar round-trip is reliable.",
        "Browser-native schematic/PCB editing is intentionally blocked; native KiCad owns editor, canvas, DRC, and ERC.",
    ]
    if not kicad_sources.get("project"):
        blockers.append("No .kicad_pro source is detected in the shared client folder.")
    if not kicad_sources.get("schematic"):
        blockers.append("No .kicad_sch source is detected in the shared client folder.")
    if not kicad_sources.get("pcb"):
        blockers.append("No .kicad_pcb source is detected in the shared client folder.")
    return {
        "project_id": project_id,
        "status": "foundation-fixture-ready",
        "storage_share_status": storage_share.get("status", "unknown"),
        "storage_owner": storage_share.get("durable_owner", "client"),
        "storage_model": storage_share.get("storage_model", "client-owned-local-folder"),
        "project_root": storage_share.get("project_root", f"client://projects/{project_id}"),
        "hidden_workspace": storage_share.get("hidden_workspace", ".bodesign"),
        "safe_save_back": {
            "mode": storage_share.get("save_back_mode", "scoped-client-storage-share"),
            "conflict_policy": storage_share.get("conflict_policy", "client-detects-conflicts-before-accepting-mcp-writes"),
            "write_scopes": storage_share.get("write_scopes", []),
            "requires_client_approval": True,
        },
        "kicad_sources": kicad_sources,
        "taxonomy_roles": roles,
        "output_artifacts": output_artifacts,
        "kicad_happy_cache": kicad_happy_cache,
        "native_extension": get_project_kicad_native_extension(project_id),
        "blocked_pipelines": ["gerber-to-design-source", "datasheet-reference-to-design-source"],
        "blockers": blockers,
        "warnings": list(storage_share.get("warnings", [])) if isinstance(storage_share.get("warnings"), list) else [],
    }


@app.get("/api/projects/{project_id}/kicad-native-extension")
@app.get("/bodesign/api/projects/{project_id}/kicad-native-extension")
def get_project_kicad_native_extension(project_id: str) -> dict[str, object]:
    if build_kicad_native_extension_contract is None:
        return {
            "project_id": project_id,
            "status": "eda-bridge package import failed",
            "integration_model": "kicad-action-plugin-plus-bodesign-mcp-sidecar",
            "native_editor_owner": "KiCad native application owns schematic editor, PCB editor, canvas, libraries, DRC, and ERC.",
            "warnings": ["KiCad native extension contract could not be built."],
        }
    return {**asdict(build_kicad_native_extension_contract(project_id)), "status": "contract-ready"}


@app.get("/api/projects/{project_id}/kicad-plugin-handshake")
@app.get("/bodesign/api/projects/{project_id}/kicad-plugin-handshake")
def get_project_kicad_plugin_handshake(project_id: str) -> dict[str, object]:
    base_path = f"/bodesign/api/projects/{project_id}"
    native_extension = get_project_kicad_native_extension(project_id)
    foundation = get_project_kicad_foundation(project_id)
    approved_capabilities = [
        "open-dashboard",
        "read-foundation-status",
        "read-native-extension-contract",
        "request-analysis-plan",
        "represent-approved-patch",
    ]
    return {
        "project_id": project_id,
        "status": "sidecar-handshake-ready",
        "sidecar_available": True,
        "integration_model": "kicad-action-plugin-plus-bodesign-mcp-sidecar",
        "urls": {
            "dashboard": f"/bodesign/projects/{project_id}",
            "foundation": f"{base_path}/kicad-foundation",
            "native_extension": f"{base_path}/kicad-native-extension",
            "request_analysis": f"{base_path}/workflow/reference-board",
            "generated_candidate": f"{base_path}/candidates/generated-design",
        },
        "approved_capabilities": approved_capabilities,
        "blocked_capabilities": [
            "run-drc-erc-from-sidecar",
            "mutate-kicad-files-without-user-approval",
            "browser-native-schematic-editor",
            "browser-native-pcb-layout-editor",
        ],
        "approval_policy": {
            "approved_for_execution": False,
            "approved_for_file_mutation": False,
            "patch_application": "approved-patch-only-through-native-kicad-or-client-save-back",
        },
        "native_extension_status": native_extension.get("status", "unknown"),
        "foundation_status": foundation.get("status", "unknown"),
        "blockers": foundation.get("blockers", []),
        "warnings": ["Handshake is informational and does not run KiCad, DRC, ERC, or write project files."],
    }


@app.get("/api/projects/{project_id}/cross-probe/{probe_id}")
@app.get("/bodesign/api/projects/{project_id}/cross-probe/{probe_id}")
def get_project_cross_probe(project_id: str, probe_id: str) -> dict[str, object]:
    return _project_cross_probe(project_id, probe_id)


@app.post("/api/projects")
@app.post("/bodesign/api/projects")
def create_project(payload: dict[str, str] | None = None) -> dict[str, object]:
    project_name = (payload or {}).get("name") or "Untitled bodesign project"
    project_id = _project_id(project_name)
    if ProjectSummary is None:
        project = {
            "id": project_id,
            "name": project_name,
            "status": "created",
            "artifact_count": 0,
            "board_design_id": None,
        }
    else:
        project = asdict(ProjectSummary(id=project_id, name=project_name))
    PROJECTS[project_id] = project
    return project


@app.post("/api/artifacts/detect")
@app.post("/bodesign/api/artifacts/detect")
def detect_artifacts(payload: dict[str, list[str]]) -> list[dict[str, object]]:
    paths = payload.get("paths", [])
    if detect_input_artifact is None:
        return [
            {
                "id": f"detected-{index}",
                "project_id": "detected",
                "filename": Path(path).name,
                "path": path,
                "artifact_type": "unknown",
                "detected_format": Path(path).suffix.lower().lstrip(".") or None,
                "status": "detected",
                "evidence_refs": [],
            }
            for index, path in enumerate(paths)
        ]
    return [asdict(detect_input_artifact(path)) for path in paths]


@app.get("/api/jobs")
@app.get("/bodesign/api/jobs")
def list_jobs() -> list[dict[str, object]]:
    if JOBS or JobSummary is None:
        return JOBS
    return []


@app.get("/api/schema-summary")
@app.get("/bodesign/api/schema-summary")
def schema_summary() -> dict[str, object]:
    return {
        "schemas": [
            "EvidenceSource",
            "EvidenceRef",
            "InputArtifact",
            "ProjectSummary",
            "ComponentKnowledge",
            "BoardDesign",
        ],
        "artifact_types": [
            "datasheet",
            "schematic",
            "bom_placement",
            "gerber",
            "drill",
            "ipc356",
            "routing_report",
            "reference_doc",
            "unknown",
        ],
        "status": "placeholder-contracts",
    }


@app.get("/api/projects/{project_id}/board-design")
@app.get("/bodesign/api/projects/{project_id}/board-design")
def get_board_design(project_id: str) -> dict[str, object]:
    if reconstruct_rockbox_placeholder is None:
        return {
            "id": f"{project_id}-board-design",
            "version": "0.1.0-placeholder",
            "title": "Rockbox reconstructed board placeholder",
            "components": [],
            "nets": [],
            "layers": [],
            "board_objects": [],
            "evidence_refs": [],
            "confidence_summary": {"overall": 0.0, "status": "placeholder"},
        }

    board_design = reconstruct_rockbox_placeholder(project_id)
    return asdict(board_design)


@app.post("/api/projects/{project_id}/rockbox/manifest")
@app.post("/bodesign/api/projects/{project_id}/rockbox/manifest")
def build_rockbox_manifest(project_id: str, payload: dict[str, list[str]]) -> dict[str, object]:
    artifact_paths = payload.get("artifact_paths", [])
    if build_rockbox_input_manifest is None:
        return {
            "project_id": project_id,
            "component_files": [],
            "gerber_files": [],
            "drill_files": [],
            "ipc_files": [],
            "routing_reports": [],
            "unknown_files": artifact_paths,
        }

    return asdict(build_rockbox_input_manifest(project_id, artifact_paths))


@app.post("/api/projects/{project_id}/rockbox/reconstruct")
@app.post("/bodesign/api/projects/{project_id}/rockbox/reconstruct")
def reconstruct_rockbox(project_id: str, payload: dict[str, list[str]]) -> dict[str, object]:
    artifact_paths = payload.get("artifact_paths", [])
    if reconstruct_rockbox_placeholder is None:
        return {
            "id": f"{project_id}-board-design",
            "version": "0.1.0-placeholder",
            "title": "Rockbox reconstructed board placeholder",
            "components": [],
            "nets": [],
            "layers": [],
            "board_objects": [],
            "evidence_refs": [],
            "confidence_summary": {"overall": 0.0, "status": "reverse-core package import failed"},
        }

    return asdict(reconstruct_rockbox_placeholder(project_id, artifact_paths))


@app.post("/api/projects/{project_id}/knowledge/datasheets")
@app.post("/bodesign/api/projects/{project_id}/knowledge/datasheets")
def ingest_datasheets(project_id: str, payload: dict[str, object]) -> dict[str, object]:
    part_number = str(payload.get("part_number") or "unknown-part")
    document_paths_value = payload.get("document_paths", [])
    document_paths = [str(document_path) for document_path in document_paths_value] if isinstance(document_paths_value, list) else []
    package_hint_value = payload.get("package_hint")
    package_hint = str(package_hint_value) if package_hint_value else None
    if ingest_datasheet_knowledge is None:
        return {
            "project_id": project_id,
            "part_number": part_number,
            "reusable_key": f"component:{part_number}",
            "document_paths": document_paths,
            "component": None,
            "status": "component-kb package import failed",
            "warnings": ["Component knowledge placeholder could not run."],
        }

    return asdict(ingest_datasheet_knowledge(project_id, part_number, document_paths, package_hint))


@app.get("/api/projects/{project_id}/knowledge/queue")
@app.get("/bodesign/api/projects/{project_id}/knowledge/queue")
def get_component_knowledge_queue(project_id: str) -> dict[str, object]:
    board_design = _project_board_design(project_id)
    components = board_design.get("components", []) if isinstance(board_design.get("components"), list) else []
    if build_component_knowledge_queue is None:
        return {"project_id": project_id, "status": "component-kb package import failed", "items": []}
    items = [asdict(item) for item in build_component_knowledge_queue(components)]
    return {"project_id": project_id, "status": "queued", "total_items": len(items), "items": items}


@app.post("/api/projects/{project_id}/knowledge/external-fetch")
@app.post("/bodesign/api/projects/{project_id}/knowledge/external-fetch")
def request_external_datasheet_fetch(project_id: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    request_payload = payload or {}
    return {
        "project_id": project_id,
        "part_number": str(request_payload.get("part_number") or "unknown-part"),
        "status": "blocked-policy-gate",
        "external_fetch_enabled": False,
        "requires_user_approval": True,
        "allowed_inputs": ["user-provided PDF", "user-provided text", "docxmcp-derived source chunks"],
        "reason": "Automatic public web datasheet downloads are disabled until the user approves an explicit fetching policy.",
    }


@app.post("/api/projects/{project_id}/openmv/plan")
@app.post("/bodesign/api/projects/{project_id}/openmv/plan")
def plan_openmv(project_id: str, payload: dict[str, list[str]]) -> dict[str, object]:
    artifact_paths = payload.get("artifact_paths", [])
    if plan_openmv_document_ingestion is None:
        return {
            "id": f"{project_id}-openmv-design-intent",
            "title": "OpenMV document-driven design intent placeholder",
            "target_functions": [],
            "source_evidence": [],
            "components": [],
            "constraints": [],
            "knowledge_gaps": ["doc-core package import failed"],
            "confidence": 0.0,
        }

    return asdict(plan_openmv_document_ingestion(project_id, artifact_paths))


@app.post("/api/projects/{project_id}/export/gerber")
@app.post("/bodesign/api/projects/{project_id}/export/gerber")
def export_gerber(project_id: str, payload: dict[str, str] | None = None) -> dict[str, object]:
    board_design_id = (payload or {}).get("board_design_id") or f"{project_id}-board-design"
    if plan_gerber_export is None:
        return {
            "project_id": project_id,
            "board_design_id": board_design_id,
            "output_paths": [],
            "report_path": None,
            "status": "source-core package import failed",
            "warnings": ["Gerber export placeholder could not be planned."],
        }

    return asdict(plan_gerber_export(project_id, board_design_id))


@app.post("/api/projects/{project_id}/export/gerber/validate")
@app.post("/bodesign/api/projects/{project_id}/export/gerber/validate")
def validate_gerber_export(project_id: str, payload: dict[str, list[str]]) -> dict[str, object]:
    output_paths = payload.get("output_paths", [])
    if validate_gerber_export_placeholder is None:
        return {
            "project_id": project_id,
            "output_paths": output_paths,
            "status": "gerber-core package import failed",
            "warnings": ["Gerber validation placeholder could not run."],
            "blocking_errors": [],
        }

    return asdict(validate_gerber_export_placeholder(project_id, output_paths))


@app.post("/api/projects/{project_id}/eda/kicad/bridge-plan")
@app.post("/bodesign/api/projects/{project_id}/eda/kicad/bridge-plan")
def plan_project_kicad_bridge(project_id: str, payload: dict[str, str] | None = None) -> dict[str, object]:
    request_payload = payload or {}
    board_design_id = request_payload.get("board_design_id") or f"{project_id}-board-design"
    integration_posture = request_payload.get("integration_posture") or "plugin-submodule-auto-workflow"
    if plan_kicad_bridge is None:
        return {
            "project_id": project_id,
            "board_design_id": board_design_id,
            "integration_posture": integration_posture,
            "execution_status": "eda-bridge package import failed",
            "planned_outputs": [],
            "warnings": ["KiCad bridge adapter could not be planned."],
        }
    return asdict(plan_kicad_bridge(project_id, board_design_id, integration_posture))


@app.post("/api/projects/{project_id}/workflow/reference-board")
@app.post("/bodesign/api/projects/{project_id}/workflow/reference-board")
def plan_project_reference_board_workflow(project_id: str, payload: dict[str, str] | None = None) -> dict[str, object]:
    request_payload = payload or {}
    board_design = _project_board_design(project_id)
    board_design_id = request_payload.get("board_design_id") or str(board_design.get("id") or f"{project_id}-board-design")
    components = board_design.get("components", []) if isinstance(board_design.get("components"), list) else []
    nets = board_design.get("nets", []) if isinstance(board_design.get("nets"), list) else []
    artifacts = _project_artifact_records(project_id)
    queue = get_component_knowledge_queue(project_id)
    queue_count = int(queue.get("total_items", 0)) if isinstance(queue.get("total_items"), int) else 0
    if plan_reference_board_workflow is None:
        return {
            "project_id": project_id,
            "board_design_id": board_design_id,
            "status": "workflow-core package import failed",
            "orchestration_model": "client-orchestrated-mcp-workflow",
            "stages": [],
            "approval_gates": [],
            "warnings": ["Reference-board workflow planner could not run."],
        }
    return asdict(
        plan_reference_board_workflow(
            project_id=project_id,
            board_design_id=board_design_id,
            artifact_count=len(artifacts),
            component_count=len(components),
            net_count=len(nets),
            knowledge_queue_count=queue_count,
            orchestration_model=str(request_payload.get("orchestration_model") or "client-orchestrated-mcp-workflow"),
        )
    )


@app.get("/api/projects/{project_id}/candidates/generated-design")
@app.get("/bodesign/api/projects/{project_id}/candidates/generated-design")
def get_generated_design_candidate_workspace(project_id: str) -> dict[str, object]:
    board_design = _project_board_design(project_id)
    board_design_id = str(board_design.get("id") or f"{project_id}-board-design")
    components = board_design.get("components", []) if isinstance(board_design.get("components"), list) else []
    nets = board_design.get("nets", []) if isinstance(board_design.get("nets"), list) else []
    artifacts = _project_artifact_records(project_id)
    if build_generated_design_candidate_workspace is None:
        return {
            "project_id": project_id,
            "candidate_id": f"{project_id}-candidate-001",
            "source_board_design_id": board_design_id,
            "status": "workflow-core package import failed",
            "approval_state": "not-approved",
            "diff_summary": [],
            "evidence_refs": [],
            "validation_gates": ["Candidate is not send-to-fab without explicit user approval."],
            "warnings": ["Generated design candidate workspace could not run."],
        }
    return asdict(
        build_generated_design_candidate_workspace(
            project_id=project_id,
            source_board_design_id=board_design_id,
            component_count=len(components),
            net_count=len(nets),
            artifact_count=len(artifacts),
        )
    )


@app.post("/api/projects/{project_id}/reports/design")
@app.post("/bodesign/api/projects/{project_id}/reports/design")
def produce_design_reconstruction_report(project_id: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    request_payload = payload or {}
    board_design_id = str(request_payload.get("board_design_id") or f"{project_id}-board-design")
    artifact_refs_value = request_payload.get("artifact_refs", [])
    artifact_refs = [str(artifact_ref) for artifact_ref in artifact_refs_value] if isinstance(artifact_refs_value, list) else []
    if produce_design_report is None:
        return {
            "project_id": project_id,
            "board_design_id": board_design_id,
            "report_type": "design-reconstruction-export",
            "title": "bodesign reconstruction/export report placeholder",
            "summary": [],
            "assumptions": [],
            "warnings": ["source-core package import failed"],
            "artifact_refs": artifact_refs,
            "status": "source-core package import failed",
        }

    return asdict(produce_design_report(project_id, board_design_id, artifact_refs))


def _project_id(project_name: str) -> str:
    safe_name = "".join(character.lower() if character.isalnum() else "-" for character in project_name).strip("-")
    return safe_name or "project"


def _list_visible_projects() -> list[dict[str, object]]:
    projects = [_builtin_rockbox_project()]
    projects.extend(project for project_id, project in PROJECTS.items() if project_id != BUILTIN_PROJECT_ID)
    return projects


def _builtin_rockbox_project() -> dict[str, object]:
    artifact_paths = _rockbox_demo_artifact_paths()
    board_design = _rockbox_demo_board_design()
    confidence = board_design.get("confidence_summary", {})
    return {
        "id": BUILTIN_PROJECT_ID,
        "name": "Rockbox reference board",
        "status": "imported-fixture",
        "source": "fixtures/private/rockbox/gerber",
        "artifact_count": len(artifact_paths),
        "board_design_id": board_design.get("id", "rockbox-board-design"),
        "components": int(confidence.get("components", 0)),
        "nets": int(confidence.get("nets", 0)),
        "viewer_url": "/bodesign/projects/rockbox",
    }


def _project_board_design(project_id: str) -> dict[str, object]:
    if project_id == BUILTIN_PROJECT_ID:
        return _rockbox_demo_board_design()
    return {
        "id": f"{project_id}-board-design",
        "components": [],
        "nets": [],
        "layers": [],
        "board_objects": [],
        "evidence_refs": [],
        "confidence_summary": {"overall": 0.0, "status": "empty-project", "components": 0, "nets": 0, "ipc_pads": 0, "ipc_vias": 0},
    }


def _project_artifact_paths(project_id: str) -> list[str]:
    if project_id == BUILTIN_PROJECT_ID:
        return _rockbox_demo_artifact_paths()
    return []


def _project_artifact_records(project_id: str) -> list[dict[str, object]]:
    records = []
    for path_string in _project_artifact_paths(project_id):
        path = Path(path_string)
        detected = detect_input_artifact(str(path)) if detect_input_artifact is not None else None
        artifact_type = detected.artifact_type if detected is not None else "unknown"
        detected_format = detected.detected_format if detected is not None else path.suffix.lower().lstrip(".")
        records.append(
            {
                "id": _artifact_id(path),
                "project_id": project_id,
                "filename": path.name,
                "path": str(path),
                "artifact_type": artifact_type,
                "detected_format": detected_format,
                "size_bytes": path.stat().st_size if path.exists() else 0,
                "viewer_url": f"/bodesign/projects/{project_id}/artifacts/{_artifact_id(path)}",
            }
        )
    return records


def _project_taxonomy_paths(project_id: str) -> list[str]:
    paths = [
        f"eda/{project_id}/{project_id}.kicad_pro",
        f"eda/{project_id}/{project_id}.kicad_sch",
        f"eda/{project_id}/{project_id}.kicad_pcb",
        "docs/datasheets/reference.pdf",
        "libraries/symbols/project.kicad_sym",
        "libraries/footprints/project.pretty/README.md",
        "reports/design-review.md",
        ".bodesign/analysis/kicad-happy/manifest.json",
    ]
    for record in _project_artifact_records(project_id):
        artifact_type = str(record.get("artifact_type") or "unknown")
        filename = str(record.get("filename") or "artifact")
        if artifact_type in {"gerber", "drill", "bom_placement", "ipc356", "routing_report"}:
            paths.append(f"outputs/manufacturing/{filename}")
        elif artifact_type in {"datasheet", "reference_doc"}:
            paths.append(f"docs/{filename}")
        elif artifact_type == "schematic":
            paths.append(f"eda/imported/{filename}")
        else:
            paths.append(f"inputs/{filename}")
    return paths


def _project_geometry(project_id: str) -> dict[str, object]:
    if parse_gerber_file is None or parse_drill_file is None:
        return {"status": "gerber-core unavailable", "gerber": None, "drill": None, "raster_renderer": None, "image_data_uri": ""}
    records = _project_artifact_records(project_id)
    gerber_record = _preferred_artifact(records, "gerber", ["L1_top.art", "L1_TOP.art", "top.art"])
    drill_record = _preferred_artifact(records, "drill", ["ROCKBOX_V2-1-6.drl"])
    gerber_summary = parse_gerber_file(str(gerber_record["path"]), sample_limit=900) if gerber_record is not None else None
    drill_summary = parse_drill_file(str(drill_record["path"]), sample_limit=700) if drill_record is not None else None
    gerber_dict = _compact_gerber_geometry(gerber_record, asdict(gerber_summary)) if gerber_summary is not None and gerber_record is not None else None
    drill_dict = _compact_drill_geometry(drill_record, asdict(drill_summary)) if drill_summary is not None and drill_record is not None else None
    board_design = _project_board_design(project_id)
    fusion_summary = _component_net_fusion_summary(
        board_design.get("components", []) if isinstance(board_design.get("components"), list) else [],
        board_design.get("nets", []) if isinstance(board_design.get("nets"), list) else [],
    )
    raster_renderer = _render_gerber_raster_artifact(project_id, gerber_record) if gerber_record is not None else None
    image_data_uri = _read_rendered_png_data_uri(raster_renderer)
    return {
        "status": "pygerber-raster-preview" if image_data_uri else "raster-render-unavailable" if gerber_record is not None else "no-geometry-artifacts",
        "gerber": gerber_dict,
        "drill": drill_dict,
        "fusion_summary": fusion_summary,
        "raster_renderer": raster_renderer,
        "image_data_uri": image_data_uri,
    }


def _render_gerber_raster_artifact(project_id: str, artifact: dict[str, object] | None) -> dict[str, object] | None:
    if artifact is None or render_gerber_raster_with_pygerber is None:
        return None
    artifact_path = Path(str(artifact["path"]))
    output_dir = REPO_ROOT / ".artifacts" / "viewer" / project_id / str(artifact["id"])
    return asdict(render_gerber_raster_with_pygerber(artifact_path, output_dir))


def _read_rendered_png_data_uri(renderer: dict[str, object] | None) -> str:
    if not renderer or renderer.get("status") != "rendered":
        return ""
    output_path = renderer.get("output_path")
    if not output_path:
        return ""
    path = Path(str(output_path))
    if not path.exists():
        return ""
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _board_raster_visual(image_data_uri: object, renderer: dict[str, object]) -> str:
    if image_data_uri:
        return f'<img class="raster-view" alt="Rendered Gerber layer" src="{escape(str(image_data_uri))}" />'
    status = escape(str(renderer.get("status") or "not-run"))
    warnings = renderer.get("warnings") if isinstance(renderer.get("warnings"), list) else []
    warning_text = escape("; ".join(str(warning) for warning in warnings[:2]) or "pygerber raster output is required for Board View.")
    return f'<div class="render-error"><div><h3>Raster render unavailable</h3><p><code>{status}</code></p><p>{warning_text}</p></div></div>'


def _preferred_artifact(records: list[dict[str, object]], artifact_type: str, preferred_names: list[str]) -> dict[str, object] | None:
    candidates = [record for record in records if record.get("artifact_type") == artifact_type]
    for preferred_name in preferred_names:
        for candidate in candidates:
            if str(candidate.get("filename")) == preferred_name:
                return candidate
    return candidates[0] if candidates else None


def _compact_gerber_geometry(record: dict[str, object], geometry: dict[str, object]) -> dict[str, object]:
    return {
        "artifact_id": record["id"],
        "filename": record["filename"],
        "unit": geometry["unit"],
        "bounds": geometry["bounds"],
        "aperture_count": len(geometry["apertures"]),
        "draw_count": geometry["draw_count"],
        "flash_count": geometry["flash_count"],
        "region_count": geometry["region_count"],
        "polarity_changes": geometry["polarity_changes"],
    }


def _compact_drill_geometry(record: dict[str, object], geometry: dict[str, object]) -> dict[str, object]:
    return {
        "artifact_id": record["id"],
        "filename": record["filename"],
        "unit": geometry["unit"],
        "bounds": geometry["bounds"],
        "tool_count": len(geometry["tools"]),
        "hit_count": geometry["hit_count"],
        "tools": geometry["tools"],
    }


def _board_overlay_components(components: list[dict[str, object]], nets: list[dict[str, object]], limit: int = 90) -> list[dict[str, object]]:
    placed_components = [component for component in components if isinstance(component.get("placement"), dict)]
    if not placed_components:
        return []
    xs = [float(component["placement"].get("x_mil", 0.0)) for component in placed_components]
    ys = [float(component["placement"].get("y_mil", 0.0)) for component in placed_components]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max(max_x - min_x, 1.0)
    height = max(max_y - min_y, 1.0)
    pins_by_refdes = _pins_by_refdes(nets)
    key_components = sorted(placed_components, key=_component_overlay_priority)
    overlay = []
    for component in key_components[:limit]:
        placement = component.get("placement") if isinstance(component.get("placement"), dict) else {}
        x_mil = float(placement.get("x_mil", 0.0))
        y_mil = float(placement.get("y_mil", 0.0))
        refdes = str(component.get("refdes", ""))
        overlay.append(
            {
                "refdes": refdes,
                "part_number": str(component.get("part_number") or placement.get("value") or ""),
                "footprint": str(component.get("footprint") or ""),
                "side": str(placement.get("side") or "unknown"),
                "category": _component_overlay_category(refdes),
                "x_mil": round(x_mil, 3),
                "y_mil": round(y_mil, 3),
                "left_percent": round(((x_mil - min_x) / width) * 100.0, 3),
                "top_percent": round(100.0 - ((y_mil - min_y) / height) * 100.0, 3),
                "pins": pins_by_refdes.get(refdes, [])[:24],
            }
        )
    return overlay


def _pins_by_refdes(nets: list[dict[str, object]]) -> dict[str, list[str]]:
    pins: dict[str, list[str]] = {}
    for net in nets:
        net_name = str(net.get("name", "net"))
        for pad in net.get("connected_pads", []):
            pad_text = str(pad)
            if "." not in pad_text or pad_text.startswith("VIA."):
                continue
            refdes, pin = pad_text.split(".", 1)
            pins.setdefault(refdes, []).append(f"{pin} → {net_name}")
    return {refdes: sorted(values) for refdes, values in pins.items()}


def _component_net_fusion_summary(components: list[dict[str, object]], nets: list[dict[str, object]], sample_limit: int = 80) -> dict[str, object]:
    pins_by_refdes = _pins_by_refdes(nets)
    rows: list[dict[str, object]] = []
    mapped_components = 0
    for component in components:
        refdes = str(component.get("refdes", "")).strip()
        if not refdes:
            continue
        pin_net_entries = pins_by_refdes.get(refdes, [])
        net_names = sorted({entry.split("→", 1)[1].strip() for entry in pin_net_entries if "→" in entry})
        if pin_net_entries:
            mapped_components += 1
        placement = component.get("placement") if isinstance(component.get("placement"), dict) else {}
        rows.append(
            {
                "refdes": refdes,
                "part_number": str(component.get("part_number") or placement.get("value") or ""),
                "pins": len(pin_net_entries),
                "nets": len(net_names),
                "sample_nets": net_names[:6],
            }
        )
    rows.sort(key=lambda item: (-int(item.get("nets", 0)), -int(item.get("pins", 0)), str(item.get("refdes", ""))))
    total_components = len(rows)
    coverage_ratio = round((mapped_components / total_components), 3) if total_components else 0.0
    return {
        "total_components": total_components,
        "mapped_components": mapped_components,
        "coverage_ratio": coverage_ratio,
        "components": rows[:sample_limit],
    }


def _project_cross_probe(project_id: str, probe_id: str) -> dict[str, object]:
    normalized_probe = probe_id.strip()
    board_design = _project_board_design(project_id)
    components = board_design.get("components", []) if isinstance(board_design.get("components"), list) else []
    nets = board_design.get("nets", []) if isinstance(board_design.get("nets"), list) else []
    records = _project_artifact_records(project_id)
    component = _find_component(components, normalized_probe)
    if component is not None:
        return _component_cross_probe(project_id, component, nets, records)
    net = _find_net(nets, normalized_probe)
    if net is not None:
        return _net_cross_probe(project_id, net, components, records)
    artifact = _find_project_artifact(project_id, normalized_probe)
    if artifact is not None:
        return _artifact_cross_probe(project_id, artifact, records)
    return {"project_id": project_id, "probe_id": probe_id, "status": "not-found", "kind": "unknown", "links": []}


def _find_component(components: list[dict[str, object]], refdes: str) -> dict[str, object] | None:
    refdes_upper = refdes.upper()
    for component in components:
        if str(component.get("refdes", "")).upper() == refdes_upper:
            return component
    return None


def _find_net(nets: list[dict[str, object]], net_name: str) -> dict[str, object] | None:
    net_upper = net_name.upper()
    for net in nets:
        if str(net.get("name", "")).upper() == net_upper:
            return net
    return None


def _component_cross_probe(project_id: str, component: dict[str, object], nets: list[dict[str, object]], records: list[dict[str, object]]) -> dict[str, object]:
    refdes = str(component.get("refdes", ""))
    connected = []
    for net in nets:
        pads = [str(pad) for pad in net.get("connected_pads", []) if str(pad).upper().startswith(f"{refdes.upper()}.")]
        if pads:
            connected.append({"net": str(net.get("name", "")), "pads": pads[:24], "pad_count": len(pads)})
    placement = component.get("placement") if isinstance(component.get("placement"), dict) else {}
    return {
        "project_id": project_id,
        "probe_id": refdes,
        "kind": "component",
        "status": "linked",
        "component": {
            "refdes": refdes,
            "part_number": str(component.get("part_number") or placement.get("value") or ""),
            "footprint": str(component.get("footprint") or ""),
            "placement": placement,
        },
        "nets": connected[:40],
        "artifacts": _cross_probe_artifact_links(records),
        "links": [f"/bodesign/api/projects/{project_id}/cross-probe/{escape_url(str(item['net']))}" for item in connected[:24]],
    }


def _net_cross_probe(project_id: str, net: dict[str, object], components: list[dict[str, object]], records: list[dict[str, object]]) -> dict[str, object]:
    component_index = {str(component.get("refdes", "")).upper(): component for component in components}
    connected_components = []
    connected_vias = []
    for pad in net.get("connected_pads", []):
        pad_text = str(pad)
        if pad_text.startswith("VIA."):
            connected_vias.append(pad_text)
            continue
        if "." not in pad_text:
            continue
        refdes, pin = pad_text.split(".", 1)
        component = component_index.get(refdes.upper(), {})
        connected_components.append({"refdes": refdes, "pin": pin, "part_number": str(component.get("part_number", ""))})
    net_name = str(net.get("name", ""))
    return {
        "project_id": project_id,
        "probe_id": net_name,
        "kind": "net",
        "status": "linked",
        "net": {"name": net_name, "pad_count": len(net.get("connected_pads", [])), "via_count": len(connected_vias)},
        "components": connected_components[:80],
        "vias": connected_vias[:80],
        "artifacts": _cross_probe_artifact_links(records),
        "links": [f"/bodesign/api/projects/{project_id}/cross-probe/{escape_url(item['refdes'])}" for item in connected_components[:40]],
    }


def _artifact_cross_probe(project_id: str, artifact: dict[str, object], records: list[dict[str, object]]) -> dict[str, object]:
    related_types = {
        "gerber": ["drill", "ipc356", "bom_placement"],
        "drill": ["gerber", "ipc356"],
        "ipc356": ["bom_placement", "gerber", "drill"],
        "bom_placement": ["ipc356", "gerber"],
    }.get(str(artifact.get("artifact_type")), [])
    related = [record for record in records if record.get("artifact_type") in related_types]
    return {
        "project_id": project_id,
        "probe_id": str(artifact.get("id", "")),
        "kind": "artifact",
        "status": "linked",
        "artifact": artifact,
        "related_artifacts": related[:40],
        "links": [str(record.get("viewer_url", "")) for record in related[:40]],
    }


def _cross_probe_artifact_links(records: list[dict[str, object]]) -> list[dict[str, object]]:
    evidence_types = {"bom_placement", "ipc356", "gerber", "drill"}
    return [
        {"id": str(record.get("id", "")), "filename": str(record.get("filename", "")), "type": str(record.get("artifact_type", "")), "viewer_url": str(record.get("viewer_url", ""))}
        for record in records
        if record.get("artifact_type") in evidence_types
    ][:80]


def escape_url(value: str) -> str:
    return value.replace("/", "%2F").replace("#", "%23").replace(" ", "%20")


def _kicad_source_markup(foundation: dict[str, object]) -> str:
    sources = foundation.get("kicad_sources") if isinstance(foundation.get("kicad_sources"), dict) else {}
    cards = []
    for source_type, label in [("project", ".kicad_pro"), ("schematic", ".kicad_sch"), ("pcb", ".kicad_pcb")]:
        paths = sources.get(source_type) if isinstance(sources.get(source_type), list) else []
        items = "".join(f"<li><code>{escape(str(path))}</code></li>" for path in paths[:8]) or '<li class="muted">Not detected yet.</li>'
        cards.append(f'<div class="card"><h3>{escape(label)}</h3><ul>{items}</ul></div>')
    return "".join(cards)


def _kicad_taxonomy_markup(foundation: dict[str, object]) -> str:
    roles = foundation.get("taxonomy_roles") if isinstance(foundation.get("taxonomy_roles"), dict) else {}
    cards = []
    for role in ["docs", "inputs", "eda", "libraries", "outputs", "reports"]:
        paths = roles.get(role) if isinstance(roles.get(role), list) else []
        items = "".join(f"<li><code>{escape(str(path))}</code></li>" for path in paths[:8]) or '<li class="muted">No paths classified yet.</li>'
        cards.append(f'<div class="card"><h3>{escape(role)}</h3><ul>{items}</ul></div>')
    return "".join(cards)


def _project_tree_markup(project_tree: dict[str, object]) -> str:
    nodes = project_tree.get("folder_nodes") if isinstance(project_tree.get("folder_nodes"), list) else []
    rows = "".join(
        "<tr>"
        f"<td><code>{escape(str(node.get('role', 'unknown')))}</code></td>"
        f"<td><code>{escape(str(node.get('path', '')))}</code></td>"
        f"<td>{escape(str(node.get('kind', '')))}</td>"
        f"<td>{escape(str(node.get('visibility', '')))}</td>"
        f"<td>{escape(str(node.get('source_count', 0)))}</td>"
        f"<td>{escape(', '.join(str(path) for path in node.get('sample_paths', [])[:4]))}</td>"
        "</tr>"
        for node in nodes
        if isinstance(node, dict)
    )
    if not rows:
        rows = '<tr><td colspan="6">No client-owned folder tree is available.</td></tr>'
    hidden = project_tree.get("hidden_workspace") if isinstance(project_tree.get("hidden_workspace"), dict) else {}
    blockers = project_tree.get("blockers") if isinstance(project_tree.get("blockers"), list) else []
    blocker_items = "".join(f"<li>{escape(str(blocker))}</li>" for blocker in blockers)
    return (
        '<div class="grid">'
        f'<div class="card"><h3>Browse mode</h3><p><code>{escape(str(project_tree.get("access_mode", "unknown")))}</code></p><p>durable owner: <code>{escape(str(project_tree.get("durable_owner", "client")))}</code></p><p class="muted">Read-only project tree derived from the storage-share manifest. No mutation capability is exposed.</p></div>'
        f'<div class="card"><h3>Hidden evidence workspace</h3><p><code>{escape(str(hidden.get("path", ".bodesign")))}</code></p><p>sources: <b>{escape(str(hidden.get("source_count", 0)))}</b></p><p>{escape(str(hidden.get("cache_policy", "mcp-cache-disposable-not-authoritative")))}</p></div>'
        '</div>'
        f'<div class="scroll"><table><thead><tr><th>Role</th><th>Path</th><th>Kind</th><th>Visibility</th><th>Sources</th><th>Samples</th></tr></thead><tbody>{rows}</tbody></table></div>'
        f'<div class="card"><h3>Folder browse blockers</h3><ul>{blocker_items}</ul></div>'
    )


def _kicad_analysis_markup(foundation: dict[str, object]) -> str:
    cache = foundation.get("kicad_happy_cache") if isinstance(foundation.get("kicad_happy_cache"), dict) else {}
    artifacts = cache.get("artifact_paths") if isinstance(cache.get("artifact_paths"), list) else []
    rows = "".join(
        f"<tr><td>{escape(str(artifact.get('category', '')))}</td><td><code>{escape(str(artifact.get('path', '')))}</code></td><td>{escape(str(artifact.get('visibility', '')))}</td></tr>"
        for artifact in artifacts[:24]
        if isinstance(artifact, dict)
    )
    if not rows:
        rows = '<tr><td colspan="3">No KiCad Happy cache mapping is available.</td></tr>'
    return (
        '<div class="grid">'
        f'<div class="card"><h3>Cache mode</h3><p><code>{escape(str(cache.get("mode", "unknown")))}</code></p><p>root: <code>{escape(str(cache.get("analysis_root", "unknown")))}</code></p><p>track_in_git: <code>{escape(str(cache.get("track_in_git", "unknown")))}</code></p></div>'
        f'<div class="card"><h3>Compatibility config</h3><p><code>{escape(str(cache.get("config_path", ".kicad-happy.json")))}</code></p><p class="muted">Compatibility config is recognized but MCP analyzer output stays hidden by default.</p></div>'
        '</div>'
        f'<div class="scroll"><table><thead><tr><th>Category</th><th>Path</th><th>Visibility</th></tr></thead><tbody>{rows}</tbody></table></div>'
    )


def _kicad_output_markup(foundation: dict[str, object]) -> str:
    artifacts = foundation.get("output_artifacts") if isinstance(foundation.get("output_artifacts"), list) else []
    rows = "".join(
        f"<tr><td>{escape(str(artifact.get('artifact_type', '')))}</td><td><code>{escape(str(artifact.get('path', '')))}</code></td><td>{escape(str(artifact.get('visibility', '')))}</td></tr>"
        for artifact in artifacts[:40]
        if isinstance(artifact, dict)
    )
    if not rows:
        rows = '<tr><td colspan="3">No manufacturing outputs detected in the human-facing outputs folder.</td></tr>'
    return f'<div class="scroll"><table><thead><tr><th>Type</th><th>Path</th><th>Visibility</th></tr></thead><tbody>{rows}</tbody></table></div>'


def _kicad_blocker_markup(foundation: dict[str, object]) -> str:
    blockers = foundation.get("blockers") if isinstance(foundation.get("blockers"), list) else []
    return "".join(f"<li>{escape(str(blocker))}</li>" for blocker in blockers) or '<li class="muted">No foundation blockers recorded.</li>'


def _kicad_native_extension_markup(extension: dict[str, object]) -> str:
    capabilities = extension.get("capabilities") if isinstance(extension.get("capabilities"), list) else []
    blocked = extension.get("blocked_browser_features") if isinstance(extension.get("blocked_browser_features"), list) else []
    capability_items = "".join(
        f"<li><strong>{escape(str(item.get('capability_id', 'capability')))}</strong> — {escape(str(item.get('owner', 'unknown')))} via {escape(str(item.get('trigger_surface', 'unknown')))}</li>"
        for item in capabilities[:8]
        if isinstance(item, dict)
    ) or '<li class="muted">No native extension capabilities defined yet.</li>'
    blocked_items = "".join(f"<li>{escape(str(item))}</li>" for item in blocked[:8]) or '<li class="muted">No browser feature blockers defined.</li>'
    return (
        '<div class="grid">'
        f'<div class="card"><h3>Integration model</h3><p><code>{escape(str(extension.get("integration_model", "unknown")))}</code></p><p>{escape(str(extension.get("native_editor_owner", "Native KiCad owns editing.")))}</p></div>'
        f'<div class="card"><h3>bodesign role</h3><p>{escape(str(extension.get("bodesign_role", "Companion dashboard.")))}</p><p><code>{escape(str(extension.get("sidecar_boundary", "unknown")))}</code></p></div>'
        '</div>'
        f'<div class="grid"><div class="card"><h3>Native extension capabilities</h3><ul>{capability_items}</ul></div><div class="card"><h3>Blocked browser features</h3><ul>{blocked_items}</ul></div></div>'
    )


def _component_fusion_row(component: dict[str, object]) -> str:
    sample_nets = component.get("sample_nets") if isinstance(component.get("sample_nets"), list) else []
    sample = ", ".join(str(net) for net in sample_nets[:6])
    return (
        "<tr>"
        f"<td><code>{escape(str(component.get('refdes', '')))}</code></td>"
        f"<td>{escape(str(component.get('part_number', '')))}</td>"
        f"<td>{escape(str(component.get('pins', 0)))}</td>"
        f"<td>{escape(str(component.get('nets', 0)))}</td>"
        f"<td>{escape(sample)}</td>"
        "</tr>"
    )


def _component_overlay_marker(component: dict[str, object]) -> str:
    refdes = escape(str(component.get("refdes", "")))
    side = escape(str(component.get("side", "unknown")))
    category = escape(str(component.get("category", "other")))
    left = float(component.get("left_percent", 0.0))
    top = float(component.get("top_percent", 0.0))
    title = escape(f"{component.get('refdes', '')} {component.get('part_number', '')}".strip())
    return f'<button class="component-marker" type="button" data-refdes="{refdes}" data-side="{side}" data-category="{category}" title="{title}" style="left:{left:.3f}%;top:{top:.3f}%">{refdes}</button>'


def _component_overlay_category(refdes: str) -> str:
    upper = refdes.upper()
    if upper.startswith(("U", "J", "ANT", "Y", "SW", "BT")):
        return "major"
    if upper.startswith(("D", "Q")):
        return "active"
    if upper.startswith("TP"):
        return "testpoint"
    if upper.startswith(("R", "C", "L", "FB")):
        return "passive"
    return "other"


def _component_overlay_priority(component: dict[str, object]) -> tuple[int, str]:
    refdes = str(component.get("refdes", ""))
    category_order = {"major": 0, "active": 1, "other": 2, "passive": 3, "testpoint": 4}
    return (category_order.get(_component_overlay_category(refdes), 9), refdes)


def _js_string_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'").replace("</", "<\\/")


def _artifact_id(path: Path) -> str:
    safe_name = "".join(character.lower() if character.isalnum() else "-" for character in path.name).strip("-")
    return safe_name or "artifact"


def _find_project_artifact(project_id: str, artifact_id: str) -> dict[str, object] | None:
    for artifact in _project_artifact_records(project_id):
        if artifact["id"] == artifact_id:
            return artifact
    return None


def _artifact_row(project_id: str, artifact: dict[str, object]) -> str:
    probe_url = f"/bodesign/api/projects/{escape(project_id)}/cross-probe/{escape_url(str(artifact['id']))}"
    return (
        "<tr>"
        f"<td><code>{escape(str(artifact['filename']))}</code></td>"
        f"<td>{escape(str(artifact['artifact_type']))}</td>"
        f"<td>{escape(str(artifact['detected_format']))}</td>"
        f"<td>{escape(str(artifact['size_bytes']))}</td>"
        f"<td><a class=\"button secondary\" href=\"/bodesign/projects/{escape(project_id)}/artifacts/{escape(str(artifact['id']))}\">Open</a> <a class=\"button secondary\" href=\"{probe_url}\">Probe</a></td>"
        "</tr>"
    )


def _gerber_summary_text(path: Path, geometry: dict[str, object]) -> str:
    bounds = geometry.get("bounds", {}) if isinstance(geometry.get("bounds"), dict) else {}
    return "\n".join(
        [
            f"Gerber geometry summary: {path.name}",
            f"unit: {geometry.get('unit')}",
            f"apertures: {len(geometry.get('apertures', []))}",
            f"draw segments: {geometry.get('draw_count')}",
            f"flashes: {geometry.get('flash_count')}",
            f"regions: {geometry.get('region_count')}",
            f"polarity changes: {geometry.get('polarity_changes')}",
            f"bounds: ({bounds.get('min_x')}, {bounds.get('min_y')}) → ({bounds.get('max_x')}, {bounds.get('max_y')})",
        ]
    )


def _drill_summary_text(path: Path, geometry: dict[str, object]) -> str:
    bounds = geometry.get("bounds", {}) if isinstance(geometry.get("bounds"), dict) else {}
    tools = geometry.get("tools", [])
    tool_lines = [f"T{tool.get('index')}: {tool.get('size_mil')} mil {tool.get('plating')} hits={tool.get('hit_count')} qty_hint={tool.get('quantity_hint')}" for tool in tools]
    return "\n".join(
        [
            f"Drill geometry summary: {path.name}",
            f"unit: {geometry.get('unit')}",
            f"hits: {geometry.get('hit_count')}",
            f"tools: {len(tools)}",
            f"bounds: ({bounds.get('min_x')}, {bounds.get('min_y')}) → ({bounds.get('max_x')}, {bounds.get('max_y')})",
            "",
            *tool_lines,
        ]
    )


def _artifact_preview(path: Path, artifact_type: str) -> dict[str, object]:
    if not path.exists():
        return {"kind": "missing", "text": "Artifact file is missing."}
    if artifact_type == "gerber" and parse_gerber_file is not None:
        geometry = parse_gerber_file(path, sample_limit=120)
        renderer = asdict(render_gerber_raster_with_pygerber(path, REPO_ROOT / ".artifacts" / "viewer" / "artifacts" / _artifact_id(path))) if render_gerber_raster_with_pygerber is not None else None
        image_data_uri = _read_rendered_png_data_uri(renderer)
        return {
            "kind": "gerber-raster" if image_data_uri else "gerber-geometry",
            "text": _gerber_summary_text(path, asdict(geometry)),
            "geometry": asdict(geometry),
            "renderer": renderer,
            "image_data_uri": image_data_uri,
        }
    if artifact_type == "drill" and parse_drill_file is not None:
        geometry = parse_drill_file(path, sample_limit=180)
        return {
            "kind": "drill-geometry",
            "text": _drill_summary_text(path, asdict(geometry)),
            "geometry": asdict(geometry),
        }
    if artifact_type in {"bom_placement", "ipc356", "routing_report", "gerber", "drill", "unknown"}:
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[:80]
        except OSError as error:
            return {"kind": "error", "text": str(error)}
        return {"kind": "text", "line_count_previewed": len(lines), "text": "\n".join(lines)}
    if artifact_type in {"datasheet", "schematic", "reference_doc"}:
        return {"kind": "document", "text": "Document preview is pending; file is registered for extraction."}
    return {"kind": "metadata", "text": "No preview adapter is available for this artifact type yet."}


def _render_artifact_viewer(project_id: str, artifact: dict[str, object]) -> str:
    preview = _artifact_preview(Path(str(artifact["path"])), str(artifact["artifact_type"]))
    preview_text = escape(str(preview.get("text", "")))
    preview_image = preview.get("image_data_uri", "")
    visual_preview = f'<img class="raster-view" alt="Rendered Gerber artifact" src="{escape(str(preview_image))}" />' if preview_image else ""
    return """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>bodesign artifact</title>
        <style>
          body { margin: 0; padding: 28px; font-family: ui-sans-serif, system-ui, sans-serif; background: #0b0f12; color: #e8f0f2; }
          a { color: #5de4c7; } code { color: #8ef6d2; }
          .meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; margin: 18px 0; }
          .card { border: 1px solid #293943; border-radius: 14px; padding: 14px; background: #111a20; }
          .geometry { border: 1px solid #293943; border-radius: 14px; padding: 12px; background: #07100d; overflow: auto; min-height: 120px; }
          .raster-view { max-width: 100%; max-height: 70vh; object-fit: contain; display: block; margin: 0 auto; }
          pre { white-space: pre-wrap; border: 1px solid #293943; border-radius: 14px; padding: 16px; background: #111a20; overflow: auto; }
        </style>
      </head>
      <body>
        <p><a href="/bodesign/projects/""" + escape(project_id) + """">← Back to project</a></p>
        <h1>""" + escape(str(artifact["filename"])) + """</h1>
        <div class="meta">
          <div class="card"><strong>type</strong><br><code>""" + escape(str(artifact["artifact_type"])) + """</code></div>
          <div class="card"><strong>format</strong><br><code>""" + escape(str(artifact["detected_format"])) + """</code></div>
          <div class="card"><strong>size</strong><br><code>""" + escape(str(artifact["size_bytes"])) + """ bytes</code></div>
          <div class="card"><strong>preview</strong><br><code>""" + escape(str(preview.get("kind", "unknown"))) + """</code></div>
        </div>
        <div class="geometry">""" + visual_preview + """</div>
        <h2>Preview</h2>
        <pre>""" + preview_text + """</pre>
      </body>
    </html>
    """


def _render_not_found(message: str) -> str:
    return f"""
    <!doctype html>
    <html lang="en"><head><meta charset="utf-8"><title>bodesign not found</title></head>
    <body style="font-family: sans-serif; background: #0b0f12; color: #e8f0f2; padding: 32px;">
      <p><a style="color: #5de4c7" href="/bodesign/">← Back to bodesign</a></p>
      <h1>{escape(message)}</h1>
    </body></html>
    """


def _project_card(project: dict[str, object]) -> str:
    name = escape(str(project.get("name", "Untitled project")))
    status = escape(str(project.get("status", "unknown")))
    project_id = escape(str(project.get("id", "")))
    artifact_count = escape(str(project.get("artifact_count", 0)))
    components = escape(str(project.get("components", "—")))
    nets = escape(str(project.get("nets", "—")))
    source = escape(str(project.get("source", "manual project")))
    viewer_url = escape(str(project.get("viewer_url", "/bodesign/")))
    return f"""
      <div class="card project-card">
        <h3>{name} <span class="pill">{status}</span></h3>
        <div class="metric"><span>project id</span><code>{project_id}</code></div>
        <div class="metric"><span>artifacts</span><code>{artifact_count}</code></div>
        <div class="metric"><span>components</span><code>{components}</code></div>
        <div class="metric"><span>nets</span><code>{nets}</code></div>
        <p class="muted">{source}</p>
        <p><a class="button" href="{viewer_url}">Open / browse</a></p>
      </div>
    """


def _rockbox_demo_board_design() -> dict[str, object]:
    artifact_paths = _rockbox_demo_artifact_paths()
    if reconstruct_rockbox_placeholder is None:
        return {
            "id": "rockbox-board-design",
            "confidence_summary": {
                "overall": 0.0,
                "status": "reverse-core package import failed",
                "component_files": 0.0,
                "gerber_files": 0.0,
                "drill_files": 0.0,
                "ipc_files": 0.0,
            },
        }
    return asdict(reconstruct_rockbox_placeholder("rockbox", artifact_paths))


def _rockbox_demo_artifact_paths() -> list[str]:
    fixture_dir = REPO_ROOT / "fixtures" / "private" / "rockbox" / "gerber"
    if not fixture_dir.exists():
        return []
    return [str(path) for path in fixture_dir.iterdir()]


def _group_artifacts(artifact_paths: list[str]) -> dict[str, list[Path]]:
    groups = {
        "datasheet": [],
        "schematic": [],
        "bom_placement": [],
        "gerber": [],
        "drill": [],
        "ipc356": [],
        "routing_report": [],
        "reference_doc": [],
        "unknown": [],
    }
    for artifact_path in sorted(artifact_paths):
        path = Path(artifact_path)
        artifact_type = detect_input_artifact(str(path)).artifact_type if detect_input_artifact is not None else path.suffix.lower().lstrip(".")
        if artifact_type not in groups:
            artifact_type = "unknown"
        groups[artifact_type].append(path)
    return groups


def _artifact_group_markup(artifact_groups: dict[str, list[Path]]) -> str:
    labels = {
        "datasheet": "Datasheets",
        "schematic": "Schematics",
        "bom_placement": "BOM / placement",
        "gerber": "Gerber artwork",
        "drill": "Drill files",
        "ipc356": "IPC-356 nets",
        "routing_report": "Routing reports",
        "reference_doc": "Reference docs",
        "unknown": "Unknown / pending",
    }
    cards = []
    for artifact_type, label in labels.items():
        files = artifact_groups.get(artifact_type, [])
        file_items = "".join(f"<li><code>{escape(path.name)}</code></li>" for path in files[:18])
        if len(files) > 18:
            file_items += f"<li class=\"muted\">+ {len(files) - 18} more</li>"
        if not file_items:
            file_items = '<li class="muted">No files detected yet.</li>'
        cards.append(f'<div class="card"><h3>{escape(label)} <span class="pill">{len(files)}</span></h3><ul>{file_items}</ul></div>')
    return "".join(cards)


def _layer_row(layer: dict[str, object]) -> str:
    name = escape(str(layer.get("name", "layer")))
    source_artifact_id = escape(str(layer.get("source_artifact_id", "unknown")))
    return f"<tr><td><code>{name}</code></td><td>{source_artifact_id}</td><td><span class=\"pill\">geometry parser available</span></td></tr>"


def _component_row(project_id: str, component: dict[str, object]) -> str:
    placement = component.get("placement") if isinstance(component.get("placement"), dict) else {}
    x_mil = placement.get("x_mil", "")
    y_mil = placement.get("y_mil", "")
    refdes = str(component.get("refdes", ""))
    probe_url = f"/bodesign/api/projects/{escape(project_id)}/cross-probe/{escape_url(refdes)}"
    return (
        "<tr>"
        f"<td><a href=\"{probe_url}\"><code>{escape(refdes)}</code></a></td>"
        f"<td>{escape(str(component.get('part_number') or placement.get('value') or ''))}</td>"
        f"<td>{escape(str(component.get('footprint') or ''))}</td>"
        f"<td>{escape(str(placement.get('side', '')))}</td>"
        f"<td>{escape(str(x_mil))}, {escape(str(y_mil))}</td>"
        "</tr>"
    )


def _candidate_workspace_markup(candidate_workspace: dict[str, object]) -> str:
    diff_items = candidate_workspace.get("diff_summary") if isinstance(candidate_workspace.get("diff_summary"), list) else []
    diff_rows = "".join(
        "<tr>"
        f"<td>{escape(str(item.get('area', 'unknown')))}</td>"
        f"<td><span class=\"pill\">{escape(str(item.get('status', 'unknown')))}</span></td>"
        f"<td>{escape(str(item.get('summary', '')))}</td>"
        f"<td>{escape(', '.join(str(ref) for ref in item.get('evidence_refs', [])))}</td>"
        "</tr>"
        for item in diff_items
        if isinstance(item, dict)
    )
    if not diff_rows:
        diff_rows = '<tr><td colspan="4">No candidate diff rows are available yet.</td></tr>'
    gates = candidate_workspace.get("validation_gates") if isinstance(candidate_workspace.get("validation_gates"), list) else []
    gate_items = "".join(f"<li>{escape(str(gate))}</li>" for gate in gates)
    warnings = candidate_workspace.get("warnings") if isinstance(candidate_workspace.get("warnings"), list) else []
    warning_items = "".join(f"<li>{escape(str(warning))}</li>" for warning in warnings)
    return f"""
      <div class="grid">
        <div class="card"><h3>Candidate</h3><p><code>{escape(str(candidate_workspace.get('candidate_id', 'unknown-candidate')))}</code></p><p>status: <b>{escape(str(candidate_workspace.get('status', 'unknown')))}</b></p></div>
        <div class="card"><h3>Source IR</h3><p><code>{escape(str(candidate_workspace.get('source_board_design_id', 'unknown-ir')))}</code></p></div>
        <div class="card"><h3>Approval</h3><p><code>{escape(str(candidate_workspace.get('approval_state', 'not-approved')))}</code></p><p class="muted">No generated layout is usable until this changes through an explicit approval workflow.</p></div>
      </div>
      <h3>Diff / evidence summary</h3>
      <div class="scroll"><table><thead><tr><th>Area</th><th>Status</th><th>Summary</th><th>Evidence</th></tr></thead><tbody>{diff_rows}</tbody></table></div>
      <div class="grid">
        <div class="card"><h3>Validation gates</h3><ul>{gate_items}</ul></div>
        <div class="card"><h3>Warnings</h3><ul>{warning_items}</ul></div>
      </div>
    """


def _compact_board_design(board_design: dict[str, object]) -> dict[str, object]:
    compact = dict(board_design)
    compact["components"] = board_design.get("components", [])[:12]
    compact["nets"] = board_design.get("nets", [])[:12]
    compact["note"] = "Preview is truncated for the web workspace; use the API for the full IR."
    return compact


def _highlight_components(components: list[dict[str, object]]) -> list[dict[str, object]]:
    priority_refdes = {"U401", "U402", "U301", "U801", "J301", "ANT501", "J302", "J402"}
    highlighted = [component for component in components if str(component.get("refdes")) in priority_refdes]
    return highlighted[:8] or components[:8]


def _component_markup(component: dict[str, object]) -> str:
    placement = component.get("placement") if isinstance(component.get("placement"), dict) else {}
    x_mil = float(placement.get("x_mil", 0.0))
    y_mil = float(placement.get("y_mil", 0.0))
    left_percent = max(4.0, min(84.0, (x_mil / 2600.0) * 100.0))
    top_percent = max(6.0, min(82.0, 92.0 - (y_mil / 2000.0) * 100.0))
    label = escape(f"{component.get('refdes', '')} {component.get('part_number') or component.get('footprint') or ''}".strip())
    return f'<div class="chip" style="left: {left_percent:.1f}%; top: {top_percent:.1f}%; width: 98px; height: 48px;">{label}</div>'
