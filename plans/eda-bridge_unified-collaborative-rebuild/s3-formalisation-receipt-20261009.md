# S3 formalisation receipt — 2026-10-09

Status: worker deliverables complete; officer phase acceptance pending. Draft, NON-FABRICABLE; human_approved false.
Authority: freeze §4.19 R-K, content first. Task 3.3c remains unchecked for officer acceptance.

## Landed surface

Changed `services/mcp/server.py` handler/schema plus the specifically approved EE membership, `tests/test_mcp_server.py`, and `tests/test_worker_group_routing.py`. Five optional top-level arguments declared: `layout_engine` (enum `["elk-layered"]`), `engine_placement_models` (string array), `engine_spacing_overrides` (object of strings), `engine_orientation_sets` (object of string arrays), `engine_outline_refs` (string array).

Handler forwards top-level values as kwargs and removes their embedded counterparts from a COPY of spec. Embedded-only R7 calls remain supported. `engine_arg_source` records per-key `top-level` / `spec` on handler success and typed engine refusal. Direct engine conflict semantics are unchanged. Two new tests cover schema and spec/top-level/both/mixed/legacy precedence without mutating the caller's spec.

`BODESIGN_DEV=1 ./mcpctl.sh restart` succeeded: `bodesign MCP restarted (dev: live source, no rebuild); socket -> /home/pkcs12/projects/bodesign/.run/bodesign.sock`.

## Served evidence

Real initialized Streamable HTTP session through the UDS at `http://127.0.0.1/mcp/`. `tools/list` returned HTTP 200 and exposed all five arguments above. Raw SSE: `/home/pkcs12/.cache/scratch/s3-formal/tools-list-served.txt`.

Invocation args (verbatim, minus spec body):

```json
{
  "connection_style": "wire",
  "out_dir": "/work/experiments/s3-formal/c03_engine-v1/",
  "power_ports": false,
  "project_name": "btdongle_ms",
  "subsystem_views": {
    "battery": ["BAT_EXT", "NTC"],
    "charge_enable": ["CHG_LED_A", "ENPPB"],
    "mcu_swd": ["SWCLK", "SWDIO"],
    "power_rail": ["BATT", "SYS"],
    "usbc": ["CC1", "CC2", "VBUS_CON"]
  },
  "symbol_dirs": [
    "/app/packages/eda-bridge/vendor_symbols",
    "/work/products/thesmart_products/04.btdongle/C03-EE/02_build/sch_gen",
    "/usr/share/kicad/symbols"
  ],
  "engine_placement_models": ["R0", "M2-R1|D1|R2"],
  "engine_spacing_overrides": {
    "elk.layered.spacing.nodeNodeBetweenLayers": "6.35",
    "elk.spacing.nodeNode": "3.81"
  },
  "layout_engine": "elk-layered"
}
```

Spec sha256 (`jq -cS`, including trailing newline): `30ad8b5226a59a5b87a235291ed38c397722de05a173cde31241b6971447723d`.
Successful full call: output `formal_invocation.json`, sourced from `/home/pkcs12/.cache/scratch/s3-formal/formal-call-ee.json`. Spec content is unchanged vs R7 except engine parameters moved to the top level; no electrical spec fix was needed.

Initial attempt, before dispatcher transport ruling (HTTP 200; application FAILURE):

```text
event: message
data: {"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"{\n  \"ok\": false,\n  \"error\": \"PermissionError: [Errno 13] Permission denied: '/home/pkcs12'\"\n}"}],"isError":false}}
```

That initial call returned no engine_reports, sheet_count or unresolved_pins. Dev compose mounts products read-only at `/work/products`, not the original host absolute path. Dispatcher ruled this an expected transport mismatch, not a defect, and approved the experiments rw path plus host-side landing. No mount, permission or compose change was made.

## Per-leaf content and S1

