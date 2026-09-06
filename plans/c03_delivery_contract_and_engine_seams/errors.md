# Errors: c03_delivery_contract_and_engine_seams

## Outcome Codomain

Every functional module declares the COMPLETE set of states it can leave behind.
Mandatory classes: `ok` / `failed` / `not-run` — the three a bare status
collapses. `empty` (ran, produced nothing) and `indeterminate` (ran, cannot
decide) must be ADDRESSED: give a value, or a row with `n/a (<reason>)`.

Every outcome names the site that emits it. An outcome nobody emits is a comment.

Six modules are declared, one per work package. `<file>:<line>` anchors point at
the site that exists today when the emission extends existing code; sites created
by this package are named by function rather than by a line number that does not
yet exist.

#### WP1 — GUIDE contract conformance check (`c03_netlist_freeze_check`)

Reads a stage directory and reports whether the frozen-netlist deliverable
required by `GUIDE.md` §Netlist freeze rule exists and is internally consistent.

| Module | Value | Class | Means | Emitted at |
| ------ | ----- | ----- | ----- | ---------- |
| `c03_netlist_freeze_check` | `ok` | ok | `C03_<product>.net` and `C03_Netlist_Freeze.json` both present, tracked, and the JSON's `sha256` matches the `.net` on disk | `check_c03.py` freeze-check branch (new) |
| `c03_netlist_freeze_check` | `failed` | failed | both files present but `sha256` mismatches, or recorded `nets_parsed` is 0, or the recorded WP4 verdict is not `ok` | same branch, mismatch arm |
| `c03_netlist_freeze_check` | `not-run` | not-run | no stage directory supplied, or the stage predates the contract (no `C03_Netlist_Freeze.json` **and** no `.net` at all) — reported as not-run, never as pass | same branch, precondition arm |
| `c03_netlist_freeze_check` | `empty` | empty | freeze JSON well-formed but records zero emitted `.net` entries — a stage that froze nothing is distinct from a stage that froze something wrong | same branch, zero-entry arm |
| `c03_netlist_freeze_check` | `indeterminate` | indeterminate | `C03_Netlist_Freeze.json` present but unreadable/unparseable, or the `.net` it names is absent — the claim cannot be checked either way | same branch, unreadable arm |

#### WP2 — PC-001 after relocation (`validate_passive_completeness`)

Existing detector, relocated per DD-08 / task 2.2 into
`packages/workflow-core/bodesign_workflow_core/check_c03.py` (adjudicated
2026-09-06; the `specs/architecture.md:101` veto premise was measured false — see
design.md DD-08). Its current vocabulary is finding-based; this table is the
codomain it must expose after relocation.

| Module | Value | Class | Means | Emitted at |
| ------ | ----- | ----- | ----- | ---------- |
| `validate_passive_completeness` | `ok` | ok | every active IC with ≥1 power pin has rail→GND decoupling, or the gap is waived with provenance | relocated detector, clean arm |
| `validate_passive_completeness` | `failed` | failed | ≥1 unwaived `PC-001` blocking finding | relocated detector, finding arm |
| `validate_passive_completeness` | `not-run` | not-run | no netlist/topology input reachable, so no IC was classified — must appear in `check_c03.not_checked` with "did NOT run" wording rather than dropping out | relocated detector, precondition arm; `check_c03.py:1010` `_NOT_CHECKED_BASE` |
| `validate_passive_completeness` | `empty` | empty | ran, and the design holds zero active ICs to carry an obligation — a passive-only board is not a pass earned by checking | relocated detector, zero-subject arm |
| `validate_passive_completeness` | `indeterminate` | indeterminate | a waiver sidecar is present but malformed — today `PassiveWaiverError` is fail-fast (`specs/architecture.md:101`); this row preserves that, surfacing as indeterminate and never as a silent waive | relocated detector, waiver-parse arm |

#### WP3 — packages resolution (`gate.py _resolve_src` + verb dispatch)

