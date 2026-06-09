# C06 Verification — turn C03/C04 evidence into honest pass/warn/fail verdicts (and name what is still not-run)

## Purpose & scope

C06 owns the **verification record**: it takes the artifacts that C03 and C04 *produced* and decides
what they *prove*. Concretely it owns four deliverables — a machine-readable **verification summary**,
a **test plan**, a **bring-up checklist**, and the **reference cross-check** against a known-good
control group — plus a rolled-up **design-review** document for the C07 transfer package.

The whole stage is governed by one idea from `../../references/honesty-model.md` (read it first): a
tool run yields a **verdict**, not a certification. C06 converts evidence into `pass`/`warn`/`fail`
*only where a tool actually ran*; everything else stays `not-run` with a reason. It is the stage most
tempted to over-claim, so it is the stage with the strictest honesty contract.

What C06 does **not** own:

- It does **not** produce the artifacts it grades. The DRC report, SI report, length-match report,
  netlist, and the engine analysis run all come from C04/C03. C06 reads them; it does not re-route or
  re-net to make a verdict come out better.
- It does **not** certify compliance. FCC Part 15, CE RED, EN 55032 / CISPR 32, IEC 62368-1,
  RoHS/REACH, ESD — these are **external-lab gates**. C06 records the *target* and the *plan* and
  marks them owned-elsewhere; it **never** writes them `pass`.
- It does **not** sign off EVT/DVT or hardware bring-up. Those need a physical board that does not yet
  exist in this package. C06 writes the checklist; an engineer executes and signs it.
- It does **not** invent a measurement. A SPICE/EMC/thermal verdict exists only after the tool runs.
  Until then the check is `not-run` — an honest, expected state at this point in the lifecycle.

## Required deliverables — Definition of Done

Produce **all** of these into the stage's `03_output/` bucket before you report C06 done or hand off
(see SKILL.md § "Definition of Done"; debug overlays/scripts go in `02_build/`). Each exists **or**
carries an honest `not-run`/`blocked` status with a reason. A record where SPICE/EMC/thermal are
honestly `not-run` and only the cross-check is `pass` is a **legitimate done-state** — but every
required file must be present and the statuses must agree across files.

| # | Required artifact | File |
|---|---|---|
| 1 | Verification summary (machine-readable) | `Verification_Summary.json` |
| 2 | Test plan | `Test_Plan.md` |
| 3 | Bring-up checklist | `Bring_Up_Checklist.md` |
| 4 | Reference cross-check run | `analysis/<run>/cross_verify.json` (→ `02_build/`) |
| 5 | EVT bring-up findings | `EVT_Bringup_Findings.md` (when a board was actually brought up) |

**Self-verify:** run `bodesign_c06_readiness` (`folder`) and the cross-check; the summary's
pass/warn/fail must match the test plan and checkbox states verbatim (no checklist that is 1/8 done
sitting beside a "board was built" claim). Model: `thesmart_products/rockbox/c06-verify/`.

## Inputs (from upstream)

From **C04 (Layout)** — see `../c04-layout/GUIDE.md`, "Handoff to C06":
- The **DRC report** (`<board>.drc.rpt` / DRC JSON) — copper + unconnected counts are the hard-fail
  signal.
- The **SI report** (`<board>.si.json`) — per-net overshoot/settling `pass/warn/fail` from ngspice.
- The **length-match report** (`<board>.lengthmatch.json`) — `kept` / `within_budget` flags.
- The **engine analysis run** (`analysis/<run>/pcb.json`, plus `cross_analysis.json`) — the PCB
  implementation, with every finding's `confidence` + `evidence_source` preserved.

From **C03 (EE)** — see `../c03-ee/GUIDE.md`:
- The **reference netlist / baseline** — the verified connectivity that is your **control group** for
  the cross-check. In the aiguard example this is the reverse-engineered `269`-net baseline
  (`openmv/C03-EE/03_output/Reverse_Engineering_Report.md`); the schematic analysis JSON (`analysis/<run>/schematic.json`)
  carries the same nets in structured form.
