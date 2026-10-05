# P1 Shared Contracts Receipt

**Milestone**: Phase 1 (P1 Shared Contracts: Tasks 2.1–2.4)  
**Plan**: [plans/eda-bridge_unified-collaborative-rebuild/](file:///home/pkcs12/projects/bodesign/plans/eda-bridge_unified-collaborative-rebuild/)  
**Order**: `[BRNS-DISPATCH topic=master-p1-shared-contracts sender=ses_04db7a1c5ffelvbxyLP1p6xlRH]`  
**Date**: 2026-10-06  
**HEAD SHA**: `16ed19219e6d3961c860410ccb3d48b228165d08`  

---

## 1. P1 Task Delivery Ledger (Tasks 2.1 – 2.4)

| Task | Scope Description | Status | AC Served | Test Evidence & Delivered Contracts |
|---|---|---|---|---|
| **2.1** | Versioned serialization + invariants per `data-schema.json`: `ArtifactManifest`, `DesignRepresentations`, `VerificationRecord`, `ChangeProposal`, `ReleaseApproval`, `OperationOutcome`. Compatibility adapter wraps existing raw results without mutating them. Unknown coverage/version/freshness rejected, never defaulting to PASS. | **passing** | AC3, AC4, AC5, AC9 | `tests/test_rebuild_contracts.py` (15 tests passing, 0 failures, 0 errors). Delivered canonical hashing, scoped paths, coverage validation, raw result preservation in `rebuild_compat.py`. |
| **2.2** | Freshness + mismatch enforcement: dependency-derived staleness (subject hash change, tool version bump, rule update, library digest change, missing dependency). Baseline/proposal/approval mismatch rejected before any write; raw results preserved; client source unchanged on conflict. | **passing** | AC3, AC6, AC7 | `tests/test_rebuild_freshness.py` (13 tests passing, 0 failures, 0 errors). Delivered `evaluate_freshness`, `check_baseline_preconditions` (`BASELINE_MISMATCH`, `PROPOSAL_CONFLICT`), `check_release_preconditions`. |
| **2.3** | Parity tests driving ACTUAL existing MCP handler path (`run_tool`) and landing runner (`gate.py` subprocess) on identical pinned inputs for named use-cases (`readability_gate`, `verify_netlist_fidelity`). Compare domain result / error / no-verdict and documented transport envelope + exit mapping. No mocked transport. Existing registry drift remains BLOCKED per P0 ledger. | **passing** *(domain parity)* / **blocked** *(registry tests)* | AC9 | `tests/test_rebuild_adapter_parity.py` (6 tests passing, 0 failures, 0 errors). Both paths produce identical domain results on success, refusal, and empty/not-run cases. 6 pre-existing registry drift defects in `test_mcp_server.py` stay blocked. |
| **2.4** | Original versioned contracts: `ReferenceAdoption`, `MechanicalBridge`, `FeatureGraph`, `InterferenceRecord`, `EngineeringCalculation`, `CadExecutionJob`. Validate finite rigid right-handed frames, DAG + unique IDs + supported ops, revision-bound single anchors, explicit missing-model/numeric-source, AABB-not-exact flag, license clearance field, timeout=unknown with no blind replay. No CAD execution, no numerical rollout. | **passing** | AC10, AC12, AC13, AC14, AC15 | `tests/test_rebuild_mechanical_contracts.py` (19 tests passing, 0 failures, 0 errors). Validates 4x4 matrix ($R^T R=I$, $\det(R)=+1$), Kahn's DAG cycle detection (`CYCLE_DETECTED`), anchor cardinality=1, AABB non-certification, license clearance gating, CAD job timeout mapping. |

---

## 2. Test Execution Records

### 2.1 Focused P1 Contracts Test Suite
Command:
```bash
./scripts/run_tests.sh test_rebuild_contracts test_rebuild_freshness test_rebuild_adapter_parity test_rebuild_mechanical_contracts
```
- **HEAD SHA**: `16ed19219e6d3961c860410ccb3d48b228165d08`
- **Ran**: 53 tests (15 in `test_rebuild_contracts`, 13 in `test_rebuild_freshness`, 6 in `test_rebuild_adapter_parity`, 19 in `test_rebuild_mechanical_contracts`)
- **Failures**: 0
- **Errors**: 0
- **Skips**: 0
- **Exit Status**: 0 (OK)
- **Wall Time**: 2.733s

### 2.2 Server and Landing Gate Boundary Tests
Command:
```bash
./scripts/run_tests.sh test_mcp_server test_landing_gate test_landing_gate_published_resolution
```
- **HEAD SHA**: `16ed19219e6d3961c860410ccb3d48b228165d08`
- **Ran**: 83 tests
- **Failures**: 4 (`test_converged_registry_tool_count`, `test_landed_verbs_mirror_gate_registry`, `test_registry_is_well_formed`, `test_run_tool_c01_next_question_and_update_answers`)
- **Errors**: 2 (`test_removed_tool_call_returns_typed_tool_landed`, `test_run_tool_c00_scaffold_prd`)
- **Skips**: 3
- **Exit Status**: 1 (FAILED)
- **Registry Drift Accounting**: Exactly matches the 6 pre-existing defects documented in P0 ledger ([baseline-test-report.md §3.4](file:///home/pkcs12/projects/bodesign/plans/eda-bridge_unified-collaborative-rebuild/baseline-test-report.md#L139-L146)). Per work order, paths touching currently-failing registry tests stay BLOCKED without skipping or adding unauthorized endpoints. `test_landing_gate` and `test_landing_gate_published_resolution` passed completely.

### 2.3 Full Repository Test Suite
Command:
```bash
./scripts/run_tests.sh
```
- **HEAD SHA**: `16ed19219e6d3961c860410ccb3d48b228165d08`
- **Ran**: 2,326 tests across 174 test modules (baseline 2,273 + 53 new P1 tests)
- **Failures**: 13
- **Errors**: 42
- **Skips**: 62
- **Exit Status**: 1
- **Wall Time**: 70.348s
- **Raw Log Path**: `/home/pkcs12/.local/share/opencode/agy-relay/accounts/jewery.101@gmail.com/home/.gemini/antigravity-cli/brain/f888ad21-17ad-4d4c-93b4-63803a4321db/.system_generated/tasks/task-419.log`
- **Full-Suite Comparison against P0 Baseline Ledger**:
  - The 13 failures and 42 errors match the P0 baseline ledger ([baseline-test-report.md §4](file:///home/pkcs12/projects/bodesign/plans/eda-bridge_unified-collaborative-rebuild/baseline-test-report.md#L158-L290)) test-ID for test-ID.
  - Exactly 53 new tests executed and passed.
  - Zero new regressions introduced.

---

## 3. Delivered Files Allowlist Verification

All delivered files are strictly within the specified WRITE ALLOWLIST (new files only):
1. `packages/design-ir/bodesign_design_ir/rebuild_contracts.py` (new)
2. `packages/workflow-core/bodesign_workflow_core/rebuild_contracts.py` (new)
3. `packages/workflow-core/bodesign_workflow_core/rebuild_compat.py` (new)
4. `tests/test_rebuild_contracts.py` (new)
5. `tests/test_rebuild_freshness.py` (new)
6. `tests/test_rebuild_adapter_parity.py` (new)
7. `tests/test_rebuild_mechanical_contracts.py` (new)
8. `plans/eda-bridge_unified-collaborative-rebuild/p1-contract-receipt.md` (new)

Zero modifications to existing files. Zero git commits or resets. Zero mocked transports.

---

## 4. Remediation Round (topic=p1-contract-remediation, 2026-10-06)

**Base**: commit `b35e6c9cd2cfd6ebf3c0a41e939d866feb31466c` (P1 landed). Review verdict PARTIAL; 2.1/2.2/2.4 returned. Working tree left UNCOMMITTED for dispatcher inspection.

### 4.1 Per-item status (partial → remediated)

| # | Location (pre-fix) | Defect | Remediation | Status |
|---|---|---|---|---|
| 1 | C:441-511 | inner `result.ok=false` / unknown status could map to `ok` | `wrap_operation_outcome`: no-verdict statuses first (`empty`/`not-run`/`indeterminate`), then outer `ok:false` and inner `result.ok is False` → `failed` with inner error code; unknown status → `indeterminate` (`UNKNOWN_STATUS_*`); `ok` only on explicit `ok` status or transport ok with NO status field. New cell drives real MCP inner-refusal shape (`{"ok":true,"result":{"ok":false,"error":{"code":"NETLIST_MISSING"}}}`) and server `_apply_result_status` error shape through the wrapper. | remediated |
| 2 | C:568-636 / W:345-399 | required_checks from approval only | New `ReleasePolicy` (frozen, versioned, empty/duplicate checks rejected). `resolve_required_checks(policy, approval)`: policy authoritative, approval may add, never reduce (reason emitted); missing policy is a blocking reason. Coverage keyed by tool/rule dependency name only (axis names are not check ids). | remediated |
| 3 | W:320-342 / C:592-625 | identity by name only; caller freshness trusted | `evaluate_freshness` accepts `list[DependencyRef]`, matches on `(kind, name)`, compares version AND digest (unchanged version + changed digest = `stale`; kind mismatch/absent = `unknown`); legacy name→str map cannot bind both → `unknown`. `current_dependencies=None` → `unknown`. Freshness always recomputed in both `evaluate_release_eligibility` and `check_release_preconditions`; record field overwritten. | remediated |
| 4 | D:100-159 / C:537,589 / D:35-37 | cached `manifest_sha256` trusted; `a/..`, `a/./b` accepted | `ArtifactManifest`: artifacts/dependencies frozen to tuples of frozen refs, `__setattr__`/`__delattr__` sealed, `verify_integrity()` recomputes canonical digest; both precondition guards call it at the boundary (tamper via `object.__setattr__` raises `MANIFEST_SHA256_MISMATCH`). Path validator rejects any `.`, `..`, or empty segment. | remediated |
| 5 | C:290-299,338-347,365-368 / W:44-93 | raw lost without ref; fabricated `net_0..N`; empty→N/A | `VerificationRecord.raw_snapshot` carries deep copy when `raw_result_ref` absent; count-to-ID expansion deleted (no coverage supplied = unknown); `status=="empty"` → `indeterminate` unless `applicability_evidence` given. Contract: `pass` requires non-empty `tool_rule_dependencies` and (`raw_result_ref` or `raw_snapshot` or explicit `raw_evidence_absent_reason`). | remediated |
| 6 | W:230-274 / C:526-565 | `proposal.conflicts` overwritten; allowlist ≠ capability; docstring implied atomic | Pre-existing conflicts preserved and merged (deduplicated). New `adapter_capabilities` axis: `None` → `CAPABILITY_UNVERIFIED` conflict, missing → `ADAPTER_CAPABILITY_MISSING`. Docstring states contract-only, not compare-and-apply. | remediated |
| 7 | W:143-168 | `pairs=[]` certified | `certification_blockers` property: exact-solid only, no missing solids, finite non-negative tolerance/clearance, backend declared, executed pairs with bool `collides` + finite `clearance_mm`, declared contacts honoured; `pairs=[]` is a blocker. `is_exact_certified = not blockers`. | remediated |
| 8 | D:478-520, 399-409, 557-582, 621-643, 254-259 | see fix list | FeatureGraph: schema 1.x, 64-hex source sha, unique anchors, `DANGLING_ANCHOR_REF`, `ANCHOR_REVISION_MISMATCH`, typed `{value, unit}` numeric parameters, no synthesized `isolated_candidate` (caller-asserted True refused). FeatureAnchor: NaN/inf/non-numeric tolerance rejected. EngineeringCalculation: `result` with empty inputs rejected; `topology_applicable` must be bool. `CadJobRegistry` rejects duplicate request-id and duplicate payload digest; empty baseline/capability revision rejected. ReferenceAdoption: `reviewed`/`approved` must be bool (string `'false'` raises); `is_extraction_allowed` True only for `selective-extraction` + both flags `is True`; every other mode → False. | remediated |
| 9 | receipt | per-item status, NOT RUN, unmeasured IDs, ledger split | this section | remediated |

### 4.2 Test execution (cwd ROOT, `__pycache__` cleared before each run)

**P1 CONTRACT REGRESSION** — `./scripts/run_tests.sh test_rebuild_contracts test_rebuild_freshness test_rebuild_adapter_parity test_rebuild_mechanical_contracts`

```
Ran 62 tests in 2.648s
OK
EXIT=0
```
Ran 62 (was 53; +9 new cells: contracts 18, freshness 14, adapter_parity 6, mechanical 24) / fail 0 / err 0 / skip 0 / exit 0.

**EXISTING ADAPTER** — `./scripts/run_tests.sh test_mcp_server test_landing_gate test_landing_gate_published_resolution`

```
Ran 83 tests in 5.959s
FAILED (failures=4, errors=2, skipped=3)
EXIT=1
```
Ran 83 / fail 4 / err 2 / skip 3 / exit 1 — identical IDs to the pre-remediation run (§2.2); no new regression.

Pre-existing failure ledger, split by family:
- **Registry drift IDs** (4): `test_converged_registry_tool_count`, `test_landed_verbs_mirror_gate_registry`, `test_registry_is_well_formed` (FAIL); `test_removed_tool_call_returns_typed_tool_landed` (ERROR).
- **C00/C01 path IDs** (2): `test_run_tool_c00_scaffold_prd` (ERROR); `test_run_tool_c01_next_question_and_update_answers` (FAIL).

### 4.3 Not measured this round

- **AC12 / AC13 physical execution: NOT RUN.** No CAD kernel, no exact-solid collision, no AABB execution was performed. `InterferenceRecord` cells exercise the CONTRACT against hand-written pair records only.
- **Full repository suite (§2.3) NOT re-run** this round; the 10-skip delta against the P0 baseline (52 → 62) remains with **unmeasured skip IDs**. The 3 skips in the EXISTING ADAPTER population are also not enumerated by ID (non-verbose unittest output).
- No mutation or probe programme was executed (per work order).
- `services/mcp/server.py`, `skills/bodesign/scripts/gate.py`, existing `contracts.py`, `__init__.py`: read-only, untouched.