| Module | Value | Class | Means | Emitted at |
| ------ | ----- | ----- | ----- | ---------- |
| `gate.py` roster/dispatch | `packages_resolved=true` + verb `ok` | ok | a candidate root containing `packages/workflow-core` was accepted and the verb ran | `gate.py:844` resolved arm; verb return |
| `gate.py` roster/dispatch | verb `failed` | failed | packages resolved, the verb ran and returned a failing verdict | verb return |
| `gate.py` roster/dispatch | verb `not-run` | not-run | `packages_resolved=false` — every roster verb returns not-run carrying the same `packages_error`; this is the state that today collapses into `LANDING_PACKAGES_NOT_FOUND` at call time | `gate.py:99` `LandingError`; `gate.py:835-842` `packages_error` + `impact` |
| `gate.py` roster/dispatch | `--list` `count=N` with `packages_resolved=false` | empty | roster complete, nothing in it runnable — already emitted correctly today and preserved unchanged | `gate.py:845-861` |
| `gate.py` roster/dispatch | `n/a (resolution is a decidable existence test)` | indeterminate | acceptance is "`<candidate>/packages/workflow-core` exists" — a path either exists or does not, and DD-04 forbids a search that could partially match. `gate.py:849` already warns that `true` proves only resolution, not runnability; that residual risk surfaces as the verb's own `failed`, not as an undecidable resolution | n/a (resolution is a decidable existence test) |

#### WP4 — `bodesign_verify_netlist_fidelity`

| Module | Value | Class | Means | Emitted at |
| ------ | ----- | ----- | ----- | ---------- |
| `verify_netlist_fidelity` | `ok` (exit 0) | ok | `nets_parsed > 0`, all `emitted` readable, and `fused` / `split` / `node_diff.spec_only` / `node_diff.emitted_only` / `nc_wired` all empty | status resolver (DD-06), clean arm |
| `verify_netlist_fidelity` | `failed` (exit 1) | failed | `nets_parsed > 0`, all readable, ≥1 of the five difference fields non-empty | status resolver, diff arm |
| `verify_netlist_fidelity` | `not-run` (exit 2) | not-run | precondition unmet before any read: `spec` absent, or `emitted` an empty list — no comparison attempted | status resolver, precondition arm |
| `verify_netlist_fidelity` | `n/a (folded into indeterminate by DD-06)` | empty | a parse yielding zero nets is NOT "ran and found nothing": the reader cannot tell it from an unreadable export, so it is deliberately given no passing-adjacent value. Recorded so the absence is a decision, not an oversight | n/a (DD-06 folds it into `indeterminate`) |
| `verify_netlist_fidelity` | `indeterminate` (exit 2) | indeterminate | `nets_parsed == 0`, or any `emitted` path unreadable/unparseable — set **before** comparison. This is the state that today returns `ok=True` on a single-pin-net spec (RCA §10.3(c)) | status resolver, pre-comparison arm; the unreadable-path list replaces `fidelity.py:220` `continue` |

#### WP5 — `bodesign_design_suggest`

| Module | Value | Class | Means | Emitted at |
| ------ | ----- | ----- | ----- | ---------- |
| `design_suggest` | `suggested` | ok | a KB rule covers the pin class and produced ≥1 value, each with an `evidence.kb_object`; `review_required=true` | verb return, rule-hit arm |
| `design_suggest` | `indeterminate` | failed | a rule covers the class but its inputs fall outside the rule's validated window — e.g. `_choose_typical` finds no typical inside `[Rp_min, Rp_max]` (`design_suggest.py:106-115` already emits a `warning` rather than forcing a value); no value is offered | verb return, out-of-window arm; `design_suggest.py:106` |
| `design_suggest` | `no-rule` | not-run | the pin class has no KB anchor surviving the `fallbackApplied` check — no rule executed, so no value could exist | verb return, uncovered-class arm |
| `design_suggest` | `no-rule` with empty `suggestions` | empty | a rule matched the class but the supplied context names zero pins of that class — ran, nothing to suggest; distinguished from plain `no-rule` by a populated `evidence` block naming the rule that found nothing to do | verb return, zero-subject arm |
| `design_suggest` | `indeterminate` | indeterminate | a required electrical input cannot be resolved — today an unresolvable rail voltage raises (`design_suggest.py:128` `_rail_voltage`, "never a guessed VCC"); at the verb boundary that becomes `indeterminate` rather than an exception crossing the MCP surface | verb return, unresolved-input arm; `design_suggest.py:128` |

#### WP6 prerequisite — the two new `route_stats` emissions (task 6.0)

DD-10: `RouteStats` (`composer.py:220-232`) carries exactly four fields today —
`wired_nets`, `labelled_nets`, `junctions`, `label_fallback_reasons` — and
`to_dict():226` emits exactly those four keys. Neither quantity the gate scores
exists yet, so each needs its own emission point and its own codomain. Both are
added to the dataclass **and** to `to_dict()` in one change: a field present on the
dataclass but absent from `to_dict()` is invisible to the gate while reading as
implemented.

