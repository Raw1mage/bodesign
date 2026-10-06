# S2 human-draft ingestion receipt (DD-13 / AC17)

Date 2026-10-06. Implementer: Sonnet 5.5 (ses_ef089c1a6ffeymTaPGOsmK17el). Dispatcher: ses_04db7a1c5ffelvbxyLP1p6xlRH.
Status: UNCOMMITTED working tree. Nothing committed, staged, reset, stashed or cleaned.

## Synthetic results do NOT satisfy AC17

The fixture is a synthetic native root + 2 leaves (`tests/fixtures/human_presentation/synthetic_root_2leaves`).
The bodesign emitter generated it once. Real kicad-cli 9.0.9 then loaded it. It proves the ingestion contract only.
The AC17 cell for a real user-authored draft is still PENDING the authorized human fixture.

## Landed files (sha256)

| file | sha256 |
| --- | --- |
| packages/eda-bridge/bodesign_eda_bridge/human_presentation.py | cc167dd4c1db6b6d5fab14562d44b25d0200ccc15475fab08be8fc300fdf2fcb |
| packages/workflow-core/bodesign_workflow_core/human_presentation.py | 154a957a498f9279eb3c4448917746aa593fb895335d33cf07af38ac1fe173b5 |
| tests/test_human_presentation.py | 3054f8b61071b06a62486e92dcca880948ddbbb7915758cadf35da05e58a20d2 |
| tests/test_human_presentation_entrypoint.py | 71f68205a180f6fc2d24395937d5a18b66b7e3250c2ecd9c156a84f1661588d5 |
| fixtures/.../brd.kicad_sch | ffee4599b6203510cc8cd0a5478d82bcc4765d69a78f37463be5e02e097d2398 |
| fixtures/.../mcu.kicad_sch | 2d588f890cdfbe4f07a45e1ee4c971bb3977be58f63379be4ea9addd96875ca6 |
| fixtures/.../power.kicad_sch | bde79bf16813925055e3d19579a982420a96fce95de471e46d562f94c539b742 |

`services/mcp/server.py` (authorized by the dispatcher, two hunks only):
`git diff --stat` BEFORE = 63 insertions (slice-A glue, untouched), AFTER = 70 insertions (+7 lines: 4 handler, 3 schema).
`git diff` sha256 before 3b0732e33845d812587475f72594f587e5a3d20c7cca0de4ceafa38b29a42519, after 5d9a2f82140bfba7b5f5f321ca6ef8d1f5696273e0cca1bb6e4bf114e20f6d18.
No other file was edited. No `__init__`, kicad_emit, composer, readability_*, hierarchical.py or child-plan edits.

## Design as built

- Entrypoint: the existing `bodesign_emit_multisheet`. When `presentation_baseline` is present, the handler returns
  `ingest_human_presentation(a)` and never falls through to the emitter. Required list unchanged; callers pass `spec: {}`.
- Manifest: `{schema_version 1.x, source:'human', source_dir (absolute), root, files:[{path,sha256}], libraries:[{name,version|digest}], kicad_version:'9.0', baseline_manifest_sha256?}`.
  Extra arguments are `declared_circuit {revision, nets, nc, isolated}` and `requested_operations` (default `[]`).
- Refusals are data (`ok:false`, `error.code`, `error.details.gaps[]`). Validation refusals happen before any write and carry `files:[]`.
  A failure AFTER the output workspace exists (derive, parse, report write) reports the real files on disk and the receipts already earned; it never reports `files:[]` (round 2, item 4).
  Codes: E_MISSING_SHEET, E_PATH_TRAVERSAL, E_PATH_ESCAPE, E_UNRESOLVED_LIBRARY, E_UNRESOLVED_IDENTITY, E_UNSUPPORTED_SYNTAX,
  E_BASELINE_CHANGED, E_SHEET_PARTITION_AMBIGUOUS, E_KICAD_VERSION, E_BASELINE_SPEC_CONFLICT, E_BASELINE_EMIT_ARGS,
  E_DECLARED_CIRCUIT_MISSING/MALFORMED, E_OPERATION_MALFORMED, E_OUTPUT_DIR.
