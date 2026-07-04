"""Executable verify-checkers (skillification of ragbase control.* objects).

Each checker realises a `control.*` object as a pure-python, zero-LLM,
fail-fast gate that emits the shared `ValidationEvidence` envelope carrying
`control_id` + `source_anchor` for datasheet-grounded traceability (DD-2).

Fail-fast contract (errors.md): checkers never substitute defaults for a
missing IR field — they raise `CheckerError(CHK_IR_FIELD_MISSING, ...)` with
the explicit list of missing field paths (no-silent-fallback).
"""

from .decoupling_pdn import check_decoupling_pdn
from .board_edge_keepout import check_board_edge_keepout, guard_tier
from .copper_spacing import check_spacing_via_return_path
from .datasheet_derating import check_datasheet_derating
from .placement_topology import check_placement_topology
from .advisory import AdvisoryScenario, build_advisory_scenarios
from .threshold import resolve_threshold_block
from .registry import CheckerBinding, CheckerRegistry, build_pilot_registry
from .errors import CheckerError

__all__ = [
    "check_decoupling_pdn",
    "check_board_edge_keepout",
    "check_spacing_via_return_path",
    "check_datasheet_derating",
    "check_placement_topology",
    "AdvisoryScenario",
    "build_advisory_scenarios",
    "guard_tier",
    "resolve_threshold_block",
    "CheckerBinding",
    "CheckerRegistry",
    "build_pilot_registry",
    "CheckerError",
]
