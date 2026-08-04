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
| `schematic-engine` | **unassigned** — 2 sessions probed · both declined (`ses_0c8efa1b4`, `ses_0c87bab06`; see notes). **`(default)` has been working this surface directly since 2026-08-02** (see §Membership below) | `packages/eda-bridge/bodesign_eda_bridge/{kicad_emit,composer,fidelity}.py`, `tests/test_{fidelity_gate,kicad_emit}.py`, `plans/eda-bridge_draftsman-series-divider-wireable/` | **20 top-level BRs**, not the 4 listed here through 2026-08-02 — enumerated in §Membership. The four originally listed: `BR_20260723b_power_ports_false_not_bypassed` · `BR_20260723e_draftsman_cannot_wire_basic_series_divider_collinear_fusion` · `BR_20260802_reset_hard_destroyed_kicad_emit…` (**restored, verified `2efc3a9`+`23c0bc7`**) · `BR_20260802_fidelity_gate_is_red_after_restore…` (**P1, 電氣正確性**) |
| `silent-success` | **unassigned** — `ses_03edcab76` 以 handler 身分修完 BR_20260731（已遣散），未任 owner | `packages/component-kb/bodesign_component_kb/vault.py`, `packages/workflow-core/bodesign_workflow_core/{reference_crosscheck,checkers/no_silent_degradation}.py`, `packages/eda-bridge/bodesign_eda_bridge/pin_allocation.py`, **`skills/bodesign/engines/kicad/scripts/domain_detectors.py`**, `ragbase/control/no-silent-degradation/` | ~~`BR_20260731_vacuous_pass…`~~ ✅closed (`b429b06`+`3de27b2`) · `KB_20260729…` (**PARTIAL**) · `BR_20260802_no_silent_degradation_lint_default_roots_miss_skills` |
| `c03-stage-discipline` | **unassigned** — `ses_0c87bab06` probed · declined · `ses_03edbc893` 以 handler 身分修完 entry-gate（已遣散）. **cross-ref: `check_c03.py` 內部語意由 `ses_0c87bab06`（BR_20260730 family，§A–§Q 19 輪）演進至 HEAD；動它的內部規則前先 inject 那顆。——行數更正：磁碟實況 927 行，前述「1200+」為二手轉述未經查證** | `packages/workflow-core/bodesign_workflow_core/{check_c03,c04_layout_constraints}.py`, `skills/bodesign/scripts/gate.py`, `skills/bodesign/stages/{c03-ee,c04-layout}/GUIDE.md`, `services/mcp/server.py:479,1163-1164` | `BR_20260707_bom_proposal…` · ~~`BR_20260707_c03_stage_entry_gate…`~~ ✅closed (`ff7bbbf`+`787bb5e`) |
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

**Open question it raised — RESOLVED 2026-08-02 (coordinator):** it asked whether
`ses_0716c7745` (schemdraw template bank) *removed* the draftsman wire engine rather
than adding an alternative, which would make `BR_20260723e` moot. **It added.**

- `composer.py:1737-1738` still validates `style in ("netlist", "draftsman")` and
  raises otherwise; 9 live branches consume it (`:1826`, `:1944`, `:2294`, `:2401`,
  `:2445`, …). `server.py:1130`'s schema enum still offers it. Dedicated regression
  suite `tests/test_composer_draftsman.py` exists.
- schemdraw lives somewhere else entirely — `skills/bodesign/engines/kicad/scripts/schemdraw_templates/`
  (skill-engine side), not in `packages/eda-bridge`. Different layer, not a replacement.
- Control group: the same grep shape returns 5 files for `draftsman`, so the
  schemdraw search was live, not a dead pattern.

**`BR_20260723e` stands.** Apply the peer's ordering rule: capture 723b's repro as a
pytest fixture before 723e lands.

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

## Membership — measured 2026-08-04, and it is 5× what this file said

The `schematic-engine` row listed **4** members. A count over the actual issue
bodies returns **20**. That is not drift in one row; it is the row having become
decorative while the work went on somewhere else.

```
top-level BR/KB                     30
  text names the eda-bridge surface 20   <- schematic-engine territory
  does not                          10   (control: nonzero, so the pattern is
                                          not simply matching everything)
```

**How the count was reached, including the part that was wrong first.** A first
pass keyed on the `Component:` header field, or on a `packages/eda-bridge` path
in the body, and returned **13**. `BR_20260723b` — a member this file itself
lists — was NOT among them: it has no `Component` field and cites
`kicad_emit.py:1377` with no directory. Bare module names had to be counted too.
**A membership probe that misses a member the registry already names is not
measuring membership**, and the 13 would have read as a plausible number.

**Two structural facts this exposes, both more useful than the number:**

- **`Family:` is not a routing key.** 13 of 30 top-level BRs carry the field;
  **17 do not**. Any dispatch procedure that begins "look up the BR's family"
  silently covers less than half the ledger. Routing works off the fix surface
  named in the body — which is why the count above is text-based, not field-based.
