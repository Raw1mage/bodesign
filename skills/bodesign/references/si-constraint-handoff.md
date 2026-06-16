# SI constraint handoff — turning the C04 routing wall into a clean handoff

For a **Tier-3** product (`feasibility-triage.md`: HDI / ≤0.4 mm BGA / DDR/RF), C04 does **not** route
on KiCad + the MCP. Instead of a half-routed dead-end, it emits the complete **SI constraint set** as
a neutral package a professional EDA tool (Allegro / Xpedition / Altium) + a human SI engineer picks
up. The wall becomes a *seamless handoff*: bodesign did the design thinking; the receiving flow does
the copper.

Run it as code: `emit_si_constraint_export(...)` in `bodesign_workflow_core.si_handoff`.

## What it produces (at the stage root)

| File | Role |
|---|---|
| `SI_Constraint_Export.json` (`bodesign.si_constraints.v1`) | **source of truth** — stackup target + every net-class constraint + placement intent + keepouts + an explicit `tbd[]` |
| `SI_Net_Classes.csv` | the net-class table EDA tools **import directly** (class · kind · Z0 · tol · match-group · max-len · topology · termination) |
| `SI_Constraint_Handoff.md` | the human handoff — stackup, net-class summary, **per-tool import mapping**, and what is TBD |

## The constraint model

- **`StackupSpec`** — layers, HDI type (IPC-2226), finest BGA pitch, via-in-pad, per-layer map
  (type / reference plane / dielectric / copper / target Z0).
- **`NetClassConstraint`** per class — `kind` (single-ended/differential), `target_impedance_ohm` +
  `impedance_tol_pct`, `diff_skew_ps`, `length_match_group` + `length_match_tol_mm`, `max_length_mm`,
  `topology` (point-to-point / multi-drop / fly-by), `termination`, `routing_layers`, `return_path`.

These come straight from C03's SI requirements (`ee-design-advisory.md` § SI) + C04's stackup/floorplan
decisions (`stackup-and-placement.md`). The point of the package is that **bodesign already computed
all of this** — the only thing it can't do is push the copper.

## Honesty — no fabricated constraints

A constraint bodesign did not derive stays `null` and is listed under **`tbd[]`** (e.g. a missing
differential skew, an un-decided stackup). The receiving engineer is told exactly what is specified
vs what they must still decide — never a guessed impedance or length to make the package look complete
(honesty rule 6). The package's `authority` line states plainly that routing, final impedance
realisation, and SI sign-off belong to the receiving flow, not to bodesign.

## Per-tool import (in the Markdown)

- **Cadence Allegro** — Constraint Manager → Electrical CSets (impedance + matched-length groups);
  assign nets to the CSet named by `net_class`.
- **Siemens Xpedition** — Constraint Manager → Net Classes + Differential Pairs; impedance rule +
  Match group.
- **Altium Designer** — xSignals (length/match) + Net Classes/Design Rules (impedance); import the CSV.

## Why this is the highest-leverage handoff

Tier-3 is bounded by C04 **routability**, not C03 design method. So the clean way to raise the
bodesign-completion fraction on hard products is exactly this: hand the receiving flow a complete,
machine-readable constraint set so the human SI engineer starts from bodesign's design intent instead
of re-deriving it. The handoff is the product for Tier 3 — make it whole.