| Leaf | Model | Pins native/declared | ERC non-lib raw → unadjudicated | lib count | S1 a,b,c,d,e,f counts | S1 overall | Sheet SHA256 |
|---|---|---|---|---|---|---|---|
| usbc | M2-R1\|D1\|R2 | 24/24 | 0→0 | 6 | 0,0,0,0,1,0 | fail | c4bf003f88ffc50d23b0cedc8da594a2742110208e0b802346133476d45c2f6d |
| power_rail | R0 | 33/33 | 7→0 accepted 7 | 9 | 0,0,0,0,8,5 | indeterminate | db590af6b63e35f0bdf3f0b6121e5c17cec34391c79560df6040d81100fccfeb |
| battery | R0 | 11/11 | 1→0 accepted 1 | 5 | 0,0,0,0,1,1 | fail | 2e40bb8e3d90243c042435eee897cf12adb3094be31f199e04456750023a71b5 |
| charge_enable | R0 | 7/7 | 3→0 accepted 3 | 3 | 0,0,0,0,0,0 | indeterminate | f4a51f81a58f6466c34780f245258888b0084d660b20fff1def0ec458bac1fac |
| mcu_swd | R0 | 37/37 | 6→0 accepted 6 | 10 | 0,1,0,0,2,0 | indeterminate | 4d98e4902acc999b91d6a2f147ff2b44d3ef265e4fb5cabae7812d3508c7e4ac |
| io | R0 | 24/24 | 3→0 accepted 3 | 12 | 0,0,0,0,0,0 | indeterminate | 5a397992572046917e918e8ee991c568b91c05ad889c3f150f6164c2d07f7345 |

Native exports and ERC were run in the EE container (kicad-cli 9.0.9). Native connected pin populations equal declared populations on every leaf, with missing/extra/name_mismatch empty; NC pins are outside that connected-pin population. All reports are under `native/<leaf>/`. Root ERC: 49 total, 45 lib_symbol_issues, 4 non-lib ACCEPTED; raw counts remain 49/4, not an ERC-clean claim. Frozen S1 instrument hash verified `53acfd4b8399091b35db4eff9b80929a5f8e754ae2d782ee29b6cb5f74f029af`; calibration record `8680263115f4373d37674654e2db97fc8f0a286c1d79a19ef7917469b2fdcc1b`, policy `63bee5d02a5ec147`. No tuning performed. Calibration is partial, evidence_authenticated false on every leaf. Explicit pair/exemption recipe retains the R7 sheet-local star rule; it is not a new officer-approved readability rule.

Class e is E_LABEL_FLAG_CORRIDOR (1/8/1/0/2/0); class f contains F_TEXT_TEXT_OVERLAP x2 + F_FLAG_THROUGH_TEXT x3 on power_rail, F_FLAG_THROUGH_TEXT x1 on battery. mcu_swd b is B2_FOREIGN_CROSS_NO_DOT x1. These are recorded, not repaired or phase gates. PAIR_PAGE_MISMATCH remains on power_rail (A4 portrait), mcu_swd and io (A3 portrait); no instrument alteration. Fail/indeterminate verdicts are not softened.

## Transport ruling and second call

Dispatcher approved served `out_dir=/work/experiments/s3-formal/c03_engine-v1/` and subsequent HOST-side copy to products; `/work/products` stays read-only. Initial PermissionError is an expected host/container transport mismatch, not a defect.

Second call HTTP 200 returned inner `ok:false`, `E_ENGINE_REFUSED` / `E_ELK_SYMBOL_UNRESOLVED` on usbc. Missing Connector.kicad_sym, Device.kicad_sym and Bodesign_Presentation.kicad_sym in the original symbol_dirs. Raw SSE at `scratch/s3-formal/emit-container-served.txt`. `engine_arg_source` records top-level for layout_engine, engine_placement_models, engine_spacing_overrides.

