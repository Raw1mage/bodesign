# BR Family Ownership — bodesign

**This file is the SSOT.** Owner session titles carry an `[OWNS bodesign/<family>]`
token as a lookup index; on disagreement **this file wins**.

Protocol: `a2a-d2d-protocol` §4. One owner per family. A non-owner that finds
something in an owned family files evidence and injects the owner — it does not
edit that family's fix surface unilaterally.

Seeded 2026-08-02 from a fix-surface survey (`ses_03f1e698b`) + a live ownership
probe (`ses_07c1ad2a4`). Every row's `still-valid` column is **evidence at HEAD
`391099c`**, not the BR's own self-description.

---

## Why `(default)` exists

Rule §4.3.2: a repo always has a `(default)` owner covering everything no named
family claims. **"No family matched" is never a reason to open a new session** —
it routes to `(default)`. Creating a session is the exception; `inject_prompt` to
an existing owner is the default.

---

## Families

| family | owner | fix surface | members |
|---|---|---|---|
| `mcp-protocol-surface` | `ses_07c1ad2a4ffesVhlKotYBmsZlq` | `services/mcp/server.py` (protocol handler / route / tool registry / `run_tool`), `mcp.json`, `services/mcp/{preflight,_skill_nudge,token_store}.py`, `skills/bodesign/doctrine.md`, 4× Dockerfile + `docker-compose*` | `BR_20260721` ✅closed · `BR_20260723` (stale) |
| `skill-shipping` | `ses_04db7a1c5ffelvbxyLP1p6xlRH` | `services/mcp/skill_shipping.py`, `server.py` `/skills` routes, 4× Dockerfile, `.dockerignore` | `BR_20260730` (PARTIAL) |
| `readiness-contract` | **unassigned** | `packages/workflow-core/bodesign_workflow_core/{c01_id_package,c02_me_package,provenance,guide_dod,readiness_common}.py`, `skills/bodesign/scripts/gate.py`, `server.py:1179-1182` | `BR_20260719_c01_readiness_folder_arg_double_prefix` · `BR_20260719_c02_readiness_provenance_root_and_dod_surface` · `BR_20260719_c01_photoreal_render_pathway_adhoc_oauth` |
| `schematic-engine` | **unassigned** — `ses_0c8efa1b4` probed · declined, see note | `packages/eda-bridge/bodesign_eda_bridge/{kicad_emit,composer,fidelity}.py`, `tests/test_{fidelity_gate,kicad_emit}.py`, `plans/eda-bridge_draftsman-series-divider-wireable/` | `BR_20260723b_power_ports_false_not_bypassed` · `BR_20260723e_draftsman_cannot_wire_basic_series_divider_collinear_fusion` |
| `silent-success` | **unassigned** | `packages/component-kb/bodesign_component_kb/vault.py`, `packages/workflow-core/bodesign_workflow_core/{reference_crosscheck,checkers/no_silent_degradation}.py`, `packages/eda-bridge/bodesign_eda_bridge/pin_allocation.py`, `ragbase/control/no-silent-degradation/` | `BR_20260731_vacuous_pass_empty_input_reads_as_verified_in_gates` · `KB_20260729_silent_degradation_antipattern_invariant_and_lint` (stale) |
| `c03-stage-discipline` | **unassigned** | `skills/bodesign/stages/{c03-ee,c04-layout}/GUIDE.md`, `packages/workflow-core/bodesign_workflow_core/{check_c03,c04_layout_constraints,c04_placement_gate}.py` | `BR_20260707_bom_proposal…` · `BR_20260707_c03_stage_entry_gate…` · `BR_20260707_ccm_workflow_bypasses_webdav_cache…` |
| `layout-route` | **unassigned** | `packages/eda-bridge/bodesign_eda_bridge/routing.py`, `Dockerfile.ee`, `docker-compose.workers.yml`, `server.py:1334-1385` | `BR_20260729_ee_worker…` (stale) · `BR_20260729_preflight…` (stale) |
| `(default)` | **unassigned** | everything not claimed above | — |

---

## Shared surfaces — NOT owned by any one family

**`services/mcp/server.py` is a hub, not a family surface.** Three families name
it. Claiming a disjoint partition here would be false, so it is declared shared
instead (§4.5: a claimed-disjoint surface that isn't is worse than an admitted
overlap).

| surface | rule |
|---|---|
| `services/mcp/server.py` — `_h_*` handler blocks | each family edits its own handlers; announce before touching another's |
| **`run_tool` dispatcher** | **shared-hotspot.** R0.6 nudge + preflight/assertion are wired into it, so it is on the call path of *every* compute tool. **Any change requires A2A announcement first — including by `mcp-protocol-surface`, its nominal owner.** Confirmed by that owner 2026-08-02. |
| `skills/bodesign/doctrine.md` | append-only in practice; `c03-stage-discipline` and `mcp-protocol-surface` both touch it |

