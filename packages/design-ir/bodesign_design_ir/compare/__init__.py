"""G7 reference comparator — deterministic IR-vs-IR comparison (DD-10..DD-13).

Library API (v1; MCP tool wrapping is a later phase):

    from bodesign_design_ir.compare import compare_designs, ScoringConfig

    result = compare_designs(candidate_ir, reference_ir)
    result.s_total                  # weighted score
    result.items                    # CrossCheckDiffItem dicts
    result.to_validation_evidence() # ValidationEvidence envelope dict
"""

from .comparator import CompareResult, compare_designs
from .config import DEFAULT_SCORING_CONFIG, CompareError, ScoringConfig
from .matching import SYM_PIN, ComponentMatch

__all__ = [
    "CompareError",
    "CompareResult",
    "ComponentMatch",
    "DEFAULT_SCORING_CONFIG",
    "SYM_PIN",
    "ScoringConfig",
    "compare_designs",
]
