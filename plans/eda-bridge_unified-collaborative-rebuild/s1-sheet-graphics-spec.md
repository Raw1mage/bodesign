# S1 sheet-layer graphic-ink coverage: specification (r8, spec-only)

Status: SPECIFICATION ONLY. No code, fixture, test or instrument-hash change was made in this round.
Approval ref: `officer:ses_04db7a1c5ffelvbxyLP1p6xlRH/s1-r8-spec-20261006`. Author: S1 owner session.
Origin: the blind spot disclosed in `s1-instrument-receipt.md` §12 (class e coherence is unmeasured; sheet-level outline ink is invisible to the instrument).
Amendment r8-amend (ref `officer:ses_04db7a1c5ffelvbxyLP1p6xlRH/s1-r8-amend-20261006`), applied in place to the baseline spec sha256 `1b64c64fe1fc56de51bdbe24767469d01aab6698d1f16b64c16c9395f7bd8907` (16363 bytes, 125 lines). Still SPECIFICATION ONLY. Sections touched are listed in §10. Rulings are folded into the body; the original questions in §9 are kept as asked, each marked RULED.

## 1. Baseline and measured gap

- Baseline instrument: `packages/eda-bridge/bodesign_eda_bridge/readability_render.py` sha256 `9c18bc518eafa4362029adf2391c8d1ce05466f8dd875299133676338669fac8`, policy digest `443bbb0185d5a914`.
- Gap (read from the baseline source, not inferred): `parse_sheet` (line 316) reads root-level `symbol`, `wire`, `junction`, `label`/`global_label`/`hierarchical_label`, `no_connect`, `text`. It never reads root-level `rectangle`, `polyline`, `circle` or `arc`. `_graphic_bbox` (line 231) handles those four tags only for graphics embedded in a `lib_symbols` entry, where they become the symbol `body` box. A sheet-level box is therefore invisible to every class.
- `SvgDoc.polys` (line 612) keeps closed comma-format polygons, but class f uses only those whose first vertex is a global/hierarchical label anchor (lines 1473-1477). A sheet rectangle is not used by any detector.

Measured subject counts (anchored sheet-level pattern, root children only; each with a control):

| subject | sheet sha256 | sheet-level graphics | control |
|---|---|---|---|
| R5b `run-r5b-s1-165624` | `1a898ecc9158197e9d403b9a8fcc5886ba578aa86d303a8f463f38d17185856b` | 1 `(rectangle` (line 1620; start 99.06 76.2, end 101.6 101.6; stroke 0.1524 dash; fill none; uuid `6fe52893-6baa-5a25-8e33-fdae41b26d87`) | the same file has 16 raw `(rectangle` occurrences; 15 are lib-symbol bodies and must NOT count as ink |
| R6 `run-r6-173849` | `8cd238d2f87a36056d6e035c8b29cb92057c253de03af766fa6d86c18f3da24c` | 0 | same anchored pattern returned 1 on R5b |
| 11 pinned fixture sheets under `tests/fixtures/readability_render/` | per file | 0 in all | lib-level tab-indented `(rectangle` pattern returned hits on the same files |

R6 therefore does NOT exercise this gap. R5b is the only available real subject that does.

## 2. Binding principle (verbatim boundary)

Parsing sheet-level graphic geometry does not imply that schematic semantics are understood. A sheet-layer rectangle or polyline is ink. The instrument does not know whether it is a group outline, a decoration, a title block or an error, and it never infers connectivity, grouping or ownership from it.

Graphic ink NEVER enters the electrical graph, the union-find/DSU structure, the pin inventory, the net or branch identity reasoning (class b pre-union identities), or any netlist comparison.

### 2.1 Observation kind (machine-enforced)

Measurements are not proof of intention or defect. Every output of P1-P4 is `kind="observation"`, never `kind="measurement"` and never a finding. Enforcement is structural, not by convention:

- Observations live in a SEPARATE population (`observations` per class report), not in `findings`. The aggregators exclude them by kind; a class verdict is computed from `findings` only.
- They do not increment defect counts, do not enter the existing `"fail" if rep.findings else "pass"` path, and do not change a class verdict, `scoped_verdict` or `verdict`.
- They never become accepting or rejecting calibration cells, and are never listed as evidence for any class.
- The report carries `observations_expected`, `observations_examined`, `observations_omitted` (each omission with a reason) and the emitted count; expected = examined + omitted.
- Unknown ownership means the ownership assessment is unmeasured. The geometric intersection itself is still measured and still reported.

## 3. Parsed model: the separate graphic-ink list

New list `sheet_graphic_ink`, built by the sheet parser from ROOT-level nodes only (never from `lib_symbols`). One entry per node:

| field | rule |
|---|---|
| `uuid` | the node's `(uuid ...)`; missing uuid is reported as `""` and counted in `ink_missing_uuid` (no invented id) |
| `kind` | `rectangle` \| `polyline` \| `circle` \| `arc` |
| `geometry_mm` | rectangle: 4 corner points; polyline: ordered points; circle: center + radius; arc: start, mid, end |
| `stroke` | `type` (default/dash/dot/...) and `width` as written; absent stroke is `unknown`, not a default |
| `fill` | `type` as written (recorded only; occlusion by fill is not modelled) |
| `closed` | rectangle and circle: true; arc: false; polyline: true only when first point equals last point within `coord_eps_mm`, else false |
| `owner` | section 4 |
| `source_line` | line of the node in the sheet text, for audit |

Page transform: sheet-level items are written directly in page coordinates (mm, y down); they carry no symbol rotation or mirror. The only transform is the identity plus the existing 4-decimal rounding, and the same `viewBox` to mm `unit_scale` that class f already uses to compare wires with SVG text boxes. No `_transform` call is made for ink.

Unparsed kinds: root-level graphic-like nodes that this slice does not model (`bezier`, `text_box`, `rule_area`, `image`, `sheet`, `polyline` with fewer than 2 points) are counted in `ink_unparsed_by_kind` and reported as unmeasured. They are never silently dropped.

## 4. Owner and boundary classification

- `owner=<ref>` is assigned ONLY from a data-layer association supplied to the instrument as declared authority, in one of two SEPARATE modes:
  - (i) explicit-map mode, `ink_owner_map {ink_uuid: ref}`: checks only exact identities, that the sheet-scoped graphic uuid exists and that the named symbol uuid/ref exists. It never reproduces a uuid5.
  - (ii) rule mode: the only mode that reproduces uuid5, for example the S3-declared rule `rect_uuid = uuid5(symbol_uuid, "presentation.outline")` (S3 `emit_result.json`, `engine_reports.usbc.outlines.D1`). SEAL CORRECTION (r9): the instrument implements exactly ONE fixed algorithm, `uuid5(symbol uuid, name)` over the declared `targets`; rule id/version are BOUND METADATA hashed into the manifest, and the resolver does not dispatch on them. No arbitrary-rule semantics are claimed.