- **19 of 30 have no `Component` field at all**, so they cannot be routed
  mechanically even by surface. That is the gap to close before this registry can
  carry dispatch weight.

**And the honest part:** `(default)` (the coordinator) has been landing commits
on this surface since 2026-08-02 — `cedc262`, `fbcc7f3`, `4be52bf`, `f37a8c7`,
`316150f`, `392200d`, `31d537b`, `4a58fdf`. That is legitimate under §4.3.2
(unclaimed families route to `(default)`), but it means **"unassigned" here has
not meant "unattended" for two days**, and a future reader would have inferred
the opposite. Recorded rather than quietly normalised: the reason two probed
sessions declined was that the family needs a durable mental model of wire
geometry and net partition, and doing the work case-by-case out of `(default)`
does not build one — it just keeps the queue moving.

---

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


### `schematic-engine` — `ses_0c87bab06` declined the family, offered the single BR (2026-08-02)

第二顆探測到的 session，**與 `ses_0c8efa1b4` 的拒絕理由方向相反且同樣正確**。

它在復原 `kicad_emit.py` 的過程中累積了這個檔案最厚的即時 context——逐函式算過傳遞閉包、
做過三方 A/B 量測、知道 HEAD 版與 recovered 版有 6 個函式本體不同。那份 context 當時沒有第二個人有。

**但它拒絕 family ownership，理由是分層的**：

> 我熱的是 `composer.py` 的 API 揭露面（provenance / typed error / schema），
> 冷的是 wire-geometry 與 net partition 的**演算法層**——那正是 `test_fidelity_gate` 紅燈的所在。
> 接下來會變成我拿 BR 的敘述去猜一個我沒有心智模型的子系統。

**這比「我不熟」精確得多**：它區分了「我碰過這個檔案」與「我有這個子系統的心智模型」。
`ses_0c8efa1b4` 拒絕時說「我熱的是鄰居不是本體」，這次是「我熱的是同一個檔案的**另一層**」。

**兩次探測共同確立的判準**：*檔案共用不是歸族依據，**同檔不同層**也不是*。

它另外交出兩格對派工有用的資訊（已寫進紅燈 BR）：

1. `test_fidelity_gate` 是**唯一**「還原讓它從沒開機變成紅燈」的模組；其餘 12 筆是
   「本來就紅、只是被 loader error 壓縮成 1 筆」。**不同類，不該混進同一份 handler brief。**
2. `only_candidate=0` / `moved=0` 是強約束——沒有節點跑到錯的 net，是**整段連接消失**。
   嫌疑收在「wire fusion / label collision 把兩條 net 熔成一條」，不是佈線或編號邏輯。
   **handler 不會自己得出這個推論，它只會看到 6≠9。**

值星官裁決：**接受拒絕**。紅燈是電氣正確性缺陷（J1 連接器與 R1/R2/R5 接點消失），
值得給有原作脈絡的人，而不是給手上有 context 的人——**那兩者這次剛好不是同一個人**。

#### 但它同時提議接下**單張 BR 的 RCA**——已授權（2026-08-02，第二輪）

它的提議把「做 RCA」與「動修法」拆開，而那條線正好落在它自陳的冷熱邊界上：

> 把 `BR_20260802_fidelity_gate_is_red_after_restore` 這一張指給我（單張，不是 family），
> 我做 RCA 到根因坐實為止，然後交證據給 family owner。
> **我不會在沒有原作脈絡的情況下動 wire geometry 的修法。**

**已授權，範圍精確如下**：

| | |
|---|---|
| 授權 | 該單張 BR 的 RCA，做到根因坐實 |
| **不**授權 | 修法落地。RCA 完成交證據回值星官，修法另行派工 |
| **不**指派 | `schematic-engine` family——本列維持 `unassigned` |
| 一律不得 | commit 修法 / restart / merge；取證需臨時改動走快照 ref |

**這是本 registry 第一筆「單張授權、非 family」的紀錄**，值得留下形狀：
family ownership 要的是**長期心智模型**，單張 RCA 要的是**當下最厚的取證 context**。
這次兩者分屬不同條件，硬要綁在一起只會逼出一個錯誤答案——
要嘛讓沒有心智模型的人去修 wire geometry，要嘛讓最有 context 的人閒置。

**授權裡加了一條它沒要求的約束**：它交出的
`only_candidate=0 / moved=0 ⇒ 整段連接消失，嫌疑在 wire fusion / label collision`
被明確標為**起點假設，不是前提**。要求回報時三態（證實／推翻／未定），
且**推翻比證實更值得回報**——若 `only_candidate=0` 有第二種成因
（節點在 candidate 側根本沒被產生，而非被熔掉），那比修好它更重要。

理由：那個約束是**它自己從自己的量測推出來的**，而它同時是唯一的取證者。
一個人既提出假設又獨力驗證時，假設會悄悄變成前提——這與本 session 全天記錄的
「缺席與失敗共用輸出」同族，只是發生在**推論**而非**指令**上。
