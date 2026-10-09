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

## 3.5 bundle

Subject: S36 HEAD `f8148a2b29bd88f3566008cbd1540c98b80ae353`; source manifest `435a63fe6f9fb02b26d008eeb5cef1d8c5fc80984601e19fb608b076b337eba1`. Landed only under `/home/pkcs12/products/bodesign/outputs/btdongle_ms/c03_engine-v1/bundle/`. No leaves regenerated; source `sha256sum -c hashes.sha256` after bundling returned exit 0 for every original file. No repo .py/server/compose/tasks edits, no stage/commit, no human-tree mirror.

### Served BOM and TOOL DEFECT

Six real UDS `/mcp/` calls to `bodesign_export_bom`, with container schematic paths and output `/work/experiments/s3-formal/bundle-bom/<leaf>/`. Args: group_by `Reference`, exclude_dnp false, include_excluded_from_bom true, xlsx false. Six call JSONs, six raw SSE responses and six served CSVs are retained in bundle `bom/` (raw served outputs, electrical axis). No refusal occurred. Each raw result is outer `ok:true`, result `status:ok`, `component_count:0`, `warnings:[]`, exclusion_audit `run`, excluded_dnp/from_bom empty, xlsx_path/netlist_path null. line_count per leaf = usbc 5, power_rail 4, battery 5, charge_enable 3, mcu_swd 6, io 4. CSV filenames returned `/work/experiments/s3-formal/bundle-bom/<leaf>/<leaf>-bom.csv`. Do NOT interpret component_count 0 as measured zero components.

TOOL DEFECT: served exporter merges unlike components even under group_by `Reference`, losing per-ref value/footprint association. Raw power_rail row, verbatim:

```csv
"C2-C5","10uF/16V,1uF/10V,22uF/10V","Capacitor_SMD:C_0402_1005Metric,Capacitor_SMD:C_0805_2012Metric","4",""
```

Dispatcher approved explicit method: **normalized from root native netlist; served export_bom retained raw**. Per-ref BOM `bom/normalized-root-bom.csv`, using existing parsed root `(components)` ref/value/footprint, not spec-derived manufacture. Cross-check `bom/bom_crosscheck.json`: expected_refs 45, native_refs 45, missing_count 0, extra_count 0, mismatch_count 0, duplicate_ref_count 0; empty missing/extra/mismatches lists. No export_bom code fix attempted; BR filing belongs to officer.

### Library binding and root subset

`library_pin_binding.json`: every used symbol (14 unique IDs / 45 refs), resolved container library path, full file SHA256 and full-symbol pin count via existing EE `resolve_symbol_library/load_symbol`. Connected consumed/native versus declared accounting is copied from original per-leaf fidelity_report.json (24/24,33/33,11/11,7/7,37/37,24/24), not hand-derived. Full symbol pin counts also include NC pins and are NOT conflated with connected counts. Current library files are bound; historical library-file identity at original S36 emission is not proven by those receipts.

Root netlist authority has 58 native nets including NC singletons. For each leaf, KiCad local `/NET` is explicitly qualified as `/<sheet>/NET`; global names remain unchanged. Literal unqualified differences recorded, not silently discarded. Count-only subset table in `netlist_subset_counts.json`:

| leaf | nets | matched qualified root names | absent names | nodes absent under matched names | literal unqualified name differences |
|---|---:|---:|---:|---:|---:|
| usbc | 5 | 5 | 0 | 0 | 3 |
| power_rail | 11 | 11 | 0 | 0 | 4 |
| battery | 4 | 4 | 0 | 0 | 1 |
| charge_enable | 5 | 5 | 0 | 0 | 1 |
| mcu_swd | 10 | 10 | 0 | 0 | 3 |
| io | 10 | 10 | 0 | 0 | 3 |

### Separate axes and reproducibility

