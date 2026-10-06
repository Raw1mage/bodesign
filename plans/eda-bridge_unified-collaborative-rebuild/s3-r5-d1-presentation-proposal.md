# S3 R5 Phase 1 — D1 presentation grouping + M2 compaction (ChangeProposal, PROPOSAL ONLY)

Status: PROPOSED. No code edited, no run executed, nothing committed in producing this file.
`approval_ref: null` · `human_approved: false` · Phase 2 does not start until `[BRNS-REPLY approved]`.
Author: S3 worker (Sonnet 5.5). Dispatch: topic=s3-elk-engine-spike round=r5 phase=1-proposal-only.

## 0. ChangeProposal header (P1 shape, `data-schema.json` ChangeProposal)

| field | value |
|---|---|
| baseline_manifest_sha256 | `c129b87f4e3522c17ac8caa92473d63527bbc2684ad66e345b433f668f9db638` (root of `run-20261006-162241/hashes.sha256`, 23 entries; the manifest does not list its own hash) |
| supported_edit_classes | `presentation.d1_group_outline.v1` (engine-generated candidate only; see §6 for the P1 boundary) |
| locked_object_ids | D1 symbol uuid, every D1 pin uuid, D1 lib symbol block, every wire/label/flag/no_connect uuid on the nets VBUS_CON, CC1, CC2, GND (all UNCHANGED by this proposal) |
| conflicts | none known (the pre-existing observations in §1.4 are disclosed, not conflicts) |
| approval_ref | `null` |

## 1. Baseline input manifest (run-20261006-162241, immutable)

### 1.1 Run artifacts (from its `hashes.sha256`)

| artifact | sha256 |
|---|---|
| out/usbc.kicad_sch | `0310d9ab4c71873f46af72c53dcdb52340e8a950c0630a5905cf7c51d56cdd62` |
| native/usbc.net | `b5baed561604683202b317649b136e2b88905ec7c9aaed66e271d5f32ede75eb` |
| native/svg/usbc.svg | `207a257750f08ab845db792da4bf067315c4a2c96e93d8cd37fd7866256155c8` |
| native/pdfpath/usbc.pdf | `e1e69b690961d44e8248aa9950c8214f18162487c7733a89c4d31f5bcfa2e763` |
| native/pdfpath/usbc-1.png | `9407f5c441f27135ff2261560bfbd6570198567bb3f186b5c8f5d23c1ed28533` |
| s1_report.json | `7eb4e70634ced3d7163228278d7884bb543d0fbb2696e799e231e1bfd77cef9c` |
| s1_invocation.json | `7f1b228aac42a95abf5e05e158c9849910ace535ecc5b54ae4030a0f105a7ab5` |
| fidelity_report.json | `bddcfd86dc6cda1f8b4fbeb4ca0c935312e68b0ce803fa277233801267b3bdd9` |

### 1.2 Source identity at proposal time (current bytes equal the manifest values)

| file | sha256 |
|---|---|
| elk_layout.py | `ebc02999abe1e8ede0a6b115617006b17315a738eb9f0d043c9ff2255521e71f` |
| kicad_emit.py | `b78ca97fd5a058d1127dafc22eb6de6462673f92f66f7a8a5487978623d1a9c4` |
| hierarchical.py | `0ce800500efa9566113e570de1847dad215f938d6edf2b6fb6bb95dbb42e3b8a` |
| tests/test_elk_layout.py | `f1d3863ba428465c816cbcc0c4d9ebe0f3258149f9cf7dfc55aa44f0f9a19ed6` |
| elk/runner.cjs | `7b63c55ecc5aa8df9635ec8888eb0628d6a20db2816b270c44ed3ad40b3bd617` |
| receipt s3-engine-spike-receipt.md | `1d903374c045ad8fd787a384230d946bf81467cae02e767827c47721c9c25dd0` |
| readability_render.py (as bound in the manifest) | `9c18bc518eafa4362029adf2391c8d1ce05466f8dd875299133676338669fac8` |

