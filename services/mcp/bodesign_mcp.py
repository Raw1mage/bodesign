from dataclasses import asdict
from pathlib import Path
import sys
from typing import Any


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

from bodesign_component_kb import ingest_datasheet_knowledge, reuse_component_knowledge
from bodesign_doc_core import plan_openmv_document_ingestion
from bodesign_gerber_core import validate_gerber_export_placeholder
from bodesign_reverse_core import build_rockbox_input_manifest, reconstruct_rockbox_placeholder
from bodesign_shared import detect_input_artifact
from bodesign_source_core import plan_gerber_export, produce_design_report


def ingest_sources(project_id: str, paths: list[str]) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "artifacts": [asdict(detect_input_artifact(path, project_id)) for path in paths],
        "status": "detected",
    }


def ingest_knowledge(project_id: str, document_paths: list[str], part_number: str | None = None) -> dict[str, Any]:
    design_intent = plan_openmv_document_ingestion(project_id, document_paths)
    component_result = ingest_datasheet_knowledge(project_id, part_number or "unknown-part", document_paths)
    return {
        "project_id": project_id,
        "design_intent": asdict(design_intent),
        "component_knowledge": asdict(component_result),
        "status": "placeholder-knowledge-ingestion",
    }


def reuse_knowledge(project_id: str, part_number: str, document_paths: list[str] | None = None) -> dict[str, Any]:
    ingestion_result = ingest_datasheet_knowledge(project_id, part_number, document_paths or [])
    if ingestion_result.component is None:
        return asdict(ingestion_result)
    return asdict(reuse_component_knowledge(project_id, part_number, ingestion_result.component))


def normalize_sources(project_id: str, paths: list[str]) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "normalized_artifacts": [asdict(detect_input_artifact(path, project_id)) for path in paths],
        "status": "placeholder-normalized",
    }


def reconstruct_board(project_id: str, artifact_paths: list[str]) -> dict[str, Any]:
    manifest = build_rockbox_input_manifest(project_id, artifact_paths)
    board_design = reconstruct_rockbox_placeholder(project_id, artifact_paths)
    return {
        "project_id": project_id,
        "manifest": asdict(manifest),
        "board_design": asdict(board_design),
        "status": "placeholder-reconstructed",
    }


def generate_board(project_id: str, document_paths: list[str]) -> dict[str, Any]:
    design_intent = plan_openmv_document_ingestion(project_id, document_paths)
    board_design = reconstruct_rockbox_placeholder(project_id, [])
    board_design.title = "Datasheet-derived BoardDesign candidate placeholder"
    board_design.confidence_summary = {
        "overall": design_intent.confidence,
        "status": "placeholder-generated-from-design-intent",
        "knowledge_gaps": float(len(design_intent.knowledge_gaps)),
    }
    return {
        "project_id": project_id,
        "design_intent": asdict(design_intent),
        "board_design": asdict(board_design),
        "status": "placeholder-generated",
    }


def validate_design(project_id: str, output_paths: list[str]) -> dict[str, Any]:
    return asdict(validate_gerber_export_placeholder(project_id, output_paths))


def export_gerber(project_id: str, board_design_id: str | None = None) -> dict[str, Any]:
    resolved_board_design_id = board_design_id or f"{project_id}-board-design"
    return asdict(plan_gerber_export(project_id, resolved_board_design_id))


def produce_report(project_id: str, board_design_id: str | None = None, artifact_refs: list[str] | None = None) -> dict[str, Any]:
    resolved_board_design_id = board_design_id or f"{project_id}-board-design"
    return asdict(produce_design_report(project_id, resolved_board_design_id, artifact_refs or []))


def open_viewer(project_id: str, base_url: str = "") -> dict[str, str]:
    viewer_path = f"/bodesign/?project={project_id}"
    return {
        "project_id": project_id,
        "viewer_url": f"{base_url.rstrip('/')}{viewer_path}" if base_url else viewer_path,
    }


TOOL_HANDLERS = {
    "ingest_sources": ingest_sources,
    "ingest_knowledge": ingest_knowledge,
    "reuse_knowledge": reuse_knowledge,
    "normalize_sources": normalize_sources,
    "reconstruct_board": reconstruct_board,
    "generate_board": generate_board,
    "validate_design": validate_design,
    "export_gerber": export_gerber,
    "produce_report": produce_report,
    "open_viewer": open_viewer,
}