Confirmed ROUTING DEFECT: `_EE_GROUP_TOOLS` omitted `bodesign_emit_multisheet`, therefore `_group_of` assigned core without native symbols/toolchain. Dispatcher explicitly approved that single membership correction and routing assertion test. Approved container symbol_dirs were verified inside EE by `docker compose exec bodesign-ee ls -ld`: all three existed. Second dev restart recreated EE; `mcpctl.sh status` later reported core, ME and EE healthy. Successful served call is the EE-routing proof; tools/list exposes the new schema but not a group annotation. No fallback, compose change or permission change.

## Regression evidence

Explicit requested `find . -name __pycache__ -prune -exec rm -rf {} +` executed before final populations. No test_hierarchical* module exists; hierarchical coverage is the six listed multisheet modules. Raw logs are under `/home/pkcs12/.cache/scratch/s3-formal/`.

```text
test_elk_layout:
Ran 21 tests in 2.819s
OK
test_readability_render:
Ran 114 tests in 17.079s
OK
test_sheet_partition test_multisheet_emit test_multisheet_global_label_link test_replica_emit test_replica_fidelity test_mcp_emit_multisheet:
Ran 117 tests in 7.876s
OK
test_mcp_server BEFORE:
Ran 49 tests in 2.060s
FAILED (failures=4, errors=2, skipped=3)
test_mcp_server AFTER, pycache cleared:
Ran 51 tests in 1.985s
FAILED (failures=4, errors=2, skipped=3)
```

Unchanged red names before and after:
- ERROR test_removed_tool_call_returns_typed_tool_landed
- ERROR test_run_tool_c00_scaffold_prd
- FAIL test_converged_registry_tool_count
- FAIL test_landed_verbs_mirror_gate_registry
- FAIL test_registry_is_well_formed
- FAIL test_run_tool_c01_next_question_and_update_answers

`git diff --check` passed. New tests account for the 49→51 population delta. No existing red was fixed.

## NOT MEASURED / remaining

Visual review deferred per §4.19 item 4. Five-leaf AC19 NOT claimed; AC16 remains partial. Full suite, whole-root partition diff including NC/replica populations, rotated/mirrored S1, typography/flag-placement repair, page-use tuning, library pin-type repair, PCB/fab/license/electrical design approval not measured or claimed. Class b crossing remains a recorded visual ambiguity, not an asserted electrical short (native partitions match). No human-tree changes, staging or commits. Architecture Sync: Verified (No doc changes); existing architecture EE native boundary is restored, not redesigned. KB Distill: Verified (no new cross-repo lesson this round); this repeats the already documented worker-membership omission failure mode (`tests/test_worker_group_routing.py`), not a new general concept.

## Successful served result and ERC adjudication

Raw JSON is attached as `emit_result.json`; raw HTTP SSE as `emit-served.sse`. Inner result: `ok:true`, `emit_mode:hierarchical`, `sheet_count:6`, `unresolved_pins:{}`. `engine_arg_source` is top-level for layout_engine, engine_placement_models, engine_spacing_overrides. Unprovided orientation/outline args remain unprovided (R7 identity/default recipe). Every leaf has engine_reports with graph/solution hashes, elkjs 0.12.0 and Node v22.23.3; usbc chooses the declared M2 model, the five other leaves choose declared R0 and record M2 candidate refusal. No legacy-router fallback.

Adjudication applies to findings from THIS export, not R7. No spec fixes / rerun for content were necessary. The raw non-lib counts are unchanged; the after column above counts UNADJUDICATED findings, not rewritten ERC results. Every original finding and named reason is attached in `native/<leaf>/erc_adjudication.json`, including root.

