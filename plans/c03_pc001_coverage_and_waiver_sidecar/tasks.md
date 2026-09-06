# Tasks: c03_pc001_coverage_and_waiver_sidecar

> **Every `- [x]` must name a machine-verifiable artifact.** Ticking a box is a
> claim made by whoever ticked it; it carries no evidence on its own. Close each
> task with an `artifact:` field so the gate can check the claim.

## Provenance

Tasks 2.7 and 2.8 below were **moved verbatim** out of
`plans/c03_delivery_contract_and_engine_seams/tasks.md` (lines 56–57) on 2026-09-06,
so that the parent package could reach `verified` without carrying an open task.
The numbering is preserved deliberately: it keeps the parent's WP2 references
resolvable. **The text is byte-identical to the source; nothing was summarized.**

> ⚠ The final sentence of 2.8 is a **seal**, not commentary:
> *"Until this runs, PC-001's real coverage on this board is 9/16, NOT 16/16, and no
> statement to the contrary may be made."*
> The parent package's `verified` state does not lift it. It is lifted only by
> completing 2.8 with a per-ref measurement.

## 1. WP2 residue — PC-001 coverage and the waiver sidecar

- [ ] 2.7 Port the DD-3 waiver sidecar (`passive_waivers.json`) to the delivery path. NOT done in this pass: the relocated rule reports `passive_completeness.waivers.status == "not_run"` with the reason that no waiver can be honoured here, so a caller is told rather than left to discover that a well-provenanced waiver was ignored. Until this lands, a legitimately-waived gap blocks C04 entry — which is the safe direction, but it is a behaviour difference from the skill-side detector and must not stay undeclared. Scope note: the skill-side copy at `validation_detectors.py:1261` is the P2 INTERNAL-TOOL copy under DD-01 — the two criteria may drift (they already do: `comp.type == 'ic'` there vs a `U*` refdes-prefix proxy here) and are deliberately NOT kept in sync. Only the delivery-path copy governs a C03 verdict. — artifact: `packages/workflow-core/bodesign_workflow_core/check_c03.py`
- [ ] 2.8 Diagnose the 7 ICs that PC-001 did NOT cover on the aiguard board (`U9`, `U10`, `U11`, `U12`, `U_EE`, `U_IMU`, `U_S`, measured 2026-09-06 on `experiments/aiguard_c03_verify/ccm.net`: `rails_checked=12`, 9 of 16 `U*` parts examined). They are named in `ics_without_identifiable_rail`, which states they were NOT looked at — it does not say why, and the two possible causes need OPPOSITE fixes: (a) the netlist carries no `pinfunction` on their supply pins — an upstream/export problem; the fix is in whatever produced the netlist, and no change to `_ic_power_rails` would help; (b) the pins ARE annotated but their net name does not satisfy `_polarity_of(net) == "power"` — the rail predicate is too narrow, and the fix is in `check_c03.py` (`_PWR_PREFIXES` / `_PWR_PATTERN:127-129`). Deciding between them is a per-ref measurement, not a judgement call: dump `_netlist_pin_functions()[ref]` and the net each supply pin sits on. Until this runs, PC-001's real coverage on this board is 9/16, NOT 16/16, and no statement to the contrary may be made. — artifact: none (measurement; fix location depends on the answer)
