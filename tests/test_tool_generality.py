"""Generality contract guard (T2) for the bodesign MCP tool layer.

Encodes the "no SILENT overfit" bar (see docs/generality-check.md) as data: every
tool that carries a board- or process-specific assumption must expose it as a
caller input. This is a schema-level regression guard — it needs no pcbnew/ngspice
and runs on a bare host. If a future change drops one of these overrides (re-baking
an assumption), the test fails.

Add a row to GENERALITY_CONTRACT whenever a tool gains a board/process input.
"""

import importlib
import unittest


# tool name -> inputs that MUST stay reachable so a board/process assumption is
# caller-overridable rather than silently baked in.
GENERALITY_CONTRACT = {
    # H1: connector pin expansion is not refdes-gated and is reported.
    "bodesign_route_net2pcb": ["connectors"],
    # H2: SI driver/load/edge/thresholds are overridable (defaults = STM32-class CMOS).
    "bodesign_si_check": ["rdrv", "cload", "edge_ns",
                          "overshoot_pass_pct", "overshoot_warn_pct"],
    # H3: placement grid / outline are overridable (defaults = small prototype board).
    "bodesign_emit_layout": ["board_mm", "columns",
                             "place_start_mm", "place_pitch_mm", "margin_mm"],
    # H4: PDF layer set is overridable (default = 2/4-layer).
    "bodesign_emit_fab": ["pdf_layers"],
    # H5: BGA via geometry is overridable (default = JLCPCB advanced POFV).
    "bodesign_via_in_pad": ["drill_mm", "pad_mm", "keep_rings"],
    # H5: plane stitch net + grid/via are overridable (default = JLCPCB-class).
    "bodesign_pour_planes": ["stitch_net", "stitch_pitch_mm",
                             "stitch_drill_mm", "stitch_pad_mm"],
}

# tools whose result must REPORT what it applied (the alternative to overriding).
REPORTED_CONTRACT = {
    "bodesign_route_net2pcb": ["applied_pinmaps", "unmapped_connectors"],
    "bodesign_si_check": ["effective"],
}


class ToolGeneralityTests(unittest.TestCase):
    def setUp(self):
        self.server = importlib.import_module("services.mcp.server")

    def test_board_process_assumptions_are_exposed_as_inputs(self):
        for tool, required in GENERALITY_CONTRACT.items():
            spec = self.server.TOOLS_BY_NAME.get(tool)
            self.assertIsNotNone(spec, f"{tool} missing from registry")
            props = spec["schema"]["properties"]
            for key in required:
                self.assertIn(
                    key, props,
                    f"{tool}: board/process input '{key}' is no longer a caller "
                    f"override — a generality regression (re-baked assumption).")

    def test_reported_assumptions_documented_in_description(self):
        # The 'reported' arm: the result fields are surfaced via the tool description
        # so an agent knows the report exists.
        for tool, fields in REPORTED_CONTRACT.items():
            spec = self.server.TOOLS_BY_NAME.get(tool)
            self.assertIsNotNone(spec, f"{tool} missing from registry")
            for field in fields:
                self.assertIn(
                    field, spec["description"],
                    f"{tool}: report field '{field}' not advertised in description.")

    def test_every_audited_tool_still_registered(self):
        # Guards against an audited tool being renamed/removed without re-auditing.
        for tool in set(GENERALITY_CONTRACT) | set(REPORTED_CONTRACT):
            self.assertIn(tool, self.server.TOOLS_BY_NAME)


if __name__ == "__main__":
    unittest.main()
