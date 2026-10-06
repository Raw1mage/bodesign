# S3 Engine Spike Receipt — elkjs layered, one usbc leaf (DD-15 / AC18 checkpoint)

Worker: ses_ef06f84feffecMAhyjhMV7Mq6P (Fable 5.1). Dispatcher: ses_04db7a1c5ffelvbxyLP1p6xlRH.
Date: 2026-10-06. Status: **spike, first-leaf checkpoint — NOT calibrated PASS, NOT five-leaf delivery.**
Nothing committed. Tree edits only. No mutation/probe programme. No KB distillation.

Run directory: `/home/pkcs12/.cache/scratch/s3-elk-spike/run-20261006-133234/` (hash manifest `hashes.sha256`,
tree manifest `tree_hashes.sha256`, `npm_ls.txt`, `costs.json`).

## 1. Landed files (uncommitted)

| path | sha256 | state |
|---|---|---|
| `packages/eda-bridge/elk/package.json` | `1fc85f6e…4a17` | new |
| `packages/eda-bridge/elk/package-lock.json` | `2fad01ff…c71e2b` | new; `integrity` == clearance value `sha512-YZcKynxV…rhEQ==` (verbatim match) |
| `packages/eda-bridge/elk/runner.cjs` | `7b63c55e…d617` | new; stdin JSON → stdout JSON; exit 2 malformed / 3 layout / 4 watchdog |
| `packages/eda-bridge/elk/LICENSE.elkjs.md` | `637e81f4…00c9` | copy of `node_modules/elkjs/LICENSE.md` (same hash) |
| `packages/eda-bridge/elk/node_modules/` | — | `npm ci` output, 8,046,654 bytes, NOT gitignored (repo has no node_modules rule; left for officer ruling) |
| `packages/eda-bridge/bodesign_eda_bridge/elk_layout.py` | `e752fdd7…79bf` | new, 908 lines |
| `packages/eda-bridge/bodesign_eda_bridge/hierarchical.py` | `798373b4…40ab` | slice-A untracked file + narrow engine edits (see §3) |
| `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py` | `ed553414…d35d` | slice-A dirty + 3 narrow hunks (see §3); `git diff --stat HEAD` = +296/−48 (slice A was +262/−48) |
| `packages/eda-bridge/THIRD_PARTY_NOTICES.md` | `b9777c38…9164` | new (elkjs EPL-2.0 entry + Node runtime entry) |
| `tests/test_elk_layout.py` | `895c28f1…1fd3` | new |
| `Dockerfile.ee` | `04639953…7396` | +34 lines, **edited, unbuilt, unmeasured** |

Allowlist respected: `Dockerfile`, `Dockerfile.core`, `Dockerfile.me`, `services/mcp/server.py`, `readability_render.py`
untouched by me (readability_render.py sha256 `da682255…ea69` == amendment 2 identity).

## 2. Clearance conditions 3–6 — what was done

- **Node** (cond. 4): `https://nodejs.org/dist/v22.23.3/node-v22.23.3-linux-x64.tar.xz`, sha256
  `df450af89261115ef9f9e3830c3eeb2cc9213b63c720b1af623cb5dcbe2e02de`; `sha256sum -c` against `SHASUMS256.txt`: `OK`.
  `SHASUMS256.txt.sig` verified: `gpg: Good signature from "Antoine du Hamel …"`, primary key
  `5BE8 A3F6 C8A5 C01D 106C 0AD8 20B1 A390 B168 D356` (listed in nodejs/release-keys `keys.list`). Key is
  `[unknown]` trust (not certified in my keyring) — the match to the published release-keys list is the evidence.
  Host install (for the spike) under `~/.cache/scratch/s3-elk-spike/node/opt` (`node v22.23.3`, `npm 10.9.9`).
  Host `/usr/bin/node` is v18.19.1 and has no npm; it was NOT used.
- **elkjs** (cond. 3/5): `npm ci --omit=dev --ignore-scripts --no-audit --no-fund` → `added 1 package`.
  `npm ls --all` verbatim:
  ```
  bodesign-elk-runner@0.1.0 /home/pkcs12/projects/bodesign/packages/eda-bridge/elk
  └── elkjs@0.12.0
  ```
  `node_modules/` contains only `elkjs` (12 files). `web-worker` not installed; runner loads `elkjs/lib/elk.bundled.js`
  in-process. One Node child per `solve_sheet`; timeout / nonzero / non-JSON → `ElkLayoutError` (never legacy router).
- **Dockerfile.ee** (cond. 4/6): tarball layer with `ARG NODE_VERSION=22.23.3`, `ARG NODE_SHA256_LINUX_X64=df45…02de`,
  `uname -m` switch failing explicitly on non-x86_64, `xz-utils` prerequisite, `npm ci` + lock-graph count check
  (`npm ls --parseable` must list exactly 1 `node_modules` entry) + `require('elkjs/lib/elk.bundled.js')`. No placeholders.
  **Not built** (WSL containers retired per brief; CT105 not touched). Image/build deltas: **unmeasured**.
- **Notices** (cond. 1/2/5): `THIRD_PARTY_NOTICES.md` written with EPL-2.0 selected, the §3.1–3.3 obligations stated as
  release-owner obligations, and the per-artifact scan of GWT build inputs recorded as still owed.

## 3. Seam edits (narrow)

`hierarchical.py`:
- `LAYOUT_ENGINE_ELK = "elk-layered"`, `_GND_RE` (module constants).
- `emit_hierarchical_schematic(..., layout_engine: str | None = None)`; inside the leaf loop, immediately before the
  legacy `auto_layout`/`layout_sheet` block: engine branch builds the drawn-net policy (forced labels from the DD-14 slice
  bound, GND → continuation), calls `elk_layout.solve_sheet`, replaces `leaf_components` poses, records
  `symbol_boxes[name]` / `engine_reports[name]`, passes `presentation_solution=` to `emit_kicad_schematic`. Unknown engine
  name → `E_ENGINE_UNKNOWN`; engine refusal → `E_ENGINE_REFUSED` (wraps the `ElkLayoutError` code+details). `elif auto_layout`
  keeps the legacy block byte-for-byte when `layout_engine is None`.