Live write-ownership of `server.py` currently sits with `readiness-contract`
(the only family with a pending *edit* there — `:1179-1182`). The other two
families' `server.py` regions are already-fixed close-outs. If either later needs
a real edit, this assumption breaks and a single MCP-surface owner must arbitrate.

---

## Fix-order dependencies (owner's call, but these are load-bearing)

- **`BR_20260723e` destroys `BR_20260723b`'s evidence.** Both rewrite wire/port
  geometry in `kicad_emit.py`. **Capture 723b's repro before 723e lands**, or you
  will not be able to tell whether 723b was fixed or merely made unreachable.
  **Upgrade (from the `ses_0c8efa1b4` probe): write that repro as a pytest
  fixture in `tests/`, not as a hand-run record** — then the dependency is
  machine-checked instead of being a convention someone has to remember. Same
  reasoning that produced the fidelity gate: ERC is blind to fusion shorts, so
  the guard needs an independent acceptance surface.
- **`c01_double_prefix` before `c02_provenance`.** Same root cause (`one folder
  param carries two incompatible directory bases`). c01 sets the contract; fixing
  c02 alone papers over the shared contract and will conflict.
- **`c03_stage_entry_gate` before/with `bom_proposal`.** The BOM BR delegates its
  machine half to `check_c03` R4 — and that gate is built but **unwired** (zero
  call sites in any C04 entry). Closing the BOM BR first leaves prose-only defence.
- **`BR_20260731` before `KB_20260729`.** The KB's lint is the executable form of
  the invariant `BR_20260731` violates — and as shipped it does **not** catch
  those three sites. Closing KB first marks the doctrine done while its own P1
  counterexample is live.
- **`ee_worker` closes as superseded before anyone touches `preflight`.** Its RCA
  is explicitly disproven by its successor; a fixer who picks it up first chases a
  toolchain `Dockerfile.ee:23` already installs.

---

## Staleness — the biggest single finding

**6 of 14 top-level BRs no longer describe reality.** The top-level `issues/`
directory substantially over-states open work, and a BR emits **no staleness
signal** — it reads like the present.

| BR | reality at HEAD |
|---|---|
| `BR_20260721` | implemented + deployed → **closed 2026-08-02** (`0f71469`) |
| `BR_20260723` | fixed the same day it was filed (`a7fe826`, `080b454`); its cited coordinate `server.py:153` no longer holds the quoted code |
| `BR_20260729_ee_worker` | self-superseded — successor states the RCA does not hold |
| `BR_20260729_preflight` | both defects fixed, with the BR id cited in-code |
| `KB_20260729` | all three targets landed (ragbase object, lint, doctrine line) |
| `BR_20260719_c01_photoreal` | half-stale — credential complaint addressed, requested verb still absent |

**Verify a BR against the tree before dispatching it.** A stale BR costs a full
handler round.

---

## Probe notes

### `schematic-engine` — `ses_0c8efa1b4` declined (2026-08-02)

Probed because its title ("防熔合") names the same defect class as `BR_20260723e`.
It declined, and **the decline carried information the acceptance would not have**:

- **It was not the author.** The 8.4–8.7 wire-geometry implementation was done by
  a coding subagent; that session did verification and close-out. `_collinear_overlap`
  and the jog/split landing choices are second-hand to it.
- **Zero knowledge of the current fix surface.** `power_endpoints`,
  `_port_intrusions`, `power_ports`, stub orientation — all post-date its work by
  17 days. The `BR_20260723*` generation is outside its knowledge boundary.
- **Its A-grade knowledge is already written down** (spec DD-8..DD-11, CHANGELOG,
  commit `1fe46df`). Nothing live beyond the record — so a fresh handler reading
  from spec + the two BRs + the fidelity gate starts no worse, **without the
  "sounds like it knows" risk**.

It declined to adjudicate the 723e→723b geometry dependency for exactly that
reason, while backing the *ordering* on independent methodological grounds. That
is the distinction this registry wants: **it separated what it could vouch for
from what it would have been guessing at.**

**Consequence for routing:** a title matching a defect class proves the class was
*handled there*, not that the geometry knowledge is *held there*. Treat title hits
as candidates to probe, never as owners to assign.

**Open question it raised, unresolved:** if `ses_0716c7745` (schemdraw template
bank) *removed* the draftsman wire engine rather than adding an alternative,
`BR_20260723e` may be moot. **Judgement to apply: as long as a `style="draftsman"`
path is still reachable in the codebase, 723e stands.** Verify before dispatching it.

## Registry maintenance

- Filing a BR writes one header line: `Owner: ses_<id>（<one-line role>）`.
  Look the family up here; no match → `(default)`.
- Handing over ownership is **three** actions: inject the new owner, update this
  file, new owner adds its title token and the old owner removes its own.
- Dead owner → successor records `succeeded-by <new id>`; **do not overwrite the
  old id** — that transcript is still the family's most complete history.
- Split a new family out only when its fix surface is **genuinely disjoint at the
  file level**. Families are a mutable classification; a registry cut too fine
  becomes one nobody maintains.
