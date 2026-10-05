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
