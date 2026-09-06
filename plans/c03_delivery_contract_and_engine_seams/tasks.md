# Tasks: c03_delivery_contract_and_engine_seams

> **Every `- [x]` must name a machine-verifiable artifact.** Ticking a box is a
> claim made by whoever ticked it; it carries no evidence on its own. Close each
> task with an `artifact:` field so the gate can check the claim.
>
> **The `artifact:` clause must sit on the checkbox line itself**, not on a
> continuation line. `ARTIFACT_RE` (`task-artifact.ts:36`) is matched against
> `CHECKBOX_RE`'s `m[4]` (`checkbox-grammar.ts:57,96`) — a single physical line —
> so a wrapped annotation is invisible to the gate and the task reads as
> unverifiable. Migrated 2026-09-06 (round 9): 57/57 entries moved onto the
> checkbox line.
>
> **`plan-validate` artifact probe: `indeterminate` in this repo — NOT a pass.**
> `findRepoRoot` (`task-artifact.ts:121-130`) requires an ancestor holding BOTH
> `.git` AND `package.json`; bodesign has no `package.json`, so `repoRoot` is
> `undefined` and every path claim returns `unverifiable` → `indeterminate`
> regardless of whether the file exists. Measured: a real path and a fabricated
> one returned byte-identical verdicts. The gate therefore cannot enforce the
> "no fake paths" rule here — the paths above were verified against the
> filesystem by hand instead. See
> `specbase/issues/BR_20260906_task_artifact_gate_findRepoRoot_requires_package_json_so_real_and_bogus_paths_share_indeterminate.md`.

Execution order is the user ruling of 2026-09-06: WP1 → WP2 → WP3 → WP4 → WP5 →
WP6. WP6 is deliberately last: BR_20260905 §8.5.2 measured a change that improved
every geometric criterion while wiring an open circuit, so a readability gate
built before the electrical gate would have passed it.

Each WP carries a **positive control** (must be non-empty / green after the work)
and a **negative control** (must be RED before the work, or must go red when the
mechanism is disabled). A negative control that cannot fail is not a control.

## 1. WP1 — C03 delivery contract rewrite (`GUIDE.md`)

- [x] 1.1 Rewrite deliverable table rows 3/5/7 (`GUIDE.md:40,42,44`) so the frozen netlist is the electrical deliverable and the docx is named as its projection; the schematic row points at the netlist as its export target. — artifact: `skills/bodesign/stages/c03-ee/GUIDE.md`
- [x] 1.2 Add a `Netlist freeze rule (MANDATORY)` section stating the file shape and location from DD-05: `<stage>/C03_<product>.net` plus `<stage>/C03_Netlist_Freeze.json` carrying, per emitted `.net`, `sha256`, `nets_parsed`, emitting revision, and the `bodesign_verify_netlist_fidelity` verdict; both tracked in version control. — artifact: `skills/bodesign/stages/c03-ee/GUIDE.md`
- [x] 1.3 Narrow the `02_build/` out-of-scope clause at `GUIDE.md:447-450` to exclude build/intermediate artifacts **except** the two promoted freeze artifacts named in 1.2; the `C03_` prefix rule is unchanged and the promoted copies carry it. — artifact: `skills/bodesign/stages/c03-ee/GUIDE.md:447`
- [x] 1.4 Move MANDATORY placement: the netlist freeze section (1.2) and the existing Vault-Absent Substitution Protocol (`:199`) carry MANDATORY; the document-consolidation section (`:399`) is retitled `Document consolidation rule (reference)` and loses the marker; the file-naming rule (`:437`) keeps it. — artifact: `skills/bodesign/stages/c03-ee/GUIDE.md:399`
- [x] 1.5 Demote the docx row `GUIDE.md:396` from bold to plain and change its Notes column to name the netlist it projects; the 37-line docx production detail at `:399-435` stays in the file as reference material, unbolded and unmarked. — artifact: `skills/bodesign/stages/c03-ee/GUIDE.md:396`
- [x] 1.6 Add the frozen netlist and the freeze JSON to the Gate / done-criteria list (`:454-494`), each with the "report absent = gate has not run, never presume PASS" wording already used for the two report JSONs. — artifact: `skills/bodesign/stages/c03-ee/GUIDE.md:454`
- [x] 1.7 POSITIVE CONTROL: count MANDATORY markers within the netlist-freeze section — must be `>= 1`. Question answered: *does the rewritten GUIDE mark the netlist as mandatory at all?*. — artifact: none (measurement recorded in the WP1 handoff note)
- [x] 1.8 NEGATIVE CONTROL: enumerate the bolded rows of the deliverables table; the assertion is that `.docx` is **not** the only bolded row. This control is RED on the current file — measured today, `:396` is the single bolded row, so the check fails before the work and can only pass after it. — artifact: none (measurement recorded in the WP1 handoff note)
- [x] 1.9 State in the WP1 handoff note that `skills/` changes reach consumers via `opencode skill resync bodesign --accept-source` and **not** via `mcpctl.sh rebuild` (AGENTS.md §3.2); run `opencode skill status bodesign` (read-only) and record the reported state. — artifact: none (deployment-path note only — see DD-01)

