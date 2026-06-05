from dataclasses import asdict
from html import escape
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
    REPO_ROOT / "packages" / "reverse-core",
    REPO_ROOT / "packages" / "source-core",
    REPO_ROOT / "packages" / "gerber-core",
]

for package_root in PACKAGE_ROOTS:
    package_path = str(package_root)
    if package_path not in sys.path:
        sys.path.append(package_path)

try:
    from bodesign_component_kb import ingest_datasheet_knowledge, reuse_component_knowledge
    from bodesign_doc_core import plan_openmv_document_ingestion
    from bodesign_gerber_core import parse_drill_file, parse_gerber_file, render_geometry_svg, validate_gerber_export_placeholder
    from bodesign_shared import JobSummary, ProjectSummary, detect_input_artifact
    from bodesign_reverse_core import build_rockbox_input_manifest, reconstruct_rockbox_placeholder
    from bodesign_source_core import plan_gerber_export, produce_design_report
except ImportError:
    ingest_datasheet_knowledge = None
    reuse_component_knowledge = None
    plan_openmv_document_ingestion = None
    parse_drill_file = None
    parse_gerber_file = None
    render_geometry_svg = None
    validate_gerber_export_placeholder = None
    JobSummary = None
    ProjectSummary = None
    detect_input_artifact = None
    build_rockbox_input_manifest = None
    reconstruct_rockbox_placeholder = None
    plan_gerber_export = None
    produce_design_report = None

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
    {"method": "POST", "path": "/bodesign/api/artifacts/detect", "purpose": "Detect artifact types before ingestion."},
    {"method": "GET", "path": "/bodesign/api/projects/{project_id}/board-design", "purpose": "Return a BoardDesign IR summary."},
    {"method": "POST", "path": "/bodesign/api/projects/{project_id}/rockbox/reconstruct", "purpose": "Reconstruct Rockbox into BoardDesign IR summary."},
    {"method": "POST", "path": "/bodesign/api/projects/{project_id}/knowledge/datasheets", "purpose": "Ingest datasheet knowledge."},
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
    board_svg = geometry.get("svg", "")
    gerber_geometry = geometry.get("gerber") or {}
    drill_geometry = geometry.get("drill") or {}
    layer_markup = "".join(_layer_row(layer) for layer in layers) or '<p class="muted">No copper layers parsed.</p>'
    document_markup = _artifact_group_markup(artifact_groups)
    artifact_table = "".join(_artifact_row(project_id, artifact) for artifact in _project_artifact_records(project_id))
    if not artifact_table:
        artifact_table = '<tr><td colspan="5">No artifacts are attached to this project yet.</td></tr>'
    component_table = "".join(_component_row(component) for component in components[:80])
    if not component_table:
        component_table = '<tr><td colspan="5">No placement/BOM components parsed.</td></tr>'
    net_markup = "".join(
        f'<tr><td><code>{escape(str(net.get("name", "net")))}</code></td><td>{len(net.get("connected_pads", []))}</td><td>{escape(", ".join(str(pad) for pad in net.get("connected_pads", [])[:8]))}</td></tr>'
        for net in nets[:80]
    )
    if not net_markup:
        net_markup = '<tr><td colspan="3">No IPC nets parsed yet.</td></tr>'
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
          .shell { display: grid; grid-template-columns: 300px 1fr; min-height: 100vh; }
          .sidebar { padding: 24px; border-right: 1px solid var(--line); background: #0f171c; }
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
          .tabs { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; position: sticky; top: 0; z-index: 1; padding: 8px 0 14px; background: linear-gradient(#0b0f12 76%, #0b0f1200); }
          .tabs input { display: none; }
          .tabs label { cursor: pointer; padding: 9px 12px; border: 1px solid var(--line); border-radius: 12px; color: var(--muted); background: var(--panel); }
          #tab-projects:checked ~ label[for="tab-projects"], #tab-documents:checked ~ label[for="tab-documents"], #tab-board:checked ~ label[for="tab-board"], #tab-gerber:checked ~ label[for="tab-gerber"], #tab-ipc:checked ~ label[for="tab-ipc"], #tab-components:checked ~ label[for="tab-components"], #tab-ir:checked ~ label[for="tab-ir"], #tab-report:checked ~ label[for="tab-report"] { color: #07100d; background: var(--accent); border-color: var(--accent); }
          .panel { display: none; border: 1px solid var(--line); border-radius: 18px; background: var(--panel); padding: 20px; min-height: calc(100vh - 96px); }
          #tab-projects:checked ~ .panels #projects, #tab-documents:checked ~ .panels #documents, #tab-board:checked ~ .panels #board, #tab-gerber:checked ~ .panels #gerber, #tab-ipc:checked ~ .panels #ipc, #tab-components:checked ~ .panels #components, #tab-ir:checked ~ .panels #ir, #tab-report:checked ~ .panels #report { display: block; }
          .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
          .card { border: 1px solid var(--line); border-radius: 16px; padding: 16px; background: var(--panel2); }
          .project-card { border-color: #3e635b; }
          .geometry-viewer { min-height: 520px; border: 1px solid #3b5560; border-radius: 16px; background: #07100d; overflow: auto; padding: 12px; }
          .geometry-viewer svg { width: 100%; min-width: 760px; height: auto; display: block; }
          table { border-collapse: collapse; width: 100%; }
          th, td { border-bottom: 1px solid var(--line); padding: 9px 8px; text-align: left; vertical-align: top; }
          th { color: #bcd0d7; font-weight: 650; }
          .scroll { max-height: 540px; overflow: auto; }
          pre { margin: 0; white-space: pre-wrap; color: #d6e3e7; }
          code { color: #8ef6d2; }
        </style>
      </head>
      <body>
        <main class="shell">
          <aside class="sidebar">
            <h1>bodesign</h1>
            <p class="muted">Project workspace from uploaded or fixture-backed hardware evidence. This is a file-centric viewer, not a fake completed schematic.</p>
            <h2>Project</h2>
            <div class="metric"><span>project</span><code>""" + escape(project_id) + """</code></div>
            <div class="metric"><span>IR</span><code>""" + escape(str(board_design["id"])) + """</code></div>
            <div class="metric"><span>status</span><code>""" + escape(str(confidence["status"])) + """</code></div>
            <div class="metric"><span>confidence</span><code>""" + escape(str(confidence["overall"])) + """</code></div>
            <p><a class="button" href="#projects">Open projects</a></p>
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
              <input checked id="tab-projects" name="workspace-tab" type="radio" />
              <input id="tab-documents" name="workspace-tab" type="radio" />
              <input id="tab-board" name="workspace-tab" type="radio" />
              <input id="tab-gerber" name="workspace-tab" type="radio" />
              <input id="tab-ipc" name="workspace-tab" type="radio" />
              <input id="tab-components" name="workspace-tab" type="radio" />
              <input id="tab-ir" name="workspace-tab" type="radio" />
              <input id="tab-report" name="workspace-tab" type="radio" />
              <label for="tab-projects">Projects</label>
              <label for="tab-documents">Documents</label>
              <label for="tab-board">Board View</label>
              <label for="tab-gerber">Gerber Layers</label>
              <label for="tab-ipc">IPC / Nets</label>
              <label for="tab-components">Components</label>
              <label for="tab-ir">BoardDesign IR</label>
              <label for="tab-report">Report</label>
              <div class="panels">
                <article class="panel" id="projects">
                  <h2>Projects</h2>
                  <p class="muted">Open or import board projects. Rockbox is preloaded from the private fixture as an already-uploaded project so it can be browsed immediately.</p>
                  <div class="grid">""" + project_markup + """
                    <div class="card">
                      <h3>Import new project</h3>
                      <p class="muted">Drop/upload is not wired yet. MCP/agent import should call <code>/bodesign/api/artifacts/detect</code> and then attach files to a project.</p>
                      <p><a class="button secondary" href="/bodesign/routes">View available API routes</a></p>
                    </div>
                  </div>
                </article>
                <article class="panel" id="documents">
                  <h2>Source Documents</h2>
                  <p class="muted">This tab is the file-centric entry point. It separates Gerber, drill, IPC, BOM/placement, routing reports and unknown files before any circuit claim is made.</p>
                  <div class="scroll"><table><thead><tr><th>File</th><th>Type</th><th>Format</th><th>Size</th><th>Open</th></tr></thead><tbody>""" + artifact_table + """</tbody></table></div>
                  <h3>Grouped by type</h3>
                  <div class="grid">""" + document_markup + """</div>
                </article>
                 <article class="panel" id="board">
                  <h2>Board View</h2>
                  <p class="muted">Evidence-based geometry preview from parsed RS-274X Gerber draw/flash operations and Excellon drill hits. This is still a parser spike, not a full EDA editor.</p>
                  <div class="grid">
                    <div class="card"><h3>Gerber source</h3><p><code>""" + escape(str(gerber_geometry.get("filename", "none"))) + """</code></p><p>draws: <b>""" + escape(str(gerber_geometry.get("draw_count", 0))) + """</b> · flashes: <b>""" + escape(str(gerber_geometry.get("flash_count", 0))) + """</b></p></div>
                    <div class="card"><h3>Drill source</h3><p><code>""" + escape(str(drill_geometry.get("filename", "none"))) + """</code></p><p>hits: <b>""" + escape(str(drill_geometry.get("hit_count", 0))) + """</b> · tools: <b>""" + escape(str(drill_geometry.get("tool_count", 0))) + """</b></p></div>
                  </div>
                  <div class="geometry-viewer">
                    """ + board_svg + """
                  </div>
                </article>
                <article class="panel" id="gerber">
                  <h2>Gerber Layers</h2>
                  <p class="muted">Layer files are visible here first. The Board View currently renders a sample copper layer plus drill hits.</p>
                  <table><thead><tr><th>Layer</th><th>Source file</th><th>Status</th></tr></thead><tbody>""" + layer_markup + """</tbody></table>
                </article>
                <article class="panel" id="ipc">
                  <h2>IPC-356 Nets</h2>
                  <p class="muted">Connectivity evidence parsed from IPC records. This is the closest current view to circuit topology.</p>
                  <div class="scroll"><table><thead><tr><th>Net</th><th>Connected pads</th><th>Sample pads</th></tr></thead><tbody>""" + net_markup + """</tbody></table></div>
                </article>
                <article class="panel" id="components">
                  <h2>Components</h2>
                  <p class="muted">Placement/BOM-derived component table. Datasheet enrichment will attach pinout and design knowledge here.</p>
                  <div class="scroll"><table><thead><tr><th>Refdes</th><th>Part/value</th><th>Footprint</th><th>Side</th><th>XY mil</th></tr></thead><tbody>""" + component_table + """</tbody></table></div>
                </article>
                <article class="panel" id="ir">
                  <h2>BoardDesign IR</h2>
                  <p class="muted">Compact JSON preview of the normalized source-of-truth model.</p>
                  <pre>""" + ir_json + """</pre>
                </article>
                <article class="panel" id="report">
                  <h2>Reconstruction Report</h2>
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


def _project_geometry(project_id: str) -> dict[str, object]:
    if parse_gerber_file is None or parse_drill_file is None or render_geometry_svg is None:
        return {"status": "gerber-core unavailable", "gerber": None, "drill": None, "svg": ""}
    records = _project_artifact_records(project_id)
    gerber_record = _preferred_artifact(records, "gerber", ["L1_top.art", "L1_TOP.art", "top.art"])
    drill_record = _preferred_artifact(records, "drill", ["ROCKBOX_V2-1-6.drl"])
    gerber_summary = parse_gerber_file(str(gerber_record["path"]), sample_limit=900) if gerber_record is not None else None
    drill_summary = parse_drill_file(str(drill_record["path"]), sample_limit=700) if drill_record is not None else None
    gerber_dict = _compact_gerber_geometry(gerber_record, asdict(gerber_summary)) if gerber_summary is not None and gerber_record is not None else None
    drill_dict = _compact_drill_geometry(drill_record, asdict(drill_summary)) if drill_summary is not None and drill_record is not None else None
    return {
        "status": "geometry-preview" if gerber_summary is not None or drill_summary is not None else "no-geometry-artifacts",
        "gerber": gerber_dict,
        "drill": drill_dict,
        "svg": render_geometry_svg(gerber_summary, drill_summary),
    }


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


def _artifact_id(path: Path) -> str:
    safe_name = "".join(character.lower() if character.isalnum() else "-" for character in path.name).strip("-")
    return safe_name or "artifact"


def _find_project_artifact(project_id: str, artifact_id: str) -> dict[str, object] | None:
    for artifact in _project_artifact_records(project_id):
        if artifact["id"] == artifact_id:
            return artifact
    return None


def _artifact_row(project_id: str, artifact: dict[str, object]) -> str:
    return (
        "<tr>"
        f"<td><code>{escape(str(artifact['filename']))}</code></td>"
        f"<td>{escape(str(artifact['artifact_type']))}</td>"
        f"<td>{escape(str(artifact['detected_format']))}</td>"
        f"<td>{escape(str(artifact['size_bytes']))}</td>"
        f"<td><a class=\"button secondary\" href=\"/bodesign/projects/{escape(project_id)}/artifacts/{escape(str(artifact['id']))}\">Open</a></td>"
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
        return {
            "kind": "gerber-geometry",
            "text": _gerber_summary_text(path, asdict(geometry)),
            "geometry": asdict(geometry),
            "svg": render_geometry_svg(geometry, None) if render_geometry_svg is not None else "",
        }
    if artifact_type == "drill" and parse_drill_file is not None:
        geometry = parse_drill_file(path, sample_limit=180)
        return {
            "kind": "drill-geometry",
            "text": _drill_summary_text(path, asdict(geometry)),
            "geometry": asdict(geometry),
            "svg": render_geometry_svg(None, geometry) if render_geometry_svg is not None else "",
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
    preview_svg = str(preview.get("svg", ""))
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
          .geometry { border: 1px solid #293943; border-radius: 14px; padding: 12px; background: #07100d; overflow: auto; }
          .geometry svg { width: 100%; min-width: 720px; height: auto; display: block; }
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
        <div class="geometry">""" + preview_svg + """</div>
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


def _component_row(component: dict[str, object]) -> str:
    placement = component.get("placement") if isinstance(component.get("placement"), dict) else {}
    x_mil = placement.get("x_mil", "")
    y_mil = placement.get("y_mil", "")
    return (
        "<tr>"
        f"<td><code>{escape(str(component.get('refdes', '')))}</code></td>"
        f"<td>{escape(str(component.get('part_number') or placement.get('value') or ''))}</td>"
        f"<td>{escape(str(component.get('footprint') or ''))}</td>"
        f"<td>{escape(str(placement.get('side', '')))}</td>"
        f"<td>{escape(str(x_mil))}, {escape(str(y_mil))}</td>"
        "</tr>"
    )


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