- The association is checked against the sheet: the named ref must exist and (rule mode) the rule must reproduce the ink uuid. A mismatch yields `owner=unknown` plus a recorded `owner_declaration_mismatch`. Duplicate or ambiguous target identities (two symbols or two ink items with the same uuid, a map key matching more than one item) assign NO owner and are recorded as a mismatch.
- No association supplied, or no match: `owner=unknown`. Unknown ownership is reported as unmeasured (`ink_owner_unknown` count and uuids). It is NEVER guessed from containment, proximity, or "the box that surrounds D1's pins".
- The COMPLETE declared authority is hashed into the subject authority manifest, as already done for `declared_pin_nets` / `required_local_pairs` (§8 of the receipt): the exact `ink_owner_map` contents, and for rule mode every rule input and parameter (rule id, version, namespace, name string, target selection), not rule id/version alone. None (no declaration) and an explicitly empty map stay distinct (receipt §9 discriminator).
- The uuid5 rule has NOT been reproduced against any sheet in this spec round (spec only, no probe, namespace not examined). AC5 states the claim limits.
- Provenance of uuid `6fe52893-…` is RESOLVED by `s3-engine-spike-receipt.md` §R6.H (sha `420a008e…`, :450); the earlier r8 reading of S3 receipt :333 as tying it to run-20261006-162241 is withdrawn. Officer-verified there: R4 run-20261006-162241 has no sheet-level rectangle, does not contain `6fe52893` (grep count 0) and its D1 symbol uuid is `975183bb-…`; the outline `6fe52893-…` belongs to R5b-S1 only (D1 `da260240-…`, outline at sheet :1620-1622). All four D1 uuids differ (R5b-S0 `7993d8ef`/outline `3402af4c`, R5b-S1 `da260240`/`6fe52893`, R6 `289b716a` with no outline) because `kicad_emit.py:245-246` `_uid()` is an unseeded uuid4; outline = `uuid5(symbol uuid, "presentation.outline")` at :1617. S3 :333 is a correct statement in §R5.2b (run-r5b-s1-165624); its parenthesis "(run-20261006-162241)" labels the baseline manifest root `c129b87f…`, not the uuid origin.

## 5. Which checks the ink participates in, and which stay human-only

Participates (GEOMETRIC-PATH INTERSECTION OBSERVATIONS, not rendered ink; every item is `kind="observation"` per §2.1, cites the ink uuid, and asserts no defect verdict or grouping semantics). All four are reported under class f (Q2 ruled); none is a class-e output.

| id | sub-check | class | observation code | method |
|---|---|---|---|---|
| P1 | wire path intersects ink path | f | `F_WIRE_THROUGH_INK` | segment-vs-segment test of each sheet wire centerline against each ink path segment; one observation per (ink, wire) pair; objects `[ink:<uuid>, wire:<uuid>]` |
| P2 | ink path intersects a text glyph box | f | `F_INK_THROUGH_TEXT` | reuse the baseline `_seg_box_clip` against each SVG text box shrunk by the same inset as `F_WIRE_THROUGH_TEXT`; one observation per (ink, text) pair |
| P3 | label flag outline intersects ink path | f | `F_FLAG_THROUGH_INK` | the flag polygons already isolated for `F_FLAG_THROUGH_TEXT` (first vertex == label anchor) against ink path segments; one per (ink, flag) pair |
| P4 | ink path passes within `coord_eps_mm` of a pin tip or pin stub segment | f | `F_INK_THROUGH_PIN` | segment-vs-pin-stub distance test; path-labelled, geometric proximity only, not a coherence reading; one per (ink, pin) pair |

### 5.1 Geometry qualification (binding on all four)

- NOT assessed: dash gaps (a dashed path is tested as if continuous), stroke envelope (stroke width is recorded in the ink list but every test uses the CENTERLINE only), fill, occlusion, z-order. An observation therefore says that two geometric paths intersect, not that two rendered strokes touch.
- Rectangle: its four EDGES are the path. The rectangle interior is NOT ink; an object wholly inside a rectangle yields no observation.
- Circle and arc: tested as chord polylines at a stated chord tolerance `ink_chord_tol_mm` (0.05 mm sagitta, `INK_CHORD_TOL_MM`: a MEASUREMENT CONFIGURATION parameter versioned by `measurement_scope_version`, NOT part of the decision-policy digest; seal ruling D1, see §6 and §11). The result is an approximation and is never called exact; an intersection within the tolerance of a tangent may be missed or added.
- Endpoint and tangent handling: a segment endpoint lying on a path segment within `coord_eps_mm`, and a collinear overlap, count as an intersection and are labelled `touch` or `overlap` in the observation; a proper interior crossing is labelled `cross`. Only the label differs; all three are observations.
- Deduplication: one observation per unordered pair (ink uuid, other object id). Several intersection points between the same pair are recorded in that single observation's `points` list, not as several observations.
- Closed-ness: a polyline that is not closed is tested as an open path; it is not implicitly closed.

