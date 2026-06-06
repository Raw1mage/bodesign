"""Design-evidence sourcing (R6): parts -> datasheet/reference-design manifest.

Generalizes the OpenMV O0-O1 source-manifest step to an arbitrary spec: given
the chips named in a spec (or an explicit part list) plus an optional local
document corpus, locate matching datasheets / schematics / BOM / reference
designs and produce a reviewable sourcing manifest with trust grades and gaps.

Local-first by design: a caller-provided corpus directory is scanned read-only
for matching documents; parts with no local evidence get structured
distributor/manufacturer source pointers with a `needs-sourcing` status. Actual
web fetching stays behind the external-fetch policy gate and is executed by the
agent via the datasheets/digikey skills, not by this server.
"""

from dataclasses import dataclass, field
from pathlib import Path
import re

# Best-effort part/chip token extraction from a natural-language spec.
_PART_PATTERNS = [
    re.compile(r"\bSTM32[A-Z]\d?[A-Z0-9]*\b", re.IGNORECASE),
    re.compile(r"\bnRF\d{4,5}[A-Z0-9\-]*\b", re.IGNORECASE),
    re.compile(r"\bMDBT\d+[A-Z0-9\-]*\b", re.IGNORECASE),
    re.compile(r"\bMX25[A-Z0-9]+\b", re.IGNORECASE),
    re.compile(r"\bESP32[A-Z0-9\-]*\b", re.IGNORECASE),
    re.compile(r"\b(?:RTL|CYW|BQ|TPS|LM|AP|MIC|TCR)\d{3,5}[A-Z0-9\-]*\b", re.IGNORECASE),
    re.compile(r"\b(?:18650|21700|14500|26650|18500)\b"),
]

_ROLE_RULES = [
    ("bom", ("bom", "bill of material")),
    ("schematic", (".dsn", ".sch", ".kicad_sch", "schematic", "原理", "電路", "电路", "連板", "连板")),
    ("pinout", ("gpio", "pinout", "pin table", "pin_table", "ballout")),
    ("datasheet", ("datasheet", "規格", "规格", "spec", "reference manual")),
    ("requirement", ("requirement", "prd", "需求", "規格書")),
    ("layout", ("layout", "gerber", "stackup", "placement")),
]


@dataclass(slots=True)
class MatchedDocument:
    path: str
    role: str


@dataclass(slots=True)
class PartEvidence:
    part: str
    local_found: bool
    documents: list[MatchedDocument] = field(default_factory=list)
    source_pointers: list[dict[str, str]] = field(default_factory=list)
    trust_grade: str = "C"
    fetch_status: str = "needs-sourcing"
    gaps: list[str] = field(default_factory=list)


def extract_part_candidates(spec_text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for pattern in _PART_PATTERNS:
        for match in pattern.finditer(spec_text or ""):
            token = match.group(0)
            key = _normalize(token)
            if key not in seen:
                seen.add(key)
                found.append(token)
    return found


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _role_for(path: str) -> str:
    lowered = path.lower()
    for role, keywords in _ROLE_RULES:
        if any(keyword in lowered for keyword in keywords):
            return role
    return "document"


def scan_corpus_for_part(part: str, corpus_dir: str | Path) -> list[MatchedDocument]:
    root = Path(corpus_dir)
    if not root.exists():
        return []
    needle = _normalize(part)
    if not needle:
        return []
    matches: list[MatchedDocument] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if needle in _normalize(path.name):
            matches.append(MatchedDocument(path=str(path.relative_to(root)), role=_role_for(path.name)))
    return matches


def _distributor_pointers(part: str) -> list[dict[str, str]]:
    return [
        {"source": "digikey", "action": "search-via-skill", "query": part, "fetch": "policy-gated"},
        {"source": "lcsc", "action": "search-via-skill", "query": part, "fetch": "policy-gated"},
        {"source": "datasheets-skill", "action": "extract-pinout-when-pdf-available", "query": part, "fetch": "policy-gated"},
    ]


def build_design_evidence_manifest(parts: list[str], corpus_dir: str | Path | None = None) -> dict[str, object]:
    entries: list[PartEvidence] = []
    for part in parts:
        documents = scan_corpus_for_part(part, corpus_dir) if corpus_dir else []
        local_found = bool(documents)
        roles = {doc.role for doc in documents}
        if local_found and ({"schematic", "datasheet", "pinout"} & roles):
            trust, status = "A", "local-evidence"
        elif local_found:
            trust, status = "B", "local-partial"
        else:
            trust, status = "C", "needs-sourcing"
        gaps: list[str] = []
        if not local_found:
            gaps.append(f"No local document matched '{part}'; resolve via distributor/manufacturer (policy-gated fetch).")
        elif "pinout" not in roles and "datasheet" not in roles:
            gaps.append(f"Local docs for '{part}' lack a datasheet/pinout; pin-level extraction still needs the datasheet.")
        entries.append(
            PartEvidence(
                part=part,
                local_found=local_found,
                documents=documents,
                source_pointers=[] if local_found else _distributor_pointers(part),
                trust_grade=trust,
                fetch_status=status,
                gaps=gaps,
            )
        )

    return {
        "artifact_id": "design-evidence-manifest",
        "corpus_dir": str(corpus_dir) if corpus_dir else None,
        "source_policy": "local-first; web fetch is policy-gated and executed by the agent via datasheets/digikey skills, not the server.",
        "counts": {
            "parts": len(entries),
            "local_evidence": sum(1 for e in entries if e.fetch_status == "local-evidence"),
            "needs_sourcing": sum(1 for e in entries if e.fetch_status == "needs-sourcing"),
        },
        "parts": [
            {
                "part": e.part,
                "local_found": e.local_found,
                "trust_grade": e.trust_grade,
                "fetch_status": e.fetch_status,
                "documents": [{"path": d.path, "role": d.role} for d in e.documents],
                "source_pointers": e.source_pointers,
                "gaps": e.gaps,
            }
            for e in entries
        ],
    }