Companion is plain `bundle/README.md`, per-leaf component/net/ERC counts, S1 verdict/class counts, SVG path. No PDF/docx generated. `c03_bundle_manifest-v1.json` has 84 file entries with independent electrical/form/provenance labels. Manifest excludes itself and bundle hash manifest to avoid circularity; bundle `hashes.sha256` covers the 84 listed files PLUS c03_bundle_manifest-v1.json. Hash manifest's own hash is external below.

ELECTRICAL: all original non-library ERC findings remain named ACCEPTED (raw reports not clean); original fidelity receipts retained; normalized BOM matches 45 refs with zero differences; all leaf nets are qualified subsets of root. FORM: S1 fail/indeterminate results and partial calibration retained verbatim, instrument `53acfd4b8399091b35db4eff9b80929a5f8e754ae2d782ee29b6cb5f74f029af`, policy `63bee5d02a5ec147`; no new visual acceptance.

Approved scratch-only scripts, reproducibility SHA256:
`3f67edc347880913d458d0e5dfc16ef462e11337493557d3519bf254c4cf6721` — `/home/pkcs12/.cache/scratch/s3-formal/bundle_library_pins.py` (stdin into EE python3, no container/source file edit).
`d3d0c3187e1c6576be9f0167f0bab4c99c4b8ca0d4c63547af2542814f78f38e` — `/home/pkcs12/.cache/scratch/s3-formal/assemble_bundle.py` (host assembly, existing native parsers).

Bundle manifest SHA256 `0038ab2c6eb755efbd47b6c11fece5c6e8e1916d12f84f4d2b277af3e3a7ca4f`.
Bundle hashes.sha256 SHA256 `5a602326a00bb3b879aa42a028f17c8b22d2ae11eff986bf96337c670e5dd4b5`.
Every landed file's sha256sum is in the exhaustive bundle hashes.sha256 (self-hash above); the full list follows below. `sha256sum -c hashes.sha256` returned exit **0**, every listed artifact OK (raw log `/home/pkcs12/.cache/scratch/s3-formal/bundle-hash-check.log`). Receipt-scoped `git diff --check` result recorded in DONE; no tests run, no Ran-lines claimed.

NOT MEASURED: visual review, AC18/AC19 acceptance, electrical design approval, release approval, S1 sensitivity or calibration completion, historical library-file byte identity, PCB/fab/license approval. Existing S1 partial state preserved. Architecture Sync: Verified (No doc changes); bundle-only provenance work. KB Distill: Verified (no new cross-repo lesson); the lossy grouping defect is recorded for officer BR rather than generalised into an unmeasured rule.

### 3.5 full landed SHA256 records

Hash-append scratch script: `/home/pkcs12/.cache/scratch/s3-formal/append_bundle_hashes.py`, SHA256 `e196deb9c095b4911b7ec015ffc4de34f410e5ccdc3766692e8e0026ca8b6ae4` (copies the raw manifest text into this receipt; no measurements).

Paths below are relative to bundle/. Raw sha256sum output:

```text
fe9130ddf53b70a299a399b2ffa78156dd84c6441be2e4a3ec85e67fac84462d  README.md
a5b596120ca26baa5ff0d5ef7f7ce8aa136e96ecbdad8ea8389de3331338fc66  bom/battery-bom.csv
2f1dfbd8e0a4f4468ae81fe0d3f28ffbcfa5c08f75e81cf44f9e8774d42784fd  bom/bom-call-battery.json
a7c2f59acb50ad489a2f7cf18945af9f206ad22996c9c7efbe89048a172e7eed  bom/bom-call-charge_enable.json
f9f6cab549c0f38a7047ebafdd2d7f3ce4562a82c43e199e0545e4194d133773  bom/bom-call-io.json
0377fae894b30f31cb22231068822acba67253b043395fb6df47964773164655  bom/bom-call-mcu_swd.json
fe57b90730e1b78ecc0c954f7bacfc37b3bfedf989483dbc643d7f95863a4552  bom/bom-call-power_rail.json
2a207958547b42b990b95771714f96977b8dfc736e4a513284cfcb4b124aa2a8  bom/bom-call-usbc.json
8812ed6eb1e11fd7ae518d92a1690294b19a39a92c325685b6c675798b7ba39d  bom/bom-response-battery.sse
a9315d7d6b77a49ba4e676092b0d8205e5acd59eda423105e94e5f35dd4cc6c4  bom/bom-response-charge_enable.sse
97b7a8a6b78b258a68775b36691451d58616758878c4607e9109f9aea7f9ec95  bom/bom-response-io.sse
297a65878dc023d08dd85b2fb59feb077ab861933193420a8254d1a0fd6d029f  bom/bom-response-mcu_swd.sse
1195c5be299f1909ea49f357c6e54237f4fce204a487a81fbead4d08d9de4e04  bom/bom-response-power_rail.sse
a8c9fb8162a40c030171309d68589651ae53f12a72829661dcea520d05d9c219  bom/bom-response-usbc.sse
36fbdbe9eefbd7a84b8bfbd47f2976d0d2f4278d151fe7a5a8b044c36c023372  bom/bom_crosscheck.json
d67bf646e1dc10900119106d5818ad27ba3c1bad7978f53824697cbd8a2bad17  bom/bom_per_ref.csv
187479efd756007966c88cd3d90e0a261ab516bfd9fd43cbd69b7a73f2ede43f  bom/charge_enable-bom.csv
30e50d56d59eadac3bf16ee01fb5ab3c286949288b6fcf36078bbee0ccbd8755  bom/io-bom.csv
d74c4cf3997bde4fe93a1a7c86726b3fc09ece3139152109a02a5fe7c8356f93  bom/mcu_swd-bom.csv
24bbe53ac43f2908d61d1436cb2c83e889663fd4dcbb1cc43b652e9ee7934223  bom/power_rail-bom.csv
135803240cc5e62a85abf710c500a6c15f4e48a18af661b176fddd44c62cc63c  bom/usbc-bom.csv
0038ab2c6eb755efbd47b6c11fece5c6e8e1916d12f84f4d2b277af3e3a7ca4f  c03_bundle_manifest-v1.json
605fe6726199a8cfbd4bd4fbbc0dcedf380d66679abc98737b5c3b14bd895c90  evidence/formal_invocation.json
435a63fe6f9fb02b26d008eeb5cef1d8c5fc80984601e19fb608b076b337eba1  evidence/hashes.sha256
6229031105d0aae5e069b51b4d0edda41e17f867e89d3eec71a8b7451c5b66f1  evidence/native/battery/battery.erc.json
eb8c11aa81fffdca037f9ccc9eadce06c6d4ba7948967021df2880ee28d23330  evidence/native/battery/battery.export-receipt.json
f36fd3ea596d2a49a1cb6674a1ef9afd97cabd79f740d64822db371b457d611e  evidence/native/battery/battery.net
afe4cbe3b0a86db6e56e5fa6cff2538b1bcd002206d38d3780e7073d849a2a16  evidence/native/battery/erc_adjudication.json
785e0fb1f518284d166bd86cc79b91515be8faa678e979e7255d6e464659edc3  evidence/native/battery/fidelity_report.json
4abadb3ba1c25a066c59b200671bd2df61c33289a1ff7646df2131701a6c586e  evidence/native/battery/s1_invocation.json
b57dd001f336832403a1a360dd31177d436d6ef891d0ce299bc3c9ee3fc9eb15  evidence/native/battery/s1_report.json
4a087de3f278e4450f4dff3fb263c322287fb02ba13d2205be67d9b95bc6b5fa  evidence/native/battery/svg/battery.svg
7ffc0b595ec37c5527057b158b5e783a1d69348af1b5dc33f1595e66cfaece49  evidence/native/charge_enable/charge_enable.erc.json
c2d3ec1dd782cb652153b1597ba48b72794acbcdaa98571785644fddb538bd87  evidence/native/charge_enable/charge_enable.export-receipt.json
7d8a92878737b1cab2b75a314cb3fc484cac5c4d6d1123a4f639088e3cfad204  evidence/native/charge_enable/charge_enable.net
58b8944e174db745347d662adc5728a51c124c707097822b5916320811b40420  evidence/native/charge_enable/erc_adjudication.json
348e2883aaa96aa2134d868b72389e1a336678ebd99e6ffe517d10d2ac07a8ed  evidence/native/charge_enable/fidelity_report.json
fcbcc010a8acd648985cb93339bcff5f5edb35ed6f663c6ab360192f43921b6f  evidence/native/charge_enable/s1_invocation.json
30eaa1a8dc6f18c1ce289dd2c799079e36e69b1e5a738970e9d3e3ee15a1a54a  evidence/native/charge_enable/s1_report.json
a5e68350cad582e683cd1df757ad0439003e7f43d9c4fc79508864afd1908315  evidence/native/charge_enable/svg/charge_enable.svg
dc26621fb15e3b4f84f2bc081ee55e3793a8fd712fb5708cd97de7af00c01336  evidence/native/io/erc_adjudication.json
72c693fc6db967f87c24f13f42f6409b08bfddacaa626fdb937a562a0072e300  evidence/native/io/fidelity_report.json
1fe45e753bc9dffec338d101eb9d2ce40e3db8c957e155710d19f3b8a2e470ff  evidence/native/io/io.erc.json
82f3d17586f397ac1df9e55ead07f9047690662701aeafce786e2e24b387d5c0  evidence/native/io/io.export-receipt.json
5fce37319835f00deeae4b6e652fa597fae1141cbba5bb9da9b24181e1770c01  evidence/native/io/io.net
7d813cd103b87ac1336eecbb42f8d02abb2e9e871728b232cbe3748917d7676b  evidence/native/io/s1_invocation.json
acfda709352468b68fd91ae800e0f3b655884e34ec95ddf8248540c523d9e170  evidence/native/io/s1_report.json
d25920db69c977d1f805336ed4f85b824d77cd2f9f2e84482a4b1b1bf52f613d  evidence/native/io/svg/io.svg
bb1a470246604b93e9a0a433c974d727e0f79a4e000bec6f7d05f074d0be26f3  evidence/native/mcu_swd/erc_adjudication.json
ee9784cca8df16233111a255a6269d5f4ad4bbb7e80f880c05634b649edc3b51  evidence/native/mcu_swd/fidelity_report.json
e1bf4b1c23bd3d6364ffecd7b940f91a70fa3aa6c707758257753cf34273a4e8  evidence/native/mcu_swd/mcu_swd.erc.json
65a1987f953871f1404f88a7db31eb21a5f36b2a80fef70ce3268afe611ba9d3  evidence/native/mcu_swd/mcu_swd.export-receipt.json
e483de3d7a20206642c171c70076b6c1e515db8ef9dc316234fb424bdc6c2a44  evidence/native/mcu_swd/mcu_swd.net
23d81b85c6a0d4ee9eff5bd3df2a9fc5506d8397b3856dd234399e92e4651628  evidence/native/mcu_swd/s1_invocation.json
8c1a64a53a31069948c3ca6f0b4f2d33257263ec0ac0adbded5adf5028ea4792  evidence/native/mcu_swd/s1_report.json
284bf6c68e1215f36f5aca7d9b42d7baae76c6be2fc2f53f90c2a166d93738c2  evidence/native/mcu_swd/svg/mcu_swd.svg
bc5e6403ef2ff48574e61a0766b0aa75505ceeb650f7a02afb9b42c4dd16e1bc  evidence/native/power_rail/erc_adjudication.json
d6e0d3c494641edbe2b1dbca88970179a2ced672ee6dc60b570b038d7bca8761  evidence/native/power_rail/fidelity_report.json
5a028222295cbda406acd2240c1a6c0d5d445469d6a62d42dae9e2ef791add35  evidence/native/power_rail/power_rail.erc.json
4c8af62710b32c2aa0a2d020a00897f035db99cd25ddd3f2c44c6832ea9bde62  evidence/native/power_rail/power_rail.export-receipt.json
e7122b0c5721108b4502897a6207cd8b2edbfe052c9a4d261ff22a61dda03e9d  evidence/native/power_rail/power_rail.net
6347cb3f8ddd657906d41c197f21b628fc050b7a077ad53fe1de2d6284f6c76d  evidence/native/power_rail/s1_invocation.json
aacdf14b9e50cd20c74e84baed94a527381891d37e6289c2feb600131580c410  evidence/native/power_rail/s1_report.json
5814ef486e6ed8da830683c804879aae5a5fb033a2cac99b743245dc122b707f  evidence/native/power_rail/svg/power_rail.svg
a4c3eefd88f5f25022673cdfe740e5c6b4a9bb6d8cf0684793c312bd8b5a3a77  evidence/native/root/btdongle_ms.erc.json
77f09e42e9a7420e32c9e09132d0f40ab8f1c7d1f86419acd69bf3ab875d4b82  evidence/native/root/btdongle_ms.net
2bc2ffef474951bf4acf6d41a1ba7d552f15785c7569eda3fb3e4b2b6a85f232  evidence/native/root/erc_adjudication.json
37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570  evidence/native/usbc/erc_adjudication.json
72c693fc6db967f87c24f13f42f6409b08bfddacaa626fdb937a562a0072e300  evidence/native/usbc/fidelity_report.json
9508fe9a1d8a03cbeec4cce6087d3145edae4d9779d48f9497368d089aaf51c6  evidence/native/usbc/s1_invocation.json
4ec65289f2f12c3a417338f839366239ae1f997da53d29495ae900c55e0a45f6  evidence/native/usbc/s1_report.json
652a88d35bb3c8d9c3e4a12787e9a3f9856a51ff98ea13c5cdba54952c4f4b8b  evidence/native/usbc/svg/usbc.svg
aae44e2ab470219533e3923658b7a59fbba4566c68f589050e8c510469e38a7d  evidence/native/usbc/usbc.erc.json
635aea1f6eb00e1449a366ee530ed835af12e1ecd62a341f6ea402797e620ca1  evidence/native/usbc/usbc.export-receipt.json
65625ea8b908aa7f89aa0c8e32050312912b7ae30ef9f65475a5a2e83ea552ad  evidence/native/usbc/usbc.net
86f26e7e2bee035c30f8b38267b8da2a95b94a83005621030c5688179aa2fa11  library_pin_binding.json
f756caa717a157faf12607e27612b3c8017913a41659fa8d7bc28ef630d05f0e  netlist_subset_counts.json
2e40bb8e3d90243c042435eee897cf12adb3094be31f199e04456750023a71b5  schematic/battery.kicad_sch
15a17e27a30b0284403a4c96c3b73578ded4be8722e3db25d13fda196e81de87  schematic/btdongle_ms.kicad_pro
f7d39262cbbd3b68d71849e94541232c23a47605e2ab3d1f491a38a58c4ac472  schematic/btdongle_ms.kicad_sch
f4a51f81a58f6466c34780f245258888b0084d660b20fff1def0ec458bac1fac  schematic/charge_enable.kicad_sch
5a397992572046917e918e8ee991c568b91c05ad889c3f150f6164c2d07f7345  schematic/io.kicad_sch
4d98e4902acc999b91d6a2f147ff2b44d3ef265e4fb5cabae7812d3508c7e4ac  schematic/mcu_swd.kicad_sch
db590af6b63e35f0bdf3f0b6121e5c17cec34391c79560df6040d81100fccfeb  schematic/power_rail.kicad_sch
c4bf003f88ffc50d23b0cedc8da594a2742110208e0b802346133476d45c2f6d  schematic/usbc.kicad_sch
5a602326a00bb3b879aa42a028f17c8b22d2ae11eff986bf96337c670e5dd4b5  hashes.sha256
```