Rules common to P1-P4: ink is read-only input; an observation never changes a net, a branch identity, or any a-d result; ink with `owner=unknown` still produces observations (the geometric intersection is measured), carrying `owner: unknown` and an ownership-assessment-unmeasured flag. A wire that leaves an enclosed component necessarily crosses its outline, so P1 observations are expected on a correct group outline (Q1 ruled: measurement-only, NO ownership-based suppression, ever).

Remains human-only, and stays listed as unmeasured in the report:

- what a rectangle or polyline MEANS (group outline, decoration, title block, error);
- grouping meaning, "package implies internal connection" reading, and one-flag-per-many-channels;
- symbol coherence (a multi-glyph symbol reads as one component): the §12 boundary is unchanged, no e-coherence detector is added. Class e is NOT redefined as wholly human-only: its existing geometric checks (wire-through-body, over-unconnected-pin and the other implemented e codes) stay as they are; only symbol coherence, group and package MEANING are human-only. No e-coverage expansion is claimed;
- whether the outline encloses the right pins, or whether containment implies ownership;
- fill occlusion, dash-style meaning, z-order.

## 6. Instrument identity and re-run obligation

- Pre-change baseline: `readability_render.py` `9c18bc518eafa4362029adf2391c8d1ce05466f8dd875299133676338669fac8`. Implementing this spec changes the module bytes and therefore REQUIRES a NEW instrument hash. Every report and calibration reference stores instrument hash + policy hash; historical 9c18bc51 reports stay valid historical measurements and are not relabelled.
- Terminology (seal ruling D1): the DECISION POLICY is the `POLICY` digest (`443bbb0185d5a914`, unchanged by this slice); the MEASUREMENT CONFIGURATION is `measurement_scope_version` and `INK_CHORD_TOL_MM`. Measurement configuration affects observations only, never findings, verdicts or the calibration population. Wording elsewhere in this file that says "in the policy digest" for the chord tolerance is superseded. Any future change that affects findings or verdicts MUST change the decision-policy digest and invalidate decision evidence, even if AC6 byte-identity then changes.
- A new instrument identity is MANDATORY, together with a new `measurement_scope_version` recorded beside the policy digest in every report and calibration reference. A historical calibration record carries the old scope version and so cannot imply coverage of observations. Calibration and authentication remain partial (`evidence_authenticated=False`, `authenticated_by=None`) whether or not the implementation tests pass. This slice does not reopen the accepted R6 leaf.
- Re-run populations under the new hash, comparing against their 9c18bc51 reports. Evidence available per subject (verified by directory listing; support level follows from it):
  - 6 pinned non-xform sheets: cp3 usbc / power_rail / battery (sheet, svg, export receipt, ARCHIVED `.net`; the historical whole-report provenance result for CP3 stays as measured), clean `clean_divider` and b1 `b1_dotted_contact` (sheet, net, svg, export receipt), `s3_usbc_20261006` (sheet, net, svg, export receipt, `s1_invocation.json`);
  - 5 pinned xform sheets, enumerated (never described as twelve transformations): `xr180` (sheet, net, svg, export receipt); `xm` (sheet, net, svg, export receipt); `sweep_r90_mx` (sheet, svg only; net ABSENT, export receipt ABSENT); `sweep_r270_my` (sheet, svg only; net ABSENT, export receipt ABSENT); `r150709/usbc` (sheet, net, svg, export receipt, `s1_invocation.json`, stored `s1_report.json`). The unpinned 12-variant sweep (`~/.cache/scratch/s1-xform/`, receipt §11.1) is NOT part of this population;
  - the R6 candidate: PNG `b25d7d50b3530627ec8f12a2330e568a0321d57f717d23fe5e1a3f909b261004`, sheet `8cd238d2f87a36056d6e035c8b29cb92057c253de03af766fa6d86c18f3da24c`. It has ZERO sheet-level graphics, so it does NOT exercise this gap. Expected result: per-class findings identical, ink list empty.
  Its evidence files (net, svg, export receipt) are in the scratch run `run-r6-173849`, not the repo fixture tree, and were not enumerated in this round; the implementation slice must enumerate them before claiming any support level.