- The **SI targets** named in C03 (USB 90 Ω diff, MIPI 100 Ω, XSPI 50 Ω …) — what the SI verdict is
  graded against.

From **C05 (FW)** — see `../c05-fw/GUIDE.md`:
- The **testable behaviours / pin map** (`Pin_Map_Bridge.json`) and PRD §7 operating modes — these
  become rows in the functional-smoke section of the bring-up checklist.

If any input is a documented upstream limit (e.g. C03 excluded a boot-ROM-configured bus for lack of
source data), carry that limit forward — do **not** invent a verdict for a net that was never claimed.

## SOP

C06 has an **engine layer** (`../../engines/kicad/`, read `ENGINE.md`) for the cross-check and the
structured readiness verdict, plus **companion sim skills** (`spice`, `emc`) for the analog/EMC
verdicts. Below, `K=../../engines/kicad/scripts`.

### 1. Gather the C04/C03 evidence and confirm what actually ran

Before assigning any verdict, list the artifacts that exist. A verdict is only as real as the tool
run behind it. Re-run the PCB and schematic analyzers if the C04 run folder is stale:

```bash
K=../../engines/kicad/scripts
python3 $K/analyze_schematic.py <design.kicad_sch> --analysis-dir analysis/
python3 $K/analyze_pcb.py <board.kicad_pcb> --full --analysis-dir analysis/
```

### 2. Run the reference cross-check against the control group

This is the heart of C06's "show reliability, don't assert it" duty (honesty rule 5).
`cross_verify.py` compares the **schematic design intent** against the **PCB implementation** and
reports component matching, diff-pair routing, power-trace, decoupling, bus routing, and (with a
thermal JSON) thermal-via checks:

```bash
python3 $K/cross_verify.py \
    --schematic analysis/<run>/schematic.json \
    --pcb        analysis/<run>/pcb.json \
    --output     analysis/<run>/cross_verify.json
```

The output's `component_matching` block is your control-group delta. Read it honestly and record
**both directions**:

- `matched` — how many refs in the schematic are placed in the PCB (this is your *shown* claim, e.g.
  "269/269 nets matched a known-good reference" in the aiguard example — net coverage from the C03
  baseline, not an adjective).
- `missing[]` — refs in the schematic but **not** placed on the board (`status: fail`). These are
  real gaps; list them, do not round them away.
- `orphans[]` — refs on the PCB with **no schematic source** (`status: fail`, "stale placement?").
  These are the *extras*. Report them as extras, not as silent matches.
- `value_mismatches[]` / `dnp_conflicts[]` — `warning`-level deltas worth surfacing.

The honest record is `269/269 matched, 0 missing, 0 orphans` **or** `267/269 matched, 2 missing
(U7, R31), 1 orphan (C99)` — whichever the tool actually returns. The cross-check verdict is `pass`
only when missing and orphan counts are zero; otherwise it is `warn`/`fail` with the deltas named.

> Why a control group: an internal consistency check ("schematic = PCB = analyzer") only proves the
> design agrees with itself. Cross-checking the *count and identity* of nets/components against the
> C03 verified baseline is what lets you *show* coverage instead of asserting "complete".

### 3. Run the structured fab-readiness verdict (optional but recommended)

`fab_release_gate.py` rolls all available analyzers into one `PASS`/`WARN`/`FAIL`/`INCOMPLETE`
verdict with per-check status and an evidence-trust posture (`--strict` promotes warns to fails):

```bash
python3 $K/fab_release_gate.py \
    --schematic analysis/<run>/schematic.json \
    --pcb        analysis/<run>/pcb.json \
    --gerbers    analysis/<run>/gerber.json \
    --text
```

Treat its verdict as evidence for the summary, not as a compliance claim — `overall_status:
INCOMPLETE` means a required input was absent, which is itself an honest finding.

### 4. Run the sim companions — only what is installed, and say which

Each of these is a separate `pass/warn/fail` *verdict*. None is a certification. **Before claiming a
verdict, prove the tool can run** — otherwise the check stays `not-run` with the reason recorded.