I re-hashed the five working-tree files above on disk this turn and they match the manifest. I did not re-hash `readability_render.py` this turn (value is the manifest's).

### 1.3 D1 symbol digest and object IDs (baseline `out/usbc.kicad_sch`)

| object | location / id | digest |
|---|---|---|
| lib symbol `Power_Protection:PESD5V0L4UF` (units `_0_1` graphics, `_1_1` pins) | lines 984–1321 | sha256 of those lines `80c0d88ae21bc0391b77e668f85af274c166ed3f6f13a3288bb54b44862f419f` |
| D1 instance | lines 1514–1526, uuid `975183bb-8215-4272-8912-cb1ed2e4d06c`, `(at 102.87 78.74 0)`, unit 1 | sha256 of those lines `e68e9177a7867393c4eb7da098e65559546944505a503e4376d29ffc5f49ea05` |
| instance pin uuids present | pin 1 `82ccaab6-9494-4806-a579-ff58c70a4589`, pin 2 `7520b6ae-8d1a-44c8-8eb6-bcf42159cb6d` | — |
| Reference property | `(at 106.68 88.9 0)` justify left | — |
| Value property | `(at 106.68 91.44 0)` justify left | — |

D1 native geometry (lib coordinates, y up; sheet = instance origin + (x, −y)):

| pin | lib tip | sheet tip | net (declared) |
|---|---|---|---|
| 1 K1 | (−2.54, 0) | (100.33, 78.74) | VBUS_CON |
| 2 A | (2.54, 0) | (105.41, 78.74) | GND |
| 5 A (hidden, stacked on pin 2) | (2.54, 0) | (105.41, 78.74) | GND |
| 3 K2 | (−2.54, −7.62) | (100.33, 86.36) | CC1 |
| 4 K3 | (−2.54, −15.24) | (100.33, 93.98) | CC2 |
| 6 K4 | (−2.54, −22.86) | (100.33, 101.60), `no_connect` present (baseline line 1591) | not connected |

Four diode glyphs, each spanning x ±1.016, at lib y 0, −7.62, −15.24, −22.86 (extent ±1.016 about each). Overall glyph extent in lib coords: x −1.016…1.016, y +1.016…−23.876.

### 1.4 Pre-existing observations in the baseline (disclosed; NOT changed by this proposal)

1. Two coincident `global_label "GND"` at (105.41, 78.74) (baseline lines 1612 and 1614), one for each of the stacked pins 2 and 5. This is the current flag duplication. The ruling says "NOT GND flag duplication" — I read that as "do not add more". I propose to leave these two exactly as they are. Removing one would change the continuation/flag emission, which is outside this slice. Ask in §7 if the officer wants it handled.
2. The D1 instance block lists `(pin ...)` entries only for pins 1 and 2 (pins 3, 4, 5, 6 have no instance pin entry). The fresh native netlist still carries all D1 pins (`fidelity_report.json` 24/24), so the lib symbol supplies them. I have not determined whether this is an emitter quirk, and I do not propose touching it.
3. The glyphs for rows 2–4 have no drawn anode connection to pin 2 in the lib symbol itself. That is the underlying cause of "four loose glyphs"; this proposal groups them visually, it does not draw the common anode.

## 2. Proposal A — D1 presentation grouping (Astra option i, narrow)

### 2.1 What is preserved byte-for-byte

- The lib symbol block (digest above), unit, pin numbers/names/types, pin tips, internal glyphs, the D1 instance `(at 102.87 78.74 0)`, unit, uuid, instance pin uuids, `lib_id`.
- Declared pin→net map, all wires/labels/flags/no_connect objects (positions are re-solved by the engine, but their net membership and count are asserted unchanged).
- No new electrical component, no new pin, no pin endpoint, no wire inside the outline, no new GND flag.

### 2.2 Exact objects added (sheet level, engine path only)

1. ONE native `(rectangle ...)` on the sheet (not in `lib_symbols`, not SVG overlay):
   - Rule (offsets relative to the D1 instance origin, which is (102.87, 78.74) in the baseline): start = origin + (−1.27, −1.27), end = origin + (+1.27, +24.13) in sheet y-down. In baseline coordinates: `(start 101.60 77.47) (end 104.14 102.87)`.
   - `(stroke (width 0.1524) (type dash)) (fill (type none))`, so it reads as a package boundary, not wire or glyph. Deterministic uuid: uuid5 of the D1 symbol uuid + `"presentation.outline"` so the run is reproducible.
   - Margins: 1.27 mm is on the 1.27 grid. It clears the glyph hull by 0.254 mm in x (1.27 vs 1.016) and in y at the top (1.27 vs 1.016) and bottom (24.13 vs 23.876), which is above the engine's `INK_CLEAR_MM = 0.25`.
2. ONE native `(group "D1 package outline" (uuid ...) (members <rectangle uuid> <D1 symbol uuid>))` tying the outline to D1's presentation identity. The D1 symbol object is referenced, not modified. Group serialization must be validated by a fresh `kicad-cli` load (§2.5). I have not tested KiCad 9.0.9 group syntax for symbols in this turn.
3. Caption: NO new text object. The one grouped caption "D1 / PESD5V0L4UF" is D1's existing native Reference and Value fields, kept stacked (two lines) as one caption block placed against the outline. This avoids a duplicate "D1" text and keeps the fields as real properties. A single-line `(text "D1 / PESD5V0L4UF")` object would duplicate the Reference and force hiding the native fields (an edit to D1's field attributes); I do NOT propose it. If the officer wants the literal single-line text, that is a separate decision.

### 2.3 Pins meeting the boundary (deliberate)

Pins 1, 3, 4, 6 cross the left boundary x = 101.60, and pins 2/5 cross the right boundary x = 104.14. Each pin tip stays 1.27 mm outside the box and the pin crosses at its midpoint. Alternative (box edge exactly at pin tips x = 100.33 / 105.41) rejected: the edge would lie on every wire end and be ambiguous against wire ends/junctions. No wire, label, flag or no_connect marker may fall inside the box (§2.4).

### 2.4 Ink model changes (engine only)

- `plan_node_ink` (elk_layout.py:373): when a presentation group is declared for a ref, the reserved hull = union(current pin-inclusive symbol hull, outline rectangle). The current `g.bbox` hull is pin-inclusive in x (the Reference text sits at pin tip + 1.27 = 106.68), so the outline is inside it in x. The outline may extend the hull in y by up to 1.27 mm at each end; the exact numbers are measured in Phase 2 and recorded.
- `PresentationSolution` (elk_layout.py:765): add the outline box and caption block box so the solution persists them. The solution verification refuses (typed refusal, not a reroute) if a foreign or own wire, label, flag or no_connect marker enters the outline interior, or the caption block overlaps any ink.
- Caption relocation rule: Reference/Value are re-chosen ONLY from the existing candidate set (`_prop_candidates`, elk_layout.py:342) evaluated against the new union hull; first candidate that clears hull, flags and exits wins. Predicted baseline effect: Reference/Value x stay at 106.68; y may shift by ≤1.27 mm to keep the centred "right" slot. This is a prediction; before/after coordinates will be recorded in the receipt. No new candidate positions, no free placement.
- Declaration surface: one new optional spec key in `hierarchical.py` (engine path only, default off), e.g. `presentation_groups: {"D1": {"outline": "package"}}`. It does not exist in the legacy path.

### 2.5 STOP / fallback conditions

- If KiCad 9.0.9 will not load the rectangle + group reliably on a fresh `kicad-cli` export (netlist, SVG, PDF), or the group needs D1's symbol object to be rewritten: FAIL EXPLICITLY with the constraint. I do not simulate the group with an SVG overlay or loose lines.
- If the outline cannot be represented without redrawing pins or internal glyphs: STOP, and propose instead (separately qualified, separate allocation) a boxed library symbol: explicit pin mapping 1–6, units/hidden/stacked-pin rules (pin 5 stacked on pin 2), and an embedded-symbol comparison against the baseline lib block. No opportunistic substitution.
- If adding the outline makes the engine produce a foreign crossing that the baseline M2 did not have, report it and stop. No new placement model is authorized in R5.

### 2.6 Unchanged-identity assertions Phase 2 will check (fresh export)

