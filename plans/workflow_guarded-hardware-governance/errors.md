# Errors: workflow_guarded-hardware-governance

## Outcome Codomain

Every functional module declares the COMPLETE set of states it can leave behind.
Mandatory classes: `ok` / `failed` / `not-run` — these are the three a bare
status collapses. `empty` (ran, produced nothing) and `indeterminate` (ran,
cannot decide) must be ADDRESSED: give a value, or a row with
`n/a (<reason>)` stating the module cannot produce it.

| Module | Value | Class | Means | Emitted at |
| ------ | ----- | ----- | ----- | ---------- |
| substate_machine | 0 | ok | State transition allowed and receipt generated | `substate_machine.py:advance` |
| substate_machine | 1 | failed | Transition blocked by unmet prerequisite gate | `substate_machine.py:advance` |
| substate_machine | 2 | empty | No transition requested (identity query) | `substate_machine.py:query` |
| substate_machine | -1 | not-run | State check bypassed in advisory mode | `substate_machine.py:advance` |
| substate_machine | n/a (deterministic FSM) | indeterminate | State engine is strictly deterministic | n/a (FSM) |
| blocker_hub | 0 | ok | Blocker logged and directed repair route dispatched | `blocker_hub.py:dispatch` |
| blocker_hub | 1 | failed | Blocker unroutable or retry threshold exceeded | `blocker_hub.py:dispatch` |
| blocker_hub | 2 | empty | Zero active blockers in system | `blocker_hub.py:query` |
| blocker_hub | -1 | not-run | Blocker processing skipped | `blocker_hub.py:dispatch` |
| blocker_hub | n/a (deterministic routing) | indeterminate | Routes mapped from static activity table | n/a (routing) |
| circuit_blocks | 0 | ok | Block instantiated and merged into netlist | `circuit_blocks/apply.py` |
| circuit_blocks | 1 | failed | Block parameters invalid or net conflict | `circuit_blocks/apply.py` |
| circuit_blocks | 2 | empty | Block declared with 0 optional passives | `circuit_blocks/apply.py` |
| circuit_blocks | -1 | not-run | Block application skipped (manual schematic entry) | `circuit_blocks/apply.py` |
| circuit_blocks | n/a (static schema) | indeterminate | Block schema is verified before load | n/a (static schema) |
| layout_tidy | 0 | ok | Geometries/silkscreen tidied without overlaps | `tidy/silk_tidy.py` |
| layout_tidy | 1 | failed | Overlap unresolved due to dense courtyard bounds | `tidy/silk_tidy.py` |
| layout_tidy | 2 | empty | Board already clean, 0 elements moved | `tidy/silk_tidy.py` |
| layout_tidy | -1 | not-run | Tidy skipped by caller option | `tidy/silk_tidy.py` |
| layout_tidy | n/a (deterministic geometry) | indeterminate | Geometry checks yield boolean intersection | n/a (geometry) |
| visual_drc_crop | 0 | ok | Crops generated for all DRC violations | `drc_crop.py:generate_crops` |
| visual_drc_crop | 1 | failed | Render failed or coordinate out of bounds | `drc_crop.py:generate_crops` |
| visual_drc_crop | 2 | empty | DRC clean (0 violations, 0 crops needed) | `drc_crop.py:generate_crops` |
| visual_drc_crop | -1 | not-run | DRC crop generation disabled | `drc_crop.py:generate_crops` |
| visual_drc_crop | n/a (pure image crop) | indeterminate | Image crop either renders or fails | n/a (pure image crop) |

## Error Catalogue

The `failed` region of the codomain above, in detail.

| Code | Condition | Surface | Recovery |
| ---- | --------- | ------- | -------- |
| `GOV_SELF_APPROVAL_PROHIBITED` | Authoring role attempts to self-approve or mint verification receipt | MCP error / exit 1 | Delegate verification to `verification-adversary` session |
| `GOV_CONTROL_VIOLATION` | Downstream agent attempts to mutate immutable upstream control artifact | MCP error / exit 1 | Route change request upstream through Activity A5 (Blocker Hub) |
| `GOV_TRANSITION_BLOCKED` | Attempt to advance state before prerequisite gate has passed | MCP tool error / CLI exit 1 | Run the prerequisite gate (e.g. `check_c03` or `placement_preflight`) and re-advance |
| `GOV_RECEIPT_INVALID` | Receipt signature mismatch, hash discrepancy, or missing `not_checked` | MCP tool error / CLI exit 1 | Re-execute the prior stage validation to mint a fresh receipt |
| `BLOCK_SCHEMA_INVALID` | Circuit block definition missing required ports or passives | Exception / exit 1 | Verify block definition schema against `CircuitBlockDefinition` specification |
| `BLOCK_PORT_CONFLICT` | Target net name collision during block application | Exception / exit 1 | Specify net prefix or rename conflicting net in schematic |
| `TIDY_COURTYARD_OVERFLOW` | Silk cannot be placed outside pad without colliding with neighbor | Warning / exit 1 | Reduce font size or relocate reference designator manually |
| `DRC_CROP_RENDER_FAILED` | PyGerber / EGL failed to render layer slice | Warning / exit 1 | Ensure display backend is available or fall back to SVG export |