| Scope | Finding | Count | Decision / evidence |
|---|---|---|---|
| power_rail | global_label_dangling ENPPB, NTC, STAT | 3 | ACCEPTED cross-sheet continuation; spec declares counterpart pins and native root has them |
| power_rail | pin_not_driven U1.8 ENPPB, U1.7 NTC | 2 | ACCEPTED standalone excludes passive switch/connector controls; root does not retain these findings |
| power_rail | power_pin_not_driven U1.2 IN | 1 | ACCEPTED external VBUS feed via passive connector/fuse; no declared power_out/PWR_FLAG driver annotation; root VBUS endpoints match spec |
| power_rail | power_pin_not_driven U1.5 PGND | 1 | ACCEPTED standalone return continuation; root GND contains it and warning disappears |
| battery | global_label_dangling NTC | 1 | ACCEPTED continuation to U1.7; root net contains J2.2, R5.1, U1.7 |
| charge_enable | global_label_dangling ENPPB, STAT, BATT | 3 | ACCEPTED declared continuation to power_rail |
| mcu_swd | global_label_dangling LED_BT, LED_WIFI, SW_USER, VBAT_SENSE | 4 | ACCEPTED declared continuation to io |
| mcu_swd | power_pin_not_driven U2.39 VSYS | 1 | ACCEPTED standalone excludes U1.1 SYS power_out; native root SYS contains both |
| mcu_swd | pin_to_pin U2.3 GND / U2.33 AGND | 1 | ACCEPTED library types mark both power_out; declared common GND is intact, not fusion of different supply nets |
| io | global_label_dangling LED_BT, LED_WIFI, BATT | 3 | ACCEPTED declared cross-sheet continuation |
| root | global_label_dangling NTC, ENPPB | 2 | ACCEPTED lone-label warning on electrically complete replica-view nets; root native NTC and ENPPB contain ALL declared endpoints |
| root | power_pin_not_driven U1.2 IN | 1 | ACCEPTED external VBUS drive-annotation gap, same reason as leaf; not source adequacy approval |
| root | pin_to_pin U2.3 / U2.33 | 1 | ACCEPTED declared common ground vs symbol power_out typing; not library/datasheet approval |

Final regression recheck after approved routing edit (verbatim):

```text
test_elk_layout: Ran 21 tests in 2.667s
OK
test_readability_render: Ran 114 tests in 16.961s
OK
multisheet six modules above: Ran 117 tests in 7.321s
OK
test_worker_group_routing: Ran 8 tests in 4.942s
OK
test_mcp_server: Ran 51 tests in 1.953s
FAILED (failures=4, errors=2, skipped=3)
```

Compared with R7: formal top-level MCP surface, served EE routing rather than host direct handler, container-path invocation + host landing, native EE exports and explicit non-lib ERC adjudication, frozen newer S1 instrument (R7 used f98dc237/policy 443bbb0185d5a914), and per-class flag-corridor findings now recorded. Circuit specification and declared placement recipe are not tuned.

## Hashes and host landing

Source: `/home/pkcs12/projects/bodesign/experiments/s3-formal/c03_engine-v1/`.
Landed by approved HOST-side `cp -r`: `/home/pkcs12/products/bodesign/outputs/btdongle_ms/c03_engine-v1/`.

Both locations contain `hashes.sha256`, listing every artifact file except the manifest itself (self-hash is reported separately). `sha256sum -c hashes.sha256` passed for EVERY listed file at BOTH locations. Host hashes were independently recomputed into `/home/pkcs12/.cache/scratch/s3-formal/landed-hashes.sha256`; `cmp` against source manifest returned exit 0. All three manifest bytes have SHA256 `435a63fe6f9fb02b26d008eeb5cef1d8c5fc80984601e19fb608b076b337eba1`.

Changed source SHA256:

```text
a78d8ab1f5d92cb4e72152e679296be78b9d3fb2b997ee5db56b9c2b491025b3  services/mcp/server.py
6c1882c1e8668ecd7f0e61be9713d29713b73b300d4b9691fbbab7760d3efc8f  tests/test_mcp_server.py
a73b87926e376741a4682090472f1af74febeda2d975b781a4f462bc06036b3b  tests/test_worker_group_routing.py
```

Receipt hash is in the BRNS-DONE report, not self-embedded here. No top-level human presentation tree was touched. No commits/staging, image rebuild, forbidden-path edits, readability instrument edits or engine-routing-semantics edits. All initial blockers were resolved by the two explicit dispatcher rulings, not by silent substitutions.