| Module | Value | Class | Means | Emitted at |
| ------ | ----- | ----- | ----- | ---------- |
| `route_stats.stub_share` | `0.0 ≤ f ≤ 1.0` | ok | fraction of drawn pin→label runs whose length is `≤ 5.2mm`, computed over runs the router actually emitted | router stub-decision site (new), surfaced via `RouteStats.to_dict()` `composer.py:226` |
| `route_stats.stub_share` | field absent from `to_dict()` | failed | the emission was added to the dataclass but not to the dict — a WP6 `not-run`, never a default `0.0`; the gate must treat a missing key as absent input, not as "no stubs" | consumed at gate precondition arm |
| `route_stats.stub_share` | `None` | not-run | no wires drawn at all (`connection_style="netlist"`), so no run was measurable — distinct from every run being long | `_build_route_stats` `composer.py:1790`, no-wire arm |
| `route_stats.stub_share` | `n/a (0.0 is a real measurement)` | empty | wires drawn and none is a stub is the value `0.0`, a genuine result; it is not an empty outcome | n/a |
| `route_stats.stub_share` | `n/a (length is measured, not inferred)` | indeterminate | run length comes from the emitted coordinates the router already holds; there is no partial-knowledge case | n/a |
| `route_stats.drawn_subcircuits` | `int ≥ 0` | ok | count of connected wired components spanning ≥2 distinct component refs | after the `composer.py:2611-2621` reconciliation, so it mirrors actual emission rather than pre-reconciliation intent |
| `route_stats.drawn_subcircuits` | field absent from `to_dict()` | failed | same dataclass/dict divergence as above | consumed at gate precondition arm |
| `route_stats.drawn_subcircuits` | `None` | not-run | no wires drawn, so no connected component could be formed | `_build_route_stats` `composer.py:1790`, no-wire arm |
| `route_stats.drawn_subcircuits` | `0` with `wired_nets > 0` | empty | wires exist but no connected group spans two component refs — the label-farm shape BR_20260905 names; a real measurement, reported rather than folded into `not-run` | post-reconciliation counting site |
| `route_stats.drawn_subcircuits` | `n/a (counted post-reconciliation)` | indeterminate | counting after `:2611-2621` means the wire set is final; there is no in-between state to report | n/a |

#### WP6 — readability gate (`gate_axis="form"`)

`N` (DD-09) is computed from the spec, not from `route_stats`: signal nets holding
≥1 passive (ref prefix R/C/L) with node count in `[2, 6]`. It is emitted in the
report beside the `drawn_subcircuits / N` ratio, so a low ratio is
distinguishable from a small denominator.

| Module | Value | Class | Means | Emitted at |
| ------ | ----- | ----- | ----- | ---------- |
| `readability_gate` | `N = 0` → ratio not evaluated | empty | the spec contains no net eligible to be a subcircuit, so the ratio has no denominator; reported as such and NOT as a met or unmet threshold | gate report, zero-denominator arm |
| `readability_gate` | `ok` | ok | every threshold in task 6.2 met on the pinned real-board corpus; report carries `gate_axis="form"` and `does_not_authorize:["electrical_correctness"]` | gate report, pass arm |
| `readability_gate` | `failed` | failed | ≥1 threshold unmet; the report names which, and still carries `does_not_authorize` | gate report, fail arm |
| `readability_gate` | `not-run` | not-run | no `route_stats` on the compose result — e.g. `connection_style="netlist"`, where `route_stats` is `None` (`composer.py:281` declares it `RouteStats \| None`). A missing `route_stats` must never read as a pass | gate report, precondition arm; `composer.py:2600` |
| `readability_gate` | `empty` | empty | `route_stats` present but records zero nets (nothing routed or labelled) — ran, nothing to score; thresholds are undefined on an empty denominator and are not evaluated | gate report, zero-net arm |
| `readability_gate` | `indeterminate` | indeterminate | **amended 2026-09-06 DD-11.** The emitter that produced these stats predates task 6.0 — it carries no `wire_runs` / `junctions_emitted` — while `wired_nets > 0`, so the stats cannot be vouched for against what was drawn. The report names the missing emitter fields | gate report, stale-emitter arm |

