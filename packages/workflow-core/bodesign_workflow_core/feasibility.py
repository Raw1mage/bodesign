"""Product feasibility triage — set the C04 completion target from C00/C03 signals.

The honest answer to "I give C00, you give C01–C04": *how far* bodesign can take a
given product depends almost entirely on whether KiCad + the bodesign MCP can actually
route its board. This module reads the complexity signals and returns the **tier** and
the **C04 completion target** up front, so the promise is honest per-product instead of
discovered at the C04 wall.

The tier is set by the *worst* (hardest) driver — one HDI-class constraint pulls the
whole product to Tier 3 regardless of how simple the rest is. See
`skills/bodesign/references/feasibility-triage.md` for the rubric and how a tier that
clashes with the user's expectation becomes a cross-stage reconciliation record.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# C04 completion target per tier — what bodesign actually delivers.
_TARGET = {
    1: "fab-ready: KiCad + MCP route + DRC/SI gate → a gated, fab-ready board package",
    2: "routed-draft: MCP routes most; critical nets need human/pro SI sign-off before fab",
    3: "concept+constraints → pro-EDA: architecture + stackup + floorplan intent + SI constraint "
       "set; HDI/DDR/RF routing handed to Allegro/Xpedition + human SI + HDI fab",
}
_LABEL = {1: "fab-ready", 2: "routed-draft (human SI sign-off)", 3: "concept+constraints → pro-EDA"}


@dataclass(slots=True)
class FeasibilityVerdict:
    tier: int                          # 1 | 2 | 3 (worst-driver wins)
    label: str
    c04_target: str
    drivers: list[str] = field(default_factory=list)   # which signals forced this tier
    confidence: str = "estimate"       # "estimate" (C00) | "firm" (C03 component set)
    rationale: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "bodesign.feasibility.v1",
            "tier": self.tier, "label": self.label, "c04_target": self.c04_target,
            "drivers": self.drivers, "confidence": self.confidence, "rationale": self.rationale,
        }


def classify_product_feasibility(
    *,
    layer_count: int | None = None,
    finest_bga_pitch_mm: float | None = None,
    hdi_required: bool | None = None,
    high_speed_nets: int = 0,          # DDR / USB3 / MIPI / SerDes — controlled-Z + length-match
    rf: bool = False,
    component_count: int | None = None,
    board_area_mm2: float | None = None,
    source: str = "C00-estimate",
) -> FeasibilityVerdict:
    """Classify a product into the C04 delivery tier from whatever signals exist.

    Runs early on C00 estimates (confidence "estimate") and again on the firm C03
    component set (confidence "firm"). Unknown signals (None) simply don't push the tier.
    """
    tier = 1
    drivers: list[str] = []

    def bump(to: int, why: str) -> None:
        nonlocal tier
        if to > tier:
            tier = to
        drivers.append(why)

    # --- Tier 3: HDI / phone-class — beyond KiCad + MCP routing ---
    if hdi_required:
        bump(3, "HDI / any-layer microvia required")
    if finest_bga_pitch_mm is not None and finest_bga_pitch_mm <= 0.4:
        bump(3, f"BGA pitch ≤0.4 mm ({finest_bga_pitch_mm} mm) → via-in-pad / HDI mandatory")
    if layer_count is not None and layer_count >= 8:
        bump(3, f"{layer_count}-layer stackup")
    if high_speed_nets >= 16:
        bump(3, f"{high_speed_nets} high-speed nets (DDR/SerDes-class density)")

    # --- Tier 2: controlled-Z / moderate density — routable but needs SI sign-off ---
    if finest_bga_pitch_mm is not None and 0.4 < finest_bga_pitch_mm <= 0.5:
        bump(2, f"BGA pitch {finest_bga_pitch_mm} mm (via-in-pad preferred)")
    if layer_count is not None and 6 <= layer_count < 8:
        bump(2, f"{layer_count}-layer stackup")
    if 0 < high_speed_nets < 16:
        bump(2, f"{high_speed_nets} high-speed / controlled-Z net(s)")
    if rf:
        bump(2, "RF / antenna integration (matching + keepout, VNA tune)")
    if (component_count and board_area_mm2 and board_area_mm2 > 0
            and component_count / board_area_mm2 > 0.5):  # >0.5 parts/mm² ≈ very dense
        bump(2, f"high placement density (~{component_count / board_area_mm2:.2f} parts/mm²)")

    confidence = "firm" if source.startswith("C03") else "estimate"
    rationale = (
        "Tier set by the hardest driver; "
        + (", ".join(drivers) if drivers else "no complexity driver tripped — simple board")
        + f". Signals from {source}."
    )
    return FeasibilityVerdict(
        tier=tier, label=_LABEL[tier], c04_target=_TARGET[tier],
        drivers=drivers, confidence=confidence, rationale=rationale,
    )
