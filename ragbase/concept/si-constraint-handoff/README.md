---
slug: concept/si-constraint-handoff
title: SI constraint handoff — the Tier-3 routing-wall handoff
layer: ragbase
type: concept
confidence: verified
---
# SI constraint handoff — the Tier-3 routing-wall handoff

For a **Tier-3** product (HDI / ≤0.4 mm BGA / DDR/RF), C04 does **not** route on KiCad + the MCP. Instead of a half-routed dead-end it emits the complete **SI constraint set** as a neutral package a pro EDA tool (Allegro/Xpedition/Altium) + a human SI engineer picks up — the wall becomes a seamless handoff. Run `emit_si_constraint_export(...)`.

Produces at the stage root: `SI_Constraint_Export.json` (source of truth — stackup target + every net-class constraint + placement intent + keepouts + explicit `tbd[]`), `SI_Net_Classes.csv` (EDA tools import directly: class/kind/Z0/tol/match-group/max-len/topology/termination), `SI_Constraint_Handoff.md` (stackup, net-class summary, **per-tool import mapping**, what is TBD). A constraint bodesign didn't derive stays `null` under `tbd[]` — never a guessed impedance. The handoff IS the Tier-3 deliverable — make it whole. This is the highest-leverage way to raise the completion fraction on hard products, since Tier-3 is bounded by C04 routability, not C03 method.

## Source evidence

- `distilled_from` → [[extract/asset/home/pkcs12/projects/bodesign/skills/bodesign/references/si/constraint/handoff/md/text|text: asset.home.pkcs12.projects.bodesign.skills.bodesign.references.si.constraint.handoff.md]] @ si-constraint-handoff.md: Tier-3 export, constraint model, per-tool import — source_weight 6

## Related

- → `constrains` [[workflow/c04-layout|C04 Layout — verified netlist → DRC-clean, gated, fab-ready board]]