- Fixture that WOULD exercise the gap: R5b `run-r5b-s1-165624` (Q5 APPROVED, §6.1).

### 6.1 R5b fixture copy (approved)

- Destination `tests/fixtures/readability_render/r5b_usbc_20261006/`: byte-preserving copy of `out/usbc.kicad_sch` (`1a898ecc…`), `native/usbc.net` (`188cc95c…`), `native/svg/usbc.svg` (`54fca7ad2508d686f15d0cdb7a455181c65fc3096a8b031dceea29510009f10b`, REQUIRED: it is an instrument input), and the ACTUAL `native/usbc.export-receipt.json` (`3619b26b92ad60bc9996c4a565c51ce748f4dba7f3297b1d8df9dbe408a41bc6`), plus a pinned manifest and a provenance README.
- The README records the original run paths and identities. The fixture path mapping is explicit and is NOT a new export receipt; nothing is regenerated, and nothing regenerated is relabelled as historical.
- R5b's own provenance, read at spec time (hash comparison only, kicad-cli NOT re-run): the receipt (`s1-export-receipt-v1`, kicad 9.0.9) binds sheet `1a898ecc…`, netlist `188cc95c…` and render `54fca7ad…`, and the three files on disk match those hashes; file mtimes order sheet (16:56:26) before net and svg (16:56:30). The CP3 stale-netlist caveat is therefore NOT transplanted; it does not apply on this evidence. It must be re-checked at copy time. If pairing is unverified then, parser/geometry tests proceed and whole-report provenance is `indeterminate`.
- Restriction: internal review use only; not cleared for redistribution or global promotion. In R5b the D1 symbol is `Power_Protection:PESD5V0L4UF` (sheet lines 984, 1515), not the `Bodesign_Presentation` library, so the library-license-pending caveat of the R6 candidate does not attach; only the GENERAL internal-use caveat applies.
- Report shape: the report gains ink fields (`sheet_graphic_ink`, `ink_missing_uuid`, `ink_unparsed_by_kind`, `ink_owner_unknown`, `owner_declaration_mismatch`). Existing per-class findings must be unchanged on every sheet that has no ink, and on any sheet WITH ink (observations never move a finding).
- Calibration stays `partial`, `evidence_authenticated=False`, `authenticated_by=None`; the e-coherence not-assessed statement is retained.

## 7. Acceptance criteria for the future implementation slice

Each is measured by a named command or test cell; "hand count" means a count taken from the sheet text with an anchored root-level pattern, recorded with its control, BEFORE the implementation runs.

