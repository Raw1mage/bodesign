"""Checker error family (errors.md CHK_* catalogue).

CheckerError carries a stable error `code` plus structured detail so callers
can surface a deterministic fail-fast signal instead of a silent default.
"""

from typing import Any


class CheckerError(ValueError):
    """Deterministic fail-fast error for the CHK_* family.

    Attributes:
      code: stable error code from errors.md (e.g. CHK_IR_FIELD_MISSING).
      detail: structured payload (e.g. {"missing_fields": [...]}). Never a
        free-form default substitution — the caller must act on it.
    """

    def __init__(self, code: str, message: str, **detail: Any) -> None:
        self.code = code
        self.detail: dict[str, Any] = dict(detail)
        super().__init__(f"{code}: {message}")