- Sheet partition is read from the root's own `sheet` blocks. A declared file that is unreachable, or reached twice, is refused. Nothing is inferred.
- Supported native version: only stamp 20250114 (KiCad 9.0), which is the one exercised against the installed kicad-cli.
- Pinning: `locked_object_ids` is every `<sheet path>#<uuid>` in every sheet (sheet, symbol, pin, label, no_connect, ...). It is not a caller subset.
- Bytes: kicad-cli runs on a retained byte-copy under `out_dir/baseline_copy`. Source and copy are sha256-asserted before and after.
- Sidecars: netlist, ERC, BOM and SVG companions go in four separate directories. Each has a receipt with input hashes, output hash, kicad-cli path and version, exact argv.
- Topology: declared vs native export. Mismatch kinds: missing, split, fused, nc, isolated, undeclared_native. Each becomes a P1 `ChangeProposal` operation
  (`affected_ids`, `before`, `after`, `declared_circuit_revision`). `approval_ref=None`. The gate is P1 `check_baseline_preconditions` with EMPTY adapter capabilities,
  so every operation carries `ADAPTER_CAPABILITY_MISSING` and `allowed=false`.
- Value / footprint / annotation / add_label requests become proposal operations (`origin: caller_request`). Unknown targets get a `TARGET_NOT_FOUND` conflict.
  Object targets must be scoped `<sheet path>#<uuid>`. A bare uuid is not resolved.
- APPLY: `NOT_IMPLEMENTED`, reported in every response. No atomic compare-and-apply is claimed. The test `test_no_apply_function_exists` pins that no `apply_*` / `write_native*` / `commit_*` symbol exists.
- Source `human` conveys editing authority only. `does_not_authorize` lists electrical_correctness, readability, manufacturing_release, human_source_is_not_approval.

## Test populations (cwd repo; `./scripts/run_tests.sh` clears `__pycache__` first; rc is the real rc of the run, not of a pipe)

| population | command | Ran | failures | errors | skips | rc |
| --- | --- | --- | --- | --- | --- | --- |
| NEW INGESTION (round 1, superseded) | same command | 53 | 0 | 0 | 0 | 0 |
| NEW INGESTION (round 2, current) | `./scripts/run_tests.sh test_human_presentation test_human_presentation_entrypoint` | 91 | 0 | 0 | 0 | 0 |
| EXISTING CONTRACTS | `./scripts/run_tests.sh test_rebuild_contracts test_rebuild_freshness test_rebuild_adapter_parity test_rebuild_mechanical_contracts` | 67 | 0 | 0 | 0 | 0 |
| EXISTING ENTRYPOINT | `./scripts/run_tests.sh test_mcp_emit_multisheet test_multisheet_emit` | 46 | 0 | 0 | 0 | 0 |

Round-2 verbatim tails: `Ran 91 tests in 63.326s / OK`, `Ran 67 tests in 2.558s / OK`, `Ran 46 tests in 2.228s / OK` (rc 0, 0, 0; the script clears `__pycache__` first).
Round-1 tails: `Ran 53 tests in 34.245s / OK`, `Ran 67 / OK`, `Ran 46 / OK`.
NEW = 39 (test_human_presentation) + 14 (test_human_presentation_entrypoint). EXISTING CONTRACTS stays at the required 67.
HUNK 1 changed no existing entrypoint cell outcome: the 46 pre-existing cells are green and unmodified.
The skipUnless gate was never needed: the entrypoint tests ran only after the hunks landed. A missing kicad-cli raises in `setUpModule`, not a skip.

## Acceptance cells (mapped to the formal handler `bodesign_emit_multisheet`)

| cell | where | pins |
| --- | --- | --- |
| (1) bytes retained | `Cell1BytesRetained`, `FormalPath.test_cell1_*` | source and retained copy sha256 before/after; copy byte-equal; every `(uuid ...)` in the files is in the pin set; control: a mutated source raises E_BASELINE_CHANGED |
| (2) same topology | `Cell2SameTopology`, `FormalPath.test_cell2_*` | status `consistent`, no proposal, 4 separate sidecar dirs, receipts with input hashes and argv run on the copy |
| (3) mismatch | `Cell3TopologyMismatch` | missing, fused, declared-connected-but-NC, declared-connected-but-isolated, declared-NC-but-connected each give a proposal, `approval_ref=None`, `allowed=false`; control: matching declaration gives none |
| (4) changed baseline | `Cell4ChangedBaseline` | leaf edited after hashing, and wrong manifest digest, are refused with no write; control: correct digest accepted |
| (5) named-gap refusals | `Cell5RefuseWithNamedGap` (17 tests) | missing referenced sheet, missing file, traversal, absolute path, escaping symlink, undeclared library, symbol not embedded, duplicate identity, unsupported version, unparseable syntax, unsupported KiCad release, unreachable sheet, spec+baseline, restyle args, no declared circuit, out_dir inside source; control: unmodified set accepted |
| (6) metadata | `Cell6MetadataNeverChangesGeometry` | value / footprint / annotation / label requests become operations; bytes and the retained copy unchanged ("22k" absent from the copy) |

