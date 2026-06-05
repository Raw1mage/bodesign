from dataclasses import asdict
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
    from bodesign_gerber_core import validate_gerber_export_placeholder
    from bodesign_shared import JobSummary, ProjectSummary, detect_input_artifact
    from bodesign_reverse_core import build_rockbox_input_manifest, reconstruct_rockbox_placeholder
    from bodesign_source_core import plan_gerber_export, produce_design_report
except ImportError:
    ingest_datasheet_knowledge = None
    reuse_component_knowledge = None
    plan_openmv_document_ingestion = None
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


@app.get("/health")
@app.get("/bodesign/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "bodesign-api"}


@app.get("/bodesign", include_in_schema=False)
def bodesign_viewer_redirect() -> RedirectResponse:
    return RedirectResponse(url="/bodesign/")


@app.get("/bodesign/", response_class=HTMLResponse)
def bodesign_viewer() -> str:
    board_design = _rockbox_demo_board_design()
    confidence = board_design["confidence_summary"]
    return """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>bodesign Rockbox Viewer</title>
        <style>
          body { margin: 0; font-family: ui-sans-serif, system-ui, sans-serif; background: #101418; color: #e8f0f2; }
          main { display: grid; grid-template-columns: 280px 1fr 320px; min-height: 100vh; }
          aside, section { padding: 24px; border-right: 1px solid #26323a; }
          h1, h2 { margin-top: 0; }
          .canvas { display: grid; place-items: center; background: radial-gradient(circle at 50% 35%, #20303a, #0b0f12 70%); }
          .board { width: min(68vw, 760px); aspect-ratio: 1.65; border: 2px solid #5de4c7; border-radius: 18px; position: relative; background: #16362e; box-shadow: 0 24px 80px #0008; }
          .chip { position: absolute; border-radius: 10px; background: #d8e1e5; color: #111; display: grid; place-items: center; font-size: 12px; font-weight: 700; }
          .trace { position: absolute; height: 4px; background: #ffc857; border-radius: 999px; transform-origin: left center; }
          .pill { display: inline-block; margin: 4px 4px 4px 0; padding: 4px 8px; border: 1px solid #39515b; border-radius: 999px; color: #9bd8ff; }
          .metric { display: flex; justify-content: space-between; margin: 8px 0; color: #cbd6d9; }
          code { color: #8ef6d2; }
        </style>
      </head>
      <body>
        <main>
          <aside>
            <h1>bodesign</h1>
            <p>Rockbox reconstructed circuit/PCB viewer placeholder.</p>
            <p><code>/bodesign/</code> is backed by MCP/API contracts and currently renders manifest-level placeholder data.</p>
            <h2>Layers</h2>
            <span class="pill">L1 top</span><span class="pill">L2 GND</span><span class="pill">L3 IN1</span>
            <span class="pill">L4 IN2</span><span class="pill">L5 IN3</span><span class="pill">L6 bot</span>
          </aside>
          <section class="canvas">
            <div class="board" aria-label="Rockbox PCB placeholder">
              <div class="chip" style="left: 42%; top: 35%; width: 120px; height: 78px;">MDBT53-P1M</div>
              <div class="chip" style="left: 18%; top: 22%; width: 86px; height: 52px;">FLASH</div>
              <div class="chip" style="right: 16%; top: 20%; width: 90px; height: 56px;">CHARGER</div>
              <div class="chip" style="right: 20%; bottom: 18%; width: 96px; height: 48px;">USB/CONN</div>
              <div class="trace" style="left: 31%; top: 36%; width: 130px; transform: rotate(10deg);"></div>
              <div class="trace" style="left: 57%; top: 45%; width: 160px; transform: rotate(-12deg);"></div>
              <div class="trace" style="left: 52%; top: 60%; width: 180px; transform: rotate(18deg);"></div>
            </div>
          </section>
          <aside>
            <h2>BoardDesign IR</h2>
            <div class="metric"><span>id</span><code>""" + str(board_design["id"]) + """</code></div>
            <div class="metric"><span>status</span><code>""" + str(confidence["status"]) + """</code></div>
            <div class="metric"><span>overall confidence</span><code>""" + str(confidence["overall"]) + """</code></div>
            <h2>Artifact Evidence</h2>
            <div class="metric"><span>Gerber layers</span><code>""" + str(int(confidence["gerber_files"])) + """</code></div>
            <div class="metric"><span>Drill files</span><code>""" + str(int(confidence["drill_files"])) + """</code></div>
            <div class="metric"><span>IPC-356</span><code>""" + str(int(confidence["ipc_files"])) + """</code></div>
            <div class="metric"><span>Placement/BOM</span><code>""" + str(int(confidence["component_files"])) + """</code></div>
            <p>Geometry is mocked until real Gerber/drill/IPC parsing lands.</p>
          </aside>
        </main>
      </body>
    </html>
    """


@app.get("/api/projects")
@app.get("/bodesign/api/projects")
def list_projects() -> list[dict[str, str]]:
    return list(PROJECTS.values())


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


def _rockbox_demo_board_design() -> dict[str, object]:
    artifact_paths = [
        "L1_top.art",
        "L2_GND.art",
        "L3_IN1.art",
        "L4_IN2.art",
        "L5_IN3.art",
        "L6_bot.art",
        "ROCKBOX_V2-1-6.drl",
        "ROCKBOX_V2.ipc",
        "ROCKBOX_V2_1-6.rou",
        "cds2f_ROCKBOX_V2.txt",
    ]
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
