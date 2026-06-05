from dataclasses import dataclass, field


@dataclass(slots=True)
class GerberValidationResult:
    project_id: str
    output_paths: list[str] = field(default_factory=list)
    status: str = "pending"
    warnings: list[str] = field(default_factory=list)
    blocking_errors: list[str] = field(default_factory=list)


def validate_gerber_export_placeholder(project_id: str, output_paths: list[str]) -> GerberValidationResult:
    warnings = [
        "Placeholder validation only; real Gerber parsing and geometry checks are pending.",
        "Generated output paths are not inspected or opened in this scaffold.",
    ]
    if not output_paths:
        warnings.append("No output paths were provided for validation.")

    return GerberValidationResult(
        project_id=project_id,
        output_paths=output_paths,
        status="placeholder-warning",
        warnings=warnings,
        blocking_errors=[],
    )