## Native commands, version, hashes (formal handler run on the fixture, out_dir outside the repo)

kicad-cli `/usr/bin/kicad-cli`, version `9.0.9`. Input native hashes are the three fixture hashes in the table above.
Baseline manifest sha256 (P1 `ArtifactManifest`, revision `rev-A`): `5283eead9902f635e02edc9d48c993f243c8989ada1bb722eb069ee417ffb176`.
Result: ok=True, status `consistent`, fixture bytes unchanged afterwards (diff of sha256 before/after was empty).

| sidecar | exact command (run on `<OUT>/baseline_copy/brd.kicad_sch`) | output sha256 |
| --- | --- | --- |
| netlist | `/usr/bin/kicad-cli sch export netlist --format kicadsexpr -o <OUT>/sidecars/netlist/native.net <root>` | af055c8568fb49af9b6f8d442b92661c49b8e4b4df12394aa2e26d1aa5fdc5ca |
| ERC | `/usr/bin/kicad-cli sch erc --format json --severity-all -o <OUT>/sidecars/erc/erc.json <root>` | f9438b58c9ed4a89fd53780a0e62420e9e43ca3699dc1aee55e5c868129465a7 |
| BOM | `/usr/bin/kicad-cli sch export bom -o <OUT>/sidecars/bom/bom.csv <root>` | cefe74466e654207c911a60b8eed8d937e514d7b9988bb4d57fc3db48b361c0f |
| SVG companion | `/usr/bin/kicad-cli sch export svg -o <OUT>/sidecars/companion_svg <root>` | brd.svg e6356090d5ae5599a6430bf5d6705ee80f33e47e9ffb1aadd3fc5edf4aaed780; brd-power.svg 81d230b077e1ce1edb2bc067aa0b2d5f62ca5c3105f2dc4c1e1a654324d5dcbb; brd-mcu.svg 99957aa9df8459b3411114d3a5dd64c96dd576319939c2ebed0f13f63a4f306d |

ERC note: the sidecar ERC reports violations (for example library `Device` not configured in the headless project, and unconnected pins). It is stored as evidence and not adjudicated. It is not a PASS or an approval.

## NOT measured / known limits

- Real user-authored draft (AC17 real cell): not run. No authorized human fixture was supplied.
- Apply is NOT IMPLEMENTED. "Approved candidate patches preserve untouched object spans" is therefore unverified in S2. There is no atomic compare-and-apply and none is claimed.
- Only native version stamp 20250114 (KiCad 9.0) is accepted. Older and newer stamps are refused, not parsed best-effort.
- Library check is by declared library name plus embedded `lib_symbols`. Library digests are carried as P1 `DependencyRef`s but not re-resolved against files on disk.
- Syntax coverage is the objects the synthetic fixture contains (symbol, label, global_label, no_connect, sheet, lib_symbols). Wires, junctions, buses, hierarchical labels and text are inventoried by head, but no fixture exercises them. Unknown heads are listed, not dropped.
- The retained copy is a plain byte copy in `out_dir`. No cross-process locking guards the source between hash and read. Changed-source detection is by hash only.
- Readability, ELK, router repair and detector (S1) were out of scope. No full-suite run was made, so no full-suite claim.
- No mutation or probe programme was run.

## Round 2 (Astra RETURN, 5 invariants)

