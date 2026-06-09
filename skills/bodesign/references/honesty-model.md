# bodesign honesty & provenance model

This is the soul of bodesign. A design package has value only because a reader can **trust** it.
Every stage guide assumes these rules; they override convenience, deadlines, and the urge to make
a deliverable look finished.

## The seven rules

1. **Never fabricate.** Do not invent an approval, a test verdict, a measurement, a fab output, a
   certification, a build that did not happen, or a pin/net/value you have not derived from a real
   source. A truthful "pending" always beats a false "complete".

2. **State provenance.** Every non-trivial fact should be traceable to its source: a datasheet
   (with page/section), a published reference (glb/pinout/firmware), an extracted netlist, or a
   tool run. The KiCad engine attaches a `confidence` label + `evidence` source to every finding
   for exactly this reason — preserve that, don't launder it into bare assertions.

3. **Mark the unproven.** Use an explicit status vocabulary and *say why*:
   `draft` (authored, not reviewed) · `pending` (blocked on a named upstream gate) ·
   `not-run` (a tool/lab step that was never executed) · `assumption` (a stand-in to be confirmed).
   A status without a reason is itself a defect.

4. **External gates stay external.** EVT/DVT, FCC Part 15, CE RED, CISPR/EN 55032, IEC 62368-1,
   RoHS/REACH, ESD — these are decided by an external lab or a physical build. bodesign records the
   *target* and the *plan*; it **never** marks them passed. The same holds for any verdict that
   needs hardware that does not yet exist.

5. **Show reliability, don't assert it.** Prefer evidence over adjectives. "269/269 nets matched a
   known-good reference (control group)" is a *shown* claim; "robust, production-ready design" is an
   empty one. When you can cross-check against a control group, do — and report the delta honestly,
   including what is an *extra* and what is *missing*.

6. **Document honest boundaries; exclude rather than guess.** When source data is missing (no
   schematic/CAD available, a bus configured by boot-ROM and absent from public firmware), record it
   as a **source-data limit** in the appropriate stage artifact and **leave it out** — do not
   back-fill with a plausible guess. A documented gap is a finding; a fabricated fill is a lie.

7. **Respect provenance vaults.** Proprietary / borrowed source material lives in gitignored vaults
   (e.g. `refs/`). Never commit it. Derived companions must be your own generation, not a copy of
   borrowed source. When a track is *preserve-only* (archival reorganisation of a real design), copy
   originals verbatim and never mutate them — your companions sit alongside and explain them.

## How this shows up per stage

- **C00–C02, C05** (PRD/ID/ME/FW spec): requirements and specs are `draft` until a named owner
  signs off. Open approvals stay *visible*, not silently resolved.
- **C03 (EE):** every value/net carries provenance; missing connectivity is a documented limit, not
  an invented net. Reverse-engineered baselines are labelled as such.
- **C04 (Layout):** the layout is a **draft** until DRC-clean and gate-passed; fab outputs are not
  "released" until the board is frozen. Do not relax a gate threshold to make a board "pass" — fix
  the board or report the warning. (See the C04 guide's gate contract.)
- **C06 (Verify):** tool runs produce `pass/warn/fail` *verdicts only*; SPICE/EMC/thermal are
  `not-run` until actually executed. Compliance is never claimed here.
- **C07 (MFG):** pre-fabrication readiness, not a record of a built board. Every fab deliverable is
  `pending` against the C04-freeze gate that owns it until it genuinely exists.

## The litmus test

Before writing any status better than the evidence supports, ask: *"If the reader fabricated the
board tomorrow and checked this claim, would it hold?"* If you cannot answer yes from a real source,
downgrade the claim and name what is missing.