## 2. WP2 — pipeline adjudication landed + migration list

- [x] 2.1 Write DD-01 into `specs/architecture.md` as a decision paragraph: P1 (`composer.py`→`kicad_emit.py`→`fidelity.py`) is the C03 delivery path; P2 (`symbol_4edge` / `host_from_pinmap` / `netlist_to_kicad_sch` / `render_hybrid_sch`) is an internal tool. State the consequence: new C03 quality rules and gates attach to P1 only. — artifact: `specs/architecture.md`
- [x] 2.2 Land the DD-08 ruling (already adjudicated, not open): PC-001 relocates to `packages/workflow-core/bodesign_workflow_core/check_c03.py` as a new rule alongside R7. The `specs/architecture.md:101` veto ("BOM CSV, cannot see whether a cap is *connected* to a rail") was true at PC-001's design time and is measurably false now: `_netlist_pin_nets:621` yields `{ref:{pin:net}}`, `_netlist_pin_functions:764` yields `{ref:{pin:pinfunction}}`, `_polarity_of:651` classifies a net as gnd/power, `_nets_to_refs:793` inverts, and R7 `_check_mandated_passives:924-934` already composes them into the rail walk PC-001 needs. Write the superseding note INTO `:101` so the stale premise is not left standing beside its reversal. — artifact: `specs/architecture.md`
- [x] 2.3 Write the PC-001 migration item: the detector logic moves from `skills/bodesign/engines/kicad/scripts/validation_detectors.py` to the adjudicated destination; the source stays in place for P2 callers and is marked as the internal-tool copy; the `_NOT_CHECKED_BASE` entry for decoupling adequacy is updated to reflect that a rule now covers it, using the conditional wording the file already uses for R7/R8 (an unrun rule must stay listed rather than drop out) — artifact: `specs/architecture.md`
- [x] 2.3b Update `_NOT_CHECKED_BASE:1010` `decoupling_adequacy` to the conditional form `_build_not_checked:1024` already uses for R7/R8: when the relocated PC-001 did not run (no netlist, no identifiable power pin), the class stays listed with its reason; only a rule that actually ran may remove its entry. Dropping the entry unconditionally would make "covered" and "never examined" the same output — the defect `_NOT_CHECKED_BASE` exists to prevent. — artifact: `packages/workflow-core/bodesign_workflow_core/check_c03.py`
- [x] 2.4 Assign each of the 8 rules in `skills/bodesign/stages/c03-ee/references/schematic-drawing-rules.md` an owner under DD-01, one row per rule: R1 tool choice → P2-internal (names P2's own render chain, no P1 equivalent); R2 4-edge symbols → P1 composer/symbol contract (`kicad_symbol.py` derives per-edge pitch constructively); R3 draw the MCU body → P2-internal (consumes `Pin_Allocation.csv`, a P2 input); R4 hybrid connection style → **P1 composer contract** — this is the rule BR_20260905's label-farm symptom violates, and it currently governs P2 only; R5 label everything → P1 emit contract; R6 one extent model → P1, already implemented (scale-coherence closed form, `specs/architecture.md:95`); R7 KiCad validity gotchas → P1 emit contract; R8 discipline (generation ≠ correctness) → stage contract, WP1. Rules routed to a measurable form criterion (R4, R5) are WP6 inputs; the rest are contract statements. — artifact: `specs/architecture.md`
- [x] 2.5 Criterion A *(rewritten 2026-09-06: original string-grep had no discriminating power — a docstring mention would pass it)*. The question is not *does the string `PC-001` appear under `packages/`* but *does the delivery path REJECT a board the rule exists to reject?* A relocated detector is proven reachable only by a verdict that changes with the defect, so the criterion is the 2.5a/2.5b pair below, run through `check_c03()` itself rather than against the detector function — the seam being tested is the call site, and calling the function directly would pass even if nothing in the delivery path ever invoked it. — artifact: `tests/test_check_c03_passive_completeness.py`
- [x] 2.5a POSITIVE CONTROL: a fixture with an active IC on a power rail and NO rail→GND capacitor yields `gate == "FAIL"` with a blocking finding whose code is `PC-001` and whose ref is the IC. Question answered: *does the delivery path fail an undecoupled board?*. — artifact: `tests/test_check_c03_passive_completeness.py`
- [x] 2.5b NEGATIVE CONTROL: the byte-identical fixture plus one decoupling cap yields no `PC-001` finding, AND every other finding is literally unchanged (compared as a sorted `(code, ref, detail)` list). The second half is load-bearing: a rule that silenced PC-001 by breaking R1–R8 would pass the first half alone. Question answered: *does the verdict track the defect, or does the rule just always fire?*. — artifact: `tests/test_check_c03_passive_completeness.py`
- [x] 2.6 NEGATIVE CONTROL: the same grep on today's tree returns **zero** files while the control grep on `skills/` returns 3 — measured 2026-09-06, so the check is red before the work and its discriminating power is shown by the paired control rather than assumed. — artifact: none (measurement recorded in WP2 handoff)
- [ ] 2.7 Port the DD-3 waiver sidecar (`passive_waivers.json`) to the delivery path. NOT done in this pass: the relocated rule reports `passive_completeness.waivers.status == "not_run"` with the reason that no waiver can be honoured here, so a caller is told rather than left to discover that a well-provenanced waiver was ignored. Until this lands, a legitimately-waived gap blocks C04 entry — which is the safe direction, but it is a behaviour difference from the skill-side detector and must not stay undeclared. Scope note: the skill-side copy at `validation_detectors.py:1261` is the P2 INTERNAL-TOOL copy under DD-01 — the two criteria may drift (they already do: `comp.type == 'ic'` there vs a `U*` refdes-prefix proxy here) and are deliberately NOT kept in sync. Only the delivery-path copy governs a C03 verdict. — artifact: `packages/workflow-core/bodesign_workflow_core/check_c03.py`
- [ ] 2.8 Diagnose the 7 ICs that PC-001 did NOT cover on the aiguard board (`U9`, `U10`, `U11`, `U12`, `U_EE`, `U_IMU`, `U_S`, measured 2026-09-06 on `experiments/aiguard_c03_verify/ccm.net`: `rails_checked=12`, 9 of 16 `U*` parts examined). They are named in `ics_without_identifiable_rail`, which states they were NOT looked at — it does not say why, and the two possible causes need OPPOSITE fixes: (a) the netlist carries no `pinfunction` on their supply pins — an upstream/export problem; the fix is in whatever produced the netlist, and no change to `_ic_power_rails` would help; (b) the pins ARE annotated but their net name does not satisfy `_polarity_of(net) == "power"` — the rail predicate is too narrow, and the fix is in `check_c03.py` (`_PWR_PREFIXES` / `_PWR_PATTERN:127-129`). Deciding between them is a per-ref measurement, not a judgement call: dump `_netlist_pin_functions()[ref]` and the net each supply pin sits on. Until this runs, PC-001's real coverage on this board is 9/16, NOT 16/16, and no statement to the contrary may be made. — artifact: none (measurement; fix location depends on the answer)

## 3. WP3 — projection carries an executable body

- [x] 3.1 Record DD-03 in the WP3 design note: `mcp.json:14-16` declares `skillPaths: ["skills"]`, and `skills/bodesign/packages` does not exist in the repo (rc=1; control `packages/` at repo root rc=0), so `packages/` is outside the projection unit rather than excluded from a list. Option (a) is therefore not implementable as stated. — artifact: `specs/architecture.md`
- [x] 3.2 Implement DD-04 in `_resolve_src()`: try a literal enumerated candidate list; accept a candidate only if `<candidate>/packages/workflow-core` exists; report the accepted one in `packages_root`. TWO DEVIATIONS from the task text as written, both deliberate: (i) ORDER — candidates are tried BEFORE the walk-up, not after. The walk-up starts at `gate.py`'s own directory, so in the published install it can only ever fail; putting it first buys nothing and makes the ordering harder to reason about. In-tree runs are unaffected: the repo root IS the first candidate, so it answers either way (`packages_origin` reports which, so the two are no longer the same output). (ii) An explicitly-set `$BODESIGN_SRC` that lacks `packages/workflow-core` now raises IMMEDIATELY rather than falling through to the candidates. Falling through would make an operator's typo indistinguishable from a correct setting while running the roster against a tree nobody named. `tests/test_landing_gate.py:68` already required this behaviour. — artifact: `skills/bodesign/scripts/gate.py:74`
- [x] 3.3 Keep the failure path typed and unchanged in shape: no candidate matches ⇒ `packages_resolved=false` plus the existing `code`/`message`/`hint`/`impact` object; no filesystem search, no partial import, no default root. — artifact: `skills/bodesign/scripts/gate.py:99`
- [x] 3.4 Make every roster verb report `not-run` rather than `ok` when `packages_resolved=false`: the per-verb dispatch path returns a typed not-run status carrying the same `packages_error`, so "the verb did nothing" and "the verb ran and found nothing" stop sharing an output. Implemented as an ADDITIVE `status` field on the envelope (`ok`/`failed`/`not-run`); `ok`, `error.code`, `error.message` and `error.hint` keep their existing shape, so no existing caller or test changes behaviour. Resolution now has its own `try` block in `main()` — only that failure is `not-run`; a verb that was reachable and refused (e.g. `VERB_NOT_LANDING`) stays `failed`, which is what gives the field discriminating power rather than one constant value. — artifact: `skills/bodesign/scripts/gate.py`
- [x] 3.5 POSITIVE CONTROL: from a scratch copy of `skills/bodesign/scripts/` standing OUTSIDE the repo (no `packages/` anywhere above it — asserted, not assumed, by walking every ancestor in `setUp`) with `BODESIGN_SRC` unset, the roster resolves via `packages_origin == "candidate:…"` and a verb pair actually executes (`c00_scaffold_prd` → `c00_readiness`), with every file the envelope claims verified on disk. Question answered: *can a consumer holding only the projected skill execute the verb the GUIDE tells them to run?* Running the module from its in-tree path would NOT answer it — the walk-up succeeds there regardless of the candidate list. — artifact: `tests/test_landing_gate_published_resolution.py`
- [x] 3.6 NEGATIVE CONTROL: force `packages_resolved=false` (point every candidate at a directory with no `packages/workflow-core`) and assert that **every** verb in the roster returns `not-run`, and specifically that none returns `ok`. Asserted over the WHOLE roster, not a sample, because the claim is universal. Paired with a REVERSE CONTROL (`emit_fab` ⇒ `status == "failed"`) so the field is shown to take more than one value — a status hard-coded to `not-run` would satisfy the main assertion and measure nothing. — artifact: `tests/test_landing_gate_published_resolution.py`
- [x] 3.7 Re-derive the candidate list in a test rather than restating it (the V4-c hand-written-list shape, `specs/architecture.md:75`); a candidate path that does not exist on the running host is skipped and does not alter the reported error. Three assertions: candidates are literal absolute paths with no glob metacharacters; prepending a dead path leaves `packages_root` unchanged; a candidate that EXISTS but lacks `packages/workflow-core` is rejected (otherwise the acceptance predicate is not actually applied) — artifact: `tests/test_landing_gate_published_resolution.py`

## 4. WP4 — `bodesign_verify_netlist_fidelity`

- [x] 4.1 Add the `.net` adapter in `fidelity.py`: a function taking `emitted: list[Path]`, calling `parse_net_file` (`:181`) per file, merging classes that share a node across sheets by union-find (same-name nets on different sheets are one net), returning `(classes, nets_parsed)` where `nets_parsed` counts the `(net ...)` blocks actually parsed. — artifact: `packages/eda-bridge/bodesign_eda_bridge/fidelity.py:181`
- [x] 4.2 Read failure is not swallowed: an unreadable or unparseable `emitted` path is collected into a named list, never `continue`d past — the `:216-221` shape is not reproduced in the new adapter. — artifact: `packages/eda-bridge/bodesign_eda_bridge/fidelity.py:216`
- [x] 4.3 Add `nc_wired` computation: for each `[ref,pin]` in `nc_declared`, if the emitted partition places it in a class with any peer, it lands in `nc_wired` and is **excluded** from `fused`. Today `fidelity.py` has zero occurrences of `nc_`/`no_connect` (control: 8 in `kicad_emit.py`), so a wired NC and a real short share one output. — artifact: `packages/eda-bridge/bodesign_eda_bridge/fidelity.py`
- [x] 4.4 Split the report into the four independent fields the verb contract names: `fused` (gained peers only, NC-excluded), `split` (lost peers only — the `disconnected` list under its contract name), `node_diff` `{spec_only, emitted_only}`, `nc_wired` — artifact: `packages/eda-bridge/bodesign_eda_bridge/fidelity.py:380`
- [x] 4.5 Implement DD-06 status resolution: `nets_parsed == 0` **or** any `emitted` path unreadable ⇒ `status="indeterminate"`, set before any comparison runs; otherwise `ok` when all four difference fields are empty, `failed` when any is non-empty; `not-run` when a precondition (missing `spec`, empty `emitted` list) means no comparison was attempted. — artifact: `packages/eda-bridge/bodesign_eda_bridge/fidelity.py`
- [x] 4.6 Register the handler in `services/mcp/server.py` — artifact: `services/mcp/server.py`
- [x] 4.7 Register the schema in `services/mcp/server.py` with inner field descriptions for `spec` (`{net: [[ref,pin],…]}`), `emitted` (list of `.net` paths, cross-sheet same-name nets merged) and `nc_declared` (`[[ref,pin],…]`); the description states that `status` is never `ok` when `nets_parsed == 0` — artifact: `services/mcp/server.py:1133`
- [x] 4.8 Map exit codes on the CLI seam, which is where an exit code exists at all *(rewritten 2026-09-06: the MCP handler has no exit code — it returns the `status` field. The frozen map is honoured by adding the landing verb `verify_netlist_fidelity` to `gate.py`, whose `main()` derives the process exit from the result's own `status`)*: `0` ↔ `ok`; `1` ↔ `failed`; `2` ↔ `not-run` and `indeterminate`, via `STATUS_EXIT_VERBS`. A caller reading only the exit code can never read an unreadable input as a pass, and an unmapped status is refused rather than assumed benign. `NETLIST_MISSING` stays on the existing `_fail` channel (exit 1) because a wrong path sends the reader somewhere different from an inconclusive comparison. — artifact: `skills/bodesign/scripts/gate.py`, `tests/test_landing_gate_published_resolution.py`
- [x] 4.9 POSITIVE CONTROL: the D1.5 case from BR_20260905 — a pin declared NC that the emitter ties to GND — appears in `nc_wired` and **not** in `fused`. Question answered: *does the verb distinguish a mis-wired NC from a real short?*. — artifact: `tests/test_fidelity_netlist_verify.py`
- [x] 4.10 NEGATIVE CONTROL A: an empty `.net` (or one whose blocks parse to zero nets) yields `status="indeterminate"`, exit 2, and never `ok`. On today's code path the equivalent input yields `ok=True` whenever the spec holds only single-pin nets (RCA §10.3(c)), so the assertion fails before the work. — artifact: `tests/test_fidelity_netlist_verify.py`
- [x] 4.11 NEGATIVE CONTROL B (mutation) *(rewritten 2026-09-06: `:221` belongs to `sch_union_classes`, off the WP4 path — MUTANT A green proved no causality; MUTANT B on `parse_net_files` is the bearing control)*: replace the `unreadable.append(...)` error-collection arm inside `parse_net_files` in `fidelity.py` with a bare `continue` (i.e. swallow the read failure) and confirm the WP4 test suite goes RED. If it stays green the tests never exercised that path, and an unreadable `.net` would silently read as an empty one — which is exactly the `indeterminate`-vs-`ok` collapse this verb exists to prevent. **Clear `__pycache__` first** (`find . -name __pycache__ -prune -exec rm -rf {} +`) — AGENTS.md §6.3 measured that `python3 -B` does not prevent an existing stale `.pyc` from being loaded, so a same-length edit can leave the mutant unapplied and the green result would be a false negative. — artifact: none (mutation proof recorded in WP4 handoff)

## 5. WP5 — `bodesign_design_suggest`

- [x] 5.1 Define the verb contract: input `{mpn, pin_class, context}`; output `{status, suggestions:[…], evidence:{…}, review_required}` with `status ∈ {suggested, no-rule, indeterminate}` and `review_required` constant `true` — artifact: `services/mcp/server.py`
- [x] 5.2 Register handler and schema (two sites), with the schema describing `pin_class` as one of the nine classes from `references/pinout-to-circuit-method.md:32-47` and stating that an unsupported class returns `no-rule`, never a value. — artifact: `services/mcp/server.py`
- [x] 5.3 Assert DD-02 property (1) by construction and (2) by test: `committed` is not a member of the status codomain, and `review_required` is `true` for every input in the test matrix. — artifact: `tests/test_design_suggest_verb.py`
- [x] 5.4 Build the nine-class coverage table. For each class in `pinout-to-circuit-method.md:32-47`, record the KB anchor found by an actual `ragbase_query`, reading `fallbackApplied` on every result: an or-degraded hit is **not** a hit (RCA §8 item 14 measured a nonsense query returning repo=5/user=5 under or-fallback). Classes with no anchor are recorded as `no-rule` and are not implemented. Known anchors today: Power/decoupling → `control.power.decoupling-pdn-strategy`; IO/GPIO pull-ups (I²C) → `control.sch.pullup-termination-sizing` (implemented, `design_suggest.py:205`); Clock/XTAL → `control.si.crystal-oscillator-layout` (implemented, `:642`); High-speed/differential → `control.si.interface-requirements` (implemented, `:445`). The five unqueried classes were queried on 2026-09-06 and the results are recorded in `design.md` §WP5 KB coverage — Ground, Reset-EN, Boot-strapping and NC-DNC returned **no class-specific anchor**; Analog-reference returned `step.sch.mcu-adc-frontend-review` under `matchMode=and-tokens`, `fallbackApplied=false`. This task is now to keep that table current, not to produce it. — artifact: `plans/c03_delivery_contract_and_engine_seams/design.md`
- [x] 5.5 Implement in the order fixed by the coverage table (see `design.md` §WP5): (1) Power/decoupling, (2) Analog-reference. Only these two of the five previously-open classes have a non-degraded anchor; the other three (Ground, Reset-EN, Boot-strapping, NC-DNC) are `no-rule` classes in the WP5 contract and are NOT implemented. Ordering basis: anchor-bearing first, then pin count governed on a typical board. — artifact: `plans/c03_delivery_contract_and_engine_seams/design.md`
- [x] 5.6 Record DD-02 via `spec_record_decision` so the adjudication lives in the event ledger, not only in this file. — artifact: verb:spec_record_decision
- [x] 5.7 POSITIVE CONTROL: an I²C pull-up request returns `status="suggested"` with an `evidence.kb_object` of `control.sch.pullup-termination-sizing`. Question answered: *does a supported class return a sourced value?*. — artifact: `tests/test_design_suggest.py`
- [x] 5.8 NEGATIVE CONTROL: a pin class with no KB rule returns `status="no-rule"` with an empty suggestion list — it must not return a guessed value and must not return `suggested`. The control is red if any code path can emit a number without an `evidence.kb_object` — artifact: `tests/test_design_suggest_verb.py`

## 6. WP6 — readability gate (form axis, last)

- [x] 6.0 PREREQUISITE — emit the two quantities the gate needs, because `route_stats` does not carry them (DD-10). Measured: `RouteStats` (`composer.py:220-232`) has exactly four fields — `wired_nets`, `labelled_nets`, `junctions`, `label_fallback_reasons` — and `to_dict():226` emits exactly those four keys; `junctions` is `max(0, len(resolvable) - 2)` summed over wired nets (`:1830`), a fan-out proxy, NOT a subcircuit count. Add to the dataclass **and** to `to_dict()` in the same change (a field on the dataclass but absent from `to_dict()` is invisible to the gate while looking implemented): `stub_share: float` — fraction of drawn pin→label runs whose length is `<= 5.2mm`, emitted at the same site the router decides a run is a stub; `drawn_subcircuits: int` — count of connected wired components spanning ≥2 distinct component refs, emitted after the `:2611-2621` reconciliation so it mirrors actual emission rather than pre-reconciliation intent. Both emission points are listed in `errors.md` §Outcome Codomain. — artifact: `packages/eda-bridge/bodesign_eda_bridge/composer.py`, `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py`
- [x] 6.1 Define the gate input as `route_stats` after 6.0: the four existing fields (`composer.py:220-232`, reconciled at `:2611-2621`) plus the two added by 6.0. `label_fallback_reasons` carries the per-net reason including the `drawn_fragments` marker from BR_20260905 §8.5.3. — artifact: `packages/eda-bridge/bodesign_eda_bridge/composer.py:1790`
- [x] 6.2 Compute `N` per DD-09 (user ruling, spec-derived not constant): `N := count of signal nets in the spec containing ≥1 passive (ref prefix R/C/L) whose node count is in [2, 6]`, power and bus kinds excluded by the same `net_kinds` classification `_build_route_stats:1790` already applies. The gate measures the ratio `drawn_subcircuits / N`. Emit `N` in the report beside the ratio so a reader can tell a low ratio from a small denominator. — artifact: `packages/eda-bridge/bodesign_eda_bridge/readability_gate.py`
- [x] 6.2b Set the other thresholds from BR_20260905 §7 as calibrated on the real 45-component / 27-net btdongle spec in §8.5.1 (`wire=111`, `junction=5`, stub share `73.0%`, anti-fusion downgraded nets `3`): `junction > 20`; stub share `< 40%`; anti-fusion label downgrades `= 0` **or** each downgraded net retains a drawn fragment (`drawn_fragments > 0`). Each threshold cites its §8.5 line. — artifact: `plans/c03_delivery_contract_and_engine_seams/design.md`
- [x] 6.2c Pin the `drawn_subcircuits / N` threshold in three steps, in this order, per DD-09 — the value is deliberately NOT set at design time: (1) MEASURE: run the gate against the real btdongle spec of §8.5.1 and record the observed `drawn_subcircuits`, the computed `N`, and their ratio; (2) PIN: set the threshold from that measurement and record the number with the run that produced it, in `design.md`; (3) NEGATIVE CONTROL: replay the §8.5.2 power-clustering fixture (11 subcircuits, junction 43, stub 32.7%) and assert it still **passes** the form gate while its report carries `does_not_authorize` — a threshold that turned that fixture red would be a form gate asserting an electrical verdict, which DD-07 forbids. — artifact: `plans/c03_delivery_contract_and_engine_seams/design.md`
- [x] 6.3 Declare the thresholds scale-dependent and pin the acceptance corpus to the real spec: BR_20260905 §8.5.5 measured a 28/21 synthetic corpus reporting `junction 21 / stub 41.5%` (apparent near-miss) where the same code on the real board reported `43 / 32.7%` (clear pass). A synthetic corpus may supplement, never decide. — artifact: `plans/c03_delivery_contract_and_engine_seams/design.md`
- [x] 6.4 Emit `gate_axis="form"` as an explicit report field, not as prose. — artifact: `packages/eda-bridge/bodesign_eda_bridge/readability_gate.py`
- [x] 6.5 Emit `does_not_authorize:["electrical_correctness"]` in every report, pass and fail alike, per DD-07. — artifact: `packages/eda-bridge/bodesign_eda_bridge/readability_gate.py`
- [x] 6.6 POSITIVE CONTROL: on a spec whose subcircuits are drawn as wired networks the gate reports pass on the form axis, and the report still carries `does_not_authorize`. Question answered: *does the gate pass a genuinely readable drawing, and does it keep disclaiming even then?*. — artifact: `tests/test_readability_gate.py`
- [x] 6.7 NEGATIVE CONTROL: replay the BR_20260905 §8.5.2 power-clustering measurement as a fixture — `junction=43`, stub `32.7%`, 11 subcircuits, all form thresholds met, while fidelity `moved=67` including an open circuit. The assertion is that the form gate reports **pass** on this input and that its report still carries `does_not_authorize:["electrical_correctness"]`, so a consumer reading the form verdict alone cannot conclude the circuit is correct. This control fails if the gate is ever wired to block or to assert anything electrical. — artifact: `tests/test_readability_gate.py`
- [x] 6.8 State the sequencing rule in the gate module's own docstring: the form verdict is reported alongside, never instead of, the WP4 electrical verdict; a delivery presenting only the form verdict is incomplete. — artifact: `packages/eda-bridge/bodesign_eda_bridge/readability_gate.py`

### WP6 implementation record (round 8, 2026-09-06)

Module: `packages/eda-bridge/bodesign_eda_bridge/readability_gate.py`.
Tests: `tests/test_readability_gate.py` — **Ran 29, OK**.

**Boundary amendment (dispatcher ruling, round 8).** Task 6.0 as written placed the
`stub_share` emission "at the same site the router decides a run is a stub", which is
in `kicad_emit.py`. Measured on the btdongle real board, that quantity was reachable
from NOWHERE else: `SchematicEmitResult` carried no wire geometry (all 17 slots
enumerated; the two coordinate-bearing fields `slot_observe_wires` /
`wire_body_intrusions` were both empty), the shared `OccupancyLedger` ended with
`{'body':45,'pin_extent':201,'label':17}` and **zero** `wire` rects, and the short-run
count (83) matched no combination of the counts that do cross the seam
(`label_count`=57, `+no_connect`=88, `2×`=114). Controls: the same parser found 116
wires on disk; a `≤0.0001mm` threshold returned 0; `grep -c '(zzznope'` rc=1 — so the
zeros were absence, not a dead probe. A ledger-backed derivation was additionally
ruled out by instrumenting `OccupancyLedger.try_reserve`: **71 `wire` reserves were
attempted against the composer's own ledger instance and 0 survived** (control: the
spy saw all 45 `body` reserves), so the call sites are reached and their writes are
lost downstream — a separate defect, not a channel to build on. DD-10 forbids the
`.kicad_sch` re-parse. The dispatcher therefore widened the boundary to
**purely additive** emission in `kicad_emit.py`.

**Emissions added.** `SchematicEmitResult.wire_runs: list[dict]` (`{"net","len_mm"}`,
appended beside all four `wire_blocks.append` sites) and
`SchematicEmitResult.junctions_emitted: int`. `RouteStats` gains `stub_share`,
`drawn_subcircuits` and `fanout_proxy`, **all three added to `to_dict()` in the same
change** per DD-10.

**Fidelity controls** (mandated: the emission must mirror the written file, not
pre-emission intent) — all three green on btdongle:

| control | expected | observed |
| --- | --- | --- |
| `len(wire_runs)` == disk `(wire` | 116 | **116** ✓ |
| `stub_share` | 0.7155 ±1e-4 | **0.715517** ✓ |
| `junctions_emitted` == disk `(junction` | 6 | **6** ✓ |

**6.2c step (1) MEASURE** — run identity recorded in
`readability_gate.MEASURE_RUN`: spec
`04.btdongle/C03-EE/02_build/sch_gen/design.py` (45 comp / 27 net),
`style="draftsman", validate=False, fidelity=False`, HEAD 2026-09-06.
Observed: `drawn_subcircuits=4`, `N=18`, **ratio 0.2222**, `stub_share=0.715517`,
`junctions=6` (landed) / `fanout_proxy=7`, anti-fusion downgrades 3.
These differ from §8.5.1 (wire 111→116, stub 73.0%→71.55%, subcircuits 3→4,
junction 5→6) in the direction §8.5.3 predicts for c3019f68, so the threshold is
pinned on THIS run and **not** on the §8.5.1 figures.

**6.2c step (2) PIN** — `MIN_SUBCIRCUIT_RATIO = 0.50`. It sits above the measured
HEAD ratio (0.222 ⇒ HEAD FAILS, which is the point: HEAD *is* the label farm the BR
exists to make visible) and below the §8.5.2 fixture ratio (11/18 = 0.611 ⇒ PASSES).

**6.2c step (3) NEGATIVE CONTROL** — TV-9 (junction 43, stub 32.7%, 11 subcircuits)
reports `status="ok"` while carrying `does_not_authorize`, asserted in
`Br20260905PowerClusteringNegativeControlTests`. **Scope honesty: this control
replays the FROZEN NUMBERS from test-vectors.json TV-9; the power-clustering path
was NOT re-composed live** (its switch is an emitter constant this WP did not
exercise).

**DD-11 (dispatcher ruling, round 8) — the `indeterminate` arm was replaced, not
tuned.** `errors.md:113` compared `route_stats.junctions` against the landed
`(junction` count, but `junctions` was `max(0, len(resolvable)-2)` summed over wired
nets — a **fan-out proxy**, never a junction count. Comparing a proxy with a count
made that arm structurally always-true (measured 7 vs 6; the BR's 7 vs 5 has the same
cause), i.e. **zero discriminating power** — worse than no check, because it reads as
a defence. Under DD-11 `junctions` is overwritten post-reconciliation with
`emit.junctions_emitted`, the old value stays visible as `fanout_proxy`, the junction
consistency check is **deleted** (now guaranteed by construction), and
`indeterminate` instead asks the question that has two answers: *did the emitter
carry the task-6.0 emissions at all?* Both arms have controls in
`IndeterminateArmTests`.

**Mutation proof** (`__pycache__` purged first — AGENTS.md §6.3: `-B` does not evict
an existing stale `.pyc`):

| mutant | effect | restored |
| --- | --- | --- |
| `drawn_subcircuits` → constant `0` | live value 4 → **0** | `cmp` rc=0 |
| `wire_runs.append` → `return` | `len(wire_runs)` 116 → **0**, C1 False, `stub_share` → None | `cmp` rc=0 |

Post-restore `grep -c MUTANT` = 0 in both files (rc=1).

**Finding the mutation proof produced, recorded because it is a defect in the test
design rather than in the code:** under mutant 1 the gate suite **stayed green at 23
tests** while the live value went 4 → 0. Those tests feed the gate hand-written
dicts, so no assertion in them could see the emission point — *fixture coverage of a
consumer is not coverage of the producer, and the two are indistinguishable from the
pass count*. `LiveEmissionTests` (6 tests, real compose) was added to close it; the
suite is 23 → **29**.