**`indeterminate` was amended, not tuned (DD-11, 2026-09-06).** The original arm
fired when `route_stats.junctions` disagreed with the landed `(junction` count,
citing BR_20260905 §8.5's "7 vs 5". Re-measured this round: 7 vs **6** — and the
cause is structural, not untraced. `composer.py:1830` computed `junctions` as
`max(0, len(resolvable) - 2)` summed over wired nets: a **fan-out proxy**, never a
junction count. Comparing a proxy against a count is always-true, so the arm fired
on every real board and 6.2c's MEASURE step could never obtain a ratio. A check
that cannot come back clean has zero discriminating power and is worse than no
check, because it reads as a defence that works. Under DD-11 `junctions` is
overwritten post-reconciliation from `SchematicEmitResult.junctions_emitted` (the
old value stays visible as `fanout_proxy`), the consistency check is **deleted** as
guaranteed-by-construction, and `indeterminate` asks the question above, which has
two answers. Both branches are controlled in `tests/test_readability_gate.py`
`IndeterminateArmTests`.

`does_not_authorize` is `["electrical_correctness", "fidelity"]` in every status.
`fidelity` is named explicitly because BR_20260905 §8.5.2's counterexample was
caught by the fidelity axis specifically; naming only the general term would let a
reader assume the specific one was covered.

## Error Catalogue

The `failed` region of the codomain above, in detail.

| Code | Condition | Surface | Recovery |
| ---- | --------- | ------- | -------- |
| `C03_NETLIST_FREEZE_MISSING` | stage has a `.net` but no `C03_Netlist_Freeze.json` | `c03_netlist_freeze_check` → `failed`, names the unfrozen `.net` | run the freeze step; commit both promoted artifacts |
| `C03_NETLIST_FREEZE_STALE` | freeze JSON `sha256` ≠ the `.net` on disk | `failed`, prints both digests | re-freeze from the current emit, or restore the recorded emit |
| `PC001_DECOUPLING_MISSING` | active IC with ≥1 power pin and zero rail→GND decoupling, unwaived | blocking finding, `severity=error`, `confidence=deterministic`, `evidence_source=topology` | add decoupling, or file a waiver carrying `source`+`reason`+`scope` |
| `PASSIVE_WAIVER_MALFORMED` | waiver sidecar present but unparseable or missing provenance | fail-fast `PassiveWaiverError` → module `indeterminate` | repair the sidecar; a malformed waiver is never treated as absent |
| `LANDING_PACKAGES_NOT_FOUND` | no candidate root contains `packages/workflow-core` | `packages_resolved=false` + `packages_error{code,message,hint,impact}`; every verb returns `not-run` | `export BODESIGN_SRC=<repo root containing packages/*>` |
| `FIDELITY_INPUT_UNREADABLE` | an `emitted` path cannot be read or parsed | `status="indeterminate"`, exit 2, unreadable paths listed by name | fix the export; never re-read exit 2 as a pass |
| `FIDELITY_PARSED_ZERO` | `nets_parsed == 0` across all `emitted` | `status="indeterminate"`, exit 2 | re-export the netlist; an empty read cannot yield "no differences" |
| `FIDELITY_PARTITION_DIVERGED` | ≥1 of `fused` / `split` / `node_diff.*` / `nc_wired` non-empty | `status="failed"`, exit 1, each field reported separately | read the field that is non-empty — a wired NC, a short, an open and a phantom node need different fixes |
| `FIDELITY_SPEC_NOT_A_PARTITION` | the spec declares a node in more than one net | reported alongside the verdict, qualifying `fused` (existing `spec_overlapping_nodes`, `fidelity.py:49-58`) | resolve the spec's own contradiction before reading `fused` as an emitter defect |
| `SUGGEST_NO_RULE` | pin class has no KB anchor surviving `fallbackApplied` | `status="no-rule"`, empty suggestions, no value | supply the value manually, or distil the rule into KB first |
| `SUGGEST_INPUT_UNRESOLVED` | a required electrical input (e.g. rail voltage) cannot be resolved | `status="indeterminate"`, names the missing input | pass the input explicitly — no default is substituted |
| `SUGGEST_OUT_OF_WINDOW` | no typical value lands inside the computed bounds | `status="indeterminate"` with the computed window | compute an exact value for this combination; the rule does not force a typical |
| `READABILITY_THRESHOLD_UNMET` | ≥1 form threshold unmet | `status="failed"`, `gate_axis="form"`, `does_not_authorize:["electrical_correctness"]` | improve the drawing; this verdict authorizes no electrical conclusion either way |
| `READABILITY_STATS_ABSENT` | compose result carries no `route_stats` | `status="not-run"` | re-run compose on a path that produces `route_stats`; absence is not a pass |
| `READABILITY_STATS_INCONSISTENT` | `route_stats` counts disagree with the emitted drawing | `status="indeterminate"`, both numbers reported | trace the discrepancy (BR_20260905 §8 boundary 4, untraced); do not adopt either number |