| id | criterion | measurement |
|---|---|---|
| AC1 | Ink-list count equals the hand count: R5b = 1 (uuid `6fe52893-6baa-5a25-8e33-fdae41b26d87`, kind rectangle, stroke dash 0.1524, closed=true); R6 = 0; each of the 11 pinned sheets = 0 | test cell per subject asserting `len(sheet_graphic_ink)` and the uuid; lib-symbol rectangles (15 on R5b) must not be counted |
| AC2 | Electrical graph byte-identical before/after on every fixture, R5b included: node set, edge set, DSU component partition, pin inventory, per-branch net identities | canonical dump of those five structures, sha256 compared between the 9c18bc51 build and the new build; equal on all sheets |
| AC3 | Synthetic P1: one sheet rectangle whose single edge is crossed by exactly one wire (wire enters from outside, ends inside) yields exactly ONE new class-f OBSERVATION, code `F_WIRE_THROUGH_INK`, objects containing the rectangle uuid and the wire uuid, label `cross`; ZERO new findings in any class | fixture + test cell; diff against the same sheet with the rectangle removed |
| AC3b | Positive plus non-contact synthetic cells for each of P2, P3, P4: P2 (ink edge through a text glyph box vs ink beside it), P3 (label flag outline crossing an ink edge vs flag clear of it), P4 (ink edge through a pin stub vs ink farther than `coord_eps_mm`). Each positive gives exactly one observation with the ink uuid; each non-contact gives zero | six test cells |
| AC3c | Geometry kinds: positive plus non-contact cell for an open polyline (one crossing; the open end is not implicitly closed), a closed polyline, and a circle and an arc (chord approximation at `ink_chord_tol_mm`, with a case at the tolerance edge asserting the documented behaviour); the rectangle-interior case (wire wholly inside, no edge contact) yields zero; endpoint-on-edge yields `touch`, collinear overlap `overlap`; two intersection points on one pair give one observation with two `points` | test cells per kind |
| AC3d | Observation isolation: a valid outline WITH observations leaves every pre-existing class verdict, `scoped_verdict` and `verdict` unchanged solely because observations exist: same sheet with and without the rectangle gives identical verdicts and identical `findings`; `observations` non-empty only in the with-rectangle run; no observation appears in any calibration cell, defect count or class `examined_ids` verdict input; `observations_expected == examined + omitted` | test cell on R5b (with its rectangle vs a rectangle-removed twin) plus a synthetic |
| AC4 | Synthetic: one sheet rectangle enclosing two pins that belong to DIFFERENT nets, with no wire touching the rectangle, yields ZERO new electrical findings and a-d reports identical to the rectangle-removed twin (no union leak: no merged component, no class b B1/B2 change) | fixture + test cell; per-class equality plus the AC2 dump equal |
| AC5 | Owner binding, modes separate. (i) explicit map: exact sheet-scoped graphic uuid + symbol identity check only. (ii) rule mode: the only mode that reproduces uuid5. No declaration gives `owner=unknown` and `ink_owner_unknown` lists the uuid; a wrong declaration gives `owner=unknown` plus `owner_declaration_mismatch`; duplicate or ambiguous target identities assign NO owner; containment never sets an owner (assert on R5b with the declaration removed) | cells for each of those cases. **Claim limit (r8 wording, SUPERSEDED by the addendum below):** the R5b rule-positive cell was not to be claimed until reproduced against both pinned subjects. If R5b fails the rule, record mismatch/unknown; historical bytes are never altered. A positive rule case may be proven on a separately labelled SYNTHETIC fixture. **Seal addendum (r9, §R6.H):** local R5b association established (rule reproduces `6fe52893-…` from D1 `da260240-…`); cross-run attribution question RESOLVED by `s3-engine-spike-receipt.md` §R6.H: the uuid belongs to R5b-S1 only; no second pinned subject exists or is needed for that claim. R4 (run-20261006-162241) is NOT claimed as a subject. The generic AC5 contract test remains the accepted cell |
| AC6 | Existing populations unchanged, PER SUBJECT by available scope (§6 enumerates the evidence). Subjects with sheet+net+svg+export receipt (cp3 ×3 with archived net, clean, b1, `s3_usbc_20261006`, `xr180`, `xm`, `r150709/usbc`, R5b): per-class verdicts and findings (code, objects, location) identical to the 9c18bc51 report, plus `verdict`/`scoped_verdict`. `sweep_r90_mx` and `sweep_r270_my` (sheet+svg only): parser and geometry comparison only; NO report is claimed, and whole-report provenance stays indeterminate. Where no 9c18bc51 report exists for a subject the gap is listed in the receipt, never filled with an invented report or receipt. Calibration still `partial`, `evidence_authenticated=False`, `authenticated_by=None` | rerun table in the receipt, one row per subject with its evidence set; before/after per subject |
| AC7 | Authority binding: changing the exact `ink_owner_map`, or ANY rule input/parameter (not only rule id/version), changes `subject_manifest_sha256`; None (no declaration) and an explicitly empty map hash differently (receipt §9 discriminator) | test cells with identical bytes |
| AC8 | Unparsed kinds are counted, not dropped: a synthetic sheet with one root-level `bezier` and one `text_box` reports `ink_unparsed_by_kind == {bezier:1, text_box:1}` and an empty ink list | test cell |
| AC9 | No coherence claim: no new code asserts grouping, package or symbol coherence; every P1-P4 code is class f and `kind="observation"`; class e is not described as wholly human-only and no e-coverage expansion is claimed; the report still lists e-coherence as not assessed; no `calibrated` verdict anywhere | grep of codes plus a report-contract cell |
| AC11 | R5b fixture integrity: the copied files hash to `1a898ecc…`, `188cc95c…`, `54fca7ad…`, `3619b26b…`; README lists original paths; the manifest is pinned in the test `PINS` | pin cells |
| AC10 | Suite: `./scripts/run_tests.sh test_readability_render` after clearing `__pycache__`; baseline Ran 60 OK; the new count, failures, errors, skips and exit code are recorded verbatim; new instrument sha256 and policy digest recorded with the old pair alongside | receipt section |