- **SPICE (analog subcircuits)** — check availability, then hand off to the `spice` skill with the
  schematic analysis JSON:
  ```bash
  which ngspice ltspice xyce        # ngspice is present in this environment
  ```
  If a simulator exists, SPICE is **runnable** → invoke `spice` and record its
  `simulation_results[].status` per subcircuit. If none exists, the check is `not-run`
  (reason: "no SPICE simulator installed").

- **EMC / EMI pre-compliance** — invoke the `emc` skill (available at `../../engines/emc`). It runs
  44 rule checks (ground plane, decoupling, switching harmonics, PDN, diff-pair skew, ESD, …) and
  produces a **risk** report + a pre-compliance **test plan**. This is a *risk verdict*, explicitly
  **not** an EN 55032 / CISPR pass — that remains an external-lab gate.
  ```bash
  python3 ../../engines/emc/scripts/analyze_emc.py \
      --schematic analysis/<run>/schematic.json --pcb analysis/<run>/pcb.json
  ```

- **Thermal** — the analysis script `analyze_thermal.py` lives **in the KiCad engine**
  (`$K/analyze_thermal.py`), but there is **no companion `thermal` skill** in this environment.
  Verify before relying on a richer thermal workflow:
  ```bash
  ls ../../engines/thermal 2>/dev/null || echo "no thermal companion skill"
  ```
  You can still run the engine's estimator for a Tj verdict:
  ```bash
  python3 $K/analyze_thermal.py \
      -s analysis/<run>/schematic.json -p analysis/<run>/pcb.json \
      --analysis-dir analysis/
  ```
  If you do not run it, the thermal check stays `not-run` (reason: "thermal estimation not executed;
  no companion thermal skill available") — record the boundary, do not fabricate a junction temp.

### 5. (Production-readiness input) Component lifecycle audit

`lifecycle_audit.py` is the **component-level** obsolescence + operating-temperature audit (LC-001
obsolete, LC-003 NRND, LT-001 temp violation, …). It is a verification *input*, not a stage gate — it
tells you whether the BOM you are about to certify is buildable. It needs network access and MPNs:

```bash
python3 $K/lifecycle_audit.py analysis/<run>/schematic.json --temp-range industrial
```

If there is no network or MPN coverage is thin, record "lifecycle audit not performed — [reason]"
rather than implying every part is active.

### 6. Assemble the four C06 deliverables

Author `Verification_Summary.json` (schema `bodesign.c06.verification_summary.v1`) as the
machine-readable source of truth, then derive `Test_Plan.md` and `Bring_Up_Checklist.md` from it.
Model them on the real example in `openmv/C06-Verification/`. The summary schema is the honesty
contract in data form:

```json
{
  "schema": "bodesign.c06.verification_summary.v1",
  "state": "drafted",
  "checks": [
    {"check": "simulate",   "title": "SPICE simulation (analog subcircuits)", "status": "not-run", "has_verdict": false},
    {"check": "emc",        "title": "EMC / EMI pre-compliance",              "status": "not-run", "has_verdict": false},
    {"check": "thermal",    "title": "Thermal analysis",                      "status": "not-run", "has_verdict": false},
    {"check": "crosscheck", "title": "Reference cross-check (control group)", "status": "pass",    "has_verdict": true}
  ],
  "certification_targets": ["FCC Part 15 …", "CE RED …", "EN 55032 / CISPR 32 …", "IEC 62368-1 …", "RoHS/REACH …", "ESD …"],
  "note": "C06 records verify-tool verdicts. Pass/warn/fail reflect tool output only; EVT/DVT and compliance certification are external-lab gates, never claimed here."
}
```

Rules for filling it:
- Every check carries **both** a `status` (`pass`/`warn`/`fail`/`not-run`) **and** `has_verdict`.
  `has_verdict: false` ⇔ `status: not-run`. A `pass` with `has_verdict: false` is a defect.
- A check is `not-run` until its tool genuinely executed — there is no shame in `not-run` at this
  stage; it is the truthful default.
- `certification_targets[]` lists the external gates as *targets*, each tagged owned-by-external-lab.
  Never give them a `pass` status; they are not `checks[]`.
- `state` is `drafted` until an owner reviews; promote to `reviewed` on sign-off (honesty rule 3).

### 7. Roll up the design-review document for C07

Generate the verification section of the design review with the kidoc engine
(`../../engines/kidoc/`), using the `design_review` report type:

```bash
python3 ../../engines/kidoc/scripts/kidoc_scaffold.py \
    --type design_review --analyze \
    --analysis-dir analysis/ --output C06_Design_Review.md
python3 ../../engines/kidoc/scripts/kidoc_generate.py C06_Design_Review.md   # -> styled PDF
```

The markdown is the human-editable source of truth; the PDF is generated. Preserve every finding's
`confidence` + `evidence_source` from the analyzers — do not launder them into bare assertions.

## Deliverables

Modelled on `openmv/C06-Verification/`.

| Artifact | File | Format / source-of-truth |
|----------|------|--------------------------|
| Verification summary | `Verification_Summary.json` | JSON, schema `…v1` — **machine-readable source of truth** |
| Test plan | `Test_Plan.md` | markdown source, derived from the summary |
| Bring-up checklist | `Bring_Up_Checklist.md` | markdown source, engineer-executed |
| Reference cross-check | `analysis/<run>/cross_verify.json` | generated (control-group delta evidence) |
| Design-review doc | `C06_Design_Review.md` (+ `.pdf`) | markdown source-of-truth; PDF generated |
| Supporting engine run | `analysis/<run>/{schematic,pcb,cross_verify,gerber}.json` | generated, expensive, keep but don't commit |

The summary/test-plan/checklist are hand-editable source; the JSON analysis runs and the PDF are
regenerable.

## Gate / done-criteria

C06 is genuinely complete when **all four** hold:

1. **Reference cross-check ran and its delta is recorded** — `matched`, `missing[]`, `orphans[]` all
   reported. A `pass` requires `0 missing, 0 orphans`; otherwise the cross-check check is `warn`/`fail`
   with the named deltas. This is the one check that is normally `pass` at C06 because it grades
   already-existing artifacts.
2. **Every sim check has an honest status** — each of `simulate`/`emc`/`thermal` is either a real
   `pass/warn/fail` (tool ran) **or** `not-run` with a reason. No blanks, no optimistic defaults.
3. **The summary's invariant holds** — `status: not-run` ⇔ `has_verdict: false` for every check; no
   external gate appears in `checks[]`; `certification_targets[]` are all owned-by-external-lab.
4. **The test plan + bring-up checklist exist** and reflect the summary status verbatim (a check that
   is `not-run` in the summary is `not-run` in the plan and unchecked in the checklist).

A C06 record where SPICE/EMC/thermal are honestly `not-run` and only the cross-check is `pass` is a
**legitimate done-state for this point in the lifecycle** — exactly what the aiguard example ships.
What is *not* done: any compliance/EVT/DVT row marked passed, or a sim verdict with no tool run behind
it.

## Honesty notes for this stage

Direct applications of `../../references/honesty-model.md`:

- **Verdicts ≠ certification** (rules 1, 4 + the C06 paragraph there): tool runs produce
  `pass/warn/fail`; FCC/CE/EN 55032/IEC 62368-1/RoHS/ESD and EVT/DVT are **external gates, never marked
  passed**. They live in `certification_targets[]`, not `checks[]`.
- **Mark the unproven, with a reason** (rule 3): `not-run` is the truthful default for any tool that
  did not execute. Always attach the reason (`no simulator`, `no thermal companion skill`, `no
  network for lifecycle audit`). A status without a reason is itself a defect; `has_verdict: false`
  enforces this in the schema.
- **Show reliability, don't assert it** (rule 5): the cross-check exists to *show* coverage —
  "269/269 nets matched the C03 control group" — and to report *extras* (`orphans`) and *missing*
  honestly. Never replace the delta with "robust" or "production-ready".
- **State provenance** (rule 2): keep the analyzers' `confidence` + `evidence_source` on every finding
  that flows into the review; cite the C03 baseline by path as the control group.
- **Honest boundaries** (rule 6): the **thermal companion skill is missing** in this environment —
  document it as a tool-availability limit and leave the check `not-run`; do not back-fill a junction
  temperature you did not compute. If an upstream bus was excluded in C03, it stays out of the verdict.

## Feedback to the design stages — a failing verdict is routed, not just reported

A `warn`/`fail` verdict with a **design owner** is the *backward* half of the co-design loop
(`../../references/cross-stage-reconciliation.md` § "Two trigger directions"). C06 does not fix it —
it doesn't own the artifact — but it must not let the fail die as a line in a report either. **Emit a
reconciliation record** routing the fail to the stage that owns the lever:

- **SI** overshoot/settling `fail` → `must_act: C04` (re-route / stackup) and/or `C03` (the SI
  requirement / part). · **EMC** margin → `C04`/`C03`. · **DRC** copper+unconnected → `C04`. ·
  **thermal** verdict → the existing `thermal` record (C02/C04/C03).

The hard rule (the floating-PSRAM lesson, and C06's own non-ownership): the `must_act` stage resolves
by **fixing the design**, and C06 **never** relaxes a threshold or rewrites a verdict to make it pass.
An `open` verify-initiated record blocks the C07 transfer the same way an unverified claim does — C07
carries it through as "open, routed to <stage>", not as resolved.

## Handoff to C07 (MFG)

To **C07 (`../c07-mfg/GUIDE.md`)** export the **verification evidence bundle** for the transfer
package: `Verification_Summary.json` (the authoritative status), `Test_Plan.md`,
`Bring_Up_Checklist.md`, the `cross_verify.json` control-group delta, and the `C06_Design_Review.md`/
PDF. C07 attaches these as the "what we verified, what is still open" section of the manufacturing
transfer — and it must carry the `not-run`/external-gate statuses through unchanged. C07 also consumes
the lifecycle audit as a buildability input. C07 turns *pending-against-freeze* fab outputs into an
order; the verification evidence tells the recipient exactly which claims are tool-backed and which
remain owned by an external lab or a future EVT/DVT build.

## Tools & companion skills

- **KiCad analysis engine** — `../../engines/kicad/` (`ENGINE.md`). Key: `cross_verify.py`
  (schematic-intent ↔ PCB implementation control-group check — the C06 reliability evidence),
  `fab_release_gate.py` (structured `PASS/WARN/FAIL/INCOMPLETE` readiness verdict; `--strict`),
  `analyze_thermal.py` (Tj estimator — engine-side, no companion skill), `lifecycle_audit.py`
  (component obsolescence/temp audit — production-readiness input, **not** a stage gate),
  `analyze_schematic.py` / `analyze_pcb.py --full` (refresh stale C04 runs),
  `summarize_findings.py`, `diff_analysis.py` (delta vs a prior review).
- **`spice`** (companion skill, present; `ngspice` installed) — analog subcircuit simulation
  verdicts. Required *when a simulator is installed*; hand off the schematic analysis JSON.
- **`emc`** (companion skill at `../../engines/emc`, present) — 44-rule EMC pre-compliance **risk**
  verdict + test plan. A risk verdict only; EN 55032/CISPR remain external-lab.
- **`thermal`** — **NOT available** as a companion skill in this environment (verify with
  `ls ../../engines/thermal`). Use the engine's `analyze_thermal.py` for a Tj estimate, or leave the
  thermal check `not-run` with the availability reason.
- **`kidoc`** (`../../engines/kidoc/`) — `kidoc_scaffold.py --type design_review --analyze` →
  `kidoc_generate.py` for the rolled-up verification design-review doc + PDF.
- **`docx` / `pdf` / `xlsx` + `docxmcp` MCP** — for any document-formatted test plan / review export.
