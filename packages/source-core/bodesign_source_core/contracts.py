from dataclasses import dataclass, field


@dataclass(slots=True)
class ExportRequest:
    project_id: str
    board_design_id: str
    export_format: str = "gerber"


@dataclass(slots=True)
class ExportPlan:
    project_id: str
    board_design_id: str
    output_paths: list[str] = field(default_factory=list)
    report_path: str | None = None
    status: str = "planned"
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DesignReport:
    project_id: str
    board_design_id: str
    report_type: str
    title: str
    summary: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    artifact_refs: list[str] = field(default_factory=list)
    status: str = "placeholder-report"


def plan_gerber_export(project_id: str, board_design_id: str) -> ExportPlan:
    output_root = f"storage/exports/{project_id}/{board_design_id}"
    return ExportPlan(
        project_id=project_id,
        board_design_id=board_design_id,
        output_paths=[
            f"{output_root}/L1_top.gbr",
            f"{output_root}/L2_GND.gbr",
            f"{output_root}/L3_IN1.gbr",
            f"{output_root}/L4_IN2.gbr",
            f"{output_root}/L5_IN3.gbr",
            f"{output_root}/L6_bot.gbr",
            f"{output_root}/drill.drl",
        ],
        report_path=f"{output_root}/export-report.json",
        status="placeholder-planned",
        warnings=[
            "Placeholder export plan only; no Gerber files have been generated.",
            "KiCad/pygerber/export bridge integration is pending.",
        ],
    )


def produce_design_report(project_id: str, board_design_id: str, artifact_refs: list[str] | None = None) -> DesignReport:
    return DesignReport(
        project_id=project_id,
        board_design_id=board_design_id,
        report_type="design-reconstruction-export",
        title="bodesign reconstruction/export report placeholder",
        summary=[
            "BoardDesign IR has placeholder reconstruction/export evidence only.",
            "Rockbox artifact classification and manifest counts are available.",
            "Gerber generation and validation are planned but not implemented.",
        ],
        assumptions=[
            "Gerber, drill, IPC-356, routing, and placement files are treated as source evidence.",
            "Datasheet-derived design generation requires normalized component knowledge before fabrication use.",
        ],
        warnings=[
            "No real Gerber geometry has been parsed.",
            "No generated output is send-to-fab ready.",
        ],
        artifact_refs=artifact_refs or [],
    )