- `emit_multisheet`: `spec["layout_engine"]` / kwarg merge; both set and different → `E_ENGINE_CONFLICT`.
- `HierarchicalEmitResult.engine_reports` + `to_dict()` now also exposes `engine_reports` and `page_fit` (needed so the
  formal handler's response carries the engine evidence; no server.py change).

`kicad_emit.py`:
- `emit_kicad_schematic(..., presentation_solution=None)` kwarg + docstring.
- Engine block before `motif_ground_points`: refuses motifs (`ENGINE_MOTIF_UNSUPPORTED`), refuses drawn nets the cross-IC
  policy wanted on labels (`ENGINE_POLICY_CONFLICT`), checks every solution pin tip against `_pin_abs` (`ENGINE_PIN_DRIFT`),
  then emits the solution's segments/junctions/label anchors through the existing `_reserve_wire` / `_wire_segment_block` /
  `_record_run` / `_junction_block` / `_place_local_label` bookkeeping; undrawn nets take the legacy label/power continuation.
- The three legacy loops iterate `_legacy_nets` (== `nets` on the legacy path, `[]` on the engine path). No other line
  of the legacy router changed.

Post-emission `fit_page` ran on the engine leaf and reported `already_fits` (dx=dy=0, A4): the validated solution was
not translated.

## 4. Formal invocation (exact)

`services/mcp/server.py:_h_emit_multisheet` called in-process with `formal_invocation.json`
(sha256 `7437b178…b025`): `out_dir`, `project_name="btdongle_ms"`, `spec` = guest btdongle design via
`experiments/btdongle_multisheet_e2e.build_spec` + `SHEET_OF_REF` + measured replicas, **plus `spec["layout_engine"]="elk-layered"`**,
`symbol_dirs=[guest sch_gen, /usr/share/kicad/symbols]`, `power_ports=False`, `connection_style="wire"`,
`subsystem_views` from `measure_subsystem_placement`. Result `ok: true`, `emit_mode: hierarchical`, 6 leaves + root.
All six leaves went through the engine (0 fused / 0 missing / 0 misrouted each, per `emit_result.json.engine_reports`);
**only usbc was exported, rendered, S1-measured and is submitted.** The other five are unreviewed by-products.

Native commands (kicad-cli 9.0.9, cwd = run dir), recorded in `native/usbc.export-receipt.json`:
```
kicad-cli sch export netlist --format kicadsexpr -o native/usbc.net out/usbc.kicad_sch      rc=0
kicad-cli sch export svg -o native/svg --no-background-color out/usbc.kicad_sch            rc=0
kicad-cli sch erc -o native/usbc.erc.json --format json --severity-all out/usbc.kicad_sch   "Found 6 violations" (all lib_symbol_issues)
convert -density 150 native/svg/usbc.svg -background white -flatten native/usbc.png        (ImageMagick; PNG is a convenience raster, SVG is the native render)
```

## 5. Artifact hashes (usbc candidate)

```
dcfdc6b2e6ac2d830922b6e56cd02190ccd30439dc3e495dc66918ba20095bf5  out/usbc.kicad_sch
49dc81417259a3958a762e6476c704ea41d135d0e3e805eb1b656b06d42bc41a  out/btdongle_ms.kicad_sch
aed12f2f50943e7293e5d8c3df91450716423f23d2971ee11d16c230e164fa8a  native/usbc.net           (FRESH export; archived CP3 .net not used)
28bd7d5e7355ec5e6711439700d18fb4c564c8ce7899a18cee45679c398e91c8  native/svg/usbc.svg
2dae808c94cba07301c3be3bdb44a4078635b49cf8f417f0a0b0e04f24122b21  native/usbc.png
a3968387573711a8db769f0195acaf69d0086115b62904716dfd0c996637765c  native/usbc.erc.json
58e79522652937b2dc86d4ed6276afb782678ef8d7a37c74560acd0b6fe7b659  native/usbc.export-receipt.json
780d6c81dd26fcf99c1635ae2427b9da8a1e43e509c1e22e09d756f2f07dc0f3  s1_invocation.json
5ea61a374a70454ff316f95f588e326c7739a741595fbb1e7dda4f34b4f4d11b  s1_report.json
d39a2b9162663c5983daf29926ea55d70d2223b07dc913e89e18f61626f1ef84  fidelity_report.json
0e8c162a744832db412c4781b1eeeba74f13c37c5cbc0daddd79119dd31b1c8d  elk_graph_usbc.json
```
Engine receipt (usbc): graph `0492bf0f…b7cf`, solution `e1a59ee6…724c`, runner `7b63c55e…d617`, elkjs 0.12.0, node v22.23.3.

## 6. Native fidelity (`fidelity_report.json`)

Regenerated `native/usbc.net` vs declared circuit restricted to usbc refs: declared pins 24 / native pins 24; declared
classes 5 / native classes 5; **fused 0 / missing 0 / misrouted 0**; pins missing in native: none. Net names: engine-drawn
local nets export as sheet-local `/CC1 /CC2 /VBUS_CON`; `GND` and `VBUS` keep global names via global labels (expected).
ERC: 6 × `lib_symbol_issues` only (library-vs-embedded symbol notes, pre-existing class); **0 connectivity violations**
(no `wire_dangling` / `pin_not_connected` / `label_dangling` / `unconnected_wire_endpoint`).
`check_replica_display_fidelity`: `empty` (usbc requests 0 replica views — nothing to examine, not a pass).

Engine-internal verification (pre-serialization): 20 segments, 3 junctions (one per 3-branch net), 14 pins examined,
0 problems. Grid: BRANDES_KOEPF + grid-multiple spacings returned every node origin and edge point on 1.27 mm already;
quantization was an identity check on this graph (measured, see `elk_layout.py` DEFAULT_LAYOUT_OPTIONS comment).

## 7. S1 diagnostics (`s1_report.json`, invocation `s1_invocation.json`)

Instrument: `readability_render.py` sha256 `da6822556ea743e97f51c797a97a18d4ae367cb5bd217b9d2580a598f5b8ea69`,
policy `s1-readability-policy-v1` digest `<in s1_invocation.json>`, calibration record `s1-calibration-record-v2` built by
`tests/test_readability_render._calibration_record()` with NO accepting entries (CP3 rejecting ×3 only; `_HYPOTHETICAL_YES`
not used — asserted in the run). `required_local_pairs` mode **explicit**: 10 pairs (root pin → each other pin of every
engine-drawn net, declared order). `local_exceptions`: 10 GND pins, reason "continuation: GND carried by global_label".
`declared_pin_nets`: 24 entries from the declared circuit. Provenance: **verified** (receipt hashes match).

| field | value |
|---|---|
| `verdict` | **fail** |
| `scoped_verdict` (a–e) | **fail** |
| `calibration_ref.status` | partial (`partial_classes = a,b,c,d,e`), `evidence_authenticated = False` |
| anomalies | none |

Per class: a pass (0 findings) · **b fail — 1 finding `B2_FOREIGN_CROSS_NO_DOT`: `/VBUS_CON × /CC1` cross at (73.66, 58.42)
without a dot** · c pass (13 pins omitted under named exceptions/K) · d pass · e pass · f pass with applicability
"partial: text-vs-text and wire-through-text only; text-vs-symbol-graphics NOT measured"; page_use bbox 0.096 / grid 0.049
(not gated); min_font 1.69 mm; 0 text overlaps; 0 wire-through-text.

Honest reading: the brief predicted `overall indeterminate`; the leaf instead returns `fail` because the instrument found
a hard class-b defect under verified lineage (precedence: a class FAIL outranks partial calibration). The crossing is
electrically a non-contact (netlist proves it) but is the "crossing without junction reads as a short" pattern the pause
note names. I probed 10 ELK option variants + 3 model orders (`elk_graph_usbc.json` is the submitted one): every variant
yields exactly 1 foreign crossing on this graph (VBUS_CON×CC1 or CC1×CC2); `forceNodeModelOrder` / `INTERACTIVE` produce
fused solutions that the verifier refuses. **I did not tune the result away** — a NO is a valid spike finding.

Uncalibrated transforms: none — all six symbols are rotation 0, no mirror (engine does not rotate).

## 8. Tests (verbatim; `find . -name __pycache__ -prune -exec rm -rf {} +` before each population)

| population | Ran | fail | error | skip | exit |
|---|---|---|---|---|---|
| S3 BRIDGE `test_elk_layout` | 5 | 0 | 0 | 0 | 0 |
| SEAMS `test_kicad_emit_seams test_composer test_motifs test_visual_companion` | 57 | 0 | **3** | 0 | 1 |
| MULTISHEET `test_sheet_partition test_multisheet_emit test_multisheet_global_label_link test_replica_emit test_replica_fidelity test_mcp_emit_multisheet` | 117 | 0 | 0 | 0 | 0 |
| S1 DIAGNOSTIC `test_readability_render` | 43 | 0 | 0 | 0 | 0 |
| CONTRACT REGRESSION `test_rebuild_contracts test_rebuild_freshness test_rebuild_adapter_parity test_rebuild_mechanical_contracts` | 67 | 0 | 0 | 0 | 0 |
| legacy control `test_p2_leaf_delivery` | 4 | 0 | 0 | 0 | 0 |

SEAMS errors: `test_composer.ComposerTests.test_compose_validates_with_kicad_cli` (`KeyError: 'MID'`),
`test_motifs.MotifIntegrationTests.test_divider_emits_junction_wires_and_local_ground` and
`test_macro_survives_compaction_and_page_fill` (`MOTIF_GROUND_FUSION: GND at (153.67, 115.57)`).
**Control**: a detached worktree at HEAD with the working-tree `bodesign_eda_bridge/*.py` overlaid and my three
`kicad_emit.py` hunks mechanically removed (control file 4559 lines vs treatment 4669) reproduces the identical 3 errors
(`Ran 24 / errors=3`). They are pre-existing in the slice-A dirty tree, not introduced by the engine edits. Not fixed
(legacy router frozen). Full suite not run.

## 9. Measured costs (`costs.json`, host WSL, 3 runs each, `/usr/bin/time -v`)

| item | value |
|---|---|
| cold start trivial 3-node graph (node spawn → solution) | 0.261–0.273 s wall, max RSS 85–87 MB |
| cold start usbc leaf (6 nodes, 7 edges) | 0.298–0.309 s wall, max RSS 91–93 MB |
| in-emit `wall_s` (per `engine_reports`, 6 leaves) | 0.277–0.319 s |
| Node tarball / extracted | 31,001,304 B / 196,362,571 B |
| `node_modules/elkjs` | 8,046,654 B |
| Docker image delta, `docker build` wall (cold/warm), `npm ci` network bytes | **unmeasured** (image not built) |

## 10. Unmeasured / not done / named gaps

- Dockerfile.ee: edited, unbuilt, unmeasured. Monolith `Dockerfile` not touched (engine unsupported there, cond. 6).
- Motif compound nodes: `E_ELK_UNSUPPORTED_MOTIF` / `ENGINE_MOTIF_UNSUPPORTED` — refused, not implemented (usbc has none).
- Text extents: refdes/value/label boxes are approximated to ELK as a 3.81 mm node margin, not measured; S1 class f
  measured 0 text overlaps on this leaf, text-vs-symbol-graphics remains unmeasured by S1 itself.
- Only one leaf exported/measured; the other five engine leaves exist in `out/` but are unreviewed.
- `node_modules/` sits untracked in the tree; whether to gitignore it is the officer's ruling.
- `npm ci` network bytes not captured; registry `dist.integrity` matched the clearance value at install.
- GPG trust: release key matched `nodejs/release-keys`, not certified by a local trust path.
- Independent fresh-eyes review: not performed by me (dispatcher's reviewer).

## R2. Round 2 candidate (Sonnet 5.5; run dir `/home/pkcs12/.cache/scratch/s3-elk-spike/run-20261006-150709`, sibling of immutable run-20261006-133234)

Status: **candidate for independent review; S1 scoped verdict = fail (one class-b crossing); not claimed as PASS.**
Manifest: `hashes.sha256` in the run dir binds every output, the render chain, the S1/declared inputs and the changed source files.

Changes (engine path only): (1) `elk_layout.plan_node_ink` reserves actual symbol hull + Reference/Value text + pin-tip flag boxes (emitter text model) per node; ELK layered IGNORES input `elk.margins` (measured identical placement with margins absent/20 mm), so each reserved side is carried by an empty OUTSIDE node label of that extent. (2) `place_ink` post-layout: Reference/Value, local labels (own-net wire anchor, text box not crossed by any wire except touching at the anchor), cross-sheet continuation flags; typed refusals E_ELK_INK_CONFLICT / E_ELK_PROP_NO_POSITION / E_ELK_LABEL_NO_POSITION / E_ELK_FLAG_NO_POSITION, no reroute/relabel. (3) `kicad_emit` consumes `presentation_solution.props/local_labels/flags` on the engine path only. (4) Bounded variants (12; spacing/order/root/model-order options; no scaling, no rotation, FIXED_POS kept); chosen = fewest foreign crossings then smallest area; all outcomes persisted in `emit_result.json.engine_reports.usbc.variant_log`. (5) Spacings reduced (nodeNode 5.08, layers 10.16). (6) T-vs-foreign-X regression in tests/test_elk_layout.py (fresh native export).

Residual defect: foreign crossing CC1 x CC2 at (69.85, 69.85) remains (moved from VBUS_CON x CC1 at (73.66, 58.42)). 12 variants + 3 extra bounded probes (layerChoiceConstraint, interactive crossing-min, explicit node-order permutations) gave minimum 1 crossing; this is NOT a proven lower bound. Model constraint as observed: J1 east pins fixed in order VBUS(A4) < CC1(A5) < CC2(B5), D1 pins fixed in a different vertical order, and the two CC branches each need an R between J1 and the D1 column; ELK layered layers nodes in columns and orders by barycentre, which interleaves the two CC trunks. Not swept further per ruling.

## R3. Round 3 slice (D1 native-orientation extension; Sonnet 5.5; sibling run dir to be named in §R3.4)

### R3.1 Predeclared transform set (written BEFORE any R3 run)

Component: **D1 only** (`Power_Protection:PESD5V0L4UF`, same lib symbol, unit 1, pin numbers, declared net map). All other components stay at identity; no combinations; no alternate J1 unit; no pin swap; no redraw.

| id | native serialization | pin local map (y-up) | pin angle map |
|---|---|---|---|
| R0 (identity) | `(at x y 0)` | (x, y) | a |
| R180 | `(at x y 180)` | (-x, -y) | a+180 |
| MX | `(at x y 0) (mirror x)` | (x, -y) | 360-a |
| MY | `(at x y 0) (mirror y)` | (-x, y) | 180-a |

Total = 4 orientations (identity included), within the <=4 ceiling. Each orientation is run with ONE layout variant, the R2-selected `model-order` (no further ordering sweep). Selection key: foreign crossings, then layout area, then declaration order (identity first). The transform maps are asserted against a fresh `kicad-cli` netlist export per orientation (round-trip), not trusted from this table.
Field justification: measured on a scratch copy before implementation (KiCad 9.0.9 SVG): R180 and MY flip a `(justify left)` field to grow leftward from its anchor; R0 and MX do not. The emitter therefore writes `(justify right)` for R180/MY so the rendered text matches the modelled ink box; this is re-measured on the final export.

### R3.2 Changes (engine path only)

`kicad_emit.py`: `ORIENTATIONS` table, `orient_point/orient_pin_angle/orient_pins/orient_rect`, `_symbol_instance_block(orientation=)` writes `(at x y rot) (mirror ..)` plus field justification; the engine path maps the embedded symbol's pin map and rects with the same functions (definition text is not edited). Refused, typed: unknown id, ref not embedded, visible pin names under a transform, one lib symbol placed with two orientations. `elk_layout.py`: `resolve_symbol_geometry(orientations=)`, `solve_sheet(orientation_sets=)` (ONE ref, R0 first, <=4 ids, no repeats, no combinations; each id run with the single R2-selected `model-order` variant), `PresentationSolution.orientations/orientation_sweep`. `hierarchical.py`: spec key `engine_orientation_sets` -> solve_sheet, sweep recorded in `engine_reports`. Rotation order: native rotation is serialized as `(at x y rot)` and `(mirror ..)` as separate tokens, KiCad applies mirror after rotation; only rot 0/180 with mirror none/x/y are used (no 90/270).

### R3.3 Result (run `/home/pkcs12/.cache/scratch/s3-elk-spike/run-20261006-161258`)

Sweep (D1, variant model-order, foreign crossings / area mm2): R0 1 / 5765.47 (CC1xCC2 at 69.85,69.85); R180 2 / 7521.28; MX 3 / 6353.21; MY 1 / 7305.15 (CC1xVBUS_CON). All four connectivity-verified. Selection key picks **R0 (identity)**: no declared transform removed the crossing; the best non-identity (MY) ties on count and has larger area. R180/MX reverse D1's vertical pin order (6,4,3,1) and add crossings against VBUS_CON. Consequence: the selected candidate is the R2 geometry; its PNG sha256 equals R2's (70335b15...), the sheet differs only in uuids. The carried reviewer items (VBUS_CON text at the wire corner, VBUS flag near F1, page use, GND flag vs D1 text) are therefore unchanged and were not separately fixed in R3; D1 bare glyphs unchanged (ruling 5).
Fresh native export: 24/24 pins, 5/5 classes, 0 fused/0 missing/0 misrouted; ERC 6 `lib_symbol_issues` only. S1 (instrument 9c18bc51..., policy 443bbb01..., real-evidence record, scope a-e, required_local_pairs explicit list): a,c,d,e,f pass; b fail (B2_FOREIGN_CROSS_NO_DOT at 69.85,69.85); calibration partial/evidence_authenticated=false. The selected D1 is rotation 0 / no mirror, so no uncalibrated transform entered the candidate; R180/MX/MY variants were evaluated by the engine only and not S1-measured or reviewed.
Constraint for architectural decision: with FIXED_POS ports, J1 fixed, D1 limited to the four declared native orientations, and the two CC branches each requiring a series resistor between J1 and D1, ELK layered with the bounded variant set yields >=1 CC crossing; orientation is not the lever.
Tests (verbatim): S3 bridge Ran 11 OK exit 0 (incl. per-transform native round-trip); MULTISHEET Ran 117 OK exit 0; S1 Ran 60 OK exit 0; CONTRACT Ran 67 OK exit 0; SEAMS Ran 57 OK exit 0. pycache cleared before; 0 skipped lines reported.
Manifest history: `hashes.sha256` root hash 86a669dc1e18d585fb7a70ecc37a5fcbee79d5497ce6bdd9e360eb018a0217d2 was the value after the first receipt rebind (superseded, retained); ba005bdbb49a2805aebd640a3975e21a0078d9c27df86d7d0d711e73478c9223 is the final root after the §R3.3 edit. Same 23 entries; no entry added between them.
Astra S1 identity ruling (received after the run): readability_render.py 9c18bc518eafa4362029adf2391c8d1ce05466f8dd875299133676338669fac8, policy 443bbb0185d5a914; both are what `s1_invocation.json` and `hashes.sha256` already bind. R90/R270 obligations: NOT TRIGGERED, because the selected D1 is R0 (rot 0, no mirror) and the declared set contains no 90/270. The S1 results above are rotation-0 diagnostic results within the current transform scope; not calibrated (calibration partial, evidence_authenticated=false). Rotate-then-mirror order: no declared transform combines a non-zero rotation with a mirror (R180 has no mirror; MX/MY have rot 0), so the order cannot differ; the per-transform native netlist round-trip test (pin tips landing on wire ends via a fresh kicad-cli export) passes for all four. D1 pin-tip-on-SVG-port-box and D1 property-text legibility were NOT checked on any R180/MX/MY render, because none was rendered.
Not measured: independent fresh-eyes review of this candidate; S1 on R180/MX/MY; the other five leaves; root netlist diff; full suite; Dockerfile build (BLOCKED, no host; no packaging edits this round).

## R4. Round 4 (lever A: bounded placement constraints; Sonnet 5.5)

### R4.0 Graph-model inspection (before any R4 run)

Built the usbc ELK graph (variant `model-order`, root `first`) from the frozen declared pin->net map; read-only script, no files changed. Edges, source -> target : net:

| edge | net |
|---|---|
| J1.A4 -> F1.1 | VBUS_CON |
| J1.A4 -> D1.1 | VBUS_CON |
| F1.2 -> C1.1 | VBUS |
| J1.A5 -> R1.1 | CC1 |
| J1.A5 -> D1.3 | CC1 |
| J1.B5 -> R2.1 | CC2 |
| J1.B5 -> D1.4 | CC2 |

Before == after: the model added NO series relation. CC1 is a star from J1.A5 to R1.1 and D1.3 (declared CC1 = {J1.A5, R1.1, D1.3}); CC2 likewise; R1.2/R2.2 are GND and undrawn (continuation policy). There is no R1->D1 or R2->D1 edge, and no edge was added or removed. The graph model needs no correction. The R3 constraint sentence ("two CC branches each requiring a series resistor between J1 and D1") was a SPATIAL-ordering statement (each CC trunk must pass R/D columns that ELK places in layers), not an electrical series claim; as electrical wording it was wrong and R1/R2 are independent pull-downs, as the reviews describe. Component adjacency in the graph: J1-D1 {CC1, CC2, VBUS_CON}, J1-R1 {CC1}, J1-R2 {CC2}, J1-F1 {VBUS_CON}, F1-C1 {VBUS}. Port sides: J1 east pins A4/A5/B5 at node-local y 2.54/7.62/10.16; D1 west pins 1/3/4 at y 1.27/8.89/16.51; R/F/C ports NORTH/SOUTH.

### R4.1 Predeclared placement models (written BEFORE any R4 run)

Frozen: all symbols identity; same native symbols/units/pins; declared circuit and continuation policy (GND undrawn); R2-selected options (`model-order` = NODES_AND_EDGES, root `first`, all spacings). Baseline `R0` (no placement constraint) is run only as the comparison. Derived from the actual port geometry in §R4.0: J1 east pins top-to-bottom VBUS_CON(A4) < CC1(A5) < CC2(B5); D1 west pins top-to-bottom VBUS_CON(1) < CC1(3) < CC2(4); R1/R2 have their drawn pin on the NORTH side (CC1 resp. CC2); in the J1-D1 gap the CC1 line is enclosed between the VBUS_CON and CC2 lines, so a resistor on CC1 can only avoid a crossing in the face above the CC1 line (between layers) or if CC1 never has to leave that band.

| model | requested layer order (left to right, ELK RIGHT) | requested within-layer relation |
|---|---|---|
| M1 `m1-D1-mid` | J1 < D1 < {R1, R2} | R1 above R2 (each aligned to its own CC branch order: CC1 above CC2) |
| M2 `m2-R1|D1|R2` | J1 < R1 < D1 < R2 | R1 before D1's layer, R2 after it (opposite sides of D1's layer; branch order CC1 then CC2 matches D1 rows 3 then 4) |

F1 and C1 carry NO constraint in either model (not fabricated). At most these two non-baseline models; no Cartesian sweep of spacing/order/root.
Mechanism (one, declared up front): ELK `elk.partitioning.activate=true` on the root and `elk.partitioning.partition=<int>` on the constrained nodes (M1: J1=0, D1=1, R1=2, R2=2; M2: J1=0, R1=1, D1=2, R2=3). Realized relationships are read back from the solved node poses; a model whose realized layer order contradicts the request is reported NOT EXECUTED (option ignored) and is excluded from selection. If partitioning is ignored entirely, `elk.layered.layering.layerChoiceConstraint` is the single alternative mechanism (same requested layers); no coordinate patch, no hand router.

### R4.2 Result (run `/home/pkcs12/.cache/scratch/s3-elk-spike/run-20261006-162241`; run-161258 untouched)

Mechanism: ELK `elk.partitioning.activate` + per-node `elk.partitioning.partition` (no layerChoiceConstraint, no coordinate written, no router edit). Requested vs realized, read back from SOLVED hull boxes (`realized_placement`); partitioning WAS honoured, so no model is NOT EXECUTED:

| model | requested | realized (all requested relations true) | foreign crossings | area mm2 | graph sha256 (prefix) |
|---|---|---|---|---|---|
| R0 baseline | none | n/a | 1 (CC1xCC2 69.85,69.85) | 5765.47 | 8b3701f85cdb |
| M1-D1-mid | J1<D1<{R1,R2}; R1 above R2 | J1 x1 63.5 <= D1 x0 73.66 <= R1/R2 x0 114.55; R1 y0 83.82 < R2 y0 107.95 | 1 | 6080.31 | a3b467fcb2e4 |
| M2-R1\|D1\|R2 | J1<R1<D1<R2 | J1 x1 63.5 <= R1 x0 76.45; R1 x1 78.49 <= D1 x0 100.33; D1 x1 105.41 <= R2 x0 134.87 | 0 | 8532.89 | 9e3071da8f01 |

Selection (unchanged criteria: electrical/ink verified, then crossings, then area): **M2**. Cost disclosed: area +48% vs R0; R2 sits at the far right (hull x0 134.87) and its CC2 local label at (135.89, 114.30) is far from J1; CC1 label at (77.47, 90.17).
Selected candidate: fresh native export 24/24 pins, 5/5 classes, 0 fused / 0 missing / 0 misrouted / 0 name mismatch; ERC 6 `lib_symbol_issues` only; engine verification fused/missing/misrouted/problems all empty; foreign_crossings = []. S1 (readability_render.py 9c18bc51…, policy 443bbb01…, real-evidence record, scope a-e, explicit 10-pair mode): a,b,c,d,e,f all pass, zero findings; b measurements b1_electrical 0, b2_perceptual 0; report `verdict`/`scoped_verdict` = **indeterminate** (calibration partial, evidence_authenticated=false per calibration_ref; all five classes listed partial) — diagnostic result, not acceptance. PNG sha256 9407f5c441f27135ff2261560bfbd6570198567bb3f186b5c8f5d23c1ed28533, NOT identical to 70335b15…, so the candidate needs independent review.

Review-3 residuals carried:
- b2 crossing CC1xCC2: not present in this candidate (engine foreign_crossings [], S1 b2_perceptual 0). Not independently reviewed.
- "VBUS_CON" text at wire corner: UNCHANGED in kind. The local label anchor is (76.2, 38.1), which is the corner of wires (67.31,38.1)-(76.2,38.1) and (76.2,38.1)-(76.2,40.64); the engine's own-net rule allows touching at the anchor. Reviewers cited this as a near-touch; not fixed (no mechanism added).
- VBUS flag near F1: flag at (76.2, 48.26) pointing left, box x 69.6-76.2; F1 text boxes x 79.0-85.6 (SVG). S1 f: flag_through_text 0, text_text_overlaps 0. Proximity to the F1 body not separately measured.
- GND / D1 text: SVG GND text box (106.8,78.1)-(110.9,79.8); D1 text (106.7,88.2)-(109.4,89.9), PESD5V0L4UF (106.7,90.7)-(120.0,92.4). No overlap in this render; S1 f 0. Text-vs-symbol-body clearance is NOT measured by S1 f.
- Page use: S1 page_use_bbox_ratio 0.162, grid ratio 0.0741 (diagnostic, no gate; no scaling applied).
- D1 bare glyphs (ruling 5): unchanged, carried.

Tests (pycache cleared; verbatim): S3 BRIDGE Ran 16 OK exit 0 (5 new placement tests); MULTISHEET Ran 117 OK exit 0; S1 Ran 60 OK exit 0; CONTRACT Ran 67 OK exit 0; SEAMS Ran 57 OK exit 0.
Touched (this round only): elk_layout.py `build_elk_graph` signature :486 + partition block :575-587; `PresentationSolution.placement_model` :765; `PLACEMENT_MODELS` :1464-1470; `realized_placement` :1473-1500; `solve_sheet` signature :1523 and plan/loop :1576-1621 (+ selection tail). hierarchical.py `emit_hierarchical_schematic` kwarg :1152, placement block :1376-1391, solve_sheet call :1410-1413, report field :1437; spec key :1870-1871. tests/test_elk_layout.py `PlacementModels` :339-375. kicad_emit.py: NOT touched in R4 (sha256 still b78ca97f…, the ownership-pin value). runner.cjs: not touched (7b63c55e…). readability_render.py: not touched.
Not measured: independent fresh-eyes review; S1 detector acceptance (calibration partial); text-vs-symbol-body clearance; the other five leaves; root netlist diff; full suite; image build (BLOCKED, no host).

## R5. Round 5 (D1 presentation grouping + M2 compaction; Sonnet 5.5; approved at officer level, approval_ref = BRNS-REPLY approved phase=2-authorized, human_approved=false)

Proposal: `s3-r5-d1-presentation-proposal.md` sha256 `73c81356fad4376f12bea03d1877f813671a93a3d376a4636a0b47a521187759`. Baseline run `run-20261006-162241` (manifest root c129b87f…), immutable.

### R5.0 Pre-edit pins (recorded BEFORE any R5 edit)

| file | sha256 |
|---|---|
| elk_layout.py | `ebc02999abe1e8ede0a6b115617006b17315a738eb9f0d043c9ff2255521e71f` |
| hierarchical.py | `0ce800500efa9566113e570de1847dad215f938d6edf2b6fb6bb95dbb42e3b8a` |
| tests/test_elk_layout.py | `f1d3863ba428465c816cbcc0c4d9ebe0f3258149f9cf7dfc55aa44f0f9a19ed6` |
| kicad_emit.py (must stay unchanged ONLY if no emitter hunk is needed; an emitter hunk IS needed for the rectangle/group, so it will change; pin recorded) | `b78ca97fd5a058d1127dafc22eb6de6462673f92f66f7a8a5487978623d1a9c4` |
| runner.cjs (must be byte-unchanged at checkpoint) | `7b63c55ecc5aa8df9635ec8888eb0628d6a20db2816b270c44ed3ad40b3bd617` |
| readability_render.py (must be byte-unchanged at checkpoint) | `9c18bc518eafa4362029adf2391c8d1ce05466f8dd875299133676338669fac8` |

Note on the dispatch wording: condition 4 lists kicad_emit.py among the allowlisted engine seams AND among the must-be-unchanged files. The rectangle+group must be serialized by the emitter, so kicad_emit.py WILL carry one engine-path hunk; I read the unchanged requirement as applying to runner.cjs and readability_render.py. Flagged in the checkpoint.

### R5.1 Predeclaration (written BEFORE any R5 run)

Outline rule: rectangle = D1's graphics-only bbox (pins excluded, post-orientation, y-down sheet coords) inflated by 0.254 mm on every side; baseline value = start (101.60, 77.47), end (104.14, 102.87), dashed, width 0.1524, fill none. One `(group "D1 package outline" … (members <rectangle uuid> <D1 uuid>))`. Caption = D1's native Reference/Value, re-chosen only from the existing candidate set against the union hull. Box asserts PACKAGE MEMBERSHIP ONLY (four diode glyphs in one SOT-363 package); it asserts no shared internal connection, and no wire, label, flag, dot or no_connect lies inside it.
Setting S0 = R4 baseline spacings (nodeNode 5.08, nodeNodeBetweenLayers 10.16, edgeEdge 2.54, edgeEdgeBetweenLayers 2.54, edgeNode 2.54, edgeNodeBetweenLayers 3.81, portPort 2.54) + outline. M2 partition J1<R1<D1<R2, variant model-order, identity orientations. S1 numeric values: NOT yet written; to be recorded in R5.1b after S0 is measured and before the S1 run.

### R5.2 STOP: native group does not load in kicad-cli 9.0.9 (run `/home/pkcs12/.cache/scratch/s3-elk-spike/run-r5-s0-164620`)

Implemented (engine path only, default off via spec keys `engine_outline_refs`, `engine_spacing_overrides`): outline in `plan_node_ink`/`place_ink` (typed refusals E_ELK_OUTLINE_*), `solve_sheet(outline_refs, spacing_overrides)`, hierarchical seam, one kicad_emit hunk emitting a dashed `(rectangle)` + `(group ... (members rect_uuid symbol_uuid))`. S0 solve succeeded (M2, 0 foreign crossings, outline [101.6,77.47,104.14,102.87], caption ref_at (106.68,88.9) val_at (106.68,91.44), unchanged vs R4).
Fresh export: `kicad-cli sch export netlist|svg|pdf|erc` all print "Failed to load schematic" on the S0 `out/usbc.kicad_sch`; no netlist/SVG/PDF produced.
Bisect on copies (`diag/`, hashes in `diag/diag.sha256`): control without rectangle+group LOADS; rectangle only LOADS; every group variant FAILS to load (14 variants: members rect+symbol, rect only, symbol only, unquoted uuids, empty name, no name, no uuid, no members, `(id ...)` instead of `(uuid ...)`, multi-line members, group placed before symbols / before rectangle / after sheet_instances). Control discriminates: the only difference between loading and failing files is the `(group ...)` object.
Per binding condition 2 (group fails => fail explicitly, no loose-line fallback) NO candidate was produced; no S1 run, no spacing S1, no test populations run this round. Not determined: whether KiCad 9.0.9 requires a group syntax I did not try, or does not accept sheet-level groups in this file version (20250114); no native KiCad-saved group sample exists on this host to copy.

### R5.1b Compact spacing S1 (written AFTER S0 was measured, BEFORE any S1 run)

Amendment A approved (approval_ref = BRNS-REPLY approved subject=amendment-A; human_approved=false). S0 run: `/home/pkcs12/.cache/scratch/s3-elk-spike/run-r5b-s0-165531` (M2 + rectangle-only D1 outline, R4 baseline spacings). S0 measured: foreign crossings 0, area 8532.89 mm2, wire length 304.8 mm, R0 comparison 1 crossing / 5765.47 mm2 / 198.12 mm. M2 hull gaps (ink margins already inside the node boxes): J1.x1 63.5 -> R1.x0 76.454 (12.95 mm), R1.x1 78.486 -> D1.x0 100.33 (21.84 mm), D1.x1 105.41 -> R2.x0 134.874 (29.46 mm). D1 caption box x 106.68-118.23; R2 hull starts 16.64 mm right of its end.
Rule (stated before use): actual body/text/flag ink is ALREADY reserved per node through `plan_node_ink` margins, so the spacing a layer gap or node gap still needs is only INK_CLEAR_MM (0.25) plus the edge channel it carries, rounded up to the 1.27 grid. nodeNodeBetweenLayers_S1 = grid_up(INK_CLEAR 0.25 + 2 x edgeEdge 2.54) = grid_up(5.33) = **6.35** (baseline 10.16). nodeNode_S1 = grid_up(INK_CLEAR 0.25 + 1 x edgeEdge 2.54) = grid_up(2.79) = **3.81** (baseline 5.08). Unchanged: edgeEdge 2.54, edgeEdgeBetweenLayers 2.54, edgeNode 2.54, edgeNodeBetweenLayers 3.81, portPort 2.54.
S1 = {"elk.layered.spacing.nodeNodeBetweenLayers": "6.35", "elk.spacing.nodeNode": "3.81"} + the same outline + M2 partition. Not a page-fill target. No post-scale, pin move, coordinate nudge or third partition. Keep S0 if S1 worsens any invariant (crossings, ink validity, 24/24 fidelity, S1 per-class findings, carried-item measurement).

### R5.2b Result (Amendment A, rectangle-only; selected run `/home/pkcs12/.cache/scratch/s3-elk-spike/run-r5b-s1-165624`; comparison S0 `/home/pkcs12/.cache/scratch/s3-elk-spike/run-r5b-s0-165531`; R4 baseline run-20261006-162241 untouched)

Scope: ONE dashed non-electrical (rectangle) around D1's four glyphs; NO native (group) is emitted anywhere (the earlier group hunk in kicad_emit.py was removed; the fresh export contains zero "(group" tokens). Statement of meaning, verbatim: the box asserts PACKAGE MEMBERSHIP ONLY (four diode glyphs in one SOT-363 package); it asserts no shared internal connection. Whether it reads as implying one is a reviewer question, not measured here.
Load failure record (verbatim): 14 group syntaxes tested, all rejected by kicad-cli 9.0.9 at file version 20250114; the supported syntax (if any) remains undetermined. The rectangle-only candidate loads on fresh netlist, SVG, PDF and ERC export.

Ownership record (data layer; also in emit_result.json engine_reports.usbc.outlines.D1): D1 symbol uuid `da260240-75a4-43c0-900e-6fd634e20a61`; rectangle uuid `6fe52893-6baa-5a25-8e33-fdae41b26d87`; rule `rect_uuid = uuid5(D1_symbol_uuid, "presentation.outline")` (checked equal on the emitted sheet); baseline version = manifest root c129b87f4e3522c17ac8caa92473d63527bbc2684ad66e345b433f668f9db638 (run-20261006-162241); this candidate's own manifest root is reported in the checkpoint message (a file cannot hold its own hash). D1 symbol uuid is uuid4 per emit, so the pair is per run. Disclosed obligation (verbatim): A human moving D1 in KiCad will NOT drag the outline; later ingestion must detect outline/symbol drift and raise a ChangeProposal, never auto-move the box. (Detection itself is out of R5 scope.)

S0 vs S1 (both M2, model-order, identity orientations, outline on; S1 spacings as written in R5.1b BEFORE its run: nodeNodeBetweenLayers 6.35, nodeNode 3.81):

| measure | R4 (no outline) | S0 baseline spacing | S1 compact |
|---|---|---|---|
| foreign crossings | 0 | 0 | 0 |
| engine verification fused/missing/misrouted | empty | empty | empty |
| native fidelity pins / classes | 24/24, 5/5 | 24/24, 5/5 | 24/24, 5/5 |
| ERC | 6 lib_symbol_issues | 6 lib_symbol_issues | 6 lib_symbol_issues |
| layout area mm2 | 8532.89 | 8532.89 | 7867.08 |
| wire length mm | 304.8 | 304.8 | 287.02 |
| S1 a b c d e f | pass x6, 0 findings | pass x6, 0 findings | pass x6, 0 findings |
| S1 page_use_bbox_ratio / grid ratio | 0.162 / 0.0741 | 0.162 / 0.0741 | 0.149 / 0.0638 |
| texts / clipped / text_text_overlaps / flag_through_text | 73/0/0/0 | 73/0/0/0 | 73/0/0/0 |

Selection (zero crossings -> electrical+ink validity -> area/wire length): S1 compact is valid on every invariant and smaller, so S1 is selected. Note: R0 (no placement constraint) was also solved inside each run for comparison only (1 foreign crossing); it is not selectable.
Page use fell from 0.162 to 0.149 bbox ratio. That is a SMALLER use of the page, not a larger one: the compaction shrank the footprint, so a reviewer concerned with an under-filled page will see it as unchanged-to-slightly-worse by that metric; the rule was clearance-derived, not page-fill.

D1 §2.6 identity assertions on the fresh candidate (measured vs baseline out/usbc.kicad_sch): (1) D1 lib symbol block sha256 80c0d88ae21bc039… equal to baseline (S0 and S1); (2) D1 instance lib_id, unit and instance pin entries (1,2) equal; D1 instance (at) differs only because the engine placed the symbol (S0 102.87 78.74 = baseline; S1 100.33 77.47); (3) fresh kicad-cli netlist: 24/24 pins, 5/5 classes, 0 fused / 0 missing / 0 misrouted / 0 name mismatch; (4) ERC only the 6 baseline lib_symbol_issues; (5) wire 21 / junction 3 / global_label 11 / label 3 / no_connect 7 equal to baseline, GND flag pair at D1 pins 2/5 still two coincident flags; (6) exactly one added rectangle, zero groups. The D1 symbol uuid is new per emit (not compared).

Before/after Reference/Value (D1): R4 and S0 ref_at (106.68, 88.9), val_at (106.68, 91.44) (pin-tip +3.81 x, +10.16 / +12.7 y relative to symbol origin); S1 ref_at (104.14, 87.63), val_at (104.14, 90.17). The caption did not move relative to D1 (same candidate "right"; D1 moved by (-2.54, -1.27)). Caption = D1's native stacked Reference/Value; no text object added.

S1 reaction to the dashed rectangle: S1 (readability_render 9c18bc51…) reports classes a-f pass with 0 findings and no anomaly on a sheet that contains the dashed rectangle; the native SVG contains exactly one stroke-dasharray group (the rectangle). The instrument's own code treats a sheet-level rectangle only inside symbol definitions (readability_render.py:234, :293), so I did NOT establish that it sees the sheet-level rectangle as ink or wire. Recorded as: no reaction observed; not demonstrated that it inspects it. verdict and scoped_verdict = indeterminate (calibration partial, evidence_authenticated=false); diagnostic, not acceptance.

Carried items (Review 4) — measured vs not:
- b2 crossing CC1xCC2: engine foreign_crossings [] and S1 b2_perceptual 0 (S0 and S1). Not independently reviewed.
- Near-crossing gap near x~397 / y 480-525 (R4 pixel frame): NOT re-measured; geometry changed in S1 (CC1 branch at x 69.85, CC2 trunk y 113.03); no numeric clearance for it was computed.
- VBUS flag vs F1 body: flag anchor (76.2, 48.26) and box 69.6-76.2 x 47.475-49.045 UNCHANGED from R4; F1 body clearance NOT numerically measured (flag_through_text 0 only).
- VBUS_CON text at wire corner: anchor (76.2, 38.1) UNCHANGED; not fixed (no mechanism added).
- B5 under CC1 wire: J1 CC1 and B5 stay 2.54 mm apart (S1: y 85.09 / 87.63); unchanged in kind, not fixed.
- R2 lopsidedness: R2 hull moved left by 7.62 x (S0 138.176 -> S1 131.826 text x); still the right-most element; page use 0.149.
- GND flag vs D1 text: S1 GND flag at (102.87, 77.47), D1 caption starts y 87.63; S1 f flag_through_text 0. Text-vs-symbol-body clearance not measured by S1 f.
- D1 bare glyphs (ruling 5) and the anode-not-drawn state (proposal §1.4 item 3): unchanged. The outline groups them visually; it does not draw the common anode.

Human view: PDF -> pdftoppm -r 150 PNG sha256 db0ba9ec09fb0ee829a49646c005c0d77e12ddba65dce3350f240f3d9d76b30b. I looked at this PNG myself (dashed blue box around the four diodes, caption right of it, pin stubs crossing the left boundary, GND flag right of pin 2); that is a self-look, not the independent fresh-eyes review the officer dispatches.

Tests (pycache cleared before each; raw in `tests.txt` of the selected run): S3 BRIDGE Ran 21 OK exit=0 (5 new: ink model, no-outline control, no-graphics refusal, exactly one rectangle/zero group/ownership fields, fresh native load); MULTISHEET Ran 117 OK exit=0; S1 Ran 60 OK exit=0; CONTRACT Ran 67 OK exit=0; SEAMS Ran 57 OK exit=0. No full-suite claim; no mutation/probe programme.

Touched this round (current line numbers): kicad_emit.py `OUTLINE_UUID_RULE_NAME` :242; `_outline_blocks` :1486; engine-path outline block :1604-1624 (the former (group) emission was inside this block and is removed: now rectangle + ownership record only); `outline_blocks=` call arg :2620; `_symbol_instance_block(symbol_uuid=)` :2719,:2724; `_schematic_document(outline_blocks=)` :4578,:4592. elk_layout.py: `SPACING_OPTION_KEYS` :96; `SymbolGeometry.gfx` :171/:243; `NodeInk.outline` :351; `OUTLINE_MARGIN_MM` + `plan_node_ink(outline=)` :386-455; `build_elk_graph(outline_refs=)` :520/:636; `PresentationSolution.outlines/spacing_overrides` :801-804; `place_ink` step 5 :1452-1493; `solve_sheet(outline_refs, spacing_overrides)` :1605-1710 incl. wire-length tiebreak; export :1758. hierarchical.py: kwargs :1153-1154, solve_sheet call :1413-1419, report fields :1444, spec keys :1880-1884. tests/test_elk_layout.py: D1Outline* classes after :379.
Unchanged bytes: runner.cjs 7b63c55e…, readability_render.py 9c18bc51….
Not measured / not done: independent fresh-eyes review; whether the box implies shared internal wiring; text-vs-symbol-body clearance; S1 detector acceptance (calibration partial); the other five leaves; root netlist diff; full suite; image build (BLOCKED, no host); P1 registration of the outline edit class (not required by the amendment).

## R6 — qualified boxed D1 symbol (presentation candidate; NON-FABRICABLE)

approval_ref `officer:ses_04db7a1c5ffelvbxyLP1p6xlRH/r6-phase2-20261006` · human_approved false. Run dir: `/home/pkcs12/.cache/scratch/s3-elk-spike/run-r6-173849` (sibling of run-r5b-s1-165624, which is untouched). A failed first attempt is kept as `run-r6-attempt1-refused-M2only`: I passed only the M2 model, and the engine refused sheet power_rail with E_ELK_PARTITION_UNRESOLVED because the model list applies to every sheet; the accepted run passes the same list as R5b (R0 + M2), the engine then picks per sheet.

Release restriction: no PCB / package / BOM / fab release; "qualified" = pin / topology / presentation scope only. Footprint defect: `/home/pkcs12/products/thesmart_products/issues/BR_20261006_d1_pesd5v0l4uf_footprint_sot363_contradicts_datasheet_sot886.md`. The D1 INSTANCE footprint stays `Package_TO_SOT_SMD:SOT-363_SC-70-6` (unchanged override, visible in out/usbc.kicad_sch and the netlist); the library Footprint property of the authored symbol is EMPTY. Correction: earlier sentences "four diode glyphs in one SOT-363 package" (receipt §R5, proposal §2) are unsupported by the datasheet (package SOT886/XSON6).

Candidate-spec selection (approved presentation selection): copy of the R5b formal_invocation.json; diff `candidate_spec.diff` sha256 fdcfde0ab693040fd9c4e47efc52bbaf020d00ea5e821542bb03ef7ddd4278a4. Only changes: D1 `symbol` -> `Bodesign_Presentation:PESD5V0L4UF_Boxed`; `engine_outline_refs` removed (OP-5, R5b dashed rectangle no longer emitted); vendor_symbols dir prepended to `symbol_dirs`. spec.json, symbol_resolver.py (e9513ef2…), _VENDOR_MAP untouched. Stock Power_Protection:PESD5V0L4UF not shadowed (test).

New / changed files (sha256): packages/eda-bridge/vendor_symbols/Bodesign_Presentation.kicad_sym 2c5edde12b5bd913760d5e64b3c6c43b204de2d3b929a71034aeefe4c40ce6da (new); vendor_symbols/PROVENANCE.md 55af809caafcd1f5ee4e56e3edf53fccb7b14d911cb8c750078f5446ba16395a (appended; was 86de3e24…; existing entries preserved); tests/test_d1_boxed_symbol.py f66d173344f4e21d3aa3b254edcf97faf39679672d8fe0a7f82e4568c6c3c23b (new); proposal s3-r5-d1-presentation-proposal.md 83e0351e8133d9534b07a35337eca722dcdd3cf88c088461a64ca8ceec7e58ee (see manifest). No engine-seam edit was needed this round: elk_layout.py ce8e2bc5…, hierarchical.py e00e0fff…, kicad_emit.py 7f0f56d7… are byte-equal to their pre-R6 pins; runner.cjs 7b63c55e…, readability_render.py 9c18bc51… unchanged.

Selected candidate: M2-R1|D1|R2, identity orientation, R5b compact spacings (nodeNodeBetweenLayers 6.35, nodeNode 3.81). Variant log: R0 area 6131.6 mm2 / 1 foreign crossing (CC1xCC2 at 69.85,77.47); M2 area 9048.37 mm2 / wire 304.8 mm / 0 crossings. R5b M2 was area 7867.08 / wire 287.02, so this body costs +15% area and +6% wire; page-use bbox ratio 0.1715.

Native checks (fresh kicad-cli 9.0.9): netlist, svg, pdf, erc all load. Fidelity: 24/24 pins, 5/5 classes, 0 fused / 0 missing / 0 split / 0 name mismatch; ERC only 6 lib_symbol_issues (same type and count as R5b). Whole D1 pin partition vs datasheet Table 3 p.2 and R5b: embedded symbol = ONE unit, six pins: 1 K1 (-7.62,0) rot0; 2 A (7.62,-7.62) rot180; 5 A same tip, hidden (distinct pin object); 3 K2 (-7.62,-5.08); 4 K3 (-7.62,-10.16); 6 K4 (-7.62,-15.24); all passive, numbers and names equal R5b. Netlist nets: 1 VBUS_CON, 2 GND, 3 CC1, 4 CC2, 5 GND; pin 6 has a no_connect at sheet (97.79,105.41) = its tip. Counts vs R5b: junction 3=3, no_connect 7=7, global_label 11=11, label 3=3, wire 21->20 (re-layout), sheet-level rectangle 0, "(group" tokens 0. Pin tips differ from R5b by design (new body, pins at +-7.62 not +-2.54).

Per-ref poses (x y rot, R5b -> R6): C1 104.14 57.15 0 -> 106.68 57.15 0; D1 100.33 77.47 0 -> 105.41 90.17 0; F1 76.2 44.45 0 unchanged; J1 48.26 95.25 0 -> 48.26 105.41 0; R1 77.47 95.25 0 -> 77.47 105.41 0; R2 129.54 119.38 0 -> 132.08 129.54 0. D1 uuid is per-emit: da260240-75a4-43c0-900e-6fd634e20a61 -> 289b716a-a8fa-45d3-ad36-83ded1b89647 (explicit old->new mapping; not a stable identity). D1 lib_id Power_Protection:PESD5V0L4UF -> Bodesign_Presentation:PESD5V0L4UF_Boxed.

S1 (readability_render.py 9c18bc51…, policy 443bbb0185d5a914, real-evidence calibration record, required_local_pairs explicit 10 pairs, verdict_scope a-e): overall indeterminate (calibration partial, evidence_authenticated=false), a b c d e f all pass, 0 findings each (b1 0, b2 0; f flag_through_text 0). Is the new body in S1 geometry? S1's parser (readability_render.py:234, :293) reads rectangle, polyline, circle and arc from the embedded lib symbol, so the box is expected to be present; I did NOT measure it directly (no probe run), and e wire_through_body=0 does not by itself prove it. No symbol-coherence claim. F covers text-vs-text, wire-through-text, flag-through-text only; text-vs-symbol-body is NOT measured.

Human view: PDF -> pdftoppm -r 150 PNG sha256 b25d7d50b3530627ec8f12a2330e568a0321d57f717d23fe5e1a3f909b261004. I looked at it: solid box around four diode rows with an internal vertical anode bus (junction dots) leaving at the right to one GND flag; K1/K2 wires from VBUS/CC1, K3 from the CC2 branch, K4 open with an x. This is my reading (WORKER READING, distinct from the independent review; see Review 6 in s3-first-leaf-review-20261006.md for that).

Carried residuals (not fixed, not specially handled): VBUS_CON text at the wire corner above F1; VBUS flag beside F1 body; near-alignment around the CC2 vertical (x about 397 sheet-px at 150 dpi) and B5/CC1 spacing; R2 branch long and lowest. Not re-measured at pixel level. VRWM/VBUS: unassessed (Table 9 p.5-6: VRWM max 5.0 V, VBR min 6.46 V); no verdict.

Tests (pycache cleared before each; raw in tests.txt sha256 3bf0b801…): NEW test_d1_boxed_symbol Ran 9 OK exit=0 (fail 0, err 0, skip 0); S3 BRIDGE test_elk_layout Ran 21 OK exit=0; MULTISHEET (6 modules) Ran 117 OK exit=0; S1 test_readability_render Ran 60 OK exit=0; CONTRACT (4 modules) Ran 67 OK exit=0; SEAMS (4 modules) Ran 57 OK exit=0. Skip counts: runner prints none.

NOT MEASURED (by the worker; the independent fresh-eyes review has since been done: see Review 6, ACCEPT, and the close-out block below): whether S1 sees the new body (code-read only); text-vs-symbol-body clearance; pixel-level carried residuals; ERC with the authored library beyond the 6 baseline-type findings; the other five leaves; root netlist diff; full suite; image build (BLOCKED, no host); any footprint/PCB consequence; VBUS tolerance vs VRWM.

### R6 close-out (document-only; approval_ref `officer:ses_04db7a1c5ffelvbxyLP1p6xlRH/r6-closeout-20261006`; human_approved false)

Verdict (Astra + officer): ACCEPT at the declared single-usbc presentation-spike scope, per independent Review 6 (`s3-first-leaf-review-20261006.md`, reviewer ses_eef662d7affeu5KgEQu1vhjnSu, PNG b25d7d50…, manifest root 174b3b4696e1edacf81aaa53d4addf58986ad371c11aeb353094ecf201e1080d). The earlier "independent fresh-eyes NOT MEASURED" line above is superseded by Review 6; my own human-view reading stays labelled WORKER READING. No engine run, emit, symbol edit, test rerun, commit, add or stash was done for this close-out.

**A. Measurement provenance (split)**

OFFICER-MEASURED (as relayed in the close-out dispatch; the worker re-observed the items marked *re-observed* read-only at close-out, it did not originate them): manifest root 174b3b46…; PNG hash; `sha256sum -c hashes.sha256` from the run dir (*re-observed*: all 31 entries print OK, no FAILED line; the shell's `rc=` printed in that call belonged to a `tail` pipe and is not the checker's exit code, so rc=0 is the officer's figure, not mine); tests.txt Ran counts (*re-observed* below); forbidden-zone byte-unchanged (*re-observed*: runner.cjs 7b63c55e…, readability_render.py 9c18bc51…, symbol_resolver.py e9513ef2… equal to their pins); candidate_spec.diff three-change check (*re-observed*: D1 `symbol`; `engine_outline_refs` removed; vendor_symbols prepended to `symbol_dirs`; plus the unavoidable `out_dir` line); zero `(group` tokens (*re-observed*: 0) and zero sheet-level rectangles (`(rectangle` count 16 in out/usbc.kicad_sch is not zero by itself; those are inside embedded lib symbols, and the earlier §R6 figure "sheet-level rectangle 0" is the worker's measurement from the R6 run, not re-derived by this grep).

WORKER-MEASURED: native fidelity 24/24 pins, 5/5 classes, 0 fused/missing/split/name-mismatch; ERC; layout metrics (area 9048.37 mm², wire 304.8 mm, page-use 0.1715); per-ref poses; D1 partition comparison; S1 record (s1_report.json).

ERC findings retained (6 `lib_symbol_issues`, from native/usbc.erc.json; the JSON carries type, message and item text, not a separate stable ID field):
1. "The current configuration does not include the symbol library 'Device'" — Symbol F1 [Polyfuse]
2. "…library 'Connector'" — Symbol J1 [USB_C_Receptacle_USB2.0_16P]
3. "…library 'Device'" — Symbol C1 [C]
4. "…library 'Device'" — Symbol R1 [R]
5. "…library 'Bodesign_Presentation'" — Symbol D1 [PESD5V0L4UF_Boxed]
6. "…library 'Device'" — Symbol R2 [R]
Finding 5 is new vs R5b (R5b's D1 finding named the 'Power_Protection' library). "Same type and count as R5b" is therefore NOT identical-finding evidence; ERC is not clean; these are library-configuration findings only. No other ERC violation types were present in this file.

Test populations (tests.txt, pycache cleared per population; raw output verbatim there). Module lists exactly as labelled in tests.txt headers:
- NEW: test_d1_boxed_symbol — Ran 9, OK, exit=0
- BRIDGE: test_elk_layout — Ran 21, OK, exit=0
- MULTISHEET: test_sheet_partition test_multisheet_emit test_multisheet_global_label_link test_replica_emit test_replica_fidelity test_mcp_emit_multisheet — Ran 117, OK, exit=0
- S1: test_readability_render — Ran 60, OK, exit=0
- CONTRACT: test_rebuild_contracts test_rebuild_freshness test_rebuild_adapter_parity test_rebuild_mechanical_contracts — Ran 67, OK, exit=0
- SEAMS: test_kicad_emit_seams test_composer test_motifs test_visual_companion — Ran 57, OK, exit=0
The literal shell wrapper line used to launch them was not saved in tests.txt and is not reconstructed here; only the module lists above are recorded. Skip counts: the runner printed none. Full suite, root netlist diff and the other five leaves: unmeasured.

**B. Invocation and model applicability**
One engine run with two explicitly predeclared placement models ['R0','M2-R1|D1|R2'], plus one earlier refused attempt (`run-r6-attempt1-refused-M2only`, typed `E_ELK_PARTITION_UNRESOLVED` on sheet power_rail, because that sheet has no R1/D1/R2). Applicability: M2 was selected for sheet usbc; the engine selects per sheet from the declared list, and R0 is an explicit declared candidate (never a silent fallback). Outputs for sheets other than usbc (battery, charge_enable, io, mcu_swd, power_rail, root) are incidental and UNACCEPTED. The refusal shows only that this ref-based M2 model does not apply to power_rail; it does not show that every leaf needs a bespoke algorithm. No generalization claim until a later approved corpus slice.

**C. S1 record**
Instrument readability_render.py 9c18bc518eafa4362029adf2391c8d1ce05466f8dd875299133676338669fac8; policy digest 443bbb0185d5a914; inputs s1_invocation.json and the real-evidence calibration record (explicit 10-pair required_local_pairs, verdict_scope a-e). Result preserved: overall indeterminate, calibration partial, evidence_authenticated=false; classes a-f pass with 0 findings (diagnostic, not detector acceptance). New-body visibility in S1 geometry and text-to-body clearance remain unmeasured. The sheet-level dashed rectangle was removed in this candidate, so it does NOT exercise the sheet-graphics coverage gap.

**D. Restrictions**
NON-FABRICABLE. No PCB / package / BOM / fab release; "qualified" = pin / topology / presentation scope only. Library license pending owner decision; internal review use only; not cleared for redistribution or global promotion. Footprint defect BR: /home/pkcs12/products/thesmart_products/issues/BR_20261006_d1_pesd5v0l4uf_footprint_sot363_contradicts_datasheet_sot886.md. Authored library Footprint property is EMPTY; the D1 instance override `Package_TO_SOT_SMD:SOT-363_SC-70-6` is unchanged and visible in out/usbc.kicad_sch. VRWM 5.0 V max / VBR 6.46 V min (datasheet Table 9, p.5-6) vs VBUS: unassessed, no verdict. D1 uuid da260240-75a4-43c0-900e-6fd634e20a61 -> 289b716a-a8fa-45d3-ad36-83ded1b89647 is an explicit old->new mapping; per-emit uuids are not stable identity.

**E. Spike close-out statement**
PROVED on one leaf (usbc): explicit candidate symbol selection via per-run spec copy + `symbol_dirs`; declared placement models with typed refusal; native kicad-cli export (netlist/SVG/PDF/ERC load); fresh fidelity 24/24; scoped S1 diagnostics; independent review ACCEPT with carried residuals (Review 6: row-3 exit stub near row-2 wire at box left edge; x≈397 collinear verticals; CC1 label / VBUS flag / D1 GND flag crowding).
NOT PROVED: general automatic placement; runtime resolver compatibility (the new test checks source text, which is not execution of the resolver); all-leaf fidelity; image deployment; sheet-graphics coverage.
Legacy hand-router path stays FROZEN outside this scope: not deleted, never used silently on engine refusal. Engine model selection and typed refusal stay at the engine/application boundary; reviewer evidence, corpus admission and qualification decisions stay explicit, not in routing heuristics.

**F. Scope line**
Closes the one-leaf S3 spike only. It does NOT tick 3.3d, five-leaf delivery or AC16 calibration. Packaging stays BLOCKED pending a build host; S4 commit is user-controlled.

**G. Manifest staleness (disclosed)**
`hashes.sha256` in run-r6-173849 binds this receipt, the proposal and (indirectly via Review 6) nothing else edited here. This close-out edited the receipt and the proposal, so their manifest entries no longer match (`sha256sum -c` would now report those two FAILED). The manifest was not rebound (outside the close-out allowlist). The pre-close-out values (receipt f748b635…, proposal 83e0351e…) and the post-edit values are in the checkpoint message; root 174b3b46… remains the identity of the accepted candidate as reviewed.

### R6.H uuid 6fe52893 provenance (document-only; approval_ref `officer:ses_04db7a1c5ffelvbxyLP1p6xlRH/s3-uuid-reconcile-20261006`; human_approved false)

Measured read-only on the four S3 run dirs under `/home/pkcs12/.cache/scratch/s3-elk-spike/` (grep over `out/usbc.kicad_sch`, `emit_result.json`, `hashes.sha256`; no byte altered):

| run | out/usbc.kicad_sch sha256 | D1 symbol uuid (instance) | sheet-level `(rectangle` | outline uuid | `6fe52893` count in sheet |
|---|---|---|---|---|---|
| run-20261006-162241 (R4, root c129b87f…) | 0310d9ab… | 975183bb-8215-4272-8912-cb1ed2e4d06c | none (every `(rectangle` is inside `lib_symbols`, which ends before line 1462) | none; no `presentation.outline` token | 0 |
| run-r5b-s0-165531 | bf1fd9e6… | 7993d8ef-d940-4f0e-9acc-d4fdbaca486a | 1 (line 1620, dash) | 3402af4c-8cdf-5501-97cf-f8a3c81bad0b (emit_result `rect_uuid`) | 0 |
| run-r5b-s1-165624 (R5b selected) | 1a898ecc… | da260240-75a4-43c0-900e-6fd634e20a61 | 1 (line 1620, dash 0.1524) | 6fe52893-6baa-5a25-8e33-fdae41b26d87 (sheet :1622 and emit_result.json :2654) | 1 |
| run-r6-173849 (R6) | 8cd238d2… | 289b716a-a8fa-45d3-ad36-83ded1b89647 | none | none | 0 |

Established:
- (a) R4 contains no sheet-level rectangle and no occurrence of 6fe52893; its `emit_result.json` has no `da260240` or `6fe52893` either. 6fe52893 and da260240 appear in exactly one run, run-r5b-s1-165624.
- (b) D1 symbol uuid in R4 (975183bb…) and in R5b (da260240…) are DIFFERENT; all four runs carry four different D1 uuids.
- (c) Not applicable, since they are not the same. For why they differ: `kicad_emit.py:245-246` `_uid()` returns `uuid.uuid4()` with no seed, and the R5b rectangle derives from it at `kicad_emit.py:1617` (`uuid5(UUID(symbol_uuid), "presentation.outline")`). The S0 and S1 R5b runs show the rule's effect: different D1 uuid gives different rectangle uuid (7993d8ef…→3402af4c…, da260240…→6fe52893…). I did not recompute the uuid5 myself; the reproduction of 6fe52893 from da260240 is the S1 owner's measurement (s1-instrument-receipt.md :396), and emit_result.json for each run records the same pair.
- (d) Line 333 is a CORRECT statement that is easy to misread, not a wrong run label. It sits in §R5.2b, which describes the selected run run-r5b-s1-165624, and the pair da260240/6fe52893 is that run's. The parenthesis "(run-20261006-162241)" follows "baseline version = manifest root c129b87f…" and labels the BASELINE (R4), not the origin of the uuids. Its second clause "D1 symbol uuid is uuid4 per emit, so the pair is per run" also holds. The proposal's "R5b only" (OP-5) is likewise consistent with the table. Per the dispatch rule (a note only if the measurement shows the line is wrong), NO correction note was added at line 333; this section is the disambiguation. Readers: the uuids belong to R5b; R4 is only its baseline and has neither.
- Not established: the S1 owner's phrase "S3 run-162241 D1 record" for line 333 is a misattribution caused by that parenthesis; I did not examine the S1 documents' own history beyond reading lines quoted by grep. No pinned R4 subject was added to the repo here.

## R7 — six-leaf fan-out of the R6 recipe (presentation draft; NON-FABRICABLE)

approval_ref `user:20261006/slice-A-five-leaf+visual-deliverable` (dispatch r7, phase five-leaf-fanout) · human_approved false. Run dir `/home/pkcs12/.cache/scratch/s3-elk-spike/run-r7-20261006-193512` (R6 and earlier runs untouched). Deliverable: `/home/pkcs12/products/bodesign/btdongle_ms/`.

Invocation: ONE `_h_emit_multisheet` call over the whole btdongle_ms project. Base = R6 `formal_invocation.json` (D1 -> `Bodesign_Presentation:PESD5V0L4UF_Boxed`, vendor_symbols first in `symbol_dirs`, no `engine_outline_refs`); diff vs R6 is the `out_dir` line only (`invocation_vs_r6.diff`). Declared placement models `['R0','M2-R1|D1|R2']`, R5b compact spacings, identity orientations, the same list for every sheet (I did not predeclare per-sheet models). M2 is ref-based (J1,R1,D1,R2), so on the five sheets lacking those refs the engine returned the typed refusal `E_ELK_PARTITION_UNRESOLVED` for the M2 candidate; R0 is a declared candidate and is the result there. No sheet was dropped silently; no legacy router used. Not edited: symbol_resolver.py, _VENDOR_MAP, spec.json, design.py, kicad_emit.py, hierarchical.py, elk_layout.py, runner.cjs (pins: kicad_emit 7f0f56d7…, elk_layout ce8e2bc5…, hierarchical e00e0fff…, runner 7b63c55e…, symbol_resolver e9513ef2…, readability_render f98dc237…).

### R7.1 Per-sheet table (fresh kicad-cli 9.0.9 export per sheet; WORKER-MEASURED)

| sheet | model used | foreign crossings (engine) | area mm2 | wire mm | page-use ratio | paper | pins native/declared | classes | fused/missing/split/name-mismatch | ERC total (types) |
|---|---|---|---|---|---|---|---|---|---|---|
| usbc | M2-R1\|D1\|R2 | 0 | 9048.37 | 304.8 | 0.1715 | A4 | 24/24 | 5/5 | 0/0/0/0 | 6 (lib_symbol_issues 6) |
| power_rail | R0 (M2 refused) | 0 | 17030.29 | 1003.3 | 0.3243 | A4 portrait | 33/33 | 11/11 | 0/0/0/0 | 16 (lib_symbol 9, global_label_dangling 3, pin_not_driven 2, power_pin_not_driven 2) |
| battery | R0 (M2 refused) | 0 | 3359.61 | 179.07 | 0.0856 | A4 | 11/11 | 4/4 | 0/0/0/0 | 6 (lib_symbol 5, global_label_dangling 1) |
| charge_enable | R0 (M2 refused) | 0 | 1895.16 | 72.39 | 0.0663 | A4 | 7/7 | 5/5 | 0/0/0/0 | 6 (lib_symbol 3, global_label_dangling 3) |
| mcu_swd | R0 (M2 refused) | 1 (SWCLK x SWDIO at 115.57,143.51) | 23525.76 | 627.38 | 0.2148 | A3 portrait (escalated from A4 by the emitter) | 37/37 | 10/10 | 0/0/0/0 | 16 (lib_symbol 10, global_label_dangling 4, pin_to_pin 1, power_pin_not_driven 1) |
| io | R0 (M2 refused) | 0 | 16396.74 | 224.79 | 0.1517 | A3 portrait (escalated) | 24/24 | 10/10 | 0/0/0/0 | 15 (lib_symbol 12, global_label_dangling 3) |

Fidelity counts only pins of refs on that sheet; pins of unconnected-* nets are counted separately (0 on every sheet). usbc: sheet content equals R6 after masking uuids (normalized diff of out/usbc.kicad_sch vs run-r6-173849: 0 lines) and the PNG is byte-identical to R6 (b25d7d50…).
ERC: not clean on 5 sheets beyond library configuration; the non-library findings (global_label_dangling, pin_not_driven, power_pin_not_driven, pin_to_pin) are per-sheet-ERC effects that I did NOT adjudicate; the root-sheet ERC of the multi-sheet project (`native/root/btdongle_ms.erc.json`) reports 49 violations in total, also not adjudicated.

### R7.2 S1 per class (readability_render.py f98dc237…, policy 443bbb0185d5a914, real-evidence calibration record from R6, required_local_pairs explicit; verdict_scope a-e; WORKER-MEASURED, diagnostic only)

Every sheet: overall and scoped verdict `indeterminate` (calibration partial, evidence_authenticated=false). Pair-rule for sheets other than usbc: star from the first sheet-local pin of each engine-drawn net (explicit mode, stored in `reports/<sheet>/s1_invocation.json`); undrawn nets are declared as local_exceptions. This pair rule is mine, not an officer-reviewed rule.

| sheet | a | b | c | d | e | f | findings | instrument anomalies |
|---|---|---|---|---|---|---|---|---|
| usbc | pass | pass | pass | pass | pass | pass | 0 | none |
| power_rail | pass | pass | pass | pass | pass | FAIL | 5: F_TEXT_TEXT_OVERLAP (92.785,62.780) (98.384,61.891); F_FLAG_THROUGH_TEXT (94.042,63.165) (100.722,62.497) (99.461,64.770) | PAIR_PAGE_MISMATCH (sheet A4 landscape dims vs SVG 210x297 portrait) |
| battery | pass | pass | pass | pass | pass | FAIL | 1: F_FLAG_THROUGH_TEXT (55.815,54.610) | none |
| charge_enable | pass | pass | pass | pass | pass | pass | 0 | none |
| mcu_swd | pass | FAIL (b2) | pass | pass | pass | pass | 1: B2_FOREIGN_CROSS_NO_DOT (115.57,143.51) = the engine's own foreign_crossings entry | PAIR_PAGE_MISMATCH (A3 vs SVG 297x420) |
| io | pass | pass | pass | pass | pass | pass | 0 | PAIR_PAGE_MISMATCH (A3 vs SVG 297x420) |

The PAIR_PAGE_MISMATCH anomalies appear on the three portrait sheets; I did not investigate whether they affect any class result (the instrument is read-only for me). Sheet-level graphics: none emitted on any sheet (ink count 0), so the sheet-graphics coverage gap is not exercised. Not run: S1 at rotated/mirrored transforms (none used; identity everywhere).

### R7.3 Tests (pycache cleared before each; raw in tests.txt)

| population | modules | Ran | fail | err | skip | exit |
|---|---|---|---|---|---|---|
| BRIDGE | test_elk_layout | 21 | 0 | 0 | none printed | 0 |
| MULTISHEET | test_sheet_partition test_multisheet_emit test_multisheet_global_label_link test_replica_emit test_replica_fidelity test_mcp_emit_multisheet | 117 | 0 | 0 | none printed | 0 |
| S1 | test_readability_render | 108 | 0 | 0 | none printed | 0 |
| CONTRACT | test_rebuild_contracts test_rebuild_freshness test_rebuild_adapter_parity test_rebuild_mechanical_contracts | 67 | 0 | 0 | none printed | 0 |
| SEAMS | test_kicad_emit_seams test_composer test_motifs test_visual_companion | 57 | 0 | 0 | none printed | 0 |

Launched as `./scripts/run_tests.sh <modules>` per population, after removing every `__pycache__` outside .venv; only the Ran/OK/FAILED lines and the exit code were kept in tests.txt. No full-suite claim.

### R7.4 Deliverable directory (`/home/pkcs12/products/bodesign/btdongle_ms/`; top level = README.md, six PNG, btdongle_ms.pdf, editable/, .src/)

| file | sha256 |
|---|---|
| usbc.png | b25d7d50b3530627ec8f12a2330e568a0321d57f717d23fe5e1a3f909b261004 |
| power_rail.png | 1acb3d761b32d67d29745796e03e80ba9459458383a24cc8705eb04a2a96981d |
| battery.png | 2fb63a3da91d07ab9c9f80187f52131dc1f88d0545c28b13d467481817d2749e |
| charge_enable.png | bf550ed168047e763b41cc7b1663097bb99b3342e99f6b5ec2e1141b0fced12d |
| mcu_swd.png | d5aecaa15926557623e2faff6df4f477bd5187e3aa05093e874b432a7f118683 |
| io.png | ce066c4d05184105a1fb2248577cc2ae2898f2bec1c347c7195edd0300d8e84b |
| btdongle_ms.pdf (7 pages: root + six sheets; one kicad-cli pass on the root sheet) | a8beb2e7d262bb3a8d75d66720260ee1fe93959c8e144012caa47ec9b3220f3f |

editable/ = the seven emitted .kicad_sch plus btdongle_ms.kicad_pro, copied from the run's out/. The index page is README.md (a table of sheets with measured status, neutral look-at lines, and the not-claimed list). Manifest: `.src/hashes.sha256` (root hash reported once in the checkpoint message; a file cannot hold its own hash).

### R7.5 What a human should look for (neutral; nothing here is verified)

- usbc: the boxed D1 and its single GND flag; residuals recorded in Review 6 (row-3 stub near row-2 wire; x~397 collinear verticals; CC1 label, VBUS flag and D1 GND flag crowding).
- power_rail: whether the labels around U1 near x 92-101, y 62-65 mm overlap each other or sit on a flag; this is the S1 f finding location.
- battery: the flag near (55.8, 54.6) mm and whether it crosses text.
- charge_enable: very sparse page (use 0.066); whether the continuation labels at D2 and SW1 are understandable.
- mcu_swd: the SWCLK and SWDIO lines near (115.6, 143.5) mm; whether the crossing without a dot reads as a junction; A3 portrait with a long vertical extent.
- io: whether the three LED branches and the labels read back to other pages; A3 portrait.

### R7.6 NOT MEASURED

Independent fresh-eyes review of any sheet other than usbc [SUPERSEDED by cross-reference: Reviews 7-11 are recorded, see §R7.R; all six sheets now have an independent blind review]; human reading by me of the five new PNGs (I did not look at them); adjudication of the non-library ERC findings and of the root ERC 49 violations; whether PAIR_PAGE_MISMATCH changes any S1 class; text-vs-symbol-body clearance; D1/other symbol body presence in S1 geometry; per-sheet engine models other than the single declared list (none predeclared, so no per-sheet optimisation was attempted); root netlist diff against the declared circuit across sheets (per-sheet fidelity only); cross-sheet global-label linking correctness; full suite; image build (BLOCKED, no build host); any footprint, PCB or electrical consequence (VBUS vs VRWM unassessed; D1 footprint BR unchanged). Restrictions of §R6.D still apply (NON-FABRICABLE; library license pending; internal use only). Close-out scope: this is a presentation fan-out of the R6 recipe; it does not tick 3.3d or AC16 calibration.

### R7.R Independent blind reviews of the R7 deliverable (document-only; approval_ref `officer:ses_04db7a1c5ffelvbxyLP1p6xlRH/r7-review-record-20261006`; human_approved false)

Five independent blind reviews (task(general), PNG-only, open questions, no intended conclusions) were relayed by the officer and recorded verbatim in `s3-first-leaf-review-20261006.md` (Reviews 7-11, plus the "Corpus classification (officer) — R7" block). Copy for the deliverable reader: `/home/pkcs12/products/bodesign/btdongle_ms/.src/reviews.md` (Reviews 6-11). The officer verified the deliverable bytes before dispatching them; I did not originate that verification.

| sheet | review | reviewer session | PNG sha256 prefix | verdict | named worst residual (reviewer's words, condensed) |
|---|---|---|---|---|---|
| usbc | 6 | ses_eef662d7affeu5KgEQu1vhjnSu | b25d7d50… | ACCEPT | row-3 exit stub ~1 line-width from row-2 wire |
| power_rail | 7 | ses_eeefb4d2effe6j8oOxEB489scL | 1acb3d76… | ACCEPT (marginal) | BATT pin-name/junction overprint at U1 14/16; IN-USB_DET shared dot above C3 |
| battery | 8 | ses_eeefa941fffe3Fin3gScYNqHim | 2fb63a3d… | ACCEPT (marginal) | Q1 pin 4 to BATT/TP2 wire not confirmable |
| charge_enable | 9 | ses_eeefa6223ffeAnt7aK0XLprYwW | bf550ed1… | ACCEPT (marginal) | unattached ENPPB annotation label; SW1 pole/throw not legible |
| mcu_swd | 10 | ses_eeefb0caeffeiNGcy7ZGRz5GcZ | d5aecaa1… | ACCEPT | SWDIO label a line-width under the RUN junction |
| io | 11 | ses_eeefad2e1ffeAUMfeIwbSrchsP | ce066c4d… | ACCEPT | LED anode/cathode vs `_K`/`_A` wire names not self-evidently consistent |

Tally: 6/6 ACCEPT, 3 marginal. Classification: accepting-candidate evidence with named residuals; none is a calibrated status, a blanket accepting entry, electrical / fab / license acceptance, or human_approved. The S1 diagnostic findings of §R7.2 (power_rail f x5, battery f x1, mcu_swd b2 x1) are not adjudicated against these reviews; the reviewers did not cite the mcu_swd SWCLK x SWDIO crossing as a defect (Review 10 read it as a correct non-connection). Review text is the reviewers' reading, not an engineering verification. Manifest root after this record is reported in the BRNS-DONE message (a file cannot hold its own hash).

## R8 — hand-drafted io sheet (no engine; presentation draft; NON-FABRICABLE)

approval_ref `user:20261006/design-something-useful-from-scratch` (dispatch r8 phase hand-draft-io) · human_approved false. Run dir `/home/pkcs12/.cache/scratch/s3-elk-spike/run-r8-20261006-203543`. Only sheet io was redrawn; the other five sheets, the engine, resolver, spec.json and design.py were not touched.

What I did: wrote the .kicad_sch S-expression through a templating script (`draft_io.py`, copied to `.src/r8_io/`). Every coordinate is a hand-chosen multiple of 1.27 mm; there is no solver, router or engine call. The script reuses the engine file's four lib symbols, symbol uuids, pin uuids, values and footprints (so the refs/values/footprints are the engine's own), adds the stock `power:GND` and `power:+3V3` symbols, and writes new wires, junctions, labels, texts and dashed rectangles. KiCad 9 file version 20250114, as the emitter.

Decisions and why:
- Grouping: three dashed-outline clusters, each with a heading: "Status LEDs" (top, full width), "User button (debounced)" and "VBAT sense ÷ 2 → ADC0" (bottom row). Reason: the three functions share no nets except GND/+3V3, so spatial separation says "three independent circuits"; a reader asks "what does this page do" and gets three answers.
- LED branches: three identical vertical branches (+3V3 or interface label at top, R, node label, LED, GND at bottom), same x-spacing (60 grid steps, 76.2 mm), same orientation, headings PWR / BT / WIFI. LED rotated 90° so the anode is on the resistor side and the cathode goes to GND. Consequence: the declared nets PWR_LED_K / BT_LED_A / WIFI_LED_A all name the ANODE node (R-to-LED junction). The declared name PWR_LED_K therefore contradicts its node (K = cathode); I kept the declared name (electrical identity must not change) and wrote a note under the PWR branch saying so. This is a defect in the declared circuit's naming, not something I fixed.
- Passive notes: one to four lines of plain text per group stating what it does (e.g. R12 10k with C12 100nF about 1 ms RC; BATT max 4.2 V gives 2.1 V). The 1 ms figure is my arithmetic from the declared values (10k x 100nF); it is not measured or simulated.
- Interface labels: kept as GLOBAL labels, shapes input/output as requested (LED_BT, LED_WIFI input; SW_USER, VBAT_SENSE output; BATT input), each with an italic home-sheet note (mcu_swd U2.GPIO16/17/18/26_ADC0 with pin numbers read from the netlist; power_rail U1.BATT pins 14, 16). I did NOT use hierarchical_label as the dispatch asked: I generated both variants and exported the whole project. With hierarchical labels the root netlist partition changed (the project's root sheet has no sheet pins, so SW_USER/VBAT_SENSE/BATT split from their mcu_swd/power_rail nets; ERC also added label_dangling and 5 pin_not_connected). With global labels the 58-net root partition is identical to the engine version. Deviation from the dispatch item 3, recorded for the officer; making hierarchical labels work needs sheet pins on the root sheet, which is outside this task.
- Power: one +3V3 flag at the head of the PWR branch and one above R12; GND flags pointing down at each branch end, no long power wires. BT and WIFI branches take their top node from the interface label, so they have no +3V3 flag.
- Page: A4 landscape (the engine put this sheet on A3 portrait). S1 page_use_bbox_ratio is 0.5195 against the dispatch's >=70% target: NOT met (frame and title block take space; three clusters leave empty margins). All 31 wires are orthogonal (0 non-orthogonal by a regex check of the final file); junction dots only at 3-way nodes (7 junctions: 3 LED nodes, SW_USER x2, VBAT_SENSE x2); I did not run a separate crossing detector, S1 class b reports no finding.
- Title block: title "Indicators & User Input", company btdongle, rev r8, date 2026-10-06, comment 1 one-sentence page purpose, comment 2 the hand-drafted statement. The rendered title block shows comment lines but the Sheet line reads "/" and file "io.kicad_sch".

Defects found while drawing (fixed in the script): rotated-symbol Reference/Value overlapped (fixed by rotating the property text with the symbol); S1 initially failed classes a and d (junction dots sitting on the SW3 and C13 pin tips); I moved the symbols 2 grid steps down along a short wire so the dots are off the pin tips; second run passed a-f.

Verification (native, no engine):
- kicad-cli 9.0.9 netlist / svg / pdf / erc all exit 0 on `out/io.kicad_sch`; PDF to `pdftoppm -r 150` PNG.
- Netlist equality, per sheet: 24 pin->net entries, identical map vs the engine version (`.src/r8_io/netlist_equality.txt` lists each pin). Root level: 58 nets in both, identical pin partition when the new io replaces the engine io in the full project.
- ERC (sheet): lib_symbol_issues 21 (symbol libraries not configured; this is a count of references, more than the engine's 12 because the two power symbols are added), global_label_dangling 3, power_pin_not_driven 2. Not clean. Root-project ERC: 58 violations (lib_symbol_issues 54, global_label_dangling 2, power_pin_not_driven 1, pin_to_pin 1), vs 49 on the engine version in R7; not adjudicated.
- S1 (readability_render.py f98dc237…, policy 443bbb0185d5a914, real-evidence record, explicit required_local_pairs of 7 hand-chosen pairs: the LED node pairs, SW_USER and VBAT_SENSE nodes; undeclared continuations exempted): classes a-f pass, 0 findings, overall indeterminate (calibration partial). The ink report counts 3 sheet-graphic ink items (the three dashed rectangles); S1 reports them with owner unknown and no finding. This is the first sheet in this corpus where S1 sees sheet-level rectangles; I recorded the observation and did not interpret it.
- PNG: sha256 3a9bd795d35257d352af96d678df7ebed18efa2e45f67dcb0100f5256addbe7e. I looked at an intermediate render (two rounds) and fixed what I saw; I did not read the final PNG (inline media budget refused it), so the final picture is unseen by me. The S1 and netlist results are measured; the look is not.

Time: about 25 minutes of wall clock from the first read of the engine file to the delivered files (start stamp 20:35:43 in the run dir; the first reads happened a few minutes before it). Most of it went to three things: finding the label-kind problem, matching KiCad's rotated-symbol property conventions, and the S1 dot-on-pin-tip failure.

What was hard: (1) rotated symbols: text placement and rotation convention (property angle must be the inverse of the symbol rotation to read upright); (2) deciding label kind: hierarchical labels are the textbook answer but break this project because the root sheet is not wired for them; (3) the declared circuit has a naming trap (PWR_LED_K at an anode node); (4) hitting "meaningful" with only symbols and text; whether the page explains itself is exactly what the blind review will test, not something I can claim.

What I would want the engine to take over: symbol and pin identity reuse, grid arithmetic, wire/junction legality (no junction on pin tips, orthogonal runs), native export plus S1/netlist checks, and re-draw on a declared-circuit change. What I would leave to a human or a design-intent source: the grouping (which parts form one function), headings and the note text (they state intent the declared circuit does not contain), the choice of interface-label vs sheet-pin policy, the decision whether to rename a misleading net, and page composition. A realistic split: the human or a design-intent record declares groups, headings, notes and which nets are interfaces; the engine places inside each group and draws the wires, with the dashed outline and heading derived from the group declaration.

NOT MEASURED: independent blind review of the new page (the officer dispatches one with "what is this page designing?"); my own reading of the final PNG; page use of 70% (measured 0.5195, target missed); sheet-level rectangle meaning in S1 (3 ink items, owner unknown); the 1 ms RC figure (computed, not simulated); the full suite, other five sheets, image build. Restrictions of §R6.D still apply; no commit, add or stash.

## §R8.R — Review 12 record (io, hand-drafted r8)

Verdict: ACCEPT (communicates design intent). Reviewer ses_eeeb5a91bffeLqOf609CMIfduw, PNG-only, PNG sha256 3a9bd795d35257d352af96d678df7ebed18efa2e45f67dcb0100f5256addbe7e. The question was "what is this page designing?" (intent), not traceability. Full text: `s3-first-leaf-review-20261006.md` Review 12 and `btdongle_ms/.src/reviews.md`. Different review axis from Reviews 1-11; not calibration evidence. Review 11 (engine r7 io, traceability ACCEPT) and Review 12 (hand r8 io, intent ACCEPT) are the same declared circuit: first intent-vs-traceability contrast specimen. Not human_approved; not electrical / fab / license acceptance.

The reviewer's four engineering questions, carried as OPEN ITEMS (none resolved here):

| # | Item | Classification | Owner / handling |
|---|---|---|---|
| i | PWR_LED_K net name sits on the LED anode node | declared-circuit defect (same family as the D1 footprint BR) | owner: thesmart_products design.py; NOT fixed here |
| ii | LED_BT / LED_WIFI label direction (drawn as outputs) vs arrow text "←" (inputs) | r8 drafting defect | fixable in a later io pass; not changed now |
| iii | LED current ~1 mA with 1k from +3V3; VBAT_SENSE tap after R13 unprotected when MCU unpowered and BATT present | electrical design questions | NOT assessed; out of presentation scope; surface to user |
| iv | BATT "pins 14, 16" unverifiable from the page | acceptable; cross-sheet reference by design | no action |

Document-only round: no engine run, no re-render, no code edit. PNG / PDF / editable / .history manifest entries unchanged.

## §R9 — Root system overview (hand-drafted, diagram mode)

Run dir: ~/.cache/scratch/s3-elk-spike/run-r9-20261006-213422/. Generator: `draft_root.py` (copy in btdongle_ms/.src/r9_root/). Hand-drafted; no engine, no router.

(a) Mode chosen: DIAGRAM MODE (non-electrical overview). Per the Astra addendum the root is NOT a live hierarchical root: no `(wire)`, no `(junction)`, no `(label)`, no `(sheet_pin)`, no bus entry, no `(group` was emitted (grep of the output: 0 of each). Flow arrows are dashed polylines with arrowheads (thick dashed = power net, thin dashed = signal net) plus text labels "NET source-page→destination-page". Electrical sheet pins were NOT attempted: the child sheets use global labels and no root sheet pins exist, so true sheet pins would need a different root/child contract; limitation recorded, not tested. Chosen shape: the native root file itself carries the overview graphics (not a separate derivative page); sheet instances, paths, the six sheet uuids and the root uuid are unchanged (38 identity lines compared modulo (at)/(size) geometry: identical). Only the sheet symbols' (at)/(size) and name/file text positions moved, and the title block was replaced.

(b) 58-net root comparison (kicad-cli 9.0.9, full project netlist before = old root, after = new root): nets 58 vs 58, pins 167 vs 167, net names identical, per-net node membership identical (`.src/r9_root/partition_equality.txt`, comparator `cmp_nets.py`). First comparator version parsed 0 nets on both sides (vacuous "identical"); it was fixed and rerun before this result. This proves CONNECTIVITY INVARIANCE only, not overview correctness. Root ERC before vs after: same type counts (54 lib_symbol_issues, 2 global_label_dangling, 1 power_pin_not_driven, 1 pin_to_pin; 58 total); per-violation identity not compared. The six child .kicad_sch files are byte-identical to the editable/ set (cmp).

(c) Legend text, verbatim (text object on page 1, confirmed in the KiCad source): "Functional flow — not electrical connectivity". Companion legend lines: "thick dashed = power net, thin dashed = signal net"; "Arrow labels: NET source page -> destination page (text reference only)." Title: "btdongle — System Overview".

Deliverables: 00.overview-v1.png (page 1 at 150 dpi, 1754x1241) sha256 9644759ccc0002edab61816f48f5140d73f08cb0f46713ca3c5bd506600423b7; 00.btdongle_ms-v3.pdf (7 pages, overview is page 1) sha256 2a9e0bc2cbdb05159ab740125e4e99c83b67c64ebbf37c2a113bdc8a6c07b927; editable/btdongle_ms.kicad_sch sha256 9d7d1f3095aeeb04963c85b7790d2966b1436ca1baab503b1991a29a569ade67. Superseded, moved to .history/: 00.btdongle_ms-v2.pdf (470c8ea0…), editable-history/00.root-v1.kicad_sch (8fff1dee…); both unchanged bytes.

What was hard: arrow routing without crossings between the over-the-top ENPPB/STAT routes and the power_rail/charge_enable blocks; keeping text off arrows is not measured.

(d) NOT MEASURED: the semantic review ("how does this board work from this page?", officer dispatches); my own reading of the rendered PNG (not viewed by me; only the PDF text layer was checked, which showed all labels present and the legend text); arrow/text overlap and zero-crossing on the page (no detector run); S1 (not applicable: no engine candidate, root has no components); page use >= 70% target (not measured); correctness of the one-line role descriptions against the netlist (written from child component values, not checked per-net); whether the arrow directions match true net drivers; per-violation ERC identity; full test suite; image build.

Hash binding for this round is in btdongle_ms/.src/hashes.sha256 (root reported in the BRNS-DONE).

## §R9.R — Review 13 record (00.overview-v1, root system overview)

Verdict: ACCEPT-marginal. Reviewer ses_eee8dabadffep0mnzPoXNbGNJk, PNG-only, PNG sha256 9644759ccc0002edab61816f48f5140d73f08cb0f46713ca3c5bd506600423b7. Axis: system-overview intent review (seven questions as dispatched); not traceability, not S1 calibration; not comparable to Reviews 1-12 as calibration evidence. Full verbatim text: `s3-first-leaf-review-20261006.md` Review 13 and `btdongle_ms/.src/reviews.md`. Cross-ref: updates the §R9 NOT MEASURED item "semantic review" (now recorded; the other §R9 unmeasured items stand). Not human_approved; not electrical / fab / license acceptance; the 58-net invariance proves connectivity only.

Named residuals (reviewer's words, recorded, not resolved):

| # | Residual |
|---|---|
| i | BATT 02<->03 double-headed arrow leaves charger / cell / Q1 direction unresolved; single worst item |
| ii | BATT 03->06 and BATT 03->04 are drawn as thick power arrows though 06 is a sense tap and 04 a switch pull level |
| iii | Q1 load-switch gate net appears on no arrow |
| iv | USB D+/D- absence is not stated |
| v | NTC arrow is faint |
| vi | ENPPB / STAT top routes visually touch near 02 |

The reviewer's nine designer questions, carried verbatim as OPEN ITEMS. Owner: design authority (user). Not resolved here.

1. What is the actual direction of BATT between 02 and 03 under charging vs discharging, and where does the Q1 load switch sit relative to SYS and BATT?
2. Does the Pico VSYS get SYS only (from the ETA6003 power-path output), or can BATT reach VSYS another way?
3. What drives the Q1 load switch (gate net name)? It appears on no arrow.
4. Is USB data (D+/D−) connected to the Pico, or is USB-C power-only? Nothing on this page says.
5. Is `BATT 03→06` only a sense tap for the VBAT divider? If so, why thick (power) rather than thin (signal)?
6. Does ENPPB originate on 04 (SW1) and terminate at U1 on 02 only, or does the MCU also see it?
7. Is the NTC thermistor physically on the battery pack (J2) or on-board R5 only?
8. Is there any power-good/charge-complete signal to the MCU besides the STAT LED on 04?
9. Why 7 sheets in the title block count "1/7" when exactly six sub-sheets are shown — is a seventh sheet hidden?

## §R10 — Typography re-compose of 06.io and 00.overview (user ruling R-C; presentation only)

Run dir: ~/.cache/scratch/s3-elk-spike/run-r10-20261006-215831/. Generators: `draft_io_r10.py`, `draft_root_r10.py` (copies in btdongle_ms/.src/r10_typography/). Hand-drafted, no engine. Superseded versions moved bytes-unchanged to .history/ (00.btdongle_ms-v3.pdf, 00.overview-v1.png, 06.io-v2.png, editable-history/00.root-v2.kicad_sch, editable-history/06.io-v2.kicad_sch).

Rule application (one free-text font size per page; refs/values, pin numbers, net-label and power-symbol text and the title block stay at KiCad defaults, per rule 5):
- 06 io: FS = 2.5 mm. Setting box: group A "Status LEDs" (most text: three wrapped notes plus tags and off-page notes). Sweep (plan mode, fit and overlap self-check): 2.5 fits with no violation; 2.6 and above overflow the frame / title block (2.8 and 3.0 also self-check text overlaps). 2.5 was the largest tested size without violation (steps 0.2 above 2.0, then 2.5 and 2.6; sizes between were not all tried). Applied to every free text on the page (headings, tags, notes, off-page notes). Boxes resized to content; vertical wire extension EXG = 0.
- 00 overview: FS = 2.2 mm (sheet-symbol Sheetname/Sheetfile properties included). Setting boxes: the 01 usbc and 05 mcu_swd role boxes (6 wrapped lines each in 54.5 mm wide blocks) set block height; the largest FS without a self-check overlap was 2.2 (2.3 and 2.4 produced one text/arrow overlap, "LED_WIFI 05->06"; 2.5 and above overflow the page). The text-width model was first too optimistic (about 2x on some lines); real extents were then measured from the rendered PDF word boxes (pdftotext -bbox) and blocks widened from 47 to 54.5 mm.

Margins and page use (rendered-page ink bbox, drawing sheet excluded, to the 10 mm frame inset; script ink.py; `.src/r10_typography/margins_pageuse.txt`):
| page | state | left | right | top | bottom | bbox page-use |
|---|---|---|---|---|---|---|
| 00 | before (v3 p1) | 2.7 | 19.1 | 7.3 | 19.0 | 0.794 |
| 00 | after (v4 p1) | 4.9 | 4.1 | 5.1 | 22.7 | 0.826 |
| 06 | before (v3 p7) | 2.5 | 7.6 | 10.2 | 17.3 | 0.825 |
| 06 | after (v4 p7) | 3.9 | 3.9 | 3.9 | 5.4 | 0.924 |
S1 page_use_bbox_ratio on 06 (symbols+wires+labels only, S1 drawable area): r8 0.5195 -> r10 0.525 (grid ratio 0.0782). This does NOT reach the 70% target by S1's definition; the ink-bbox figures above include text and dashed outlines. Both numbers are reported; the S1 one is the instrument's.

Electrical results (kicad-cli 9.0.9, non-vacuous comparator `cmp2.py`; `final_equality.txt`):
- 06 io per-sheet: nets 10 vs 10, pins 24 vs 24, per-pin pin->net identical vs v2.
- Root project netlist: 58 vs 58 nets, 167 vs 167 pins, identical partition vs both the original root and the r9 root.
- 06: 31 wires, all passed an orthogonality assert in the generator; 7 junctions; same refs/uuids as v2. Root ERC type counts unchanged (54 lib_symbol_issues, 2 global_label_dangling, 1 power_pin_not_driven, 1 pin_to_pin); per-violation identity not compared.
- 00 guardrails: 0 (wire), 0 (junction), 0 (sheet_pin), 0 (label), 0 (group) in the root file; 38 sheet-identity lines identical to the original root modulo (at)/(size); legend object present once, verbatim "Functional flow — not electrical connectivity". Five unchanged child sheets byte-identical (cmp) to the previous set; io is the re-composed one.

S1 f98dc237 on 06 (real-evidence calibration record; module sha256 f98dc2371afc3202485bd1a7cc808b9b118a9578b8dbfed131a6cc68fdad269f): classes a-f pass, 0 findings; overall verdict indeterminate. calibration_ref.status = out_of_scope ("subject rotations [270, 90] not in supported [0]") exactly as read from the report, so a-f results are diagnostic only, not detector acceptance. S1 min font 1.69 mm. 3 sheet-graphic ink items (dashed outlines), owner unknown. 00 has no components; page use by bbox only (above).

Carried defects, not fixed: rendered word-box overlaps on 06 of the KiCad default ref/value text (e.g. R9 vs 1k, D3 vs PWR_GREEN), 12 pairs, identical count to v2 (r8 baseline 12) by pdftotext word boxes; S1 f reports none. PWR_LED_K misnomer and the label-direction item remain open (§R8.R). Review 13 residuals on the overview (BATT 02<->03 arrow, etc.) are not addressed by this typography-only round.

Delivered (sha256): 00.overview-v2.png bc699a5af36a5430406ee3967e8a6a98c7b51c2c4196c0412d6431935bc98485; 06.io-v3.png 04942fe559b8b66d55e97cf45d98286a8ee9cc554bb0a7f8ab6b7320d551ea8a; 00.btdongle_ms-v4.pdf 70d93c7fd3d3015c633edeb39f801a1a6ca0d37239e2cc2ddd1847f7bd2f65d8 (7 pages); editable/io.kicad_sch 65430dad52fb700472833a2ddae2221ad87ed5a2681a2dd7f2ca04589b55964c; editable/btdongle_ms.kicad_sch e7f81ec86ffd697f39d506824d6db6d60fbf2e0762f6bccee0832559e1aca07d.

I did NOT view the final PNGs (media budget); all layout checks are numeric (word boxes, ink bbox). Intermediate renders were not viewed either.

NOT MEASURED: independent blind review of v2/v3 (officer dispatches); whether the text now looks right; text-vs-symbol-body clearance; per-violation ERC identity; whether the 00 overview text is clipped by anything other than the checked word boxes; full suite; image build. The "mcu_swd" box-edge crossings printed by chk00.py (x=86.2) are a false positive of the checker (that x is a power_rail column edge; the mcu_swd box spans x 74..128.5).

## §R10.R — Review 14/15 verdicts (typography/composition before-after)

Reviewer ses_eee6830c2ffe7xGc4gToL0lHEF (independent, PNG-only); verbatim in s3-first-leaf-review-20261006.md Review 14 (pair A, 00.overview v1->v2) and Review 15 (pair B, 06.io v2->v3), plus "Corpus classification (officer) — R10". Verdict on both pairs: IMPROVED (balance and font size confirmed fixed), with new defects introduced by the re-compose. Axis differs from Reviews 1-13; not calibration evidence. This supersedes the §R10 NOT MEASURED item "independent blind review of v2/v3" for v2/v3 only; v3/v4 (fix round below) are NOT yet reviewed.

## §R10.1 — Fix round (00.overview-v3, 06.io-v4; presentation only)

Run dir: ~/.cache/scratch/s3-elk-spike/run-r10fix-20261006-222711/. Generators: `draft_root_r10.py` / `draft_io_r10.py` (modified copies in btdongle_ms/.src/r10fix/; the r10 originals stay in .src/r10_typography/). Hand-drafted, no engine. Base for the root generator = original root (editable-history/00.root-v1.kicad_sch); a first attempt on the r10 root doubled the text objects (rendered word overlaps 219/352) and was discarded.

Font size (fit-to-box rule re-applied, unchanged): 06 = 2.5 mm, set by group A "Status LEDs" (2.6 still fails: C bottom 170.3 > 164 and B bottom 201.1 > 197); 00 = 2.2 mm (unchanged; 2.3 not re-tested). No size change was forced.

06 fixes: (a) title-block comments shortened ("Status LEDs, debounced user button, VBAT divider to MCU ADC." / "Hand-drafted (r10); same circuit as the engine version."); no rendered word right of x=284.5 other than frame labels. (b) SW_USER note broken at a word boundary into two lines ("-> mcu_swd" / "U2.GPIO18 (pin 24)"); VBAT divider column moved left so "<- power_rail U1.BATT (pins 14, 16)" and the GPIO26 reference no longer wrap per generator wrap(). (c) group heading now sits one line above the BT/PWR/WIFI sub-headings, all three on one baseline (yTag = yH + 1.7*LP). (d) the three user-button notes now one block (no inter-paragraph gaps), same as LED notes. Added text, not requested: a PWR off-page note "<- +3V3 from mcu_swd U2 (pin 36)" so the three columns match; pin 36 is taken from the 05 mcu_swd role text / review, not re-verified here.

00 fixes: (a) ENPPB/STAT over-the-top routes moved to x offsets 38/48 mm inside boxes 02/04, clear of the sheet-name text. (b) SW_USER and VBAT_SENSE rows now inside the 05->06 gap (rows start at box top + 2 mm, 6 mm step); box 05 moved to x=60, box 06 to x=177 (gap widened). BATT 03->06 drop moved to x=io+8. (c) role text inset 3.0 mm from box edge (was 1.6) for arrowhead clearance. (d) notes split into three columns across the band under the blocks (Power path x=15.5, legend x=107, Interfaces x=213).

Measured (kicad-cli 9.0.9):
- 06 per-pin: 10 nets / 24 pins identical to v3 and v2 (cmp2.py, non-vacuous). 31 wires orthogonal (generator assert), 7 junctions.
- Full project: 58 nets / 167 pins, names and partition identical to the r10 v4 export and to the ORIGINAL root (r9 before.net). Proves connectivity invariance only.
- 00 root: 0 wire/junction/sheet_pin/label/group; legend text present exactly once, verbatim "Functional flow — not electrical connectivity"; five child sheets byte-identical to editable/; rendered word-box overlaps on page 1 = 0; word boxes vs arrow polylines overlaps = 0 (my own check, polyline segments padded 0.1 mm).
- 06 rendered word-box overlaps = 12, same ref/value default-text pairs as v2/v3 (R9 vs 1k, D3 vs PWR_GREEN ...); carried, not fixed (refs/values stay KiCad default per ruling).
- ERC full project: 58 violations, same type counts as r10 (lib_symbol_issues 54, global_label_dangling 2, power_pin_not_driven 1, pin_to_pin 1); per-violation identity not compared.
- S1 f98dc237 on 06 (real-evidence record, explicit 7-pair mode, same as r8): a-f all pass, 0 findings; overall indeterminate; 3 sheet-graphic ink objects (owner unknown, no findings). page_use_bbox_ratio 0.4586 (r10: 0.525; r8: 0.5195): it fell because the divider moved left; S1 target 70% is not met.
- Ink bbox (drawing sheet excluded, to 10 mm frame inset): 00: left 4.9 / right 4.1 / top 5.1 / bottom 44.5 mm, page-use 0.7153 (r10: 4.9/4.1/5.1/22.7, 0.8264). The content block is now shorter, so the bottom margin and page-use got WORSE vs r10 (the Review 14 centre hole is filled but the whole composition ends at y=155.6 mm). 06: 3.9/3.9/3.9/6.4, 0.9192 (r10: 0.9244).

Delivered (sha256): 00.overview-v3.png 945a7df15ee94ec76fda0d2422c7392b981fe3a5373877f974b3bc859a73552c; 06.io-v4.png 820d88c0a023a9f06813e5ab173cef0d1655a50bedb9330b86c0fce31f861ee9; 00.btdongle_ms-v5.pdf ca266c959b30af85873e70c393e4222ace9a9029ddef8468cb9d908116c65ae1; editable/io.kicad_sch bfba88be17f8db07a2ef2a0b2be2e5ae4c5d00d4532fbcadf503160d3b0049ee; editable/btdongle_ms.kicad_sch 359a2314963d3f193ddddbfd96f6d869cbe9449807e620d2497f435982bfe801. Superseded moved bytes-unchanged to .history/ (00.overview-v2.png bc699a5a..., 06.io-v3.png 04942fe5..., 00.btdongle_ms-v4.pdf 70d93c7f..., editable-history/00.root-v3.kicad_sch e7f81ec8..., editable-history/06.io-v3.kicad_sch 65430dad...); hashes verified equal before and after the move.

I did NOT view the final PNGs or any intermediate render (media budget); every check is numeric (word boxes, polyline/word overlap, ink bbox). Whether the Review 14/15 defects are visually gone is therefore unmeasured by me.

NOT MEASURED: independent review of v3/v4 (officer dispatches); visual result; whether arrow labels on 00 now sit unambiguously beside their arrows; text-vs-symbol-body clearance; per-violation ERC identity; Review 13 residuals (BATT 02<->03 etc.) still not addressed; full suite; image build.

## §R10.2 — Review 16 verdicts and fix round 2 (00.overview-v4; 06.io-v4 FINAL)

Review 16 (reviewer ses_eee5db110ffeh83xtuErNW6Ra9, axis "typography/composition verification"; verbatim in s3-first-leaf-review-20261006.md, classification R10.2): 06.io-v4 ACCEPT (B1-B4, B6 fixed; B5 two-size look = rule-5 exclusion, carried); 00.overview-v3 ACCEPT-marginal (A1-A3 fixed; A4 partial, blank strip bottom-left; A5 new, title-block comment overrun). 06 was not touched in this round (editable/io.kicad_sch still bfba88be...).

Run dir: ~/.cache/scratch/s3-elk-spike/run-r10fix2-20261006-223639/. Generator: modified `draft_root_r10.py` (copy in btdongle_ms/.src/r10fix2/); base = original root (editable-history/00.root-v1.kicad_sch).
Changes (00 only, font 2.2 mm unchanged): (a) title-block comments shortened to "Functional overview of six sheets (diagram only)." and "Hand-drafted overview; sheet instances unchanged."; pdftotext -bbox: no rendered word right of x=284.5 except frame labels, title-block text max x1 273.7 mm, no body word in the title-block area. (b) I chose to stack the Interfaces note under the Power path note (left column, 85 mm wrap) and widen the block-row gap from 16 to 22 mm (env GAP=22; 23 also planned clean, 30+ violates), leaving the legend column in place. Not a vertical spread to the title-block line by construction: the notes now end at y=194 mm.
Measured: ink bbox (drawing sheet excluded) left 4.9 / right 4.1 / top 5.1 / bottom 6.4 mm, page-use 0.9092 (v3: 4.9/4.1/5.1/44.5, 0.7153; r10 v2: 0.8264). Note: the notes block now sits across x 15.5..~100 at y up to 194 and the title block occupies x>=177 on the bottom right; the generator's own overlap check and the rendered word boxes show no collision.
Electrical/identity: full project 58 nets / 167 pins, names and partition identical to the r10fix v5 export and to the ORIGINAL root (equality.txt; non-vacuous cmp2.py); 0 wire/junction/sheet_pin/label/group; legend verbatim once; six child sheets byte-identical to editable/; page-1 rendered word-box overlaps 0; ERC 58 violations, same type counts (lib_symbol_issues 54, global_label_dangling 2, power_pin_not_driven 1, pin_to_pin 1), per-violation identity not compared. Word-box vs arrow-polyline overlap check was NOT re-run in this round (the generator's own text/arrow self-check reports 0).
Delivered (sha256): 00.overview-v4.png 1fb1a3da843df67462d43cc497977fd7be5360f5f43dd7b7ce8280ece81d7c99; 00.btdongle_ms-v6.pdf 7d2b56ba8c67bb4f46da85e6382821a114c81f74c590633fbecee165a738367b; editable/btdongle_ms.kicad_sch 865c253a6d1bc7a7c2f899fb17ea1646ff22eedcdd085bcb10482077fe521786. Superseded moved bytes-unchanged to .history/ (00.overview-v3.png 945a7df1..., 00.btdongle_ms-v5.pdf ca266c95..., editable-history/00.root-v4.kicad_sch 359a2314...), hashes equal before and after.
I rendered the final PNG but did NOT view it (media budget); layout is checked numerically only.
NOT MEASURED: independent review of 00 v4 (officer dispatches); visual result; Review 13 residuals (BATT 02<->03 etc.); text-vs-symbol-body clearance; per-violation ERC identity; full suite; image build.

## §R10.3 — Review 17 and close of the r10 typography round

Review 17 (reviewer ses_eee58b995ffeF5B0tH8xT2QveL, axis "typography/composition verification"; verbatim in s3-first-leaf-review-20261006.md, classification R10.3): 00.overview-v4 (PNG 1fb1a3da843df67462d43cc497977fd7be5360f5f43dd7b7ce8280ece81d7c99) = ACCEPT. A5 FIXED (both title-block comment lines end about x1405 px, border about x1685). A4 FIXED (Interfaces note runs level with the title-block bottom). No regressions found by the reviewer. Named residual (reviewer words): about 6% blank band centre-bottom below the legend (x 560-1045, y 890-1165 px), cosmetic only. This supersedes the Review 16 ACCEPT-marginal of v3.

Round close (r10 typography, presentation only): both pages FINAL for this round: 00.overview-v4 (font 2.2 mm) and 06.io-v4 (font 2.5 mm, Review 16 ACCEPT). Final PDF 00.btdongle_ms-v6.pdf. The v4/v4 files are unchanged by this record step (no render, no edit of any drawing file).

Carried, not resolved here:
- Rule-5 two-size look on 06 (KiCad-default ref/value/net-label text is about half the size of box text): carried as a user-decision item; owner = user.
- Review 13 residuals (BATT 02<->03 direction, thick BATT arrows to 04/06, Q1 gate net, USB D+/D- absence, faint NTC arrow, ENPPB/STAT routes) and the nine designer questions: still open; owner = user (design authority). Reviews 14-17 do not address them.
- Open items from §R8.R unchanged (PWR_LED_K misnomer, label glyph direction, LED current / VBAT_SENSE tap questions).

Reviews 14-17 are typography/composition evidence only: not calibrated status, not human_approved, not electrical / fab / license acceptance.

NOT MEASURED: whether the author's own reading matches the reviewers' (I did not view the PNGs); text-vs-symbol-body clearance; per-violation ERC identity; full suite; image build.