1. D1 lib symbol block digest equals `80c0d88a…` (Phase 2 will diff the block; the instance block differs only in the two property `(at …)` if the caption moves).
2. D1 instance uuid, `(at …)`, unit, `lib_id`, and instance pin uuids unchanged.
3. Fresh `kicad-cli` netlist: net set and node set equal the declared map; 24/24 pins, 5/5 classes, 0 fused / 0 missing / 0 misrouted / 0 name mismatch; D1 pins 1–6 present with the same nets.
4. ERC: no violation type beyond the baseline's six `lib_symbol_issues`.
5. Count of wire/label/flag/no_connect objects per net unchanged; the GND flag pair at pins 2/5 unchanged in count and net.
6. Exactly one added rectangle and one added group on the sheet; nothing else added.

### 2.7 Expected output

Editable `out/usbc.kicad_sch` containing the D1 dashed package outline + group, fresh netlist, ERC, SVG (S1 input), native PDF → `pdftoppm -r 150` PNG, export receipt, S1 `measure()` (readability_render.py as on disk, record the hash; real-evidence calibration record; scope a–e; same explicit 10-pair `required_local_pairs` as R4), `hashes.sha256` binding every output and render chain (the manifest's own hash reported once after the last rebind, not listed as an entry).

### 2.8 Risks, stated rather than hidden

- S1 has not been run on any schematic with a sheet-level dashed rectangle. It may read the dashed rectangle as ink or wire in the SVG. I will report whatever it does and will not edit `readability_render.py`.
- A box around four diode glyphs whose anodes are not drawn together may itself imply a shared internal connection (the electrical truth is a common anode, pins 2/5). The ruling forbids implying internal wiring. The reviewer must judge this; I cannot measure it.
- The outline does not fix the missing anode drawing (§1.4 item 3).

## 3. Proposal B — M2 compaction (Astra option i)

- Retained: M2 partition J1 < R1 < D1 < R2 (`elk.partitioning` partitions J1=0, R1=1, D1=2, R2=3), identity orientation for all symbols, the R2-selected ELK options other than the spacing below.
- Baseline spacings (R4): `nodeNode 5.08`, `nodeNodeBetweenLayers 10.16`, `edgeEdge 2.54`, `edgeEdgeBetweenLayers 2.54`, `edgeNode 2.54`, `edgeNodeBetweenLayers 3.81`, `portPort 2.54` (elk_layout.py:82–88).
- Settings: at most TWO — S0 = R4 baseline spacings (with the D1 outline), S1 = ONE compact setting.
- S1 values are NOT fixed in this proposal. Rule: each changed spacing = the smallest grid multiple that still holds (largest facing ink margin on both sides from `plan_node_ink` + `INK_CLEAR_MM` + the number of edges in the channel × `edgeEdge`); the bound comes from actual body/text/flag clearance and not from page-fill %. The numeric values will be written to receipt §R5.1 after the D1 outline run at S0 has been measured and BEFORE the S1 run. Observed baseline gaps for context: R1.x1 78.49 → D1.x0 100.33 (21.84 mm); D1.x1 105.41 → R2.x0 134.87 (29.46 mm); area 8532.89 mm².
- Forbidden: post-scaling, pin movement, coordinate nudge, a third partition, any new option sweep.
- Selection order: zero foreign crossings → electrical + ink validity → area / total wire length. Keep S0 if S1 worsens any invariant: crossings, ink validity, 24/24 fidelity, S1 per-class finding counts, or a carried-item measurement from §4.

## 4. Carried items named for the review scope

Carried from Review 4, each re-measured from the fresh SVG/geometry in Phase 2, with no special-casing:

1. Near-crossing gap at x≈397 (y 480–525). I read the PNG pixel values (150 dpi) as ≈ 67.2 mm, y ≈ 81.3–88.9 mm; this mapping is my own conversion and unchecked against the reviewer's frame. Not addressed by any R5 mechanism; reported as found.
2. VBUS flag 1–8 px from the F1 body (≈ 0.2–1.4 mm at 150 dpi). Not addressed; re-measured.
3. VBUS_CON text ≈ 3 px from the wire corner (anchor (76.2, 38.1) in R4). Not addressed; re-measured.
4. B5 ≈ 4 px under the CC1 wire. Not addressed; re-measured.
5. R2 position / lopsidedness. Targeted only through the Proposal B compaction.
6. Class e (D1 four loose glyphs): Proposal A. Class f density (R2 far right): Proposal B.
7. GND flag over D1 text, D1 bare-glyph state, text-vs-symbol-body clearance (not covered by S1 f), and the §1.4 observations: unchanged and reported.

Reviewer questions to cover: does D1 now read as one package (e)? does the dashed outline read as non-electrical and avoid implying internal wiring? is the caption one block? is the layout less lopsided (f)? do items 1–4 remain?

## 5. Phase 2 plan (after approval only)

1. Write the §R5.1 predeclaration (outline rule, caption rule, S0 spacing) before any run.
2. Implement the outline in the engine seams, with tests: (a) outline round-trips through a fresh `kicad-cli` export (netlist equality + SVG/PDF present); (b) typed refusal when ink would enter the outline; (c) D1 lib block digest unchanged.
3. Run M2 + outline at S0, record measurements, then write S1 values to §R5.1, run S1.
4. Select by §3; S1 instrument measurement; render chain; manifest; test table (S3 BRIDGE, MULTISHEET 6 modules, S1, CONTRACT 4 modules, SEAMS 4 modules; pycache cleared; verbatim Ran/exit); `[BRNS-ASK checkpoint=r5]`. Stop even if NO. Packaging stays BLOCKED (no build host).

## 6. Allowlist Phase 2 will need (declared now)

- elk_layout.py (`plan_node_ink`, `PresentationSolution`, solution verification, `solve_sheet` plumbing)
- hierarchical.py (engine-path spec key + report field)
- kicad_emit.py (engine-path emission of the rectangle + group; caption consumption) — I will re-read it before editing and record touched function names and line ranges
- tests/test_elk_layout.py
- receipt `s3-engine-spike-receipt.md` §R5
- a new sibling run dir `~/.cache/scratch/s3-elk-spike/run-<ts>/`
- Not needed: symbol-library edits, runner.cjs, readability_render.py, P1 schema or adapter code. This proposal does NOT require a P1 schema change or library/source edit; the added edit class label is documentation of the candidate's generated content, not a registration in the P1 adapter. If the officer wants `presentation.d1_group_outline.v1` registered in P1 `supported_edit_classes` or the boxed-library-symbol fallback activated, that needs separate allocation.

## 7. Open questions for the officer (answer in the approval, or Phase 2 uses the stated default)

1. Caption form: native Reference/Value stacked (default) vs a literal single-line text object.
2. Leave the stacked GND flag pair on pins 2/5 as-is (default) vs dedupe.

## 8. Not measured in Phase 1

KiCad 9.0.9 group/rectangle serialization and load; S1 behaviour with a dashed rectangle; actual hull/caption coordinates after the outline; the S1 compact spacing values; whether the outline changes ELK's M2 outcome.

## 9. Amendment A — rectangle-only (scope amendment; NOT an automatic fallback)

Status: PROPOSED amendment. Sections 0-8 above are unchanged and still the record of what was approved at officer level on 2026-10-06 (approval_ref = BRNS-REPLY approved phase=2-authorized). This amendment is NOT approved until a new `[BRNS-REPLY approved]` arrives. `approval_ref` for Amendment A: `null` · `human_approved: false`. Astra ruled option (a); (b) boxed-library-symbol is NOT authorized.

### 9.1 Why (recorded as measured)

During Phase 2 the engine solve of S0 succeeded (M2, 0 foreign crossings; outline [101.6, 77.47, 104.14, 102.87]; caption ref_at (106.68, 88.9), val_at (106.68, 91.44)). The emitted sheet then failed to load: **14 group syntaxes tested, all rejected by kicad-cli 9.0.9 at file version 20250114; the supported syntax (if any) remains undetermined.** A control without rectangle+group loaded, and a sheet with the dashed rectangle alone loaded. Evidence: receipt §R5.2, run `run-r5-s0-164620`, `diag/diag.sha256`. This amendment does not claim anything about KiCad's schematic-group support beyond that statement.

### 9.2 Change to the added-object list (supersedes §2.2 items 1-2)

- REMOVED: the native `(group ...)` object. No group of any syntax is emitted.
- Added objects = EXACTLY ONE dashed `(rectangle ...)` with `(stroke (width 0.1524) (type dash)) (fill (type none))` and `uuid = uuid5(<D1 symbol uuid>, "presentation.outline")`. Geometry rule, margins, ink reservation, caption rule (native stacked Reference/Value, no new text object), pin boundary crossing and all §2.4 engine behaviour are unchanged.
- The default-off group emission already present in `kicad_emit.py` (the `(group ...)` block appended to `_outline_blocks`) is REMOVED in Step 2, not left reachable; the line range of that hunk is recorded in the checkpoint.

### 9.3 Identity tie: DATA-LAYER ownership association (supersedes the group's role)

The tie between D1 and its outline is a record, not a KiCad object. `PresentationSolution.outlines[<ref>]` AND the receipt (and `engine_reports[sheet].outlines`) SHALL record, per outline: (1) D1 symbol UUID (as emitted in the sheet); (2) rectangle UUID; (3) the derivation rule, verbatim `rect_uuid = uuid5(D1_symbol_uuid, "presentation.outline")`; (4) the baseline version: baseline manifest root `c129b87f4e3522c17ac8caa92473d63527bbc2684ad66e345b433f668f9db638` (run-20261006-162241) and the candidate's own manifest root once bound; (5) the outline box and caption box. Identification SHALL NOT rely on refdes or coordinates alone. Note stated rather than hidden: the D1 symbol UUID is generated per emit (`_uid()`, uuid4), so the rectangle UUID is reproducible from the recorded symbol UUID, not across independent emits; the receipt therefore records the actual pair per run.

### 9.4 Disclosed limitation (verbatim)

A human moving D1 in KiCad will NOT drag the outline; later ingestion must detect outline/symbol drift and raise a ChangeProposal, never auto-move the box. (Detection itself is out of R5 scope — this only declares the obligation.)

### 9.5 Conditions carried unchanged

D1 lib symbol block, pins, tips, units, internal glyphs and nets byte-identical (§2.6 assertions 1-6 re-checked on the fresh export; assertion 6 now reads "exactly one added rectangle and no group; nothing else added"). No simulated group (no loose lines, no SVG overlay). Ink reserved in the engine model; typed refusal (E_ELK_OUTLINE_*) when ink enters the outline or the caption overlaps it. "Does the box imply internal shared wiring?" is a reviewer question: if the reviewer says yes it is a NO finding, not patched in R5; the receipt states verbatim that the box asserts package membership only. STOP on any new foreign crossing. Spacing: S0 (R4 baseline + outline) and ONE predeclared compact S1; the S1 numeric values are written to receipt §R5.1b BEFORE the S1 run, derived from measured clearance; keep S0 if S1 worsens any invariant. Allowlist unchanged (elk_layout.py / hierarchical.py / kicad_emit.py engine seams, tests/test_elk_layout.py, receipt §R5, new run dir); runner.cjs `7b63c55e…` and readability_render.py `9c18bc51…` must stay byte-unchanged.

### 9.6 Added Step 2 checks specific to this amendment

(i) Fresh `kicad-cli` netlist/SVG/PDF/ERC load on the candidate (the failure that triggered this amendment must not recur). (ii) Whether S1 (9c18bc51…) reacts to the dashed rectangle is recorded explicitly. (iii) A test that the emitted sheet contains exactly one rectangle owned by D1 and zero `(group` tokens. (iv) A test of the ownership record fields in 9.3.

## 10. R6 — qualified boxed D1 symbol (NEW ChangeProposal; PROPOSAL ONLY)

Status: APPROVED WITH AMENDMENTS at officer level (Astra static review + officer) as a bounded presentation candidate; NOT a blanket symbol qualification, NOT an electrical or product approval. `approval_ref: officer:ses_04db7a1c5ffelvbxyLP1p6xlRH/r6-phase2-20261006` · `human_approved: false`. This does NOT authorize S2 apply or the NOT_IMPLEMENTED path.

> **CORRECTION NOTE (prominent; old text not rewritten).** The sentences "four diode glyphs in one SOT-363 package" in receipt §R5 (outline rule and scope statements) and in this proposal (§2) are UNSUPPORTED by the datasheet: the datasheet package is SOT886 / XSON6 and the string SOT-363 occurs nowhere in it (see 10.1). Read those sentences as "four diode glyphs in one package".
>
> **RELEASE RESTRICTION.** Footprint defect filed in the owning repo: `/home/pkcs12/products/thesmart_products/issues/BR_20261006_d1_pesd5v0l4uf_footprint_sot363_contradicts_datasheet_sot886.md`. No PCB / package / BOM / fab release from this work; "qualified" here means pin / topology / presentation scope only. The Phase 2 candidate is NON-FABRICABLE. Author: S3 worker (Sonnet 5.5). Dispatch: topic=s3-elk-engine-spike round=r6 phase=1 (gate-1 evidence authorized by ★main).

Baseline binding: run-r5b-s1-165624, `hashes.sha256` root `1001bc33b0c6f359a9c3ff92d41a8c22e982f159a43ea1e6866c1b153cc97638` (25 entries). Its `out/usbc.kicad_sch` = `1a898ecc9158197e9d403b9a8fcc5886ba578aa86d303a8f463f38d17185856b`, `native/usbc.net` = `188cc95ccbe36242878750ef6f2637b45c02485e2cb9b724f2eb19f9fbb993f2`, PNG `native/pdfpath/usbc-1.png` = `db0ba9ec09fb0ee829a49646c005c0d77e12ddba65dce3350f240f3d9d76b30b`. R5b stays the reference NO.

### 10.1 GATE 1 — datasheet evidence (PASSES, with one disclosed conflict)

Source file (read by me, host `pdfinfo` / `pdftotext -layout` / `pdftoppm`): `$XDG_CACHE_HOME/scratch/s3-elk-spike/datasheets/PESDXL4UF_G_W.pdf`.

| item | value |
|---|---|
| URL | `https://assets.nexperia.com/documents/data-sheet/PESDXL4UF_G_W.pdf` (the URL named by the KiCad symbol's Datasheet property) |
| fetch 1 | curl default UA: HTTP 403, 433-byte Akamai "Access Denied" HTML, kept as `PESDXL4UF_G_W.http403.html` sha256 `0087f16d192b12740eae2ca76072cee548ab236dc223df213a8d5ef52c8a0828`, date `Tue, 06 Oct 2026 09:10:16 GMT` |
| fetch 2 (ruled, one retry, browser UA) | HTTP/2 200, `content-type: application/pdf`, `content-length: 671899`, `date: Tue, 06 Oct 2026 09:11:34 GMT`, `last-modified: Fri, 18 Oct 2024 09:47:13 GMT`; headers kept as `PESDXL4UF_G_W.retry.headers` sha256 `ed3175c04b7d191076298674618d2b451a586864a2ead9a39ad9b335f9fe834f` |
| PDF sha256 / size | `62d2166079ebe42ac5d37b1fe704abde1a59b5a1c74d48daf50dc9682bcf036a` / 671899 bytes |
| validity | `pdfinfo`: valid PDF 1.7, **17 pages** (the officer's webfetch copy was described as 14 pages; the file I hold is 17, footers read "x of 17"); `pdftotext -layout` returned 57102 bytes, sha256 `6dc69a5c5c5b653634c5f9bfa3c8d42a5223c097e470021ecc9970716bc049a8` |
| PDF own metadata | Title "PESDxL4UF; PESDxL4UG; PESDxL4UW Low capacitance unidirectional quadruple ESD protection diode arrays"; Author Nexperia; Creator Aspose Ltd.; CreationDate Fri Feb 1 19:48:01 2008 CST; ModDate Tue May 9 17:54:19 2017 CST (both confirmed from the file) |
| document identity (from text) | Document ID `PESDXL4UF_G_W_4`, "Rev. 04 — 28 February 2008", "Product data sheet"; revision table (Table 11, p.15): release date 20080228, supersedes `PESDXL4UF_G_W_3`; page footers "© Nexperia B.V. 2017" |

Per-field table (page = "n of 17" printed in the footer; text = `pdftotext` output; figure = rendered page 2 at 130 dpi, sha256 `d2ae246fe3442ea65680d7a1db01c48bc5741f632c32c1ddd65b01f4d54cc5f3`, and a 300 dpi crop of the symbol, sha256 `a3d7d0bd09aec9157e2edf4681acf9b5a2fd1af1f1ec995a8f9e438f04a25448`):

| field | result | evidence |
|---|---|---|
| exact MPN PESD5V0L4UF named | PASS | Table 1 (p.1) row "PESD5V0L4UF SOT886 - MO-252 leadless ultra small"; Table 3 (p.2) header "PESD3V3L4UF; PESD5V0L4UF" |
| revision / date | PASS | Rev. 04, 28 Feb 2008 (above); the PDF carries a 2017 re-issue stamp, so revision identity = document ID `PESDXL4UF_G_W_4` |
| pin assignment (6-pin UF variant) | PASS | Table 3 p.2, verbatim: `1 cathode (diode 1)` · `2 common anode` · `3 cathode (diode 2)` · `4 cathode (diode 3)` · `5 common anode` · `6 cathode (diode 4)` |
| internal circuit | PASS | p.2 symbol drawing, code `006aaa156` (in Table 3's "Symbol" column; it is not a numbered "Fig N"): left terminals 1/2/3, right terminals 6/5/4; four diodes with the cathode (bar) at the outer terminal and the anode end at one vertical bus with junction dots; terminal 2 and terminal 5 are drawn as one horizontal line crossing the bus. Terminals 2 and 5 are tied together by the drawing only; the text table does not say it in words |
| shared terminal = anode, not cathode | PASS | Table 3 text "common anode" at pins 2 and 5; footnotes [2] to Tables 6, 9 and 7 p.3-6: "For PESDxL4UF measured from pin 1, 3, 4 or 6 to pin 2 or 5" (anode pins named as the return) |
| package name | PASS, **CONFLICT with repo** | Table 1 p.1: Nexperia package `SOT886`, JEDEC `MO-252`, "leadless ultra small". Table 4 p.3: Name `XSON6`, "plastic extremely thin small outline package; no leads; 6 terminals; body 1 x 1.45 x 0.5 mm", Version `SOT886`. Package outline Fig 10 p.11 "PESDxL4UF (SOT886)"; reflow footprint Fig 13 p.12 (SOT886). The strings `SOT363` and `SOT-363` occur NOWHERE in the document; `SOT353` / SC-88A is the 5-lead PESDxL4UG variant, `SOT665` is the PESDxL4UW variant |
| unit-level hidden/stacked pin facts | MISSING (not a datasheet concept) | Stacking / hiding is a KiCad drawing choice, not in the datasheet |

Package-name reconciliation, recorded, NOT resolved here: datasheet = SOT886 / XSON6 (matches the LCSC "XSON-6" catalogue name and KiCad's own library footprint property `Package_TO_SOT_SMD:SOT-886`); the usbc candidate's D1 INSTANCE footprint property = `Package_TO_SOT_SMD:SOT-363_SC-70-6` (it comes from the C03 compose spec, `experiments/aiguard_c03_compose/spec.json`, not from the library). Consequences stated, not acted on: (a) the footprint value is fixed by this proposal's brief and is left untouched; (b) the receipt/proposal sentences "four diode glyphs in one SOT-363 package" (receipt §R5 outline rule and scope statements; proposal §2) are NOT supported by the datasheet and will be corrected by an explicit note in the Phase 2 receipt, not by editing old text; (c) a SOT-363 vs SOT-886 pad-numbering mismatch is a PCB-level risk for the officer; it does not affect schematic net identity.

Approved path attempt (R6 step 2, once): `bodesign_vault_ingest` was called with the PDF path. Call 1 was rejected client-side with `Input validation error: 'actor' is a required property`. Call 2 (with `actor` set) reached the server and returned, verbatim: `VAULT-E101 "Empty or invalid MPN: ingest payload must include component, document, or specs"` (http_status 400). This is a payload-shape error (a bare file path is not a valid payload), NOT the VAULT-E002 the officer expected, so "ingest is blocked by the unconfigured vault" is NOT established by this attempt. I stopped that line after call 2 (two calls, because call 1 never left the client). No vault dir was guessed and no other payload shape was tried. The evidence above does not depend on the vault.

Wording reconciliation (brief asked for it before the phrase appears anywhere): the datasheet says each of the four diodes has its OWN cathode terminal (pins 1, 3, 4, 6, "cathode (diode 1..4)") and that pins 2 and 5 are one "common anode". The phrase "cathode -> common anode bar" is therefore NOT used in this proposal. Datasheet-faithful wording: "four independent cathode terminals; the four anodes meet at one internal common-anode node, brought out on pins 2 and 5". Whether pins 2 and 5 are one internal node is shown by the drawing (code 006aaa156), and the text only calls both pins "common anode".

### 10.2 GATE 2 — symbol search (RESULT: no existing boxed symbol; authoring proposed)

Searched: installed KiCad 9.0.9 libraries (`kicad-symbols 9.0.9~ubuntu24.04.1`, `/usr/share/kicad/symbols`) and the repo `packages/eda-bridge/vendor_symbols/` (ST only). Not searched: any other source (none was authorized); the LCSC/EasyEDA catalogue lookup earlier returned a catalogue row only, no symbol asset.

| item | measured |
|---|---|
| installed symbols for the exact MPN | `Power_Protection:PESD5V0L4UF` (file lines 32921-32984, `(extends "PESD3V3L4UF")`; base block lines 13095-13330). Single-diode `PESDxS1UL` entries in `Diode.kicad_sym` are other parts |
| boxed? | NO. The base block contains `polyline` artwork for ONE glyph in the shared unit `_0_1` and four pin units `_1_1.._4_1`; no `(rectangle)` and no `(circle)` junction dot. `grep` of `(rectangle`/`(circle`/`(arc` over the file lists nothing between lines 12991 and 14545 and nothing at 32921 onward, so no PESD quad (UF/UG/UW) or fivefold symbol in `Power_Protection` has a body box. No common-anode bus is drawn |
| library file | `Power_Protection.kicad_sym` sha256 `92c5bd5e45f30f9c134106f7abdc71571a4c9fe4a46ff3f80f319deeee993b8a` |
| library license | `/usr/share/doc/kicad-symbols/LICENSE.md` sha256 `45d2bce75e5a4208f5afb01b8fb2c406e700371c4fe2b5f5cd5c443d46db4d8f`: CC BY-SA 4.0 with the KiCad design-use exception (use in a design does not impose the license on the design; redistributing the library or parts of it, including modified, does) |
| text-range digests (lines, not parsed objects) | base `PESD3V3L4UF` 13095-13330: `67b46996fbe898a680eabb4fa145c0e045765b4a1a305047c41a3af81fd60b5b`; `PESD5V0L4UF` 32921-32984: `521c51e37918a8f65e36db6ae842f6c1421e81a0cdaf96f7f92f79c7bb627f94` |
| R5b embedded D1 block (sheet lines 984-1321) | `80c0d88ae21bc0391b77e668f85af274c166ed3f6f13a3288bb54b44862f419f` (differs from both library ranges: the emitter flattens the four library units into ONE unit with six pins and four glyphs; pin 5 is hidden and stacked on pin 2) |

Consequence: Gate 2 finds nothing to adopt. Proposal is to AUTHOR a native symbol from the verified datasheet (section 10.5 names the paths). Licensing stated, not resolved: copying KiCad's glyph polylines into a new file would make it an adaptation of CC BY-SA material; copying Nexperia's figure artwork is not offered either (document 12.3 grants no license). The authored file should use freshly drawn generic geometry (standard diode triangle/bar, a rectangle, a bus, junction dots) and take only facts from the datasheet (pin table, topology, MPN). The license to put on the authored file is an officer decision.

Re-check of the "not boxed" claim: `grep -P '^\t\t\t\((rectangle|circle|arc)'` over `Power_Protection.kicad_sym` (36754 lines) returns no hit in lines 12992-14544 or at 32900 onward; the last such hit in the file is line 31732, which precedes the PESD5V0 entries at 32921.

### 10.3 Qualification table: R5b D1 vs proposed boxed symbol

R5b facts are read from `run-r5b-s1-165624/out/usbc.kicad_sch` (embedded block lines 984-1321, instance lines 1514-1526, no_connect lines 1585-1591) and `native/usbc.net`. Symbol-local coordinates are y-up as in `.kicad_sym`; R5b instance is at sheet (100.33, 77.47) rot 0, so sheet y = 77.47 - local y.

| phys. pin | datasheet function (Table 3 p.2) | R5b pin name / type | declared net (native netlist) | R5b hidden/stacked | R5b tip (local) / dir | proposed symbol |
|---|---|---|---|---|---|---|
| 1 | cathode (diode 1) | K1 / passive | /VBUS_CON | visible | (-2.54, 0) / 0 | K1, passive, same number/name/type; left side; tip moves with the box (10.4) |
| 2 | common anode | A / passive | GND | visible; anchor of the stacked pair | (2.54, 0) / 180 | A, passive; stacked pair anchor on the common-anode bus; tip moves with the box |
| 3 | cathode (diode 2) | K2 / passive | /CC1 | visible | (-2.54, -7.62) / 0 | K2, passive, left side |
| 4 | cathode (diode 3) | K3 / passive | /CC2 | visible | (-2.54, -15.24) / 0 | K3, passive, left side |
| 5 | common anode | A / passive | GND | HIDDEN, stacked on pin 2 | (2.54, 0) / 180 | A, passive, stays a distinct pin object stacked on pin 2's tip (not deleted, not renumbered, not merged); see Q1 for the datasheet's opposite-side alternative |
| 6 | cathode (diode 4) | K4 / passive | unconnected (`no_connect` at sheet (97.79, 100.33) = tip of pin 6) | visible | (-2.54, -22.86) / 0 | K4, passive, left side; the `no_connect` stays on its tip |

Partition comparison (whole native pin partition, not only the 24 exported nodes): D1 has exactly 6 physical pins {1,2,3,4,5,6}; netlist nodes for D1 = pins 1,2,3,4,5 on nets VBUS_CON, GND, CC1, CC2, GND; pin 6 is the one unconnected pin (explicit no_connect). Required equality after Phase 2: same six pin numbers, same names K1..K4/A/A, same type `passive`, same net per pin, pin 6 still carries a `no_connect`, pin 5 still a separate pin object. R5b embedded library form: ONE unit (`PESD5V0L4UF_1_1`) with six pins plus shared artwork unit `_0_1` (four glyphs), body style 1, `pin_numbers` and `pin_names` hidden; the installed library form has 4 units (unit 1 = pins 1,2,5; units 2,3,4 = pins 3,4,6). The proposed symbol is also ONE unit, body style 1, six pins, so the instance `(unit 1)` and the instance `pin` entries do not change shape.

Identity fields that stay fixed (data, not geometry): D1 Value `PESD5V0L4UF`; D1 instance Footprint `Package_TO_SOT_SMD:SOT-363_SC-70-6` (conflict with the datasheet recorded in 10.1, NOT altered); declared nets and the continuation policy (labels `VBUS_CON`/`CC1`/`CC2`, flag pair on GND); the circuit declaration `experiments/aiguard_c03_compose/spec.json` is not edited. Changes that are intended: the instance `lib_id` string and the embedded `lib_symbols` block, and (library-level only, not instance) the new symbol's Datasheet property = the Nexperia URL and its Description. Embedded-symbol digests to compare in Phase 2: R5b block `80c0d88ae21b…` (full value in 10.2) vs the new block, plus the new `.kicad_sym` file digest.

Datasheet cross-check of the declared net map (a fact check, not a design change): cathodes (pins 1, 3, 4, 6) carry the signal nets VBUS_CON, CC1, CC2 and pin 6 is open; the common anode (pins 2, 5) is on GND. That is the polarity the datasheet topology implies for a line clamp to ground (footnote [2] p.3-6: stress is measured "from pin 1, 3, 4 or 6 to pin 2 or 5"). Not assessed here, outside this slice, stated for the officer only: Table 9 p.5-6 gives VRWM max 5.0 V and VBR min 6.46 V for PESD5V0L4UF, while D1 sits on a VBUS net; whether VBUS tolerance fits is a design question I did not evaluate.

### 10.4 Named operations (all on D1; nothing else)

| op | what | object IDs |
|---|---|---|
| OP-1 symbol replacement | D1 instance `lib_id` changes from `Power_Protection:PESD5V0L4UF` to the authored boxed symbol; embedded `lib_symbols` block replaced | D1 instance uuid (per emit; R5b value `da260240-75a4-43c0-900e-6fd634e20a61`), D1 lib block `80c0d88a…` |
| OP-2 symbol artwork | body = ONE solid rectangle enclosing four diode glyphs (cathode bar at the pin side); anodes joined by ONE internal vertical bus with junction dots, leaving the body at the common-anode terminal. This depicts the datasheet topology (p.2, 006aaa156) as native symbol artwork. External connections remain real wires on pin tips | new symbol file (10.5) |
| OP-3 pin identity | six pins keep number, name, type, unit 1, body style 1; pin 5 stays a separate pin object stacked on pin 2's tip, hidden as in R5b | D1 pins 1-6 |
| OP-4 caption | Reference/Value stay native properties; positions re-chosen by the existing own-ink placement against the new body hull; no new text object, no field hidden | D1 Reference/Value |
| OP-5 outline removal (EXPLICIT scope) | the R5b sheet-level dashed rectangle is no longer emitted, because the symbol's own body replaces it; the engine's outline code stays in the tree, unused (`engine_outline_refs` unset) | R5b rectangle uuid `6fe52893-6baa-5a25-8e33-fdae41b26d87` (R5b only) |
| OP-6 one re-layout | ONE engine run for the new hull with placement model M2 (J1 < R1 < D1 < R2), identity orientation, and the R5b compact spacings (`nodeNodeBetweenLayers` 6.35, `nodeNode` 3.81); no orientation or placement sweep, no other ELK option changes | engine report |

Allowed changes outside D1 are only those the re-layout forces (wire routes, label and flag anchors on the same nets). Electrical declaration unchanged: 24 nodes, 5 net classes, 0 fused / 0 missing / 0 misrouted.

Officer rulings (these replace the earlier "defaults"; nothing is silently defaulted):
- Q1 pin sides: K1..K4 left, common-anode anchor right, identity orientation. Pins 2 and 5 stay distinct pin objects, pin 5 hidden/stacked as in R5b, pin 6 NC retained. Corrected reasoning: Table 3's "Symbol" drawing (006aaa156) is an internal-circuit schematic, not a package drawing; its placement is not binding, only pin FUNCTION/connectivity is. All six physical pin identities stay in verification.
- Resolver: PER-RUN, PER-REF explicit replacement for D1 ONLY. No `_VENDOR_MAP` change, no `symbol_resolver.py` edit. A COPIED candidate spec with only D1's `symbol` field changed, plus the allocated library dir through the existing `symbol_dirs` input. Original spec bytes untouched; the candidate-spec diff and hash are recorded in the receipt as the approved presentation selection. `Power_Protection:PESD5V0L4UF` is not shadowed by path ordering. If the explicit path cannot load: typed refusal and stop, no fallback.
- Naming: `packages/eda-bridge/vendor_symbols/Bodesign_Presentation.kicad_sym`, symbol `PESD5V0L4UF_Boxed`, lib_id `Bodesign_Presentation:PESD5V0L4UF_Boxed`. Fresh generic geometry only. Value `PESD5V0L4UF`, pin numbers/names/types and the Datasheet URL property kept.
- Q2 license: the repo has no root LICENSE (`elk/LICENSE.elkjs.md` is not borrowed). PROVENANCE.md marks the asset "project-authored from datasheet facts; license pending owner decision; not cleared for redistribution or global promotion; internal review use only". No SPDX invented.
- Q3 footprint: the D1 instance footprint stays unchanged in this NON-FABRICABLE candidate; the library Footprint property is EMPTY (SOT-363 is not written as the authored default). The unchanged instance override is disclosed visibly in the receipt.
- VBUS/VRWM: an unassessed electrical-applicability item with sourced values (Table 9 p.5-6: VRWM max 5.0 V, VBR min 6.46 V); no verdict, no redesign.

OP-6 amendment: allowable presentation differences explicitly include moved component poses (a per-ref before/after table is recorded in the receipt), not only wires/labels/anchors. D1 identity: preserve the uuid where supported, else an explicit old->new uuid mapping is recorded; a per-emit uuid replacement is not a stable identity.

### 10.5 Phase 2 plan (after approval only)

> SUPERSEDED (allocation (a) below): the approved asset is `packages/eda-bridge/vendor_symbols/Bodesign_Presentation.kicad_sym`, symbol `Bodesign_Presentation:PESD5V0L4UF_Boxed` (see the 10.4 rulings, Naming bullet). `Nexperia_vendor.kicad_sym` / `PESD5V0L4UF` was never created. No global vendor-map promotion.

Worker: Sonnet 5.5. Paths I would need allocated, none created now: (a) `packages/eda-bridge/vendor_symbols/Nexperia_vendor.kicad_sym` (new; one symbol `PESD5V0L4UF`) [SUPERSEDED, see note above]; (b) its entry in `packages/eda-bridge/vendor_symbols/PROVENANCE.md` (source URL, PDF sha256 `62d21660…`, document ID `PESDXL4UF_G_W_4`, page citations, license choice); (c) SUPERSEDED by the officer ruling: no `_VENDOR_MAP` change and no `symbol_resolver.py` edit; per-run, per-ref selection through a copied candidate spec and `symbol_dirs` (see 10.4 rulings); (d) a new test file `tests/test_d1_boxed_symbol.py`; (e) the existing engine seams `elk_layout.py` / `hierarchical.py` / `kicad_emit.py` only if the symbol hull or flattening needs it; (f) receipt section and a new run dir. Steps: author symbol; check it loads in kicad-cli 9.0.9 on a fresh netlist/SVG/PDF/ERC export; run the 10.3 pin-identity and partition comparison against R5b; ONE engine run; fresh editable native files; netlist/ERC; PDF -> pdftoppm PNG; SVG; S1 measure (instrument `9c18bc51…`, real-evidence record, same explicit 10-pair mode) and say whether S1 reads the new body; the five test populations with `__pycache__` cleared; one checkpoint; manifest root once, not an entry in itself. Stop after the checkpoint even on NO.

### 10.6 Reviewer questions to pre-declare

Visual readability questions (the reviewer answers what the diagram communicates BEFORE any intended conclusion is stated to them): 1. Trace each of the CC1, CC2 and VBUS_CON clamps from its signal pin and name the net its return path reaches. 2. Which pins of D1 does the diagram show as electrically joined to each other, and by what drawn element? 3. What does the diagram say about the sixth D1 pin? 4. Describe the near-alignment at x about 397, the B5 wire under CC1, and the R2 branch length, and say whether each could be misread. 5. Describe what the VBUS_CON text at the wire corner and the VBUS flag near F1 are attached to. A NO on any is a valid result and is not patched inside this slice.

Source-fidelity checks (kept separate; measured by me against the datasheet and the native export, not by a screenshot reviewer): pin function/connectivity of all six pins against Table 3 p.2; declared nets per pin; pin 5 stacked on pin 2; pin 6 with its no_connect. "Verified" is engineering evidence, not something a screenshot proves.

### 10.7 Not measured in this proposal

KiCad loading of the authored symbol; whether the symbol-library path used by the emitter can read a vendor file for this MPN (resolver call path unread); ERC findings with a custom library; hull and coordinates of the new body; whether the ELK result under M2 stays at 0 crossings; datasheet figure fidelity beyond the p.2 symbol drawing (internal diagram read from a rendered image and from text, no vector extraction); VBUS tolerance versus VRWM 5.0 V / VBR 6.46 V. The vault holds no copy of this datasheet (ingest payload-shape rejection above, not an infra proof).
