# Spec: c03_delivery_contract_and_engine_seams

## Purpose

C03's delivery contract, its pipeline adjudication, and the four engine seams that
follow from it. The guarantee: after this package, the C03 deliverable is a frozen
netlist whose electrical fidelity was checked by a verb that cannot report `ok`
from an input it could not read; the pipeline that produces it is named in
`specs/architecture.md`, so a fix cannot land on the pipeline nobody executes; and
the readability verdict is emitted on a separate axis that carries, as data, the
statement that it authorizes no electrical claim.

## Requirements

### Requirement: A1 — the C03 deliverable is a frozen netlist, not a document

The stage contract SHALL name a frozen, version-controlled netlist as the C03
electrical deliverable, and SHALL describe the `.docx` as its projection.

#### Scenario: netlist carries a MANDATORY marker

- **WHEN** the rewritten `GUIDE.md` is scanned for `MANDATORY` markers inside the
  netlist-freeze section
- **THEN** the count is `>= 1`

#### Scenario: docx is no longer the sole emphasised deliverable

- **WHEN** the bolded rows of the deliverables table are enumerated
- **THEN** the `.docx` row is not the only one — the control that fails on today's
  file, where `GUIDE.md:396` is the single bolded row

### Requirement: A2 — the delivery pipeline is adjudicated and recorded

`specs/architecture.md` SHALL state that the MCP pipeline is the C03 delivery path
and the skill pipeline is an internal tool, and SHALL carry the migration list
that follows, including PC-001's destination and an owner for each of the 8
drawing rules.

#### Scenario: the passive-completeness backstop becomes reachable

- **WHEN** `grep -rl 'PC-001' packages/` runs after the migration
- **THEN** at least one file matches — against today's measured zero, with the
  paired control on `skills/` returning 3

#### Scenario: every drawing rule has exactly one owner

- **WHEN** the 8 rules of `schematic-drawing-rules.md` are read against the
  ownership map
- **THEN** each rule names one owner among {P1 contract, P2 internal, stage
  contract}, and no rule is unassigned

### Requirement: A3 — a projected skill either runs its roster or reports not-run

`gate.py` SHALL resolve the bodesign `packages/` tree under an XDG install through
`BODESIGN_SRC`, then a fixed enumerated candidate list, and SHALL NOT search the
filesystem. When resolution fails, every roster verb SHALL report `not-run`.

#### Scenario: published skill executes the verb the GUIDE prescribes

- **WHEN** `gate.py check_c03 --repo <abs>` is run from the published skill with
  `BODESIGN_SRC` unset
- **THEN** the verb runs and returns a report envelope

#### Scenario: unresolved packages never read as success

- **WHEN** every candidate points at a directory with no `packages/workflow-core`
- **THEN** `packages_resolved` is `false` and every roster verb returns `not-run`;
  no verb returns `ok`

### Requirement: A4 — fidelity is callable standalone and cannot pass an unread input

`bodesign_verify_netlist_fidelity` SHALL accept `{spec, emitted, nc_declared}`,
report `fused` / `split` / `node_diff` / `nc_wired` as independent fields with a
`nets_parsed` count, and SHALL resolve `status` to `indeterminate` whenever
`nets_parsed == 0` or any `emitted` path is unreadable.

#### Scenario: a mis-wired NC is not reported as a short

- **WHEN** a pin declared in `nc_declared` is tied to GND by the emitter (the
  BR_20260905 D1.5 case)
- **THEN** it appears in `nc_wired` and does not appear in `fused`

#### Scenario: an empty netlist yields indeterminate, never ok

- **WHEN** every `emitted` path parses to zero nets
- **THEN** `status` is `indeterminate` and the exit code is 2 — against today's
  path, which returns `ok=True` for a spec of single-pin nets

#### Scenario: the swallowing continue is covered by test

- **WHEN** `fidelity.py:221`'s `continue` is replaced by a `raise`, after
  `__pycache__` is cleared
- **THEN** the WP4 test suite turns red

### Requirement: A5 — design suggestions are sourced, reviewable, and never decisions

`bodesign_design_suggest` SHALL return `status` in
{`suggested`, `no-rule`, `indeterminate`}, SHALL set `review_required` to `true`
for every input, and SHALL attach an `evidence` block naming a KB object to every
numeric value it emits.

#### Scenario: a covered class returns a sourced value

- **WHEN** an I²C pull-up suggestion is requested for a supported bus
- **THEN** `status` is `suggested` and `evidence.kb_object` is
  `control.sch.pullup-termination-sizing`

#### Scenario: an uncovered class returns no-rule rather than a guess

- **WHEN** a pin class with no KB anchor surviving the `fallbackApplied` check is
  requested
- **THEN** `status` is `no-rule`, the suggestion list is empty, and no numeric
  value is returned

### Requirement: A6 — the readability verdict authorizes nothing electrical

The readability gate SHALL emit `gate_axis="form"` and
`does_not_authorize:["electrical_correctness"]` as report fields on every run,
pass and fail alike, and SHALL derive thresholds from the real-board measurements
in BR_20260905 §8.5.

#### Scenario: a geometrically clean but electrically broken drawing still passes form

- **WHEN** the BR_20260905 §8.5.2 power-clustering fixture is scored (junction 43,
  stub 32.7%, 11 subcircuits, fidelity `moved=67` with an open circuit)
- **THEN** the form gate reports pass and the report carries
  `does_not_authorize:["electrical_correctness"]`, so the form verdict alone
  cannot be read as electrical approval

#### Scenario: absent route_stats is not a pass

- **WHEN** the compose result carries no `route_stats` (e.g.
  `connection_style="netlist"`)
- **THEN** `status` is `not-run`

## Acceptance Checks

- [ ] `plan-validate.ts plans/c03_delivery_contract_and_engine_seams --target-state designed` passes with no scaffold-marker finding
- [ ] `GUIDE.md` netlist-freeze section MANDATORY count `>= 1`; `.docx` is not the only bolded deliverable row
- [ ] `grep -rl 'PC-001' packages/` non-empty; control grep on `skills/` still non-empty
- [ ] each of the 8 drawing rules has exactly one recorded owner
- [ ] published-skill `gate.py check_c03` runs with `BODESIGN_SRC` unset; forced-unresolved run returns `not-run` for every verb and `ok` for none
- [ ] declared-NC-tied-to-GND lands in `nc_wired`, not `fused`
- [ ] zero-net `emitted` yields `status="indeterminate"`, exit 2
- [ ] mutating `fidelity.py:221` `continue` → `raise` turns the WP4 suite red, `__pycache__` cleared first
- [ ] I²C request returns `suggested` with `evidence.kb_object`; uncovered class returns `no-rule` with no value; `review_required` true across the test matrix
- [ ] every readability report carries `gate_axis="form"` and `does_not_authorize:["electrical_correctness"]`, including on pass
- [ ] DD-01 and DD-02 exist as `spec_record_decision` entries, not only as prose here
