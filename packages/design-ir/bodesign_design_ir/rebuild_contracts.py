"""Unified Collaborative Rebuild — Shared Domain & Exchange Contracts (P1/DD-1..12).

Implements versioned serialization, immutable manifest hashing, finite rigid frame
geometry validation, acyclic feature graph compilation, sourced engineering calculations,
and external adoption / CAD execution contracts per data-schema.json.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from typing import Any, Literal


# ---------------------------------------------------------------------------
# Artifact & Dependency Reference Contracts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ArtifactRef:
    """Scoped relative path to a disk artifact with immutable content digest."""
    role: str
    path: str
    sha256: str
    byte_size: int

    def __post_init__(self) -> None:
        if not self.role or not isinstance(self.role, str):
            raise ValueError("ArtifactRef requires non-empty string role")
        if not self.path or not isinstance(self.path, str):
            raise ValueError("ArtifactRef requires non-empty string path")
        # Relative path only; no leading slash, no traversal
        norm = self.path.replace("\\", "/")
        if norm.startswith("/") or norm.startswith("../") or "/../" in norm or norm == "..":
            raise ValueError(f"ArtifactRef path must be a scoped relative path without traversal: {self.path!r}")
        if not isinstance(self.sha256, str) or len(self.sha256) != 64 or not all(c in "0123456789abcdefABCDEF" for c in self.sha256):
            raise ValueError(f"ArtifactRef requires 64-char hex sha256 digest, got {self.sha256!r}")
        if not isinstance(self.byte_size, int) or self.byte_size < 0:
            raise ValueError(f"ArtifactRef requires non-negative byte_size, got {self.byte_size!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "path": self.path.replace("\\", "/"),
            "sha256": self.sha256.lower(),
            "byte_size": self.byte_size,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArtifactRef:
        return cls(
            role=str(data["role"]),
            path=str(data["path"]),
            sha256=str(data["sha256"]).lower(),
            byte_size=int(data["byte_size"]),
        )


@dataclass(frozen=True)
class DependencyRef:
    """Identity, version, and digest of an external source, tool, library, or rule."""
    kind: Literal["source", "library", "tool", "rule"]
    name: str
    version: str | None = None
    digest: str | None = None

    def __post_init__(self) -> None:
        valid_kinds = ("source", "library", "tool", "rule")
        if self.kind not in valid_kinds:
            raise ValueError(f"DependencyRef kind must be one of {valid_kinds}, got {self.kind!r}")
        if not self.name or not isinstance(self.name, str):
            raise ValueError("DependencyRef requires non-empty string name")
        if self.version is None and self.digest is None:
            raise ValueError(f"DependencyRef requires at least one of version or digest for {self.name!r}")

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"kind": self.kind, "name": self.name}
        if self.version is not None:
            d["version"] = self.version
        if self.digest is not None:
            d["digest"] = self.digest
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DependencyRef:
        return cls(
            kind=data["kind"],
            name=str(data["name"]),
            version=str(data["version"]) if data.get("version") is not None else None,
            digest=str(data["digest"]) if data.get("digest") is not None else None,
        )


# ---------------------------------------------------------------------------
# 2.1 ArtifactManifest Contract
# ---------------------------------------------------------------------------

@dataclass
class ArtifactManifest:
    """Immutable release artifact manifest with canonical hash validation."""
    schema_version: str
    revision_id: str
    artifacts: list[ArtifactRef]
    dependencies: list[DependencyRef]
    manifest_sha256: str = ""

    def __post_init__(self) -> None:
        if not self.schema_version.startswith("1."):
            raise ValueError(f"Unsupported schema_version: {self.schema_version!r} (expected 1.x)")
        if not self.revision_id:
            raise ValueError("ArtifactManifest requires non-empty revision_id")
        if not self.artifacts:
            raise ValueError("ArtifactManifest requires non-empty artifacts list")

        # Validate unique scoped paths
        seen_paths: set[str] = set()
        for a in self.artifacts:
            norm_path = a.path.replace("\\", "/")
            if norm_path in seen_paths:
                raise ValueError(f"Duplicate artifact path in manifest: {norm_path!r}")
            seen_paths.add(norm_path)

        computed = self.compute_canonical_sha256()
        if not self.manifest_sha256:
            self.manifest_sha256 = computed
        elif self.manifest_sha256.lower() != computed:
            raise ValueError(
                f"MANIFEST_SHA256_MISMATCH: declared {self.manifest_sha256} != computed {computed}"
            )

    def canonical_payload_dict(self) -> dict[str, Any]:
        """Payload excluding manifest_sha256, with sorted artifact paths."""
        sorted_artifacts = sorted(
            [a.to_dict() for a in self.artifacts],
            key=lambda x: x["path"],
        )
        sorted_dependencies = sorted(
            [d.to_dict() for d in self.dependencies],
            key=lambda x: (x["kind"], x["name"]),
        )
        return {
            "schema_version": self.schema_version,
            "revision_id": self.revision_id,
            "artifacts": sorted_artifacts,
            "dependencies": sorted_dependencies,
        }

    def compute_canonical_sha256(self) -> str:
        """Deterministic digest of canonical JSON payload (UTF-8, sorted keys)."""
        payload = self.canonical_payload_dict()
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        d = self.canonical_payload_dict()
        d["manifest_sha256"] = self.manifest_sha256.lower()
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArtifactManifest:
        artifacts = [ArtifactRef.from_dict(a) for a in data.get("artifacts", [])]
        dependencies = [DependencyRef.from_dict(d) for d in data.get("dependencies", [])]
        return cls(
            schema_version=str(data["schema_version"]),
            revision_id=str(data["revision_id"]),
            artifacts=artifacts,
            dependencies=dependencies,
            manifest_sha256=str(data.get("manifest_sha256", "")),
        )


# ---------------------------------------------------------------------------
# 2.1 DesignRepresentations Contract
# ---------------------------------------------------------------------------

@dataclass
class DesignRepresentations:
    """Separation of intent, native implementation, presentation, and physical constraints."""
    intent_revision: str
    native_manifest_sha256: str
    circuit: dict[str, Any]
    presentation: dict[str, Any]
    layout_constraints: dict[str, Any]
    reconciliation: Literal["consistent", "pending", "conflict"]

    def __post_init__(self) -> None:
        valid_reconciliation = ("consistent", "pending", "conflict")
        if self.reconciliation not in valid_reconciliation:
            raise ValueError(f"reconciliation must be one of {valid_reconciliation}, got {self.reconciliation!r}")
        if not self.intent_revision:
            raise ValueError("intent_revision must not be empty")
        if not self.native_manifest_sha256:
            raise ValueError("native_manifest_sha256 must not be empty")
        if not isinstance(self.circuit, dict):
            raise ValueError("circuit representation must be a dict")
        if not isinstance(self.presentation, dict):
            raise ValueError("presentation representation must be a dict")
        if not isinstance(self.layout_constraints, dict):
            raise ValueError("layout_constraints must be a dict")

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_revision": self.intent_revision,
            "native_manifest_sha256": self.native_manifest_sha256,
            "circuit": self.circuit,
            "presentation": self.presentation,
            "layout_constraints": self.layout_constraints,
            "reconciliation": self.reconciliation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DesignRepresentations:
        return cls(
            intent_revision=str(data["intent_revision"]),
            native_manifest_sha256=str(data["native_manifest_sha256"]),
            circuit=dict(data.get("circuit", {})),
            presentation=dict(data.get("presentation", {})),
            layout_constraints=dict(data.get("layout_constraints", {})),
            reconciliation=data["reconciliation"],
        )


# ---------------------------------------------------------------------------
# 2.4 ReferenceAdoption Contract
# ---------------------------------------------------------------------------

@dataclass
class ReferenceAdoption:
    """Traceable external reference evaluation and license clearance contract."""
    source: dict[str, Any]
    license: dict[str, Any]
    integration: Literal["selective-extraction", "native-design", "vendor-adapter", "deferred"]

    def __post_init__(self) -> None:
        valid_integrations = ("selective-extraction", "native-design", "vendor-adapter", "deferred")
        if self.integration not in valid_integrations:
            raise ValueError(f"integration must be one of {valid_integrations}, got {self.integration!r}")

        # Validate source
        for req in ("url", "commit", "paths", "evidence_kind"):
            if req not in self.source:
                raise ValueError(f"ReferenceAdoption.source missing required field: {req!r}")
        valid_evidence_kinds = ("source", "test-source", "document-claim")
        if self.source["evidence_kind"] not in valid_evidence_kinds:
            raise ValueError(f"source.evidence_kind must be in {valid_evidence_kinds}, got {self.source['evidence_kind']!r}")

        # Validate license
        for req in ("grant", "notice_paths", "reviewed", "approved"):
            if req not in self.license:
                raise ValueError(f"ReferenceAdoption.license missing required field: {req!r}")

    @property
    def is_extraction_allowed(self) -> bool:
        """License clearance: extraction permitted only with approved, reviewed grant."""
        if self.integration == "selective-extraction":
            return bool(self.license.get("approved") and self.license.get("reviewed"))
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "license": self.license,
            "integration": self.integration,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReferenceAdoption:
        return cls(
            source=dict(data["source"]),
            license=dict(data["license"]),
            integration=data["integration"],
        )


# ---------------------------------------------------------------------------
# 2.4 MechanicalBridge Contract
# ---------------------------------------------------------------------------

def validate_rigid_frame_4x4(matrix: list[list[float]], eps: float = 1e-4) -> None:
    """Validate that a 4x4 matrix is a finite, rigid, right-handed transform (R^T*R=I, det(R)=+1)."""
    if len(matrix) != 4 or any(len(row) != 4 for row in matrix):
        raise ValueError(f"Transform must be a 4x4 matrix, got shape {len(matrix)}x{len(matrix[0]) if matrix else 0}")

    for r_idx, row in enumerate(matrix):
        for c_idx, val in enumerate(row):
            if not isinstance(val, (int, float)) or not math.isfinite(val):
                raise ValueError(f"Transform element [{r_idx}][{c_idx}] is non-finite: {val!r}")

    # Bottom row must be [0, 0, 0, 1]
    bottom = matrix[3]
    if abs(bottom[0]) > eps or abs(bottom[1]) > eps or abs(bottom[2]) > eps or abs(bottom[3] - 1.0) > eps:
        raise ValueError(f"Bottom row of 4x4 rigid frame must be [0, 0, 0, 1], got {bottom}")

    # Extract 3x3 rotation
    R = [row[:3] for row in matrix[:3]]

    # Compute R^T * R
    for i in range(3):
        for j in range(3):
            dot = sum(R[k][i] * R[k][j] for k in range(3))
            expected = 1.0 if i == j else 0.0
            if abs(dot - expected) > eps:
                raise ValueError(
                    f"Transform rotation component is not orthonormal: (R^T*R)[{i}][{j}] = {dot:.6f} (expected {expected})"
                )

    # Compute determinant of 3x3
    det = (
        R[0][0] * (R[1][1] * R[2][2] - R[1][2] * R[2][1])
        - R[0][1] * (R[1][0] * R[2][2] - R[1][2] * R[2][0])
        + R[0][2] * (R[1][0] * R[2][1] - R[1][1] * R[2][0])
    )
    if abs(det - 1.0) > eps:
        if abs(det + 1.0) <= eps:
            raise ValueError(f"Transform involves reflection: det(R) = {det:.6f} (must be +1 for right-handed frame)")
        raise ValueError(f"Transform is non-rigid or scaled: det(R) = {det:.6f} (must be 1.0)")


@dataclass
class MechanicalBridge:
    """ECAD-MCAD exchange contract connecting board exports with mechanical frame."""
    board_manifest_sha256: str
    enclosure_manifest_sha256: str
    frame: dict[str, Any]
    models: list[dict[str, Any]]
    fixed_constraints: list[dict[str, Any]]

    def __post_init__(self) -> None:
        if not self.board_manifest_sha256:
            raise ValueError("board_manifest_sha256 is required")
        if not self.enclosure_manifest_sha256:
            raise ValueError("enclosure_manifest_sha256 is required")

        # Frame requirements: mm units, right-handed axes, origin, board normal, rigid 4x4 transform
        if self.frame.get("units") != "mm":
            raise ValueError(f"MechanicalBridge frame units must be 'mm', got {self.frame.get('units')!r}")
        if self.frame.get("axes") != "right-handed":
            raise ValueError(f"MechanicalBridge frame axes must be 'right-handed', got {self.frame.get('axes')!r}")

        origin = self.frame.get("origin")
        if not isinstance(origin, list) or len(origin) != 3 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in origin):
            raise ValueError(f"frame.origin must be 3-element finite coordinate list, got {origin!r}")

        normal = self.frame.get("board_normal")
        if not isinstance(normal, list) or len(normal) != 3 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in normal):
            raise ValueError(f"frame.board_normal must be 3-element finite vector list, got {normal!r}")

        transform = self.frame.get("transform")
        if not isinstance(transform, list):
            raise ValueError("frame.transform must be a 4x4 list of lists")
        validate_rigid_frame_4x4(transform)

        # Missing models must be explicit
        for m in self.models:
            if "object_id" not in m:
                raise ValueError("Each model entry must declare object_id")
            if not m.get("solid_hash") and not m.get("is_missing"):
                raise ValueError(f"Model {m['object_id']} without solid_hash must explicitly declare is_missing=True")

    def to_dict(self) -> dict[str, Any]:
        return {
            "board_manifest_sha256": self.board_manifest_sha256,
            "enclosure_manifest_sha256": self.enclosure_manifest_sha256,
            "frame": self.frame,
            "models": self.models,
            "fixed_constraints": self.fixed_constraints,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MechanicalBridge:
        return cls(
            board_manifest_sha256=str(data["board_manifest_sha256"]),
            enclosure_manifest_sha256=str(data["enclosure_manifest_sha256"]),
            frame=dict(data["frame"]),
            models=list(data.get("models", [])),
            fixed_constraints=list(data.get("fixed_constraints", [])),
        )


# ---------------------------------------------------------------------------
# 2.4 FeatureGraph Contract
# ---------------------------------------------------------------------------

SUPPORTED_FEATURE_OPERATIONS = frozenset({"enclosure", "boss", "cutout"})


@dataclass(frozen=True)
class FeatureAnchor:
    """Semantic anchor bound to a single source entity (cardinality=1)."""
    object_id: str
    semantic_role: str
    source_revision: str
    geometric_predicate: str
    tolerance: float
    cardinality: int = 1

    def __post_init__(self) -> None:
        if not self.object_id:
            raise ValueError("FeatureAnchor object_id is required")
        if not self.semantic_role:
            raise ValueError("FeatureAnchor semantic_role is required")
        if not self.source_revision:
            raise ValueError("FeatureAnchor source_revision is required")
        if self.cardinality != 1:
            raise ValueError(f"FeatureAnchor cardinality must be exactly 1, got {self.cardinality} (ambiguous anchors forbidden)")
        if self.tolerance <= 0:
            raise ValueError(f"FeatureAnchor tolerance must be positive, got {self.tolerance}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeatureAnchor:
        return cls(
            object_id=str(data["object_id"]),
            semantic_role=str(data["semantic_role"]),
            source_revision=str(data["source_revision"]),
            geometric_predicate=str(data["geometric_predicate"]),
            tolerance=float(data["tolerance"]),
            cardinality=int(data.get("cardinality", 1)),
        )


@dataclass
class FeatureNode:
    """Acyclic feature operation node in the compilation graph."""
    id: str
    operation: Literal["enclosure", "boss", "cutout"]
    depends_on: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    anchor_refs: list[str] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("FeatureNode requires non-empty id")
        if self.operation not in SUPPORTED_FEATURE_OPERATIONS:
            raise ValueError(
                f"UNSUPPORTED_OPERATION: {self.operation!r} is not in {sorted(SUPPORTED_FEATURE_OPERATIONS)}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "operation": self.operation,
            "depends_on": list(self.depends_on),
            "parameters": self.parameters,
            "anchor_refs": list(self.anchor_refs),
            "constraints": self.constraints,
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeatureNode:
        return cls(
            id=str(data["id"]),
            operation=data["operation"],
            depends_on=list(data.get("depends_on", [])),
            parameters=dict(data.get("parameters", {})),
            anchor_refs=list(data.get("anchor_refs", [])),
            constraints=dict(data.get("constraints", {})),
            evidence=dict(data.get("evidence", {})),
        )


@dataclass
class FeatureGraph:
    """bodesign-owned bounded acyclic feature compilation graph."""
    schema_version: str
    source_manifest_sha256: str
    nodes: list[FeatureNode]
    anchors: list[FeatureAnchor] = field(default_factory=list)
    execution: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.nodes:
            raise ValueError("FeatureGraph requires non-empty nodes list")

        # Validate unique IDs and absence of cycles (DAG check via Kahn's algorithm)
        node_map: dict[str, FeatureNode] = {}
        in_degree: dict[str, int] = {}
        adjacency: dict[str, list[str]] = {}

        for n in self.nodes:
            if n.id in node_map:
                raise ValueError(f"DUPLICATE_NODE_ID: {n.id!r}")
            node_map[n.id] = n
            in_degree[n.id] = 0
            adjacency[n.id] = []

        for n in self.nodes:
            for dep in n.depends_on:
                if dep not in node_map:
                    raise ValueError(f"DANGLING_DEPENDENCY: Node {n.id!r} depends on non-existent {dep!r}")
                adjacency[dep].append(n.id)
                in_degree[n.id] += 1

        queue = sorted([nid for nid, deg in in_degree.items() if deg == 0])
        ordered: list[str] = []
        while queue:
            curr = queue.pop(0)
            ordered.append(curr)
            for neighbor in adjacency[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
            queue.sort()

        if len(ordered) != len(self.nodes):
            unresolved = sorted([nid for nid, deg in in_degree.items() if deg > 0])
            raise ValueError(f"CYCLE_DETECTED: FeatureGraph contains cycle among nodes: {unresolved}")

        # Record deterministic topological ordering in execution
        self.execution = {
            "topological_order": ordered,
            "isolated_candidate": True,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_manifest_sha256": self.source_manifest_sha256,
            "nodes": [n.to_dict() for n in self.nodes],
            "anchors": [a.to_dict() for a in self.anchors],
            "execution": self.execution,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeatureGraph:
        nodes = [FeatureNode.from_dict(n) for n in data.get("nodes", [])]
        anchors = [FeatureAnchor.from_dict(a) for a in data.get("anchors", [])]
        return cls(
            schema_version=str(data["schema_version"]),
            source_manifest_sha256=str(data["source_manifest_sha256"]),
            nodes=nodes,
            anchors=anchors,
            execution=dict(data.get("execution", {})),
        )


# ---------------------------------------------------------------------------
# 2.4 EngineeringCalculation Contract
# ---------------------------------------------------------------------------

@dataclass
class EngineeringCalculation:
    """Sourced physical calculations with explicit assumptions and missing-data fail-loud."""
    model: dict[str, Any]
    inputs: list[dict[str, Any]]
    result: dict[str, Any] | None = None
    gaps: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for req in ("formula_id", "version", "topology_applicable"):
            if req not in self.model:
                raise ValueError(f"EngineeringCalculation.model missing {req!r}")

        # Check for unverified inputs or missing applicability
        if not self.model.get("topology_applicable"):
            self.result = None
            if "Topology not applicable for formula" not in self.gaps:
                self.gaps.append("Topology not applicable for formula")

        missing_inputs = []
        for inp in self.inputs:
            for req in ("name", "unit", "source"):
                if req not in inp:
                    raise ValueError(f"Calculation input missing {req!r}: {inp}")
            if inp.get("value") is None or inp.get("source") is None:
                missing_inputs.append(inp.get("name", "unknown"))
            elif inp.get("is_assumed"):
                self.limitations.append(f"Input {inp['name']} is unverified assumption from {inp['source']}")

        if missing_inputs:
            self.result = None
            for mi in missing_inputs:
                if f"Missing required input: {mi}" not in self.gaps:
                    self.gaps.append(f"Missing required input: {mi}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "inputs": self.inputs,
            "result": self.result,
            "gaps": self.gaps,
            "limitations": self.limitations,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EngineeringCalculation:
        return cls(
            model=dict(data["model"]),
            inputs=list(data.get("inputs", [])),
            result=data.get("result"),
            gaps=list(data.get("gaps", [])),
            limitations=list(data.get("limitations", [])),
        )


# ---------------------------------------------------------------------------
# 2.4 CadExecutionJob Contract
# ---------------------------------------------------------------------------

CAD_JOB_STATES = frozenset({"queued", "running", "succeeded", "failed", "cancelled-before-start", "unknown"})


@dataclass
class CadExecutionJob:
    """External CAD execution job contract with timeout=unknown and no blind replay."""
    request_id: str
    payload_digest: str
    baseline_revision: str
    capability_revision: str
    state: Literal["queued", "running", "succeeded", "failed", "cancelled-before-start", "unknown"] = "queued"
    receipt: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("CadExecutionJob request_id is required")
        if not self.payload_digest:
            raise ValueError("CadExecutionJob payload_digest is required")
        if self.state not in CAD_JOB_STATES:
            raise ValueError(f"CadExecutionJob state must be in {sorted(CAD_JOB_STATES)}, got {self.state!r}")

    def cancel(self) -> bool:
        """Only queued jobs can be cancelled side-effect-free."""
        if self.state == "queued":
            self.state = "cancelled-before-start"
            return True
        return False

    def handle_timeout(self) -> None:
        """Running job timeout maps to unknown state; no blind replay."""
        if self.state == "running":
            self.state = "unknown"
            self.receipt = {
                "error": "EXECUTION_TIMEOUT",
                "message": "Job timed out during external CAD execution; outcome unknown; authoritative read-back required",
            }

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "payload_digest": self.payload_digest,
            "baseline_revision": self.baseline_revision,
            "capability_revision": self.capability_revision,
            "state": self.state,
            "receipt": self.receipt,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CadExecutionJob:
        return cls(
            request_id=str(data["request_id"]),
            payload_digest=str(data["payload_digest"]),
            baseline_revision=str(data["baseline_revision"]),
            capability_revision=str(data["capability_revision"]),
            state=data.get("state", "queued"),
            receipt=data.get("receipt"),
        )