Order of proof: AC2 and AC6 first (nothing existing moved), then AC1, AC3, AC3b-d, AC4 (new behaviour, observation isolation and the no-leak property), then AC5, AC7, AC8, AC9, AC11.

## 8. Not in scope

(Amendment record is §10 at the end of this file.)

- Any e-coherence detector, any reading of what an outline means, any "enclosure implies ownership" inference.
- Any calibration claim, calibrated verdict, or flip of `evidence_authenticated`; the calibration record stays partial.
- Electrical use of ink in any form (union, net assignment, pin association, connectivity from containment).
- Modelling `bezier`, `text_box`, `rule_area`, `image`, hierarchical `sheet` boxes, fill occlusion, z-order, dash-style meaning.
- Changes to `_transform`, rotation/mirror scope, `supported_scope`, or the calibration resolver.
- Detecting outline/symbol drift after a human moves a symbol (S3 disclosed obligation, S3 receipt §R5.2b :333).

- Implementing, fixture-building, copying R5b, or editing any file other than this spec in round r8 (the R5b copy is approved but belongs to the implementation slice).
- Reconciling the uuid `6fe52893-…` provenance (S3 owner's task).
- Using observations for suppression, calibration, or any verdict.
- Rendering-side verification that the SVG actually drew the ink (the SVG polygon/rect list is not used for ink in this spec).

## 9. Open questions for the officer

All five are RULED (officer + Astra, `s1-r8-amend-20261006`); the rulings are applied in §2.1, §4, §5, §5.1, §6, §6.1 and §7. The questions are kept verbatim for the record.

- **Q1 RULED: measurement-only, no ownership suppression, machine-enforced as `kind=observation` (§2.1). (expected-by-design findings).** A wire that leaves an enclosed component must cross its outline, so P1 fires on every correct outline. Options: (a) report as measurements only, human reads them (this spec's default); (b) suppress P1 for wires whose declared net belongs to pins of the ink's declared owner. (b) uses ownership to decide, so it needs `owner` to come from declared authority and a declared net list; it must never apply when `owner=unknown`. Which?
- **Q2 RULED: P4 is class f, `F_INK_THROUGH_PIN`, observation-only; class e is not redefined (§5). (class placement of P4).** `E_INK_THROUGH_PIN` is a geometric collision, but class e carries the "not assessed" coherence boundary. Putting a new code in e risks "zero e findings" being read as more than it is. Alternative: report P4 under f. Which class, and does the e annotation (receipt §12) need an added sentence?
- **Q3 RULED: ownership modes split, full authority hashed; provenance since RESOLVED by S3 §R6.H (§4, AC5). (uuid provenance).** r8 text, kept for the record: it read S3 receipt :333 as tying uuid `6fe52893-…` to run-20261006-162241. That reading was a misread (the parenthesis labels the baseline manifest root, not the uuid origin); §R6.H shows the uuid belongs to R5b-S1 only.
- **Q4 RULED: population is the five pinned xform sheets, enumerated with evidence (§6, AC6). (xform population).** Only 5 of the "x12" xform sheets are pinned. Should the implementation slice pin the other 8 variants (inputs and raw SVGs exist in scratch, receipt §11.1) so AC6 covers 12, or is the 5 pinned sheets plus the sweep fixtures acceptable?
- **Q5 RULED/APPROVED: byte-preserving copy under `r5b_usbc_20261006/` (§6.1). (R5b as a fixture).** R5b is not in the repo fixture tree. Pinning needs its sheet, `.net` (`188cc95c…`), export receipt and SVG. Is the officer content for it to be copied under a new fixture subdir, with the netlist provenance caveat (archived `.net` age, receipt §5/§6) re-checked at copy time?

## 10. Amendment record (r8-amend, 2026-10-06)

- Baseline before this amendment: sha256 `1b64c64fe1fc56de51bdbe24767469d01aab6698d1f16b64c16c9395f7bd8907`, 16363 bytes, 125 lines. The after-hash is reported in the BRNS-DONE receipt (a file cannot hold its own hash).
- Sections touched: header note; new 2.1 (observation kind, machine-enforced); 4 (ownership modes, full-authority hash, duplicate handling, uuid5 unreproduced); 5 (observation wording, P4 to class f, new 5.1 geometry qualification, class e not redefined); 6 (mandatory new identity plus measurement_scope_version, per-subject evidence enumeration, new 6.1 R5b fixture copy); 7 (AC3 reworded, new AC3b/AC3c/AC3d, AC5 claim limit, AC6 per-subject, AC7 full authority, AC9 class f/observation, new AC11); 8 (not-in-scope additions); 9 (all five questions marked RULED).
- Verified at amendment time by directory listing and hashing only: R5b run files and their hashes; xform per-sheet evidence; R5b D1 library name at sheet lines 984/1515. NOT done: no kicad-cli run, no uuid5 probe, no R6 evidence enumeration, no code or test change.

## 11. Seal record (r9 phase=seal, 2026-10-06), approval_ref `officer:ses_04db7a1c5ffelvbxyLP1p6xlRH/s1-r9-seal-20261006`

- Verdict: r9 implementation ACCEPTED at bounded diagnostic-coverage-extension scope (D1/D2/D3 accepted). Instrument `readability_render.py` `f98dc2371afc3202485bd1a7cc808b9b118a9578b8dbfed131a6cc68fdad269f`; officer rerun Ran 108 / OK / exit 0. Results and measured values are in receipt section 13 (13.8 is the seal).
- D1: decision policy (digest `443bbb0185d5a914`) is distinct from measurement configuration (`measurement_scope_version`, `INK_CHORD_TOL_MM`); the latter affects observations only. This is not a claim that byte-identity outranks evidence invalidation. Wording corrected in sections 5.1 and 6.
- D2: an ink-free subject's unchanged manifest identifies the same SUBJECT, not the same instrument execution or coverage. Reports are identified by instrument hash + `measurement_scope_version` + report identity, never deduplicated by manifest alone. Empty parsed ink is not "no graphic content"; `ink_unparsed_by_kind` stays visible and unmeasured. `measurement_scope_version` in a report is a claim, not authenticated proof of execution.
- D3: observations attach after the class f verdict (`readability_render.py:2142-2145`), outside the verdict ladder (`:2201-2225`).
- Owner rule: id/version are bound metadata for one fixed `uuid5(symbol uuid, name)` algorithm (resolver `:1886-1905`); corrected in section 4.
- AC5 recorded in the AC5 row: R5b rule reproduction measured; cross-run attribution RESOLVED by S3 §R6.H (seal addendum, same approval_ref): uuid belongs to R5b-S1 only, no second pinned subject needed, R4 not claimed as a subject.
- AC checkbox status: ACs are recorded as measured in receipt 13.5; none is ticked here. AC5 historical lineage subclaim stays open.
- Not granted: authority to commit, deploy, promote calibration, or reopen R6 visual acceptance. AC16 partial / unauthenticated. Packaging BLOCKED.
