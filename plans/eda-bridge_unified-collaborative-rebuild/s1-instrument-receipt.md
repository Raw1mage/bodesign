# S1 Instrument Receipt — readability_render (DD-14 / AC16)

Worker: ses_ef0e7e310ffeYHnGBQ4FrFzZIr (Fable 5.1). Dispatcher: ses_04db7a1c5ffelvbxyLP1p6xlRH.
Date: 2026-10-06. Status: **partial calibration** — CP3 cells measured; CP1/CP2 cells BLOCKED (bytes not on disk).
Nothing committed. Tree edits only.

## Approved AC16 corpus amendment (2026-10-06)

The officer-approved [AC16 replacement corpus contract](spec.md#acceptance-checks) supersedes the requirement to recover all nine historical cells; it does not rewrite the historical measurements below. CP1/CP2's six cells remain permanently blocked, never passed. The replacement corpus contains the three archived, reviewer-adjudicated CP3 rejecting cells; every independently reviewed S3 output, classified according to its actual review; and hand-built paired clean/b1 cases, labelled `hand-verified, unadjudicated` until independently reviewed. Hand-built cases count as accepting only after that review.

`calibrated` requires at least one adjudicated rejecting and one independently reviewed accepting entry for each class a–e, with content-bound evidence; class f requires its own applicability ruling. CP3 provenance limitations remain in force. Current calibration remains **partial**; this amendment does not accept round-3 implementation, complete 3.3a, or grant S3 license/dispatch clearance. The first S3 leaf may become an accepting candidate before calibration closes, but only its independent review determines corpus classification; AC18 final acceptance is unchanged.

## 1. Landed files (uncommitted)

| path | sha256 | state |
|---|---|---|
| `packages/eda-bridge/bodesign_eda_bridge/readability_render.py` | `56e96d643c62c38fe0fe7a611392865567368069fc9a26568484e119c5869deb` | new (1377 lines) |
| `tests/test_readability_render.py` | `934a2c8fe0c06c48639c997677053504adc05167f24940e8a57e2f6cb260ebfa` | new |
| `tests/fixtures/readability_render/cp3/*` (12 files) | pinned in test `PINS` | copies of archive bytes + verbatim reviewer notes |
| `tests/fixtures/readability_render/clean/*` (3 files) | pinned in test `PINS` | hand-built accepting exemplar, natively exported |

Allowlist respected: `readability_gate.py`, `kicad_emit.py`, `hierarchical.py`, `composer.py`, `server.py`, `gate.py` untouched (`git status` shows only the three `??` entries above plus pre-existing dirty files from other sessions).

## 2. Policy (frozen BEFORE calibration run)

`POLICY["version"] = "s1-readability-policy-v1"`, `frozen_on = 2026-10-06`. Values: `coord_eps_mm 0.01`, `pin_tip_band_mm 1.27`, `corridor_band_mm 2.54`, `corridor_min_pins 2`, `local_net_max_nodes_k 4`, `text_graphics_clearance_mm 0.25`, `text_overlap_ratio 0.15`, `page_use_gate None`, `page_grid_cell_mm 10`, `frame_margin_mm 12`. No value was changed after the first calibration run. One **code** fix was made after the first run (class b findings now also carry `net:<name>` object tags so the evidence assertion can name the net) — a reporting-shape change, not a threshold.

Input binding: `.kicad_sch` (objects, pin geometry via embedded `lib_symbols`, rotation/mirror transform) + `kicad-cli` sexpr netlist (net identity) + `kicad-cli` SVG (viewBox→mm, stroke width, text extents). Pairing checks: paper vs SVG size, every sheet wire covered by rendered segments, netlist `source` name, netlist refs ⊆ sheet refs. Any anomaly ⇒ `verdict=indeterminate`. SVG-only input raises `ReadabilityInputError`. Uncalibrated pass ⇒ `indeterminate`.

## 3. Per-artifact calibration table

Reviewer verdicts/classes transcribed from the CP3 notes copied verbatim into `tests/fixtures/readability_render/cp3/<leaf>.reviewer-cp3.md`.

| artifact | sha256 (.kicad_sch / .svg / .net) | reviewer verdict | reviewer classes (my mapping) | instrument classes (non-empty) | match |
|---|---|---|---|---|---|
| usbc CP3 | `63432d2f…` / `1e670c1a…` / `2fb48c09…` | NO | a, c, d, f | a, b, c, d, f | **y** (all reviewer classes present; evidence localized: `D_DOT_ON_PIN_CONTINUES F1`, `A_DOT_ON_PIN_TIP F1.1`, `C_PIN_LABEL_ONLY R1.1/R2.1/J1.B5/D1.4`, `F_WIRE_THROUGH_TEXT VBUS_CON`) |
| power_rail CP3 | `e91672c4…` / `bf19a2bd…` / `97a2f6ec…` | NO | b, c, e, f | a, b, c, d, e, f | **y** (`B2_FOREIGN_CROSS_NO_DOT /ISET2×VBUS`, `C_PIN_LABEL_ONLY L1.1/U1.3/U1.4`, `E_PIN_ROW_CORRIDOR U1.2/6/13/8/7/11`, `F_TEXT_TEXT_OVERLAP VBUS/IN`) |
| battery CP3 | `71375ea2…` / `ee3a50a6…` / `922152aa…` | NO | c, e, f | c, e, f | **y** (`C_PIN_LABEL_ONLY Q1.2`, `E_WIRE_THROUGH_BODY J2` (along body edge 2.54 mm), `F_TEXT_TEXT_OVERLAP BAT_EXT/1`, `F_WIRE_THROUGH_TEXT BAT_EXT`) |
| clean_divider (accepting) | `124020b7…` / `c6296e47…` / `b1224418…` | hand-verified clean (no independent reviewer) | — | none in a–e; f none | **y** (verdict `pass` with `calibration_ref=calibrated`) |
| usbc CP1 (png 6d953e14) | — | NO | — | — | **BLOCKED** no .kicad_sch/.svg/.net on disk |
| power_rail CP1 (png e4df67c1) | — | NO | — | — | BLOCKED |
| battery CP1 (png 152ed3da) | — | NO | — | — | BLOCKED |
| usbc CP2 (png 61fc8e60) | — | NO | — | — | BLOCKED |
| power_rail CP2 (png 6211f238) | — | NO | — | — | BLOCKED |
| battery CP2 (png af182be3) | — | NO | — | — | BLOCKED |

Full sha256 values are in `tests/test_readability_render.py::PINS`.

Provenance note on the `.net` fixtures: the archived `*.net` files (05:49–05:50) predate the CP3 `.kicad_sch` (06:43). I re-exported netlists from the CP3 sheets with `kicad-cli 9.0.9`: usbc and battery differ only in net ordering and libpart listing; **power_rail differs materially** — the regenerated export drops `/ISET2` and `/USB_DET` (U1.12/U1.13/R4.1/R6.2 vanish; ERC reports two `wire_dangling` 0.0127 mm stubs at U1.12/13). The archived `.net` carries those nets. I measured against the **archived** netlist (the bytes the pause note's "0 fused/0 missing" claim refers to) and pinned it. The regenerated-export discrepancy is reported here, not resolved — it is outside S1 scope but the officer should know the CP3 power_rail sheet does not reproduce its own archived netlist. SVGs: archived == re-export modulo `<title>` date, all three.

## 4. Per-class false-positive / false-negative / coverage (CP3 + clean, n=4)

FP = instrument flags a class the reviewer did not cite. FN = reviewer cited, instrument silent. Reviewer notes are free text; mapping to classes is mine (§3).

| class | measured on | FN (reviewer cited, missed) | FP (flagged, not cited) | coverage note |
|---|---|---|---|---|
| a | 4/4 | 0 | power_rail (reviewer did not call out dots; instrument flags C3.1 / U1.16 dot-on-pin-tip and 3 missing dots) | dot-on-pin-tip and missing-dot both fire on usbc F1 as reviewer described |
| b | 4/4 | 0 | usbc (`B1_SAME_NET_T_NO_DOT` at F1 top meet — reviewer described it as bypass, class d) | b1/b2 split reported separately in `measurements` |
| c | 4/4 | 0 | 0 | K=4; exemptions recorded in `omitted` (global/hier label = continuation, power, replica, NC, >K) |
| d | 4/4 | 0 | power_rail (`D_DOT_ON_PIN_CONTINUES C3` — reviewer silent on C3) | all findings `kind=perceptual`; `D_DRAWN_BYPASS` never fired (test asserts it) |
| e | 4/4 | 0 | 0 | battery J2 detected as "along body edge", not strictly inside — reviewer's "through the body" is a visual read of the same geometry |
| f | 4/4 | 0 (overlaps named by reviewers all present) | 0 | page-use reported (bbox 0.24–0.32, grid 0.05–0.09), **not gated** |

Classes with a counted FP on CP3 are still correct on the accepting exemplar (0 findings a–e), so the FPs are not always-NO behaviour; they are findings the reviewer did not mention, on sheets the reviewer rejected anyway. Whether they are true FPs needs a reviewed accepting exemplar per class (see §6).

## 5. Test run (verbatim, after `find . -name __pycache__ -prune -exec rm -rf {} +`)

```
$ ./scripts/run_tests.sh test_readability_render
.................
----------------------------------------------------------------------
Ran 17 tests in 1.553s

OK
exit=0
```

Ran 17 / failures 0 / errors 0 / skipped 0 / exit 0.

## 6. Unmeasured / not done

- **CP1 and CP2 (6 of the 9 reviewer cells)**: no native pairs on disk; only PNG hashes exist in the pause note. Not reconstructed. Officer search 2026-10-06: 0/25 PNG hashes under `~/.cache/scratch/p2-leaf-delivery/` match; cells permanently blocked, no reconstruction. S1 accepted by the officer at scope "CP3 rejecting cells + one hand-verified accepting exemplar".
- **Independently reviewed accepting exemplar**: none exists. The accepting exemplar is a hand-built fixture I verified by reading the render; it has no fresh-eyes YES on file. Paired corrected cases per class: not produced.
- **Rotation/mirror**: transform implemented; all four calibration sheets are rotation 0, so rotated placement is uncalibrated.
- **Class e corridor** uses sheet-space distance with the rendered stroke width as the collinearity band; it does not rasterize. "Visually unresolved separation" at sub-stroke scale is approximated, not rendered.
- **Class f**: text-vs-symbol-graphics clearance not measured (only text-vs-text and wire-through-text); font legibility reported as `min_font_mm` only. Child-plan DD-14/DD-16 tests were NOT reused (their population is emitter-internal geometry, not render space).
- **kicad-cli version** is not embedded in the SVG; `render_context.renderer` says so and the version (9.0.9) must be pinned externally.
- Reviewer-class mapping (§3) is my interpretation of free-text notes; a different mapping could move a cell between FP and match.
- Full suite not run; only the named module.

## 7. Round 2 (Astra invariants 1–4), 2026-10-06

Wording correction to §4: classes the instrument flags beyond the reviewer's cited set are **unadjudicated extras**, not confirmed false positives (no reviewer ruled on them). "0 FN" in §4 is relative to my class mapping in `REVIEWER_CELLS`, not validated sensitivity.

| # | finding | change (readability_render.py) | test cell | status |
|---|---|---|---|---|
| 1 | provenance = filename/page/wire-sample pairing, not lineage | `EXPORT_RECEIPT_SCHEMA` + `write_export_receipt()` (sheet-set hashes, netlist hash, render hash, kicad version, commands); `_resolve_provenance()` → `verified | mismatch | unknown`; `measure(export_receipt=…)`; PASS only on `verified`; findings retained on mismatch/unknown. CP3 receipts record the **regenerated**-netlist lineage of the CP3 sch bytes, so the archived 55-min-older `.net` reports `PROVENANCE_MISMATCH` + `indeterminate` (historical diagnostic input, kept). PAIR_* anomalies (inputs not one artifact) → `indeterminate`, never `fail`. | `Provenance.*` (5): cp3 archived net → mismatch+indeterminate with findings; no receipt → unknown blocks PASS; verified receipt binds hashes/version/command; same-named changed sheet refused; stale export refused; `Contract.test_mismatched_pair_is_indeterminate` | done |
| 2 | B1 self-erasure: union at dots assigned the merged component one identity | `DrawnGraph.contacts` / `pin_wires` keep pre-union structure; `_branch_identities(p)` computes each branch's identity WITHOUT traversing the contact at p; `_foreign_branches()`; `_class_b` rewritten on contacts (B1_FOREIGN_CONTACT[_WITH_DOT], B1_FOREIGN_CROSS_WITH_DOT, B1_SAME_NET_T_NO_DOT, B2_FOREIGN_CROSS_NO_DOT); pin authority = declared circuit when supplied else native; empty authority → `measured=False`, `indeterminate` | new fixture `b1/b1_dotted_contact.*` (R3.1 dotted onto the R1/R2 rail; declared NETA≠NETB; natively exported, receipt-bound): `B1DottedForeignContact.*` (4): B1 fires under declared identity at (60,40); distinct from no-dot B2 (b2=0 there); native-only cannot see it and says so (`applicability` names the source); empty authority → unmeasured | done |
| 3 | calibration was caller-asserted | `CALIBRATION_RECORD_SCHEMA`; `_resolve_calibration(record, policy_digest, classes)` → `calibrated | partial | uncalibrated`; must name policy digest, per-class population and reviewer-evidence refs; `measure(calibration_record=…)` (the old `calibration_ref={"status":"calibrated"}` path removed) | `CalibrationRecord.*` (6): accepting exemplar passes only with a resolved record; no record → uncalibrated+indeterminate; bare assertion rejected; wrong policy digest → uncalibrated; partial class cover → partial; clean fixture measures a real population | done |
| 4a | class d population: examined added before reconcile; n1==n2 undecidable natively | `expected` = every two-terminal non-power/replica element; `examined` ⊂ expected after omit; n1==n2 → `not_assessed` (`indeterminate` class verdict) unless `declared_pin_nets` supplied, then `D_FUSED_SERIES` (declared series drawn as one net) or "declared shunt" omit | `Population.test_class_d_expected_equals_examined_plus_omitted`, `test_shunt_without_declared_intent_is_not_assessed` (b1 R4), `test_shunt_with_declared_intent_is_assessed` | done |
| 4b | class c: global label exempted the whole net | `_derive_local_pairs()` (policy-K population when no explicit list) + `measure(required_local_pairs=…, local_exceptions=…)`; exceptions are per-pin named records (power / continuation / NC / replica), never a net-wide blanket; continuation exemption applies only to the pin the global/hier label sits on | `Population.test_class_c_consumes_explicit_required_pairs`, `test_class_c_global_label_does_not_exempt_the_whole_net` | done |
| 4c | class f partial | `applicability` now states "partial: … text-vs-symbol-graphics clearance NOT measured"; verdict gate excludes f (`abcde` only) | `Contract.test_f_cannot_contribute_a_full_pass` | done |
| — | clean exemplar | KiCad dropped the 50→70 GND segment at the 60,80 junction in its own render (coverage check caught it); fixture split at the junction and re-exported natively; receipt-bound | `AcceptingExemplar` via `CalibrationRecord.test_accepting_exemplar_passes_only_with_a_resolved_record` | re-pinned |

New fixture pins (all in `PINS`): b1 sch `306a0dab…` / svg `11fc9872…` / net `3e5fce5c…` / receipt `ca98f0c0…`; clean sch `606b142d…` / svg `01be7b19…` / net `7c6b2d9a…` / receipt `1df44293…`; cp3 receipts usbc `bd69948f…` / power_rail `9d4ca893…` / battery `3a87b551…`. CP3 sch/svg/archived.net/reviewer pins unchanged.

File hashes after round 2: `readability_render.py` `b722d69518a67aabf6323b779ac51d1801436a442cf29545af4752ea1eb035c4`; `tests/test_readability_render.py` `c58c36065851246e4dff56d068bb2e64ad2985745d841ac2567a0a24b5480c02`.

Round-2 run (verbatim, after `find . -name __pycache__ -prune -exec rm -rf {} +`):

```
$ ./scripts/run_tests.sh test_readability_render
...................................
----------------------------------------------------------------------
Ran 35 tests in 4.011s

OK
exit=0
```
Ran 35 / failures 0 / errors 0 / skipped 0 / exit 0.

Still unmeasured after round 2: CP1/CP2 (permanently blocked, §6); no independent YES on the accepting exemplars (clean + b1 are hand-verified); text-vs-symbol-graphics clearance (f partial); rotation ≠ 0 uncalibrated; full suite not run. Under native-only identity the CP3 cells' class d still shows `not_assessed=0` because every CP3 two-terminal element has two distinct native nets — the `not_assessed` path is exercised on the b1 fixture only.

## 8. Round 3 (Astra r2 invariants), 2026-10-06

**Correction to §7 row 1.** As measured in round 2 the CP3 cells reported `verdict=fail`, not `indeterminate`: the round-2 code let a class FAIL outrank provenance mismatch unless the anomaly was `PAIR_*`, and `RejectingExemplars._cell` asserted `fail`. §7 row 1 described the intended behaviour, not the measured one. Round 3 makes the code match: provenance mismatch/unknown ⇒ overall `indeterminate`, class outcomes retained.

| # | finding | change (readability_render.py) | test cell | status |
|---|---|---|---|---|
| 1 | precedence: class FAIL won over provenance mismatch | verdict ladder reordered: `PAIR_*` anomaly → `indeterminate`; **provenance ≠ verified → `indeterminate`** (before any class read); then class fail → `fail`; unmeasured/indeterminate class → `indeterminate`; calibration ≠ calibrated → `indeterminate`; else `pass`. Class verdicts/findings untouched (diagnostics retained). | `RejectingExemplars._cell` now asserts mismatch + `verdict=indeterminate` + `scoped_verdict=indeterminate` + ≥1 class `fail` + non-empty offenders; new `Provenance.test_mismatch_outranks_class_fail_for_the_overall_verdict` (3 cells) | done |
| 2 | calibration record was a declaration (truthy population + refs) | `CALIBRATION_RECORD_SCHEMA = "s1-calibration-record-v2"`; v1 refused. Record = `policy_digest` + `supported_scope{rotations, classes}` + per class `rejecting[]` / `accepting[]`, each entry `{artifact_sha256 (hex64), decision_ref}`. `_resolve_calibration(record, policy_digest, classes, subject_scope)` is a pure consistency check → `uncalibrated | inconsistent | out_of_scope | partial | calibrated`: every entry needs hash+ref; every required class needs ≥1 rejecting AND ≥1 accepting; supported rotations must cover the subject's symbol rotations (+mirror). Any partial class ⇒ `partial` ⇒ overall `indeterminate`. | Test helper `_calibration_record()` now carries **only real evidence**: rejecting = CP3 svg hash + `reviewer-cp3.md#NO` for the classes each reviewer named (a:1, b:1, c:3, d:1, e:2); accepting = **none**. `CalibrationRecord.test_todays_evidence_is_partial_and_the_clean_fixture_cannot_pass` asserts `status=partial`, `partial_classes=[a,b,c,d,e]`, `accepting=0` per class, overall `indeterminate` on the clean fixture. Resolver acceptance is proven with an explicitly labelled `_HYPOTHETICAL_YES` (decision_ref = "HYPOTHETICAL: no independent YES exists on 2026-10-06") in `test_resolver_accepts_wellformed_evidence_but_six_class_report_stays_partial`; also `test_v1_declaration_record_is_no_longer_accepted`, `test_entry_without_hash_or_decision_is_inconsistent`, `test_subject_rotation_outside_supported_scope_is_refused`, `test_partial_class_cover_is_partial_not_calibrated` (d,e partial). No YES fabricated. | done |
| 3a | PASS decided on a–e silently | `ReadabilityReport.verdict_scope="a-e"` + `scoped_verdict` (the a–e decision). Top-level six-class `verdict` ∈ {`fail`, `indeterminate`} only: `fail` when a–e fail or f finds a hard defect under verified lineage; otherwise `indeterminate` (never `pass`) while f is partial. | `Contract.test_f_cannot_contribute_a_full_pass`: with hypothetical YES, `scoped_verdict=pass`, `verdict≠pass`, `verdict_scope="a-e"` | done |
| 3b | subject manifest hashed three files only | `authority_digests` = sha256 of `declared_pin_nets`, `required_local_pairs`, `local_exceptions` (sorted reprs) + `policy_digest`; `subject_manifest_sha256` = sha256 over artifact hashes ∪ authority digests. | `Contract.test_subject_manifest_binds_authority_inputs`: same artifact bytes, four authority variants → four distinct manifests; identical inputs → identical manifest | done |

File hashes after round 3: `readability_render.py` `3aaf865c48676cc2f9ecb005a8bd46658758be96388778515d9d723a5ae6213c`; `tests/test_readability_render.py` `ae67cf29b8ee18be918ef7dfb1efd046bde40f2803b712d1bd2fde2cd5c9deb1`. Fixture pins unchanged from round 2.

Round-3 run (verbatim, after `find . -name __pycache__ -prune -exec rm -rf {} +`):

```
$ ./scripts/run_tests.sh test_readability_render
.........................................
----------------------------------------------------------------------
Ran 41 tests in 6.886s

OK
exit=0
```
Ran 41 / failures 0 / errors 0 / skipped 0 / exit 0.

**Honest state after round 3.** No artifact reaches `scoped_verdict=pass` with the evidence on hand: calibration is `partial` for every class (no independently reviewed accepting case exists), and the six-class `verdict` cannot be `pass` while f is partial. The clean fixture measures zero findings in a–e under verified lineage — that is a diagnostic result, not a calibrated PASS. Still unmeasured: CP1/CP2 (blocked); independent YES per class; text-vs-symbol-graphics clearance; rotations ≠ 0 (fixtures are all 0°, so `subject_scope.rotations=[0]` and the record declares `[0]` only); full suite not run.

## 9. Round 4 residuals (Astra r3: ACCEPT-AS-DIAGNOSTIC-READY), 2026-10-06

| # | finding | change (readability_render.py) | test cell | status |
|---|---|---|---|---|
| 1 | `required_local_pairs=None` (derive under policy K) and `[]` (explicit empty population) hashed identically in the authority digest | digest now hashes a tagged value: `{"mode":"derived"}` vs `{"mode":"explicit","pairs":[…]}` | `Contract.test_none_and_empty_required_pairs_are_distinct_subjects`: same artifact bytes → distinct `subject_manifest_sha256` and `authority_digests["required_local_pairs"]`; class c `applicability` reads "derived" vs "caller-declared"; derived has `required_pairs>0` with findings, explicit-empty has 0 pairs and no findings | done |
| 2 | calibration record check is structural, not evidence authentication | module docstring states the limit explicitly; every `calibration_ref` (partial / calibrated) carries `evidence_authenticated=False, authenticated_by=None`. No application boundary built this round. | `Contract.test_calibration_ref_declares_evidence_not_authenticated` (real-evidence record and hypothetical-YES record both report `False` / `None`) | done |

**What the record check cannot do.** `_check_entries` verifies only that each entry has a 64-hex `artifact_sha256` and a non-empty `decision_ref`; `_resolve_calibration` verifies counts and scope cover. It cannot verify that the hash names the artifact the reviewer actually looked at, that the decision ref resolves to a real review, or that the review adjudicates the class the entry is filed under. Consequently a syntactically complete record **cannot yield calibrated evidence** until an application boundary binds each entry to its reviewed artifact and to a per-class decision. One general YES on an artifact does **not** cover every class unless that review explicitly adjudicates those classes; a boundary that fans one YES out to a–e would be fabricating per-class evidence. The `calibrated` status returned today means "structurally complete", and `evidence_authenticated=False` says so in-band.

File hashes after round 4: `readability_render.py` `da6822556ea743e97f51c797a97a18d4ae367cb5bd217b9d2580a598f5b8ea69`; `tests/test_readability_render.py` `44b37c106f83b7ca767874bd171c8df204313308c01149b4b51bd054060bad81`. Fixture pins unchanged.

Round-4 run (verbatim, after `find . -name __pycache__ -prune -exec rm -rf {} +`):

```
$ ./scripts/run_tests.sh test_readability_render
...........................................
----------------------------------------------------------------------
Ran 43 tests in 7.366s

OK
exit=0
```
Ran 43 / failures 0 / errors 0 / skipped 0 / exit 0.

Unmeasured in round 4: full suite not run (module only); the evidence-binding boundary itself (deliberately not built); everything listed under round 3 still stands.

## 10. Round 5 detector coverage (S3 usbc leaf, run-20261006-133234), 2026-10-06

Subject (immutable, hashes re-verified on disk before measuring): `native/svg/usbc.svg` 28bd7d5e…, `out/usbc.kicad_sch` dcfdc6b2…, `native/usbc.net` aed12f2f…; PDF-path PNG `native/pdfpath/usbc-1.png` ddd66e93… (1754x1240, 5.906 px/mm). Reviewer record: `s3-first-leaf-review-20261006.md` Review 2. Same authority inputs as the officer's `s1_invocation.json` (copied into `tests/fixtures/readability_render/s3_usbc_20261006/`, pinned). This round fixes **no** candidate defect; S3 owns the artifact.

### 10.1 Why `wire_through_text` was 0 (measured, not inferred)

Two independent causes, each shown on the exact subject:

| cause | evidence |
|---|---|
| **A. sampling blind spot (items 1-3).** Class f tested a wire against a glyph box by sampling the segment at t = .25/.5/.75 of the WHOLE wire. All three strikes are on long wires whose glyph box lies between sample points. | Old test re-run on the four pairs: `USB_C_16P`×wire cacea585 (x=73.66, y 40.64→81.28): samples y = 50.8 / 61.0 / 71.1, box y = 56.7–58.4 → miss. `USB_C_16P`×d62747ae (x=71.12, y 45.72→58.42): samples 48.9 / 52.1 / 55.2 vs box 56.7–58.4 → miss. `CC2`×d62747ae: samples 48.9 / 52.1 / 55.2 vs 47.5–49.2 → miss. `CC1`×cacea585: samples 50.8 / 61.0 / 71.1 vs 72.6–74.3 → miss. All four `old-sample-hit=False`. |
| **B. flag ink not modelled (item 4).** KiCad draws a global-label flag outline as a comma-format closed path (`d="M 83.8200,81.2800 84.9313,82.5504 … Z"`). `parse_svg` only tokenised `M x y L …` paths, so the outline (and every symbol body) was never in the model. | SVG line 8705-8711 holds the GND flag outline at (83.82,81.28); `svg.paths` had 0 entries for it (33 comma-format paths in the file, none parsed). |

Ruled out: text extent model (the four texts ARE in `svg.texts` with boxes matching the reviewer px to ±2 px: `USB_C_16P` 395-459 × 335-345; `CC1` 420-443 × 429-439; `CC2` 405-428 × 279-289; `D1` 515-531 × 467-476); symbol-property text excluded (`USB_C_16P` and `D1` are Value/Reference properties and ARE present).

### 10.2 px → mm, owner, mapping table (reviewer labels preserved, no relabel of history)

Instrument class for all four is **f** (text-vs-ink); the reviewer's own label stays in the first column. Review 1 had put the GND-flag/D1 overlap under reviewer-e and Review 2 under reviewer-f; both are kept.

| # | reviewer defect (Review 2) | reviewer class | px (x,y) | mm (x,y) | instrument class / code | finding location (px) | status |
|---|---|---|---|---|---|---|---|
| 1 | CC1/VBUS_CON verticals (x≈420/435) strike "USB_C_16P" (396-458, 339) | **e** | 435,340 / 420,340 | 73.66,57.58 / 71.12,57.58 | **f** `F_WIRE_THROUGH_TEXT` ×2 (wires cacea585, d62747ae); plus a third vertical x=68.58 (wire 0a1c7170) | (435,340) (420,340) (405,340) | detected |
| 2 | "CC2" label (417,283) sits on the CC1 wire | **f** | 417,283 | 70.6,47.9 | **f** `F_WIRE_THROUGH_TEXT` CC2×d62747ae | (420,284) | detected (geometry only — see 10.4) |
| 3 | "CC1" label (421-441, 432) struck by VBUS_CON vertical | **f** | 435,432 | 73.66,73.1 | **f** `F_WIRE_THROUGH_TEXT` CC1×cacea585 | (435,434) | detected |
| 4 | GND flag (497-540, 480) overlaps D1 refdes/value | **f** (Review 1: **e**) | 523,473 | 88.5,80.0 | **f** `F_FLAG_THROUGH_TEXT` D1×flag:GND@(83.82,81.28) and PESD5V0L4UF×same flag | (523,473) (524,488) | detected (refdes AND value) |

Why f, not e: class e is defined as foreign-net corridors / pin-row proximity / wire through *body*. Text strike-through is text-vs-ink, which the module already houses in class f's text-vs-wire sensor. Moving it to e would require a new e sensor and would double-report. **Consequence flagged for the officer (not decided here):** the corpus classification in the review record lists reviewer-e as "REJECTING (text strike-through, TVS body)"; in the instrument that evidence lands on class f, and class e has no finding on this subject. The calibration record's per-class rejecting entries (v2) should cite the review under the class the instrument reports, or the e-entry would authenticate nothing the e-detector can see. The TVS-body half of reviewer-e remains unmeasured (10.4).

### 10.3 Change and per-class delta (same inputs, `measure()` re-run)

Change (`readability_render.py`): (1) `_seg_box_clip` — exact Liang-Barsky clip replaces the 3-sample test; one finding per (text, wire), `at` = midpoint of the struck stretch; the glyph box is shrunk by 5×`coord_eps_mm` so a label's own wire ending at/along the anchor edge is not a strike. (2) `parse_svg` now reads comma-format closed polygons into `SvgDoc.polys` (deduplicated; KiCad emits duplicated labels twice). (3) class f: `F_FLAG_THROUGH_TEXT` — global/hier label flag outline (identified by first vertex == a sheet label anchor) crossing any text that is not wholly inside the flag's own bbox. (4) `flag_through_text` measurement; f `applicability` text updated. POLICY untouched (digest unchanged); no authority/authentication logic touched.

| class | before (`s1_report.json`) | after | note |
|---|---|---|---|
| a | pass, 0 | pass, 0 | unchanged |
| b | fail, 1 (`B2_FOREIGN_CROSS_NO_DOT` at 73.66,58.42) | fail, 1 | unchanged |
| c | pass, 0 | pass, 0 | unchanged |
| d | pass, 0 | pass, 0 | unchanged |
| e | pass, 0 | pass, 0 | unchanged (see 10.2) |
| f | pass, 0 (`wire_through_text`=0) | **fail, 9** (`wire_through_text`=7, `flag_through_text`=2) | the four reviewer sites + extras below |
| overall | `fail` (carried by b) | `fail` (b and f) | `scoped_verdict` fail; provenance verified; calibration partial; `subject_manifest_sha256` 63ee49db… identical (same artifacts + authority + policy) |

Nine f findings = the four reviewer sites (items 1: 3 findings incl. the third vertical; 2: 1; 3: 1; 4: 2) plus two the reviewer did not cite: `J1`×wire 0a1c7170 at (405,322) and `VBUS_CON`×wire f2d78bd7 at (480,359). These are **unadjudicated extras**, not confirmed false positives and not confirmed true positives. (The VBUS_CON strike sits next to the reviewer's "VBUS_CON text under the crossing" remark in b2 but was not cited as a text strike.)

### 10.4 What this does not cover

- Glyph boxes are estimates (SVG `textLength`, y-extent −0.8/+0.2 × font size), not rasterised ink; a strike within ~0.05 mm of the box edge is ignored by design.
- Item 2's "labels the wrong net visually" is a semantic reading; the instrument reports only that the CC2 text box is crossed by the CC1 wire.
- A label whose own wire passes through its own glyph box is reported as a strike (control: the clean fixture and CP3 own-label cases stay f-clean on the pinned fixtures; not exhaustive).
- Symbol-body / pin-graphic clearance (reviewer-e "TVS drawn as four bare diode glyphs") is still NOT measured; reviewer-f "500mA nearly touches VBUS flag" (near-touch, no overlap) is NOT measured; page-use remains reported, not gated.
- Only the flag outlines of global/hierarchical labels are modelled; other polygons are skipped. No new detector was run against CP3/B1 beyond the existing assertions (those tests pass), so CP3 per-class f counts may have moved and were not re-tabulated.
- Full suite not run (module only). No candidate artifact was changed.

### 10.5 Tests and hashes

New fixture subdir `tests/fixtures/readability_render/s3_usbc_20261006/` (5 files, pinned in `PINS`): usbc.kicad_sch dcfdc6b2…, usbc.svg 28bd7d5e…, usbc.net aed12f2f…, usbc.export-receipt.json 58e79522…, s1_invocation.json 780d6c81…. New class `S3UsbcCoverage` (7 cells): items 1/2/3/4 each located within 12 px of the reviewer coordinate; per-class delta; two controls (clean fixture f-clean; only the one GND flag whose outline crosses D1 is reported of 5 flags). Baseline 43 → 50.

File hashes after round 5: `readability_render.py` `d0dca6c8c5c49f9cb43b767df7372e7688c9b10e2fce5e7610c00b9b818cab8d`; `tests/test_readability_render.py` `f3be23a535b583d79108a3221dccca21870b269d7326d0ad0e189c25bffc1bb9`.

Run (verbatim, after `find . -name __pycache__ -prune -exec rm -rf {} +`):

```
$ ./scripts/run_tests.sh test_readability_render
..................................................
----------------------------------------------------------------------
Ran 50 tests in 8.802s

OK
exit=0
```
Ran 50 / failures 0 / errors 0 / skipped 0 / exit 0.

## 11. Round 6 transform coverage (S3 R3: only D1 may carry rotation/mirror), 2026-10-06

**Identity continuity.** Historical reports produced under `d0dca6c8…` remain historical measurements: not invalidated, not relabelled. S3 R3 is remeasured under `9c18bc51…`, and both identities are kept on record.

**Instrument identity.** Round 6 changed `_transform` (a defect, below), so by ruling (1) this is a NEW instrument identity: `readability_render.py` **9c18bc51…** replaces **d0dca6c8…** (the bound S1 identity for S3 R2; reports stored under d0dca6c8 stay valid for that hash). Policy digest unchanged (`443bbb0185d5a914`). `supported_scope.rotations` NOT expanded; nothing declared calibrated.

### 11.1 Defect found and fixed (measured against kicad-cli 9.0.9 ink)

`_transform` applied the mirror BEFORE the rotation. KiCad applies it after. The orders agree at rot 0/180 and disagree at 90/270. Probe: one 3-pin symbol (`Test:U3`, asymmetric body) placed at 12 variants (rot 0/90/180/270 x none/x/y), each exported natively; pin tip, pin stub end and body box compared to the exported ink (path endpoints; body `<rect>`).

**Provenance of the 12-variant count (exploration, not the pinned regression).** The 12 hand-built sources and their 12 raw native kicad-cli 9.0.9 SVG outputs are retained on disk, outside the repo and unpinned, at `~/.cache/scratch/s1-xform/{v<rot><n|x|y>.kicad_sch, o_v<rot><n|x|y>/v<rot><n|x|y>.svg}` (rot in 0/90/180/270; combined sha256 of `sha256sum v*.kicad_sch o_*/*.svg`: `6b873e23b9ec03b33e6bdfcc62df391e0c1b71f6d347275c1d454ce02e4e449c`). The comparison probe itself was ad hoc and no measurement receipt or probe script was retained. The 12/12 and 0/3 vs 3/3 figures below are therefore **worker-reported, not independently reproducible here** from a retained script; only the inputs/outputs are retained. Only two of the twelve (R90+MX, R270+MY) are copied into the repo as pinned fixtures.

| variant family | old order (d0dca6c8) | new order (9c18bc51) |
|---|---|---|
| rot 0/90/180/270, no mirror | 3/3 pins on ink | 3/3 |
| rot 0/180 x mirror x/y | 3/3 | 3/3 |
| **rot 90/270 x mirror x/y (4 variants)** | **0/3 tips, 0/3 stub ends on ink** | **3/3, 3/3** |
| body box == native body rect, 12 variants | not compared (probe gap, see 11.4) | 12/12 within 0.02 mm |

### 11.2 Coverage table (what is measured, and what is not)

Column "observed" means observed on these fixtures and conditions only; it is not a claim of transform-correctness in general. What `Ran 60 / OK` proves for geometry is the **four pinned U1 cases** in `TransformCoverage.CASES` (`tests/test_readability_render.py:697-698`): xr180 (R180), xm (MY), sweep_r90_mx (R90+MX), sweep_r270_my (R270+MY). It does **not** prove the 12-variant sweep (see 11.1: worker-reported).

| layer / class | observed on these fixtures/conditions | evidence |
|---|---|---|
| geometry: pin tip, stub end, body box | **observed on the 4 pinned cases** (R180, MY, R90+MX, R270+MY): pin tips and stub ends within 0.02 mm of native ink, body box equals a native `<rect>`. The remaining 8 of 12 variants: worker-reported only (11.1) | `test_pin_tips_and_stub_ends_land_on_native_ink`, `test_body_box_equals_native_body_rectangle` (loop over the four CASES); `test_old_mirror_then_rotate_order_was_wrong_at_90_and_270` (old order: 0/3 on both sweep fixtures) |
| a junction ambiguity | observed at R180 and MY/MX (1 dot at the same-net T (125,112); no spurious/missing) | `test_detectors_on_rotated_and_mirrored_fixtures` |
| b cross-net contact/crossing | observed at R180 and MY/MX (one `B2_FOREIGN_CROSS_NO_DOT` at (115.0,102.54), nets GND vs the U1 signal net) | same |
| c local wired-path completeness | observed at R180 and MY/MX (clean, 3/3 pairs) | same |
| d series-path legibility | observed at R180 and MY/MX (clean) | same |
| e wire-through-body / pin-tip bands | observed at R180 and MY/MX (one `E_WIRE_THROUGH_BODY` on U1 in each; asymmetric body means a wrong body box would move or drop it) | same |
| f text / label flag | observed clean at R180 and MY/MX; **text rotation inside rotated symbols NOT exercised** | same; 11.4 |
| detectors on rot 90/270 | **geometry only**: the sweep fixtures have no net/receipt, so no class detector ran on them | 11.4 |

Same-net T and foreign crossing present in both detector fixtures (`xr180`, `xm`); same topology, same findings, only the net name of the U1 pin differs.

### 11.3 Scope and rotation-0 invariance

- Rotated/mirrored subjects: with a record whose rotations are `[0]` the resolver returns `out_of_scope` (`reason: subject rotations [...] not in supported [0]`), findings retained, `scoped_verdict` and `verdict` never `pass` (`test_rotated_and_mirrored_subjects_are_out_of_supported_scope`, xr180 -> [180], xm -> [0,"mirror"]).
- Resolver crash found and fixed: a record naming `[0,"mirror"]` raised `TypeError` (sorting int vs str). Now sorts with `key=str`; such a record still earns only `partial`, `evidence_authenticated=False` (`test_mixed_scope_record_does_not_crash_the_resolver`).
- Rotation-0 invariance (`test_rotation_zero_findings_are_identical_old_vs_new_transform`): the same 7 subjects measured under the old and the new `_transform` give identical per-class verdicts and identical findings (code, objects, location): CP3 usbc / power_rail / battery, clean, b1, run-133234, run-150709. Precondition asserted separately: all 7 have only (rot 0, no mirror) symbols (`test_rotation_zero_subjects_have_no_transform_exposure`).
- Run-150709: a fresh run equals the stored `s1_report.json` (module d0dca6c8) class by class and on `subject_manifest_sha256` (`test_run_150709_matches_its_stored_report`): a 0 a / b fail 1 / c, d, e, f pass 0, overall fail.
- Run-133234: its stored report predates the round-5 detector (f pass 0, round-5 delta f fail 9 recorded in section 10). Round 6 itself moves nothing there (old-vs-new transform identical).

### 11.4 Not measured / caveats

- Class detectors on rot 90/270 and on 90/270 x mirror: only geometry is verified there.
- Text rotation: the SVG text parser handles `rotate(...)` groups, but no fixture here rotates the symbol property text, so class f text boxes inside rotated symbols are unmeasured. KiCad also changes property text justification under mirror; not examined.
- Multi-unit symbols, arcs/circles under transform (only the rectangle body is compared to ink), and bodies built from polylines are not exercised; the body box is a bbox of graphic extremes.
- The first body-vs-ink probe compared against the wrong ink shape (5-point paths; KiCad draws `<rect>`) and reported 12/12 mismatch including rot 0; the comparison was corrected, not the code. The old-order body box was therefore not compared.
- Hand-built fixtures: same lib symbols as b1 (`Device:R`) plus a hand-written 3-pin `Test:U3`; kicad-cli reports the library as unknown (`lib_symbol_issues`) and some off-grid endpoints; this does not affect the geometry compared. They are not real S3 output. The two sweep fixtures carry the kicad-cli SVG only (no netlist/receipt).
- Reviewer-e TVS-body item and the two unadjudicated extras: untouched, per ruling (2). No e accepting cell inferred.
- Full suite not run (module only). No S3 file touched.

### 11.5 Tests and hashes

New fixtures `tests/fixtures/readability_render/xform/` (18 files, pinned): `xr180.*` (R180 U1, R1, R2), `xm.*` (U1 mirror y, R1/R2 mirror x), `sweep_r90_mx.{kicad_sch,svg}`, `sweep_r270_my.{kicad_sch,svg}`, `r150709/*` (run-150709 copy: sch 9db00c80…, svg 8cc7f322…, net 677e8d08…, report 3164f85e…). New class `TransformCoverage` (10 cells). Baseline 50 -> 60.

Hashes: `readability_render.py` `9c18bc518eafa4362029adf2391c8d1ce05466f8dd875299133676338669fac8`; `tests/test_readability_render.py` `8001ee6018229014690617b677c3a0fd32d6b6ea01926508c671ec6ca61ea48b`.

Run (verbatim, after `find . -name __pycache__ -prune -exec rm -rf {} +`):

```
$ ./scripts/run_tests.sh test_readability_render
............................................................
----------------------------------------------------------------------
Ran 60 tests in 12.180s

OK
exit=0
```
Ran 60 / failures 0 / errors 0 / skipped 0 / exit 0.

## 12. Class e scope annotation: package/group coherence is not assessed (Astra r4), 2026-10-06

Documentary only. No code, test or fixture changed; instrument identity stays `readability_render.py` 9c18bc51….

1. **Not assessed.** Class e "package/group coherence" (a multi-glyph symbol reads as one component; one flag per many channels) is NOT ASSESSED by any implemented sensor. The only implemented e sensors are wire-through-body and over-unconnected-pin. Zero findings from those two must not be described as full class-e acceptance; at most it means "no wire-through-body / over-unconnected-pin finding".
2. **Review 4 (run-162241, PNG sha256 9407f5c441f27135ff2261560bfbd6570198567bb3f186b5c8f5d23c1ed28533).** The reviewer-e rejection (D1 drawn as four loose glyphs) is recorded as **e / unmeasured-by-instrument**. It is NOT remapped to f. The §10 e→f mapping applies only to text-strike defects (wire-through-text, flag-through-text) and is not extended here. The S3 run-162241 diagnostic of a,b,c,d,e,f all pass with zero findings is therefore consistent with this rejection: the instrument has no sensor that could see it.
3. **Future work, out of scope.** An e-coherence sensor needs its own object/group semantics (what counts as one component and one flag per channel group) and an adjudicated corpus. Neither exists; none is built in this slice.

## 13. Round 9: sheet-layer graphic ink + observations (spec s1-sheet-graphics-spec.md sha 00baa4c4…), 2026-10-06

**Identity.** NEW instrument `readability_render.py` sha256 `f98dc2371afc3202485bd1a7cc808b9b118a9578b8dbfed131a6cc68fdad269f` (2258 lines) replaces `9c18bc518eafa4362029adf2391c8d1ce05466f8dd875299133676338669fac8` (1852 lines). Test module `tests/test_readability_render.py` `3bc2838d702ae132ad3a2d54f75735cfbf9a2a055a9ce02598c112eb5217ae24` (was `8001ee60…`, 931 lines; now 1589). `measurement_scope_version` = `s1-measurement-scope-v2-sheet-ink-observations`. Policy digest before `443bbb0185d5a914`, after `443bbb0185d5a914` (UNCHANGED, see deviation D1). Historical 9c18bc51 reports stay historical; both identities are kept. Calibration stays `partial`, `evidence_authenticated=False`, `authenticated_by=None` (asserted by tests). Tree left uncommitted.

### 13.1 Deviations and decisions to rule on
- **D1 (needs ruling): `ink_chord_tol_mm` is NOT in `POLICY`.** The brief says "chords at ink_chord_tol_mm 0.05 in policy digest". Putting it in `POLICY` changes the policy digest of EVERY subject, which changes every stored manifest and invalidates every stored calibration record, contradicting AC6 (ink-free manifests byte-identical). I kept it as the module constant `INK_CHORD_TOL_MM = 0.05`, reported in `report.measurement_scope`, and hashed into the subject manifest ONLY for subjects that carry ink or an ink-owner declaration (`authority.ink_chord_tol_mm`, `authority.measurement_scope_version`, `authority.ink_owner`). If the officer wants it inside `POLICY`, every manifest and the calibration policy digest move; that is a separate decision.
- **D2: ink-owner authority joins the manifest only when ink or a declaration exists.** An ink-free subject with no declaration keeps its 9c18bc51 manifest byte-for-byte (measured below). R5b's manifest changes `87b44e5fdd205cb7` -> `478e99927d65fd3f` solely because it carries ink; its verdicts, classes and graph are unchanged.
- **D3: `Observation` is a separate dataclass held in `ClassReport.observations`**, never in `findings`; `offenders()`, `offender_classes()`, every verdict path and every calibration function read `findings` only. Reports gain `sheet_graphic_ink`, `ink_report`, `measurement_scope`.

### 13.2 What was built (files)
`readability_render.py`: `InkItem`, `_parse_ink` (root-level only, via `source_line`; unparsed `bezier/text_box/rule_area/image/sheet` and degenerate polylines counted in `ink_unparsed`), `_ink_paths` (rect edges; polyline; circle/arc as chords at sagitta <= 0.05 mm), `_seg_hit` (cross/touch/overlap), `_ink_observations` (P1-P4, one per pair, `expected == examined + omitted`), `_resolve_ink_owners` (explicit-map vs rule; duplicate/ambiguous => no owner; both modes at once is refused), `measure(..., ink_owner_map=, ink_owner_rule=)`. No change to `build_drawn_graph`, `_UF`, class a-e code, `_resolve_calibration`, or any other module.
New fixtures: `tests/fixtures/readability_render/r5b_usbc_20261006/` (byte-preserving `cp -p` copy; manifest `MANIFEST.sha256` + `README.md`; hashes below) and `synthetic_ink/` (`ac3_wire_cross`, `ac4_enclose_two_pins`: `clean_divider.kicad_sch` + one root-level rectangle, netlist/SVG natively exported by kicad-cli 9.0.9, receipts written by `write_export_receipt`).

R5b manifest (copied files, all 4 match the original run hashes): `usbc.kicad_sch` 1a898ecc9158197e9d403b9a8fcc5886ba578aa86d303a8f463f38d17185856b; `usbc.net` 188cc95ccbe36242878750ef6f2637b45c02485e2cb9b724f2eb19f9fbb993f2; `usbc.svg` 54fca7ad2508d686f15d0cdb7a455181c65fc3096a8b031dceea29510009f10b; `usbc.export-receipt.json` 3619b26b92ad60bc9996c4a565c51ce748f4dba7f3297b1d8df9dbe408a41bc6; README 781856bf…; MANIFEST 19d75d02…. Pairing re-check: receipt binds sheet/net/render hashes, all match disk, `measure()` reports provenance `verified`, anomalies `[]`; the CP3 stale-netlist caveat does not apply. kicad-cli was not re-run on R5b. Restriction: internal review use only (general caveat; D1 is `Power_Protection:PESD5V0L4UF`).
Synthetic fixture hashes: ac3 sch 55058743…, net e92b8f9c…, svg fe4dd202…, receipt 90311ac6…; ac4 sch 2c845462…, net eb37ce74…, svg 08c7cddc…, receipt db824817….

### 13.3 Test run (verbatim; `find . -name __pycache__ -prune -exec rm -rf {} +` first)
```
$ ./scripts/run_tests.sh test_readability_render
............................................................................................................
----------------------------------------------------------------------
Ran 108 tests in 17.297s

OK
exit=0
```
Ran 108 / failures 0 / errors 0 / skipped 0 / exit 0. Baseline Ran 60 OK -> 108 (48 new cells). The original 60 cells are unmodified and still pass (one existing cell, `test_pin_table_covers_every_fixture_file`, was failing only until the new fixture files were added to `PINS`; that is a pin-table update, not a verdict change). Two new cells (`InkAC1Count.test_ac1_r6_candidate_has_zero_ink`, `InkAC2AC6Unchanged.test_ac6_r6_candidate_unchanged_when_present`) read the unpinned R6 scratch run and `skipTest` if it is absent; they ran here (0 skipped).

### 13.4 Population rerun under f98dc237 vs the 9c18bc51 baseline
Baseline dump taken from a saved copy of the old module on the same bytes BEFORE any edit; compared field by field (verdict, scoped_verdict, per-class verdict + findings, provenance, calibration status, policy digest, manifest, anomalies, graph-structure sha256).

**Population enumeration (seal-round wording; do NOT read as "14 full reports identical").** The dump has 14 invocations over 13 unique subject sheets, in two separate comparison kinds:
- *Full-report comparisons: 12 invocations over 11 unique sheets* (verdict, scoped_verdict, per-class verdict + findings, provenance, calibration status, policy digest, manifest, anomalies, graph hash): cp3 usbc, cp3 power_rail, cp3 battery (3); clean (1); b1 (1 sheet, TWO invocations: `b1` and `b1+declared`, i.e. two authority variants of one sheet, one graph hash); s3_usbc_20261006 (1); xr180 (1); xm (1); r150709 (1); R6 candidate (1, unpinned scratch, NON-PORTABLE, see 13.8); R5b (1). Sheets: 3+1+1+1+1+1+1+1+1 = 11; invocations 11+1 = 12.
- *Parser / graph-only sweeps: 2 invocations over 2 unique sheets* (`sweep_r90_mx`, `sweep_r270_my`): ink list and graph hash only; no net, no export receipt, no report claimed.
- Graph-structure hash equality (AC2) therefore covers 13 unique sheets (11 reporting + 2 sweep); it is not 14 distinct subjects.
- The R5b manifest change `87b44e5f…` -> `478e9992…` is INTENTIONAL (the sheet now carries ink, so the ink authority joins the manifest, see D2); all other compared R5b fields are identical.

| subject | sheet ink | all compared fields vs 9c18bc51 | graph sha256 (before = after) |
|---|---|---|---|
| cp3 usbc / power_rail / battery | 0 | identical | c7a274d1… / 119b1c5d… / ca98113c… |
| clean | 0 | identical | 3d7d790e… |
| b1 / b1+declared | 0 | identical | c22c0b13… |
| s3_usbc_20261006 | 0 | identical | 4460404b… |
| xform xr180 / xm | 0 | identical | 1f298a18… / de6d8626… |
| xform r150709 | 0 | identical | 676fa561… |
| xform sweep_r90_mx / sweep_r270_my | 0 | parser + graph only (no net, no receipt; no report claimed) | 754f7134… both |
| R6 candidate (sch 8cd238d2…, scratch, unpinned) | 0 | identical | b6bdd505… |
| **R5b (1a898ecc…)** | **1** (6fe52893-6baa-5a25-8e33-fdae41b26d87, rectangle, dash 0.1524, closed) | identical EXCEPT manifest (87b44e5f… -> 478e9992…, ink authority) | 0f41b4af… |

No pre-existing verdict changed for any reason. (STOP condition not triggered.)

### 13.5 AC table (measured values)
| AC | measured | test cell(s) |
|---|---|---|
| AC1 | R5b 1 (hand count 1; lib-symbol control: 16 raw `(rectangle` on R5b, 15 not counted); R6 0; every pinned sheet equals its anchored hand count (0); synthetic 1 each | `InkAC1Count` (4) |
| AC2 | graph-structure sha256 identical on all 11 reporting subjects + 2 sweep sheets, values pinned from the 9c18bc51 build | `InkAC2AC6Unchanged.test_ac2_…` |
| AC3 | `ac3_wire_cross`: exactly 1 observation `F_WIRE_THROUGH_INK`, `cross` at (80.0, 60.0), objects ink uuid 5a000000-…a3 + wire 9c2f1b3e-…da; 0 findings; a-f hash == clean twin | `InkAC3AC4Synthetic` |
| AC3b | P2, P3, P4 each positive + non-contact (6 cells), unit-level hand-built sheet/SVG (NOT native exports) | `InkAC3bP2P3P4` |
| AC3c | open polyline (not implicitly closed), closed polyline, circle (2 points -> 1 observation), arc, rectangle interior = 0, touch / overlap labels, chord sagitta <= 0.05; unit-level | `InkAC3cGeometryKinds` (8) |
| AC3d | with vs without rectangle: identical class verdicts, finding counts, `verdict`, `scoped_verdict` on both synthetics and on R5b (rectangle-removed twin built from the R5b text, same svg/net); observations only in the with-ink run; `expected == examined + omitted`; no observation in calibration_ref | `InkAC3dIsolation` (5) |
| AC4 | `ac4_enclose_two_pins`: R2.1 and R2.2 on different nets, different components; a-f classes hash == twin; graph hash == `clean_divider`; 0 findings in a-e; only 2 `F_INK_THROUGH_PIN` observations (rect edge crosses R2 pin stubs at y=67 and y=73) | `InkAC3AC4Synthetic` |
| AC5 | explicit map exact-identity; rule mode uuid5; no declaration -> unknown + listed; wrong declaration -> unknown + mismatch; duplicate ink uuid / duplicate symbol ref -> no owner; both modes -> refused; rule-positive proven on a labelled SYNTHETIC fixture; containment alone never sets an owner on R5b. **R5b rule cell NOT claimed**: see 13.6 | `InkAC5Ownership` (9) |
| AC6 | per-subject table 13.4; ink-free manifests byte-identical; sweep subjects parser/geometry only | `InkAC2AC6Unchanged` |
| AC7 | map contents, rule name, rule targets, rule version, extra rule parameter, None vs `{}` each give a distinct manifest (8 variants + base all distinct); same inputs same manifest | `InkAC7AC8AC9Contract` |
| AC8 | `{bezier:1, text_box:1}` counted, ink list empty; missing uuid counted (`""`, not invented) | same |
| AC9 | all P1-P4 are class f `kind="observation"`; none in any `findings`; no COHERENCE/GROUP/PACKAGE code in source; class e still measured; `not_assessed` lists symbol coherence; calibration `partial`, unauthenticated | same |
| AC10 | 13.3 | -- |
| AC11 | copied bytes == original hashes, manifest and README present, pairing `verified`, anomalies `[]` | `InkAC11R5bFixture` (3) |

### 13.6 R5b observations and the AC5 claim limit
R5b measured (no owner declaration): P1 21/21 examined, 0 emitted; P2 73/73, 0; P3 7/7, 0; P4 31 expected, 24 examined, 7 omitted (hidden pins J1.A12/B1/B12/A9/B4/B9, D1.5), 5 emitted: `F_INK_THROUGH_PIN` on D1.1, D1.2, D1.3, D1.4, D1.6, all `cross` (the narrow 2.54 mm outline edges pass through those pin stubs). All 5 carry `owner=unknown`, ownership assessment unmeasured.
Owner-rule measurement (RECORDED, not the AC5 claim): with rule `{name: "presentation.outline", targets: ["D1"]}` on the R5b bytes, `uuid5(D1 symbol uuid da260240-75a4-43c0-900e-6fd634e20a61, "presentation.outline")` reproduces ink uuid 6fe52893-… (`owner=D1`, `owner_declaration_mismatch=[]`). r9 wording (superseded by the seal addendum, 13.8 amendment 6): the historical AC5 was held UNRESOLVED pending S3 reconciliation, because S3 receipt :333 was read as tying the uuid to run-20261006-162241. That reading is withdrawn; S3 `s3-engine-spike-receipt.md` §R6.H (sha `420a008e…`, :450) resolves it: the uuid belongs to R5b-S1 only. This measurement establishes the local R5b association; no second pinned subject is needed.

### 13.7 NOT MEASURED / caveats
- Full suite not run (module only).
- kicad-cli was not re-run on R5b; the three R5b inputs were checked by hash and mtime.
- P1-P4 are centerline geometric-path intersections: dash gaps, stroke envelope, fill, z-order, what an outline means, grouping, symbol coherence, "package implies internal connection" are NOT assessed. Class e coherence stays not assessed; no e-coverage expansion.
- Circle/arc chord approximation: a tangent within the tolerance may be missed or added; the AC3c tangent-edge cell asserts the documented sagitta bound, not exact tangency.
- P2 uses the instrument's estimated glyph boxes (not SVG-measured), as class f does.
- AC3b/AC3c are unit-level hand-built geometry, not native exports; only AC3/AC4 (and R5b) are native.
- R6's own net/svg/export-receipt files were used from unpinned scratch for the rerun; their enumeration and pinning is not done here. The R6 cells skip if scratch is absent.
- Observation behaviour on rotated/mirrored symbols' pin stubs is geometry-only (pins come from the existing transform path); no ink fixture carries a rotation.
- Test-time scratch writes go to `~/.cache/scratch/s1-ink-tests/` and are removed by the cells.
- No calibration claim is made; the calibration record is untouched.

### 13.8 Seal round (r9 phase=seal), approval_ref `officer:ses_04db7a1c5ffelvbxyLP1p6xlRH/s1-r9-seal-20261006`

Verdict recorded: r9 ACCEPTED at bounded diagnostic-coverage-extension scope; D1/D2/D3 ACCEPTED. Document-only round: no code, fixture or test change; instrument stays `f98dc2371afc3202485bd1a7cc808b9b118a9578b8dbfed131a6cc68fdad269f`. Officer rerun recorded by the dispatcher: Ran 108 / OK / exit 0 (not re-run in this round).

**D1 ratified (decision policy vs measurement configuration).** The decision-policy digest `443bbb0185d5a914` is retained. `measurement_scope_version` and `INK_CHORD_TOL_MM` are versioned separately as MEASUREMENT CONFIGURATION. Rationale: these parameters affect OBSERVATIONS only, never decision policy or the calibration population. It is NOT a ruling that byte-identity outranks evidence invalidation. Rule going forward: any future change that affects findings or verdicts MUST invalidate decision evidence (new policy digest), even if AC6 byte-identity then changes. The 13.1 phrase "in policy digest" quoted from the brief is superseded by this distinction; `INK_CHORD_TOL_MM` is not in the policy digest.

**D2 ratified (conditional manifest binding).** An ink-free subject's unchanged manifest identifies the same SUBJECT, not the same instrument execution or coverage. Reports are identified by instrument hash + `measurement_scope_version` + report identity, and are never deduplicated by subject manifest alone. Empty parsed ink is not "no graphic content": `ink_unparsed_by_kind` and its unmeasured status stay visible. Presence of `measurement_scope_version` in a report is a report claim, not authenticated proof of execution.

**D3 ratified (anchors).** Observations attach after the `_class_f` verdict is fixed (`readability_render.py:2142-2145`: `f_rep0.observations, ... = _ink_observations(...)`), outside the verdict ladder (`:2201-2225`: scoped_verdict and verdict read class `verdict`/`measured` and provenance/calibration only). Line numbers are for hash `f98dc237…`.

**Amendments.**
1. Population wording: see the enumeration added under 13.4 (12 full-report invocations / 11 unique sheets; b1 = one sheet, two authority variants; 2 parser/graph-only sweeps; AC2 graph equality over 13 unique sheets). The R5b manifest change is intentional.
2. R6 scratch-dependent checks are NON-PORTABLE: `InkAC1Count.test_ac1_r6_candidate_has_zero_ink` and `InkAC2AC6Unchanged.test_ac6_r6_candidate_unchanged_when_present` ran with 0 skips here, but `skipTest` when the unpinned scratch run is absent. They are not a repository-contained R6 regression guarantee. No further fixture copying is done or authorized.
3. Three-way fixture distinction, preserved: (a) native-export fixtures (`synthetic_ink/ac3_wire_cross`, `ac4_enclose_two_pins`, and `r5b_usbc_20261006`); (b) hand-built geometry unit cells (AC3b, AC3c); (c) the rectangle-removed R5b twin (R5b text with the rectangle deleted, same net and SVG). The twin proves in-process observation isolation (AC3d) only; it does NOT prove native re-export equivalence and is NOT a valid new pairing.
4. R5b's five `F_INK_THROUGH_PIN` observations (D1.1, D1.2, D1.3, D1.4, D1.6) have `owner=unknown`: geometry measured, ownership unmeasured. They are not defects and not calibration evidence. Declared limits stay visible: estimated text boxes (not SVG-measured), 0.05 mm chord tolerance, 7 hidden-pin omissions in P4, dash / fill / z-order not assessed, no rotated ink fixture.
5. Owner rule: `rule id/version` are BOUND METADATA hashed into the manifest for the ONE fixed algorithm `uuid5(symbol uuid, name)` over the declared `targets`. The resolver (`:1886-1905`) does not dispatch on rule id or version; no arbitrary-rule semantics are claimed.
6. AC5 (seal addendum, same approval_ref). Local R5b association established: rule `{name: "presentation.outline", targets: ["D1"]}`, `uuid5(D1 symbol uuid da260240-…, "presentation.outline")` reproduces ink uuid `6fe52893-6baa-5a25-8e33-fdae41b26d87` on the R5b bytes (13.6). Cross-run attribution question RESOLVED by `s3-engine-spike-receipt.md` §R6.H (sha `420a008e…`, :450): the uuid belongs to R5b-S1 only; no second pinned subject exists or is needed for that claim. Officer-verified there: R4 run-20261006-162241 has no sheet-level rectangle and does not contain `6fe52893` (grep count 0), D1 symbol uuid `975183bb-…`; R5b-S0 D1 `7993d8ef` / outline `3402af4c`; R5b-S1 D1 `da260240` / outline `6fe52893` (:1620-1622); R6 D1 `289b716a`, no outline; all four D1 uuids differ (`kicad_emit.py:245-246` `_uid()` unseeded uuid4; outline = uuid5(symbol uuid, "presentation.outline") at :1617). S3 :333 sits in §R5.2b (run-r5b-s1-165624) and is a CORRECT statement; its parenthesis "(run-20261006-162241)" labels the baseline manifest root `c129b87f…`, not the uuid origin. The earlier S1 spec/receipt readings of :333 as an R4 attribution are withdrawn (documentary correction; no instrument report changed). The generic AC5 contract test (`InkAC5Ownership`) remains the accepted cell; R4 is not claimed as a subject.
7. Historical identities preserved: all `9c18bc51…` reports stay labelled as such and are not relabelled.

**Seal receipt (documents touched).**
- `s1-instrument-receipt.md`: before `438766cb8f2f5a00b47651b62895e1a4c853dc69a8046ebfac8396a3bde79434`, 52850 bytes, 408 lines; after hash reported in the BRNS-DONE (a file cannot hold its own hash). Sections touched: 13.4 (enumeration paragraph), new 13.8.
- `s1-sheet-graphics-spec.md`: before `00baa4c47bd3d016fd9aacfed41a5a0846a104654ffcd492b45de6ea3eeda676`, 27968 bytes, 172 lines. Sections touched: 4, 5.1, 6, 7 (AC5), new 11.

**Closing.** This seal confers no authority to commit, deploy, promote calibration, or reopen R6 visual acceptance. AC16 stays partial / unauthenticated (`calibration=partial`, `evidence_authenticated=False`, `authenticated_by=None`). Packaging remains BLOCKED.