Scope: the two `human_presentation.py` modules, the two test files, the fixtures and this receipt. `services/mcp/server.py` was not touched
in round 2 (its `git diff` sha256 is still 5d9a2f82140bfba7b5f5f321ca6ef8d1f5696273e0cca1bb6e4bf114e20f6d18).
New file sha256: E `7d1efc72bf22ce20fc6ef71ba1f8a342c59aa254aab0bd5e0e77d70311dd7a50`, W `743ee6d0068a92d944ea882ef188f7d4d00c12681843bf8aece8b6f546cd0009`,
tests `703ba72e673aacb10b926490f29d21c479ee4d3917af57966bfa9f1672fb3f28`, entrypoint tests `9e39efb3e1a5ab5371f8328ff8b95922122d0b854e3a85e0c6576650e8cf5d06`.
Test counts: `test_human_presentation` 72, `test_human_presentation_entrypoint` 19 (91 total).

| # | invariant | change | test cell | status |
| --- | --- | --- | --- | --- |
| 1 | source preservation / output aliases | `out_dir` must not exist at all (`os.path.lexists`, so symlinks, dangling links and files are refused) and is created exclusively. Fresh 0700 workspace + exclusive Python writes (`O_CREAT|O_EXCL|O_NOFOLLOW` for the files Python writes itself); tool-level writes (kicad-cli sidecars) are not flag-enforced. `derive_sidecars` refuses a non-empty or symlinked workspace. `files` lists only this invocation's own artifacts. | `R2_1OutputAliases` (7 tests), `Round2FormalPath.test_r1_*` | Landed. Symlinked and hardlinked report targets are refused with source bytes untouched. |
| 2 | topology false consistency | Duplicate declared net names are refused (`E_DECLARED_CIRCUIT_MALFORMED`). `compare_topology` keys fused/split on unique declared partition cells, not display names. An all-NC / all-isolated circuit (`nets: []`) is supported. A declaration of nothing is refused. | `R2_2PartitionIdentity` (5 tests), `Round2FormalPath.test_r2_*` | Landed. Same-label cells merged natively report `fused`. |
| 3 | declared subject binding | Canonical declared-circuit sha256 (revision, nets, nc, isolated). The proposal, gate, outcome and report are bound to a `subject_manifest_sha256` that adds it as a `source` dependency. Library identities are labelled caller-declared and unverified. `baseline_manifest_sha256` (native bytes + libs) is still returned separately. | `R2_3DeclaredSubjectBinding` (3 tests), `Round2FormalPath.test_r3_*` | Landed. Library digests are NOT re-resolved against disk. |
| 4 | derivation / failure honesty | An export succeeds only with rc 0 and exactly the expected non-empty output files (SVG: a COUNT of non-empty regular files equal to the sheet count; not per-sheet identity or content). `OSError` / timeout become failed receipts. Netlist failure gives `derive_status=failed`, a typed refusal that keeps the real files and receipts. Any other sidecar failure gives `derive_status=partial` with `ok:false` and `error.code=E_DERIVE_PARTIAL`; `topology_status` stays a separate field. ERC violations are findings (`erc_findings`). Parse and hash failures route through the typed refusal. | `R2_4DerivationHonesty` (9 tests), `Round2FormalPath.test_r4_*` | Landed. The blanket round-1 `files:[]` claim is narrowed above. |
| 5 | pin population | `native_pin_population` reads expected pins from each placed symbol's embedded definition (power symbols excluded). `reconcile_pin_population` refuses with `E_PIN_POPULATION_INCOMPLETE` when a pin is absent from the export, an exported node has no symbol pin, or a definition is unresolvable. Omitted pins are never assigned NC or isolated. | `R2_5PinPopulation` (3 tests) | Landed. |
| a | typed targets | `requested_operations` needs `target_kind` in `object` / `component` / `pin`. Each kind resolves only as itself; there is no cascade. Allowed kinds per edit class: set_value / set_footprint / set_annotation take object or component, add_label takes pin. Ambiguous component references are a conflict. `R2.1` is no longer accepted as an object target. | `R2_6TypedTargets` (6 tests), `Round2FormalPath.test_r5_*` | Landed. |

Control cells (each negative has a paired positive): `test_control_real_svg_export_meets_its_coverage`, `test_control_unpatched_export_reconciles_every_pin`,
`test_control_distinct_cells_native_distinct_report_nothing`.

### Still NOT measured after round 2
- Real-user-draft AC17 (synthetic fixture only).
- Apply is NOT IMPLEMENTED.
- Hardlink aliasing of the SOURCE files themselves is not detected; only outputs are protected, by fresh-workspace exclusivity.
- A race that swaps the source between hash and read is detected by hash only. There is no locking.
- The pin population covers placed symbols with embedded definitions. Symbols using `extends` are reported as unresolved and refuse; multi-unit symbols read units 0 and the placed unit only.
- The failure paths for ERC timeout, OSError, BOM failure and an unreadable netlist are exercised by mocking `_run_export` / `subprocess.run`. A real kicad-cli timeout was not induced.

