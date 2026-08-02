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
| `mcp-protocol-surface` | `ses_07c1ad2a4ffesVhlKotYBmsZlq` | `services/mcp/server.py` (protocol handler / route / tool registry / `run_tool`), `mcp.json`, `services/mcp/{preflight,_skill_nudge,token_store}.py`, `skills/bodesign/doctrine.md`, 4× Dockerfile + `docker-compose*` | `BR_20260721` ✅closed · `BR_20260723` (**verified closeable 2026-08-02 — owner's call**) |
| `skill-shipping` | `ses_04db7a1c5ffelvbxyLP1p6xlRH` | `services/mcp/skill_shipping.py`, `server.py` `/skills` routes, 4× Dockerfile, `.dockerignore` | `BR_20260730` (PARTIAL) |
| `readiness-contract` | **unassigned** | `packages/workflow-core/bodesign_workflow_core/{c01_id_package,c02_me_package,provenance,guide_dod,readiness_common}.py`, `skills/bodesign/scripts/gate.py`, `server.py:1179-1182` | `BR_20260719_c01_readiness_folder_arg_double_prefix` · `BR_20260719_c02_readiness_provenance_root_and_dod_surface` · `BR_20260719_c01_photoreal_render_pathway_adhoc_oauth` |
| `schematic-engine` | **unassigned** — `ses_0c8efa1b4` probed · declined, see note | `packages/eda-bridge/bodesign_eda_bridge/{kicad_emit,composer,fidelity}.py`, `tests/test_{fidelity_gate,kicad_emit}.py`, `plans/eda-bridge_draftsman-series-divider-wireable/` | `BR_20260723b_power_ports_false_not_bypassed` · `BR_20260723e_draftsman_cannot_wire_basic_series_divider_collinear_fusion` |
| `silent-success` | **unassigned** | `packages/component-kb/bodesign_component_kb/vault.py`, `packages/workflow-core/bodesign_workflow_core/{reference_crosscheck,checkers/no_silent_degradation}.py`, `packages/eda-bridge/bodesign_eda_bridge/pin_allocation.py`, `ragbase/control/no-silent-degradation/` | `BR_20260731_vacuous_pass_empty_input_reads_as_verified_in_gates` · `KB_20260729_silent_degradation_antipattern_invariant_and_lint` (**PARTIAL** — lint 抓不到自己的反例) |
| `c03-stage-discipline` | **unassigned** — `ses_0c87bab06` probed · declined, see note. **cross-ref: `check_c03.py` 內部語意由 `ses_0c87bab06`（BR_20260730 family，§A–§Q 19 輪）演進至 HEAD（927→1200+ 行）；動它的內部規則前先 inject 那顆** | `packages/workflow-core/bodesign_workflow_core/{check_c03,c04_layout_constraints}.py`, `skills/bodesign/scripts/gate.py`, `skills/bodesign/stages/{c03-ee,c04-layout}/GUIDE.md`, `services/mcp/server.py:479,1163-1164` | `BR_20260707_bom_proposal…` · `BR_20260707_c03_stage_entry_gate…` |
| `layout-route` | **unassigned** | `packages/eda-bridge/bodesign_eda_bridge/routing.py`, `Dockerfile.ee`, `docker-compose.workers.yml`, `server.py:1334-1385` | `BR_20260802_freerouting_jar_default_path…` · ~~`BR_20260729_ee_worker`~~ ✅closed · ~~`BR_20260729_preflight`~~ ✅closed |
| `(default)` | `ses_04db7a1c5ffelvbxyLP1p6xlRH`（coordinator） | everything not claimed above | — |

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
| `BR_20260729_ee_worker` | self-superseded → **closed 2026-08-02** |
| `BR_20260729_preflight` | all §A–§L fixed (not just the 2 sections the survey saw) → **closed 2026-08-02**, after correcting a false "already fixed" record inside it |
| `KB_20260729` | targets landed AND the adjudication happened → **PARTIAL**, stays top-level: the lint misses its own live counterexample |
| `BR_20260719_c01_photoreal` | **rewritten 2026-08-02** — credential half deleted; the undone part is bigger than thought (shipped verb is text-to-image; this BR's pathway is image-to-image) |

**Re-verification changed three of five verdicts.** The pre-archival adversarial
pass (`ses_03f060b48`, briefed to *falsify* the staleness call) turned two
"archive it" into "archive it, but file the defect it hides first" / "keep it
open with a named remainder", and one "half-stale" into a larger gap. **A survey
that only confirms is a survey that was not attacked.**

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

### `c03-stage-discipline` — `ses_0c87bab06` declined (2026-08-02), **and corrected my root cause**

Probed because its title ("C03 有據建議電路設計能力層") names the family's core file.
It declined ownership — but the reply's value was not the decline; it was that
**my survey's root cause was wrong in a way that changes the fix**.

**What I had concluded (from grep):** `check_c03` is built but unwired — zero call
sites in any C04 entry, so `GUIDE.md:507`「C04 entry is refused while…」is prose.

**What is actually true (peer's finding, coordinator re-verified at HEAD):** the
C03→C04 entry **does** have a live gate — `c04_layout_constraints.py:144
_assess_upstream_fulfilment`, called at `:321`/`:359`, and it really blocks
(`:369-372` → `status = "blocked_upstream_c03_missing"`, comment self-describes as
"The load-bearing fix"). But it checks only whether **three files exist**
(`C03-EE/`, a `.net` netlist, `Mechanical_Constraint_Export.json`).

| | `_assess_upstream_fulfilment` (**wired**) | `check_c03` (**unwired**) |
|---|---|---|
| asks | did C03 **run**? (do files exist) | is C03's delivery **acceptable**? (BOM schema / readiness / drawability / SSOT) |
| blocks | yes | no — zero callers |
| covers BR_20260707's 4 ACs | **none of them** | all four |

The BR's symptom class — BOM carrying draft/blocked rows, Pin_Allocation conflicts,
unsynced pad counts — occurs precisely when `C03-EE/` and the `.net` **do** exist.
So the wired gate returns `fulfilled: true` and waves it through.

> **An existence check standing where an acceptance check belongs.**

**Why the wording matters:** "the gate isn't wired up" implies the fix is wiring.
It isn't — the position is **already occupied, by something that returns green**.
Connecting `check_c03` requires first deciding its relation to the incumbent
(chain? replace? demote the incumbent to tier-0?). That is a design adjudication,
and any survey that asks only "does the C04 entry have a gate?" gets "yes" and stops.

**Two further facts, coordinator-verified independently:**

- **`check_c03` is not a landing verb.** Zero hits in `skills/bodesign/scripts/gate.py`
  (control: same file has 235 def/verb hits, so the grep is live). It exists only on
  the MCP container tool surface — so even "an agent runs it by hand on the host" is
  not a low-friction path.
- **`check_c04` does not exist.** Repo-wide, the only occurrence is inside
  `server.py:1164`'s own description string, which calls itself "the entry counterpart
  to check_c04's output gate". Control: the same pattern shape for c03 returns 7 hits.
  **`BR_20260707_c03_stage_entry_gate`'s Root Cause premise ("only a C04 output gate
  exists") is therefore expired** and must be corrected when it is dispatched.

**Boundary changes accepted from the probe:**
- **added** `c04_layout_constraints.py` (the actual incumbent) and
  `skills/bodesign/scripts/gate.py` (landing-plane registration)
- **removed** `c04_placement_gate.py` — it guards placement→routing (owner approval
  marker), a different gate at a different stage boundary; keeping it blurs the family
- **removed** `BR_20260707_ccm_workflow_bypasses_webdav_cache` → `(default)`. "A rail
  exists but the workflow didn't pick it" and "a gate was never wired" do not share a
  root cause. **A shared file is not a grouping criterion** — `doctrine.md`/`GUIDE.md`
  are the repo's widest shared surface, and by that standard almost any BR could be
  filed under almost any family.

**Why this family still must not start from zero.** A fresh handler would
re-discover the incumbent gate, and would *not* know that `check_c03.py` grew
927→1200+ lines across the BR_20260730 family's 19 rounds — it would bring a
927-line worldview to a substantially evolved file. Hence the cross-ref in the
family row: `ses_0c87bab06` stays injectable and answers same-round for any change
to `check_c03.py`'s internal rules, without owning the family.

**Methodological echo of the `schematic-engine` probe:** that session was hot on
*a neighbour*, not the body — it owns `check_c03`'s interior (1 of the family's
files) and is cold on the C04 side, which is exactly where the fix decision lives.
Two probes, two declines, two different reasons — and both declines carried
information no acceptance would have.

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
