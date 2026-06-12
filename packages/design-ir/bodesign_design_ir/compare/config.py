"""G7 scoring configuration (DD-12).

Weights and thresholds live in ONE config object — never scattered as
hard-coded constants. Defaults follow pcbGPT (arXiv 2606.01188):
S = 0.4*S_comp(Dice) + 0.2*S_attr + 0.4*S_conn.

CMP_CONFIG_INVALID: weights must be non-negative and sum to 1.0.
"""

from dataclasses import dataclass


class CompareError(ValueError):
    """Raised for comparator input/config violations (CMP_* family)."""


@dataclass(frozen=True, slots=True)
class ScoringConfig:
    weight_comp: float = 0.4
    weight_attr: float = 0.2
    weight_conn: float = 0.4
    # Minimum pairwise similarity for a Hungarian assignment to count as a match.
    min_match_similarity: float = 0.1
    # Refdes prefixes treated as symmetric two-pin passives (pin names -> __sym__).
    symmetric_passive_prefixes: tuple[str, ...] = ("R", "C", "L")

    def __post_init__(self) -> None:
        weights = (self.weight_comp, self.weight_attr, self.weight_conn)
        if any(w < 0 for w in weights) or abs(sum(weights) - 1.0) > 1e-9:
            raise CompareError(
                "CMP_CONFIG_INVALID: comparator scoring config invalid: weights must be "
                f"non-negative and sum to 1.0 (got {weights})"
            )
        if not (0.0 <= self.min_match_similarity <= 1.0):
            raise CompareError(
                "CMP_CONFIG_INVALID: min_match_similarity must be within [0, 1] "
                f"(got {self.min_match_similarity})"
            )


DEFAULT_SCORING_CONFIG = ScoringConfig()