## Round 3 (Astra r2 RETURN: output-validation remainder of invariant 4)

Scope: the two `human_presentation.py` modules, `tests/test_human_presentation.py`, this receipt. `server.py` untouched
(`git diff` sha256 still 5d9a2f82140bfba7b5f5f321ca6ef8d1f5696273e0cca1bb6e4bf114e20f6d18).
File sha256: E `18d671c8c768419a76238076599210f9bc58cf85806d6c9086918c437717e9ad`, W `cf9df1a382571563eff8768fd102493fd721a08c2103dbfaab140a924a97af30`,
tests `cac3cfc859da4ee0554106a9cd278edbaf4cb5c601d70d8f475a3bd842186f10`, entrypoint tests `9e39efb3e1a5ab5371f8328ff8b95922122d0b854e3a85e0c6576650e8cf5d06` (unchanged).

| # | item | change | test cell | status |
| --- | --- | --- | --- | --- |
| A | ERC output validation | `erc_findings` validates: valid JSON, top-level object, `sheets` list, each sheet an object with a `violations` list, each violation an object with a non-empty string `severity`. Any failure raises typed `E_OUTPUT_INVALID` (gap `kind=output_validation, tool=erc`). `derive_sidecars` catches it, adds `erc` to `failed_sidecars` and `output_validation_failures`, keeps the rc=0 receipt (`status=succeeded`) and the file, and sets `erc_findings={unusable,...}` (no `total`, so never zero findings). Derive becomes `partial`, so W returns `ok=false`, `E_DERIVE_PARTIAL`. Real ERC violations remain findings and `ok=true`. | `R3_OutputValidation.test_erc_parser_rejects_each_malformed_shape` (10 shapes: invalid text, `[]`, `null`, number, no sheets, sheets not list, sheet not object, no violations, violation not object, missing severity); `test_malformed_erc_output_makes_derive_partial_and_keeps_the_rc0_receipt` (real kicad-cli, output overwritten after run, rc stays 0); controls `test_erc_parser_control_valid_shapes`, `test_control_real_erc_violations_stay_findings_and_ok` | Landed |
| B | netlist parser shape validation | `parse_native_connectivity` raises typed `E_OUTPUT_INVALID` (`tool=netlist`) on: unparseable s-expression, root not `export`, missing `nets`/`components`, net without name, node missing ref or pin (including empty atoms), comp missing ref. No catch-all; W's existing `ValueError` route returns the typed refusal with files and receipts. | `test_netlist_parser_rejects_each_malformed_shape` (11 real malformed S-expressions through the real parser); `test_malformed_netlist_is_a_typed_refusal_with_files_and_receipts` (missing ref / missing pin / empty atoms injected into the real formal path; source hashes unchanged); control `test_netlist_parser_control_valid_shape` | Landed |

W additionally surfaces `output_validation_failures` in the result, the report and the `DERIVE_PARTIAL` outcome details.
Receipt precision edits applied to round-2 rows 1 and 4.

Populations (`./scripts/run_tests.sh`, pycache cleared by the script; rc is the run's own):

| Population | Ran | Failures / errors / skips | rc |
| --- | --- | --- | --- |
| NEW INGESTION (`test_human_presentation test_human_presentation_entrypoint`) | 98 (79 + 19) | 0 / 0 / 0 | 0 |
| EXISTING CONTRACTS | 67 | 0 / 0 / 0 | 0 |
| EXISTING ENTRYPOINT (`test_mcp_emit_multisheet test_multisheet_emit`) | 46 | 0 / 0 / 0 | 0 |

### Not measured after round 3
- Real-user-draft AC17; apply stays NOT IMPLEMENTED; no full-suite run.
- ERC validation checks structure and `severity` type only, not that the findings are semantically complete. The injected malformed outputs overwrite a real run's file, so a kicad-cli that itself emits such output was not observed.
- Netlist validation covers the fields the comparison consumes; other netlist sections are not validated.
- Earlier "not measured" items (source hardlinks, hash-to-read race, `extends` symbols, mocked timeouts) are unchanged.
