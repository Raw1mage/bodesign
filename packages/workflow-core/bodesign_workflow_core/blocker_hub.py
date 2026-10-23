"""
Blocker Hub (Activity A5) for IDEF0 A2A Institutional Exception Arbitration.

Provides structured blocker logging (BLK-nnn.json), deterministic repair routing
back to owning A2A activities, and retry-limit enforcement preventing infinite loops.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
from typing import Any

from .substate_machine import A2ARole


class BlockerStatus(str, Enum):
    OPEN = "OPEN"
    ROUTED = "ROUTED"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


# Activity to target repair role mapping
ACTIVITY_OWNER_ROLE: dict[str, A2ARole] = {
    "A1": A2ARole.EE_DESIGNER,
    "A2": A2ARole.EE_DESIGNER,
    "A3": A2ARole.LAYOUT_SPECIALIST,
    "A4": A2ARole.LAYOUT_SPECIALIST,
    "A5": A2ARole.ORCHESTRATOR,
}

DEFAULT_MAX_RETRIES: int = 2


@dataclass(slots=True)
class BlockerRecord:
    blocker_id: str
    source_step: int | str
    owning_activity: str
    error_code: str
    summary: str
    evidence: dict[str, Any]
    resume_condition: str
    target_role: str
    retry_count: int = 0
    max_retries: int = DEFAULT_MAX_RETRIES
    status: BlockerStatus = BlockerStatus.OPEN
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolution_notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocker_id": self.blocker_id,
            "source_step": self.source_step,
            "owning_activity": self.owning_activity,
            "error_code": self.error_code,
            "summary": self.summary,
            "evidence": dict(self.evidence),
            "resume_condition": self.resume_condition,
            "target_role": self.target_role,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "resolution_notes": self.resolution_notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlockerRecord:
        return cls(
            blocker_id=data["blocker_id"],
            source_step=data["source_step"],
            owning_activity=data["owning_activity"],
            error_code=data["error_code"],
            summary=data.get("summary", ""),
            evidence=dict(data.get("evidence", {})),
            resume_condition=data.get("resume_condition", ""),
            target_role=data.get("target_role", "orchestrator"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", DEFAULT_MAX_RETRIES),
            status=BlockerStatus(data.get("status", BlockerStatus.OPEN.value)),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
            resolution_notes=data.get("resolution_notes"),
        )


class BlockerHub:
    """Central arbitration hub managing lifecycle and routing of blocker events."""

    def __init__(self, storage_dir: Path | str | None = None) -> None:
        self.storage_dir = Path(storage_dir) if storage_dir else None
        self._blockers: dict[str, BlockerRecord] = {}
        self._counter: int = 1

    def create_blocker(
        self,
        source_step: int | str,
        owning_activity: str,
        error_code: str,
        summary: str,
        evidence: dict[str, Any],
        resume_condition: str,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> BlockerRecord:
        """Create a new tracked blocker record."""
        blocker_id = f"BLK-{self._counter:03d}"
        self._counter += 1

        target_role = ACTIVITY_OWNER_ROLE.get(owning_activity, A2ARole.ORCHESTRATOR).value

        record = BlockerRecord(
            blocker_id=blocker_id,
            source_step=source_step,
            owning_activity=owning_activity,
            error_code=error_code,
            summary=summary,
            evidence=evidence,
            resume_condition=resume_condition,
            target_role=target_role,
            max_retries=max_retries,
        )

        self._blockers[blocker_id] = record
        self._persist(record)
        return record

    def dispatch_repair(self, blocker_id: str) -> dict[str, Any]:
        """Dispatch a repair work order for an open blocker, checking retry bounds."""
        record = self._blockers.get(blocker_id)
        if not record:
            raise KeyError(f"Blocker {blocker_id} not found in BlockerHub.")

        if record.status == BlockerStatus.RESOLVED:
            return {"status": "ALREADY_RESOLVED", "blocker_id": blocker_id}

        record.retry_count += 1
        record.updated_at = datetime.now(timezone.utc).isoformat()

        if record.retry_count > record.max_retries:
            record.status = BlockerStatus.ESCALATED
            self._persist(record)
            return {
                "status": "ESCALATED",
                "blocker_id": blocker_id,
                "message": f"Blocker {blocker_id} exceeded max retries ({record.max_retries}). Escalated to Orchestrator/Operator.",
                "target_role": A2ARole.ORCHESTRATOR.value,
            }

        record.status = BlockerStatus.ROUTED
        self._persist(record)

        return {
            "status": "ROUTED",
            "blocker_id": blocker_id,
            "target_role": record.target_role,
            "owning_activity": record.owning_activity,
            "repair_directive": {
                "error_code": record.error_code,
                "summary": record.summary,
                "evidence": record.evidence,
                "resume_condition": record.resume_condition,
                "attempt": record.retry_count,
            },
        }

    def resolve_blocker(self, blocker_id: str, resolution_notes: str) -> BlockerRecord:
        """Mark a blocker as resolved with evidence notes."""
        record = self._blockers.get(blocker_id)
        if not record:
            raise KeyError(f"Blocker {blocker_id} not found in BlockerHub.")

        record.status = BlockerStatus.RESOLVED
        record.resolution_notes = resolution_notes
        record.updated_at = datetime.now(timezone.utc).isoformat()
        self._persist(record)
        return record

    def get_blocker(self, blocker_id: str) -> BlockerRecord | None:
        return self._blockers.get(blocker_id)

    def list_open_blockers(self) -> list[BlockerRecord]:
        return [b for b in self._blockers.values() if b.status in (BlockerStatus.OPEN, BlockerStatus.ROUTED)]

    def _persist(self, record: BlockerRecord) -> None:
        if self.storage_dir:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            target_path = self.storage_dir / f"{record.blocker_id}.json"
            target_path.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")
