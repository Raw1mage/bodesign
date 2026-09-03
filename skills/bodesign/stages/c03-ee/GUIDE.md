# C03 EE — Electrical Engineering: design definition → schematic → BOM → netlist → bridges

## Purpose & scope

C03 turns the product intent (C00) and interface constraints (C01) into the **electrical
truth** of the board: a design definition, a captured schematic (KiCad), a complete machine
BOM, a netlist (pin → net), a GPIO/interface pinmap, a power-frontend diagram, and the
`Mechanical_Constraint_Export.json` that bridges back to ME (C02) and forward to layout (C04).

This stage HAS an execution engine — the **KiCad analysis engine** at
`../../engines/kicad/` (full reference: `../../engines/kicad/ENGINE.md`). You do not eyeball a
schematic and assert it is correct; you run `analyze_schematic.py`, read its structured JSON,
and every finding you carry forward keeps its `confidence` label and `evidence_source`.

**C03 owns:** electrical architecture, schematic capture/review, regulator + power-tree design,
component selection (with provenance), pin allocation, net connectivity, signal-integrity
*requirements* (the numbers C04 must hit), and the C03→C02/C04 mechanical bridge.

**C03 does NOT own:** board outline, placement, routing, stackup, impedance *realisation*
(that is C04 — you hand it the target Z0 and length-match groups, it makes copper meet them);
SPICE/EMC/thermal *verdicts* (C06 runs those — you name the plan); final sourcing/ordering
(the `bom` skill + distributor skills do the pricing/stock/order). You produce the netlist and
the constraint export; you do not relax a requirement to make a downstream gate pass.

## Required deliverables — Definition of Done

> **`readiness_pct: 100` ≠ done.** The readiness tools enforce this table as a machine-checkable
> manifest: the real gate is **`dod_ok: true`** in the readiness output — true only when every row
> below is `present` (or honestly deferred via a `dod_status.json` entry) and no `answered` field is
> fake-complete (a `TBC`/placeholder value). Read the `guide_compliance` block, not the bare percent.

Produce **all** of these before you report C03 done or hand off (see SKILL.md § "Definition of
Done"). Each exists on disk **or** carries an explicit `draft`/`blocked` status with a reason — a
connectivity gap is documented in `Netlist_Status.md`, never silently dropped.

| # | Required artifact | File | Notes |
|---|---|---|---|
| 1 | Design definition + architecture | `Design_Definition.md` / `EE_Design_Specification.md` + `Architecture.md` (or a merged `Architecture_and_BOM.md`) | `draft` until a named EE owner signs off |
| 2 | Power tree | `Power_Tree.md` (+ `..._power_frontend.svg`) | rails, decoupling, budget |
| 3 | Schematic | `generated/sch*/*.kicad_sch` | or the honest interface subset; MPNs on properties |
| 4 | Complete BOM | `BOM.csv` / `..._完整BOM.xlsx` | exported from the *verified* analyzer JSON |
| 5 | Netlist | `..._網路表.xlsx` / `.net` | full, or honest subset |
| 6 | GPIO/interface pinmap | `..._GPIO_pinout.xlsx` / `Pin_Allocation.csv` | drives C05 |
| 7 | Netlist status | `Netlist_Status.md` | required **iff** a full netlist is not recoverable |
| 8 | Mechanical bridge | `Mechanical_Constraint_Export.json` | `approval=false` |
| 9 | PRD-BOM crosscheck report | `prd_bom_crosscheck.report.json` | `gate: PASS` required; report absent = gate **not run** (never presume PASS) — § 3b |
| 10 | C03 stage-entry gate report | `check_c03.report.json` | `gate: PASS` required — R1 schema / R2 readiness / R3 symbol-source **claim** / R4 SSOT / R5 BOM↔netlist / R6 pin-spec polarity (`bodesign_check_c03`); absent = **not run** — § 3c |

> **Landing-verb prerequisite (BR_20260903a).** `gate.py` executes out of the bodesign `packages/`
> tree. When the skill is projected outside the bodesign checkout (XDG install at
> `~/.local/share/opencode/skills/bodesign/`, which ships **no** `packages/`), export
> `BODESIGN_SRC=<bodesign repo root containing packages/*>` **before** the first `gate.py` call —
> otherwise every landing verb fails with `LANDING_PACKAGES_NOT_FOUND`. `gate.py --list` reports
> the answer as `result.packages_resolved` (it stays `ok:true` either way — read the field, not `count`).

**Self-verify:** run `analyze_schematic.py` and clear (or explicitly justify) every `high` finding —
no open DS-001 / SS-001 / PP-001 / RS-002. There is **no `c03_readiness` verb**; the analyzer's gate
is your self-check, plus the `package_readiness` landing verb (`gate.py package_readiness --repo
<abs-project>` — NOT an MCP tool) for the roll-up. Model:
`thesmart_products/rockbox/c03-ee/` (note its merged `Architecture_and_BOM.md`).

## Inputs (from upstream)

- **From C00 (PRD):** the product thesis, target market / certification target (gates review
  severity — see `../../engines/kicad/references/design-intent.md`), power source (battery vs
  mains vs USB), feature list that drives the block diagram. Read `../c00-prd/`.
- **From C01 (ID/UX + interfaces):** the interface/connector list, external-port inventory
  (USB-C, RJ45, camera, SD…), user-I/O (LED, button), enclosure-driven edge preferences. Read
  `../c01-id/`. These become rows in your Interface Definitions and openings in the mechanical
  export.
- **For a *derived* or *reverse-engineered* board:** a reference schematic PDF / published
  pinout / glb model in the gitignored `refs/` vault. Treat it as evidence to cite, never as
  something to copy (honesty rule 7). Label every reconstructed fact as reverse-engineered.

## SOP

The flow is: define → capture → analyse → verify against datasheets → cross-check → export.
Steps 1–2 are authoring; 3–6 drive the engine; 7–8 are the bridges.

In all commands, `ENG=../../engines/kicad/scripts` (the KiCad engine script dir). Prefer
`--analysis-dir analysis/` so every run lands in one timestamped folder tracked by
`analysis/manifest.json`.

### 0. Ingest the refs SSOT first (refs-first gate)

Before authoring anything, run the **`refs_ingest`** landing verb (`folder` = the stage dir or an
explicit `01_refs/` path; via `gate.py`): it scans the stage's `01_refs/` SSOT into a read-only,
authority-ranked source manifest (absent root → `root_visible: false`, loud — never a clean empty).
C03 is where fabrication-adjacent claims are born — pin allocation, BOM lines, netlist connectivity
— and every one of them must trace back to an `01_refs/` source, because downstream C04 runs
`c04_dod_traceback` against provenance anchors of the form `<ssot_file>:<locator>`: an item with no
anchor is `untraceable` (憑空發明) and **blocks** the C04 DoD. Build the manifest first, cite
against it as you author (steps 1–2), and keep the anchors in the exported tables (steps 7–8) so
the traceback gate has something to verify.

### 1. Write the Design Definition + Architecture

Author `Design_Definition.md` (or `EE_Design_Specification.md`): design intent, the block
architecture (a table of blocks → key parts → datasheet/reference provenance), the power tree,
the key interfaces, and a "design/verification notes for C06" section. Add an `Architecture.md`
block diagram. **Use a functional/circuit block diagram (functional blocks + buses/interfaces) for
EE architecture — NOT a C4-model container diagram.** C4 (Context/Container/Component) is a
*software*-architecture notation and is the wrong tool for describing a circuit; the same applies to
C04. Power distribution may use IDEF0; signal/data flow a flow diagram — but the system/host
architecture is a functional block diagram. **Do not hand-author this SVG** — for the host /
MCU-centric form (center SoC + peripherals radiating to the four sides + buses) emit it with the
`c03_emit_host_block_diagram` landing verb (via `gate.py`; MODEL = {center_part, peripherals[{name,
side, bus?, type?}], reference_baseline?}); for a board-level core↔carrier split / fan-out use the
`c03_emit_partition_diagram` landing verb. Both are deterministic, layered, honest-boundary-gated
emitters (see SKILL.md concept-diagram router). For a **derived product**, pass
`reference_baseline` so the diagram honestly carries the derived-from / diffs / sourcing-gates
provenance. Model these on the real examples — see
`thesmart_products/openmv/C03-EE/03_output/Design_Definition.md` and
`thesmart_products/openmv/N6_board/C03_EE/{EE_Design_Specification,Architecture,Power_Tree,Interface_Definitions}.md`.

Once the key parts are chosen, **re-run the feasibility triage on the firm component set**
(`../../references/feasibility-triage.md`: `classify_product_feasibility(..., source="C03-componentset")`)
— now the finest BGA pitch, high-speed-net count, and layer estimate are real, so the tier becomes
`confidence: firm`. If it rose above what C01 declared (e.g. C00 looked Tier-2 but the chosen SoC is a
0.4 mm BGA → Tier-3), that is a reconciliation routed to C00/C01 to re-set the delivery expectation —
not a surprise to bury until C04 can't route it.

Mark the document `draft` with a reason until an EE owner signs off ("未核可;佈局凍結前需 EE
設計審查 gate"). An unsigned spec is `draft`, not silently "done" (honesty rule 3).

If this is a reverse-engineered baseline, write a `Reverse_Engineering_Report.md` first: state
your **method**, what was **reliably extracted** vs what **needs original CAD**, the whole-board
inventory (component/net/pin counts), and the block architecture. Label it reverse-engineered
throughout. See `thesmart_products/openmv/C03-EE/03_output/Reverse_Engineering_Report.md`.

### 2. Capture the schematic — generate via the MCP, or author in KiCad

Produce `.kicad_sch` sheets (one per block for a large design — e.g. `generated/sch_memory/`,
`sch_rgmii/`, `sch_sensors/` in the aiguard example) plus a `symbols/` library for non-standard
parts. Put MPNs and `Datasheet` URLs on the symbol properties as you go — the analyzer's
sourcing gate (SS-001/002/003) and the datasheet sync both key off MPN coverage.

**Primary path — bodesign MCP (when reachable; see `../../SKILL.md` § "Relationship to the
bodesign MCP server"):** generate rather than hand-draw.
- `bodesign_emit_symbol` for each non-standard part (pins + footprint filter + datasheet).
- `bodesign_compose_schematic` (`out_dir`, `project_name`, `spec`, `symbol_dirs`, `validate=true`)
  to place + net a schematic from the structured design spec; it returns `placed`, `nets`,
  `unresolved_pins`, and a `kicad-cli` validation block. Resolve `unresolved_pins` before moving on.
  **The `spec` is the output of reasoning, not a given** — derive it with the pinout→circuit method
  in `references/pinout-to-circuit-method.md` (classify each pin's obligation → ground in the
  reference design → complete each interface), so every net traces to a datasheet requirement rather
  than being invented to fill the spec.
- the `pin_allocation` landing verb (`nets`, `mcu_refs`; via `gate.py`) to derive the GPIO/peripheral map for step 7/FW.

**Standard step — render readable, deliverable-grade schematics.** Produce directly-openable
`.kicad_sch` sheets that KiCad's own engine renders to white-background PNGs, with chips as true
4-edge symbols, the MCU drawn as the hub, and a hybrid connection style (discrete R/C/decoupling as
wired networks, wide buses by net label). The full ruleset — and the **why** behind each rule, since
every one came from a real failure (one-sided strips, crammed connectors, off-canvas clipping,
text overlap, empty-yet-crammed layout) — is in **`references/schematic-drawing-rules.md`**. Read it
before generating or modifying schematics; the rules are load-bearing, not style preferences.

Pipeline (scripts in `engines/kicad/scripts/`; deps: `kicad-cli`, `pip install cairosvg`):

```sh
symbol_4edge.py  in.kicad_sym out.kicad_sym          # every symbol incl. stock connectors -> 4 edges
host_from_pinmap.py Pin_Allocation.csv mcu.kicad_sym host.net   # draw the MCU body (the core chip)
netlist_to_kicad_sch.py <sub>.net out.kicad_sch      # hybrid compose (symbols/ resolved beside .net)
render_hybrid_sch.sh out.kicad_sch out.png           # kicad-cli svg --exclude-drawing-sheet -> white PNG -> autocrop
```

The single most important rule (the RCA for the recurring overlap/clipping/empty churn): **one
text-extent model drives cell sizing, ref/value placement AND the page size** — when they diverge you
under- and over-estimate at once. After rendering, **verify no-clip** (autocropped ink must not touch
any image edge). A quick netlistsvg connectivity preview exists (`netlist_to_schematic.py`) but is
**not** a deliverable — netlistsvg can't draw 4-edge symbols.

**Fallback — manual KiCad capture** (MCP absent, or a reverse-engineered baseline with no spec to
generate from): author the `.kicad_sch` by hand as above.

Either way, the generated/authored schematic is **unverified** until step 4–5. Generation ≠
correctness — do not skip the analyzer because a tool produced the file.

If a full CAD capture is out of scope (reverse-engineered baseline, no original CAD), say so and
deliver the *interface + major-IC* connectivity instead, with a documented gap — see step 6 and
`Netlist_Status.md`. Do not invent a schematic to look complete.

### 3. Sync datasheets (verification prerequisite)

Datasheets are what turn a *consistency* check into a *correctness* check. Without them the
engine can only confirm the design agrees with itself. Sync before reading any analyzer output:

```bash
python3 ../../engines/datasheets/../digikey/scripts/sync_datasheets_digikey.py <file.kicad_sch>
# DigiKey best (direct PDF URLs); element14 reliable; lcsc for LCSC-only; mouser last resort.
```

The engine exposes the `datasheets` and `emc` bridges via `../../engines/datasheets` and
`../../engines/emc` symlinks. If sync fails or no API keys exist, fall back to the `Datasheet`
property URLs, the `digikey` skill for individual parts, or **ask the user** — do not silently
skip verification. Datasheets cache into `datasheets/` with a `manifest.json`; extractions land
in `datasheets/extracted/<MPN>.json` and are reused across runs.

### 3b. Vault-Absent Substitution Protocol (MANDATORY when a PRD-named part is unavailable)

When the vault has no datasheet for a part the C00 PRD names (G4 cold start) and you must
substitute, the substitution decision is **not yours to make freely**. The C00 manifest
(`main_components_structured.json`, extracted from `s04_system_architecture.main_components`
and human-audited) is the envelope SSOT:

1. **Check the envelope first.** Compare your candidate against the role's
   `allowed_alternatives` in the manifest. An in-envelope match (e.g. an NPN linear current
   sink where the PRD says "NPN/resistor linear current sink or AL5809-ish CC regulator") may
   be adopted directly — record it in the C04/C06 handoff as `substituted (in_envelope)`.
2. **Out-of-envelope = BLOCKING, always.** If the candidate matches neither the role's primary
   `patterns` nor any `allowed_alternatives`, STOP. List the options (restore the PRD-named
   part via datasheet ingest, pick an in-envelope alternative, or ask the user to approve the
   out-of-envelope substitute) and wait for the user's decision. Never pick the landing point
   yourself. Case law: the E2E LED-driver board degraded "linear current sink" into a bare
   ballast resistor — a resistor is **not** a current sink; the board shipped Gerbers that
   could not meet the PRD's 60 mA ±10% target
   (`issues/BR_20260703_prd_bom_crosscheck_gap_cc_regulator_missing.md`).
3. **`approvals[]` is user-owned.** An out-of-envelope substitute becomes non-blocking only
   through an `approvals[]` entry in the manifest (`role` / `substitute` / `approved_by:
   "user"` / verbatim `quote` / `date`) — written only on the user's explicit instruction.
   The agent never writes an approval on its own.
4. **Gate before C04.** Run the MCP tool `bodesign_prd_bom_crosscheck` (`manifest_path` +
   the exported netlist) before entering C04. Every role must come back `present` or a
   non-blocking `substituted`; a `FAIL` gate (any `missing` role, or an unapproved
   out-of-envelope substitution) refuses C04 entry until the design is fixed or the user
   records an approval. A degraded schematic that passes ERC is still a non-conforming
   deliverable — ERC checks self-consistency; this gate checks PRD fulfilment.

### 3c. BOM 提案必讀清單 + SSOT 衝突自查段（MANDATORY，先讀後提）

R4 的 BOM↔SSOT 衝突（U4 wireless-scheme 的類別：BOM 提了一顆 pin allocation 從未帳到的
主動件）之所以要到 C04 才被碰撞發現，根因是 **BOM 提案時沒有把 pin-allocation SSOT 當前提
讀進來對照**。以下把「先讀」變成硬性前置，把「衝突自查」變成必附段落。

**提出任何 BOM 行之前，必讀（缺一即不得宣稱 BOM ready）：**

1. `Pin_Allocation.csv`（本階段 pin 分配 SSOT）——確認 BOM 的 active 件（`U*` / `J*` /
   `Y*` / `SW*`）都在 pin 分配裡有著落；BOM 若引入 pin 分配沒有涵蓋的 active 件 = 衝突，
   不是新增。
   > **schema 裁決（BR_20260730）**：本檔的權威形狀由交付物表第 6 項定義——
   > **ball → GPIO → peripheral function 的 pinmap**（見上表與 §「Deliverables」的
   > `exported` 註記）。它**沒有 ref 欄**，這是設計如此，不是缺漏。fleet 內 4 份
   > `Pin_Allocation.csv` 全部遵守這個形狀。
   > 因此 `check_c03` 的 R4 **ref 級**比對只在檔案另外帶有 `ref`/`refdes`/`component`
   > 欄位時才適用；ball/peripheral 形狀的檔案會回報
   > `ssot_crosscheck.status = "not_run"` 並列出未被驗證的 active ref，**而不是**把
   > 每一個 active 件都報成衝突（修前實測：26 個 active 件全部被誤報為
   > 「BOM↔SSOT conflict — owner must reconcile」，讀起來像 26 件真實待裁決事項）。
   > 本條的「必讀」義務是**人工前置**，不因 R4 不適用而免除。
2. `Interface_Definitions.md` + C01 連接器/外部埠清單——確認接口方案（有線 vs 無線、
   哪顆 PHY/無線模組）在 BOM 與 pinmap 之間**單一**、不並存兩套。
3. `main_components_structured.json`（C00 role 封套 SSOT）——候選件落在 role 的 `patterns`
   / `allowed_alternatives` 封套內；越界走 §3b 的 approvals 流程，不自行落點。
4. `frozen_pad_counts`（若 J_* 已凍結）——連接器 pad 數必須與凍結值一致，改動要回 C02/C04
   重新凍結，不在 BOM 端偷改。

**BOM 交付必附「SSOT 衝突自查」段（固定格式，逐項填、不得留空）：**

```md
## SSOT 衝突自查 (C03 BOM ready 前置)
- Pin_Allocation 對照: <PASS | CONFLICT: ref 清單 | N/A: pinmap 無 ref 欄（R4 not_run）> — 每個 active BOM 件是否在 pin 分配裡有著落
- BOM↔netlist 對照 (R5): <PASS | CONFLICT: ref 清單 | NOT_RUN: 未提供 netlist> — BOM 每一行是否真的被畫進 schematic（**與 R3 不同**：R3 只看那行有沒有宣告 symbol 來源）
- 接口方案單一性: <PASS | CONFLICT: 說明> — 有線/無線、PHY/模組是否僅一套 (U4-class 檢查)
- Role 封套 (C00): <PASS | OUT-OF-ENVELOPE: role→substitute + 是否已 approvals[]>
- 連接器 pad 凍結: <PASS | N/A | MISMATCH: ref 期望 vs 實際>
- 自查結論: <READY | BLOCKED: 待決事項清單>
```

每列必須是 `PASS` 或明列衝突內容 + 負責人/待決；**禁止**用「大致沒問題」等模糊字帶過
（no-silent-fallback 天條）。此段是 `bodesign_check_c03` 機檢的人類對應面——自查段說 READY
但 `check_c03` 回 `gate=FAIL`，以機檢為準、回頭修設計或補 approvals。

**機檢 gate（§ Gate 引用）：** 提完 BOM，跑 `bodesign_check_c03`（`bom_csv` + 選配
`pin_allocation_csv` + `frozen_pad_counts`）作為 C04 **入口** gate；R1 schema / R2 readiness /
R3 drawability / R4 SSOT 任一 blocking 即 `gate=FAIL`，拒絕進 C04，直到修正或使用者記錄
approvals。這是 §3b `prd_bom_crosscheck`（PRD role 履行）之外、針對 **C03 交付完整性**的
互補入口關卡：前者問「PRD 要的角色到齊了嗎」，後者問「BOM 本身可繪、就緒、與 SSOT 不衝突嗎」。

### 4. Run the schematic analyzer

```bash
python3 $ENG/analyze_schematic.py <file.kicad_sch> --analysis-dir analysis/
# Stage/audience filtered views:
python3 $ENG/analyze_schematic.py <file.kicad_sch> --stage schematic --audience reviewer --text
# Network + MPNs available → fold in obsolescence/EOL audit:
python3 $ENG/analyze_schematic.py <file.kicad_sch> --lifecycle --analysis-dir analysis/
```

This emits ~60–220 KB JSON: components/BOM, full nets (pin→net), detected subcircuits
(regulators with Vout + `vref_source`, dividers, RC/LC filters, crystals, ESD, decoupling, buses,
diff pairs, power-sequencing…), IC pinout analysis, power analysis (PDN impedance, budget, EN/PG
chains), and ERC. Read the JSON directly — don't write ad-hoc extractors. If the shape surprises
you, run `python3 $ENG/analyze_schematic.py --schema` first.

**The output envelope carries the honesty model for you.** Every finding has `rule_id`,
`detector`, `severity`, `confidence` (`deterministic` / `heuristic` / `datasheet-backed`), and
`evidence_source`; the `trust_summary` rolls up `trust_level`, `by_confidence`, and
`provenance_coverage_pct`. When you quote a finding in a deliverable, keep that label — do not
launder a `heuristic` Vout estimate into a bare assertion (honesty rule 2).

Watch these gate findings:
- **DS-001** (datasheet coverage, `high`): no verified claim is possible. Either sync datasheets,
  populate MPNs, or state explicitly that every pin/electrical/regulator finding is *consistency
  only* — and never write "verified"/"confirmed"/"per datasheet" anywhere.
- **SS-001** (MPN < 50 %, `high`): a pre-fab blocker; resolve before any handoff to sourcing.
- **PP-001** (`high`): an IC power pin reaches its rail only through a capacitor (no DC path).
- **RS-002** (`high`): a rail depends on the user closing an open jumper.
- **NT-001**: single-pin/floating net.

### 5. Verify analyzer output against the raw schematic + datasheets

The analyzer can produce plausible-but-wrong results (wrong Vout, wrong pin→net, missing MPN)
without erroring. These flow into your report unless you check. Verify, don't trust:

- **Component count** vs raw `(symbol (lib_id` blocks (minus power symbols) — must match exactly.
- **Pin-to-net** for every IC against the datasheet pin table — the highest-value check; a wrong
  pin map is invisible to ERC and kills the board. Cite the datasheet page/figure in your notes.
- **Transistor/regulator pinout assumptions:** a SOT-23 `lib_id` suffix (`Q_NPN_BEC`…) encodes a
  pinout that may not match the real part. With an MPN, verify against the datasheet; without one,
  assess *plausibility* against the common convention and report the confidence level — "matches
  the most common SOT-23 BCE convention" vs "could go either way" (honesty: show, don't assert).
- **Regulator Vout:** check `vref_source` — `lookup` = datasheet-verified; `heuristic` = a guess
  needing manual confirmation. `vout_net_mismatch` flags >15 % disagreement with the rail name.

Deep checklist: `../../engines/kicad/references/schematic-analysis.md`.

### 6. Cross-check, simulate, and document the connectivity boundary

- **Reference cross-check (do this when a control group exists):** if you have a known-good
  reference netlist (e.g. the source board you derived from), compare net-by-net and report the
  delta honestly — what matched, what is an *extra*, what is *missing*. "269/269 nets matched the
  reference" is a *shown* claim (honesty rule 5). `diff_analysis.py base.json head.json --text`
  compares two analyzer runs.
- **What-if** any value you are unsure of before committing it:
  `python3 $ENG/what_if.py analysis/<run>/schematic.json R5=4.7k --text` (recalculates divider
  ratios, filter cutoffs, regulator Vout; `--fix voltage_dividers[0] --target 3.3` solves
  inverse with E-series snapping).
- **SPICE (analog front-ends):** if `which ngspice ltspice xyce` finds a simulator, hand the
  schematic JSON to the `spice` skill to verify filter/divider/gain math. This is a *plan* item
  for C06's verdict — at C03 it is a sanity check, marked `not-run` in the spec until C06 runs it.
- **Document the honest connectivity boundary.** When source data cannot yield a full netlist
  (no original CAD; a bus configured by boot-ROM and absent from public firmware; ~600 passives
  with no shared identifier between a glb and a lossy schematic PDF), write `Netlist_Status.md`:
  what is *required*, what is *recoverable* and from where, what *is* derivable (named ICs,
  header I/O, power-rail membership), and the **conclusion** that the gap is a *source-data
  limit, not a process failure*. This is the canonical pattern — model it exactly on
  `thesmart_products/openmv/N6_board/C03_EE/Netlist_Status.md`. A documented gap is a finding; a
  back-filled guess is a lie (honesty rule 6).

### 7. Export the deliverable tables

From the verified analyzer JSON (not by hand), export:
- **Complete BOM** — `BOM.csv` (or `..._完整BOM.xlsx`): reference / value / footprint / MPN /
  manufacturer / qty / block. Hand to the `bom` skill for enrichment, pricing, stock, lifecycle,
  and fab BOM/CPL — do not reimplement sourcing here.
- **Netlist** — `..._網路表.xlsx` or `.net`: net → pins (or the honest interface subset per
  step 6).
- **GPIO + interface pinmap** — `..._GPIO_pinout.xlsx`, `..._介面pinmap.xlsx`,
  `Pin_Allocation.csv`: MCU ball → GPIO → peripheral function. Drives FW (C05) and headers.
- **Power-frontend diagram** — `..._power_frontend.svg` (+ `.png`): the input-protection →
  charger → OR-ing → regulators → rails chain. Generate via the `kidoc` engine's power-tree
  diagram or the `drawmiat` skill; keep `Power_Tree.md` as the markdown source of truth.

### 8. Produce the Mechanical_Constraint_Export.json (C03→C02/C04 bridge)

This is the structured handoff that lets ME finalise the enclosure and Layout place connectors.
Export **only explicit C03 values** — component heights, connector openings (with preferred edge
and owner), heat sources (W), antenna keepouts, ESD/EMC notes, and a battery envelope marked
`TBC` if ME has not confirmed it. Board outline, mounting holes, placement coordinates, and final
dimensions stay C04/C02 responsibilities — say so in the `source.notes`. Set
`approval.mechanical_approval` / `layout_approval` to `false`: this export is a handoff, not an
approval (honesty rule 4). Model it exactly on
`thesmart_products/openmv/C03-EE/03_output/Mechanical_Constraint_Export.json`.

Optionally generate an engineering doc package (HDD / power-analysis / schematic-review) via the
`kidoc` engine: `python3 ../../engines/kidoc/scripts/kidoc_scaffold.py --type power_analysis
--analyze --output <md>` then `kidoc_generate.py` for PDF. See `../../engines/kidoc/ENGINE.md`.

## Deliverables

Source-of-truth = markdown/CSV/JSON you author or export; generated = engine/diagram outputs.

| Artifact | File | Kind | Notes |
|---|---|---|---|
| Design definition | `Design_Definition.md` / `EE_Design_Specification.md` | source | intent, blocks, power, interfaces; `draft` until signed |
| Reverse-eng report | `Reverse_Engineering_Report.md` | source | only for derived baselines; method + reliable-vs-needs-CAD |
| Architecture | `Architecture.md` | source | block diagram + component evidence |
| Power tree | `Power_Tree.md` (+ `..._power_frontend.svg/.png`) | source + generated | rails, decoupling, budget (to-confirm) |
| Interfaces | `Interface_Definitions.md` | source | connector → electrical → SI requirement |
| Schematic | `generated/sch*/*.kicad_sch` + `symbols/` | source | KiCad; MPNs on properties |
| Complete BOM | `BOM.csv` / `..._完整BOM.xlsx` | exported | ref/value/fp/MPN/qty/block |
| Netlist | `..._網路表.xlsx` / `.net` | exported | full, or honest interface subset |
| Pinmap | `C03_..._GPIO_pinout.xlsx`, `C03_Pin_Allocation.csv` | exported | ball→GPIO→function |
| Netlist status | `Netlist_Status.md` | source | the honest connectivity boundary (when full netlist is blocked) |
| Mechanical bridge | `C03_Mechanical_Constraint_Export.json` | exported | C03→C02/C04; `approval=false` |
| **Consolidated EE document** | **`<product>_電路設計文件.docx` / `C03_Circuit_Design.docx`** | **generated** | **ONE merged Word doc — see "Document consolidation rule" below** |
| Analyzer runs | `analysis/<run>/*.json` + `manifest.json` | generated | keep; gitignored, manifest tracked |

### Document consolidation rule (the single-doc + `img/` workflow — MANDATORY)

The C03 Word deliverable is **one consolidated document**, not a scatter of per-section `.docx`
files. An earlier C03 emitted nine separate `C03_架構.docx` / `C03_電源樹.docx` / `C03_介面定義.docx` …
files plus a pile of loose `*.png` at the stage root — it was disorienting and created a
"which file is canonical?" ambiguity. The rule, going forward:

1. **One markdown source of truth → one docx.** Author a single merged markdown (e.g.
   `02_build/<product>_完整設計文件.md`) whose chapters ARE the former per-section docs — design
   definition, architecture, power tree, schematic figure set, interface definitions, module-port
   ICD, core-module ICD, board partition, component dimensions, connectivity boundary. Render it to
   ONE `.docx` at the stage root. **Do not** emit a separate docx per source `.md`.
2. **All figures live in `<stage>/img/`.** Collect every deliverable PNG (block diagram, power
   tree, per-subsystem schematics, pinout, processing flow) into a single `img/` folder at the
   stage root. The markdown embeds them by relative path (`![cap](img/<name>.png)`); the renderer
   embeds them into the docx. Do not leave loose figure PNGs scattered at the stage root.
3. **Every figure is referenced + captioned.** A PNG that no document references is either folded
   into the consolidated doc with an honest caption (what it shows, its source `.md`, its
   draft/representative status) or removed. No orphan figures.
4. **Honesty labels survive the merge.** Each chapter keeps its `draft` / `derived` /
   `representative` / `consistency-only` / `not-run` markers — consolidation is a layout change, not
   a status upgrade. Schematic figures stay labelled representative/topological, never "verified".
5. **Render path.** Prefer `bodesign_emit_doc` (md → docx+pdf) when the worker has LibreOffice;
   otherwise use the **docxmcp Mode A** path (the AGENTS-preferred route): stage `body.md` + `media/`
   (or `img/`) + a minimal `manifest.json` (`workflow_state=decomposed`, `format=docx`) →
   `docxmcp_document(action=assemble, doc_dir=<bare-token>, template=cht_template, clean_headings=…)`
   → `docxmcp_document(action=add_front_matter, doc_dir=<bare-token>, cover_spec=…, include_toc=true)`
   for the cover + Word TOC field. **Critical facade contract:** the `document` facade passes a bare
   `tok_XXXX` as the **`doc_dir`** arg, NOT `token` — assemble/add_front_matter read `doc_dir` only,
   so a `token=` call fails with a bare `--doc-dir` usage error. **Numbering:** `cht_template`
   headings carry `numPr` auto-numbering (壹/一/（一）); if the markdown already writes decimal
   chapter prefixes (第 N 章 / N.1), pass `clean_headings=true` to strip the template's numPr and
   avoid double-numbering (壹、第 1 章 …). Cover blocks use cht style names `置中大大` / `置中大` /
   `置中`; the TOC uses `TOC Heading`. **Verify before claiming done:** confirm `word/media/` holds
   every figure, `numPr` count matches intent, the TOC field is present, and render a few pages to
   images for a visual no-clip / no-double-number check. `ok=true` from a tool is not proof — the
   embedded image count and a rendered page are.

### File-naming rule — `C03_` prefix on every deliverable (MANDATORY)

Every **formal deliverable** at the stage root — regardless of extension (`.docx`, `.csv`, `.json`,
`.net`, `.svg`, …) — MUST carry the stage prefix `C03_` (generally `C0N_` for stage N). This makes a
file identifiable as a C03 deliverable on sight, even detached from its folder, and removes the
"which file belongs to which stage?" ambiguity when deliverables are copied into downstream packages
or shared. Examples: `C03_電路設計文件.docx`, `C03_BOM.csv`, `C03_Pin_Allocation.csv`,
`C03_Mechanical_Constraint_Export.json`, `C03_aiguard_power_frontend.svg`/`.net`.

Scope of the rule:
- **In scope:** every tracked deliverable that lives at the stage root (`<stage>/`).
- **Out of scope:** build/intermediate artifacts under `02_build/` and external source under
  `01_refs/` (and `img/` figure-library members, which are already grouped by folder). These are not
  user-facing deliverables, so they are not required to carry the prefix.
- When renaming an existing deliverable to add the prefix, `git mv` it and update every reference
  (README delivery list, source markdown, sibling `.md`) in the same change — no dangling links.

## Gate / done-criteria

C03 is genuinely complete when:
- Design definition is reviewed and signed by a named EE owner (else it is `draft`).
- Schematic analyzer runs clean of **`high`** findings, or each is explicitly justified:
  **no open DS-001** (datasheets synced or the consistency-only caveat stated), **no SS-001**
  (MPN coverage adequate for sourcing), **no unresolved PP-001 / RS-002**.
- Every IC pin-to-net is verified against its datasheet (or the unverifiable ones are flagged
  with a plausibility assessment).
- BOM, netlist, pinmap, and power-frontend are exported from the *verified* JSON.
- `bodesign_prd_bom_crosscheck` has run against the exported netlist and reports `gate: PASS`
  (every `main_components_structured.json` role `present` or non-blocking `substituted` — § 3b).
  A missing report means the gate **has not run**: say so explicitly; never presume PASS.
- `bodesign_check_c03` (C03→C04 stage-entry gate) has run against the exported BOM (+ `Pin_Allocation.csv`,
  the schematic `.net` export(s) via `netlist_path`, and any `frozen_pad_counts`) and reports `gate: PASS`
  — no R1 schema / R2 readiness / R3 symbol-source-claim / R4 SSOT / R5 BOM↔netlist / R6 pin-polarity
  blocker (§ 3c). A missing `check_c03.report.json` means the entry gate **has not run**: say so;
  never presume PASS. This gate is deliverable-completeness; § 3b is PRD-role fulfilment — both must PASS.
- **Write both reports where C04 reads them: pass `out_dir=<project>/C03-EE`.** Since BR_20260707
  these two are no longer prose C04 is trusted to honour — `assess_c04_layout_readiness` reads them
  at those exact pinned paths and refuses entry (`blocked_c03_entry_gate_*`) when either is absent,
  unreadable, `FAIL`, or a PASS whose `netlist_crosscheck` never ran. A gate run without `out_dir`
  leaves no artifact, and from C04's side that is indistinguishable from never having run it.
- **Read the per-check status, not only `gate`** (BR_20260730). Each crosscheck reports its own basis, and
  a `PASS` earned without an input is not the same claim as a `PASS` earned with it:
  - `netlist_crosscheck.status` — `not_run` means **no BOM row was checked against any schematic**; a
    `gate: PASS` alongside it does NOT mean every part is drawn. Also read `boards_not_captured`
    (a board with zero drawn refs needs its schematic captured — a different fix from adding one symbol).
  - `pin_polarity.status` / `refs_checked` — a `run` with an empty `refs_checked` examined nothing.
  - `ssot_crosscheck.status` — `not_run` + `active_parts_unverified` lists what R4 could not verify.
  - **R3 vs R5 are not interchangeable**: R3 asserts the row *claims* a symbol source; R5 asserts the
    symbol was *actually drawn*. R3 passing alone never means the part exists in the schematic.
- `Mechanical_Constraint_Export.json` is produced with `approval=false`.
- If a full netlist is not recoverable, `Netlist_Status.md` documents the source-data limit.
- **Schematic fidelity gate PASS** (when the schematic is engine-composed): `compose_schematic(..., fidelity=True)` returns `fidelity.ok` / diff 0/0 — the emitted net partition matches the spec. ERC passing is NOT sufficient; it is blind to collinear-wire net FUSION. A connector-dense sheet with no fidelity check is `draft`.
- **Render-layer text QA violation = 0** on every schematic page: `render_qa.qa_svg_text(<page.svg>)` over the kicad-cli SVG export. Model-layer / anchor-only QA passing does NOT satisfy this — it has a structural blind spot for pin-name/refdes/value glyphs.
- **One fresh-eyes visual QA pass** after the machine gates are 0: a review subagent reads the rendered PNGs and confirms no smears/black-blocks/broken nets. The machine gate gets you to the door; a human-equivalent look confirms it. (Learned 2026-07-06: 2 rounds shipped "QA passed" that fresh eyes then failed.)

Still `draft` if any `high` finding is unexplained, datasheets are unsynced with claims made
anyway, or a connectivity gap is silently back-filled. SPICE/EMC/thermal *verdicts* are **not**
a C03 gate — they are `not-run` here and owned by C06.

## Honesty notes for this stage

Anchored in `../../references/honesty-model.md`:
- **Every value/net carries provenance** (rule 2). The analyzer's `confidence` + `evidence_source`
  exist precisely so you don't have to launder findings into bare assertions — preserve them.
- **Missing connectivity is a documented limit, not an invented net** (rule 6). `Netlist_Status.md`
  is the canonical artifact: state required / recoverable / derivable / conclusion. Exclude rather
  than guess.
- **Reverse-engineered baselines are labelled as such** — and `refs/` source material is cited by
  path/role, never copied into the deliverable (rule 7).
- **External gates stay external** (rule 4): FCC Part 15 / CE RED / EN 55032 / IEC 62368-1 /
  RoHS-REACH and ESD-lab results are *targets + plans* here. `Mechanical_Constraint_Export.json`
  carries `approval=false`.
- **Show reliability, don't assert it** (rule 5): "269/269 nets matched the reference (control
  group)" beats "robust design". Report extras and misses both.
- Litmus test before upgrading any status: *if the reader fabricated the board tomorrow and
  checked this claim, would it hold?* If not, downgrade and name what is missing.

## Handoff to C04 (Layout) and C06 (Verify)

To **C04 (`../c04-layout/GUIDE.md`)** export:
- the **PRD-BOM crosscheck PASS** (`prd_bom_crosscheck.report.json`) — C04 entry is refused
  while the gate reports `FAIL` or has not run (§ 3b),
- the **C03 stage-entry gate PASS** (`check_c03.report.json`) — C04 entry is refused while
  BOM schema/readiness/drawability/SSOT reports `FAIL` or the gate has not run (§ 3c),
- the verified **netlist** (the connectivity C04 routes — full or the honest subset),
- the **SI requirements as targets** (USB 90 Ω diff; MIPI CSI-2 100 Ω diff length-matched; XSPI
  50 Ω SE DQS-matched; SDMMC 50 Ω) — C04 makes copper meet these; you do not pre-route,
- the **`Mechanical_Constraint_Export.json`** (heights, connector edges/openings, heat sources,
  antenna keepouts) so C04 can place and C02 can finalise the enclosure.

To **C06 (`../c06-verify/GUIDE.md`)** export the same analyzer run as the **reference cross-check
baseline** and the design/verification notes (which checks to run: ERC/DRC, SPICE on analog
front-ends, EMC pre-compliance, thermal on the linear charger, reference netlist crosscheck).
C06 produces the verdicts; C03 names the plan.

## Tools & companion skills

- **`references/ee-design-advisory.md`** — the *design-side* judgment layer: regulator topology
  (LDO/buck/boost) selection, decoupling cascade + dielectric/derating, the **SI requirement numbers
  C04 must hit** (Z0, return paths, 3W, termination, λ/10 threshold), thermal sizing (θJA, copper,
  thermal vias), RF link budget. Heuristics for *what to design*; the engine below still **verifies**,
  the `datasheets` engine backs the part specs, and SPICE/EMC **verdicts** stay in C06 — never assert
  a value a rule of thumb produced but the analyzer/datasheet hasn't confirmed.
- **`references/pinout-to-circuit-method.md`** — the *reasoning method* for the most AI-heavy part of
  C03: going from an extracted chip **pinout → a complete design `spec`**. Classify every pin into its
  mandatory obligation (power→decoupling, boot-strap→defined pull, clock→load caps…), ground in the
  datasheet's reference design, complete each interface, then build+verify. This is what produces the
  `spec` that `bodesign_compose_schematic` consumes — use it in SOP steps 1–2.
- **KiCad analysis engine** — `../../engines/kicad/` (`ENGINE.md`). Scripts in
  `engines/kicad/scripts/`: `analyze_schematic.py` (with `--lifecycle`, `--schema`,
  `--stage/--audience`), `what_if.py`, `diff_analysis.py`, `summarize_findings.py`,
  `cross_analysis.py`/`cross_verify.py` (when a PCB exists), `export_issues.py`. Bridges:
  `../../engines/datasheets`, `../../engines/emc`.
- **Readable-schematic toolchain** (`../../engines/kicad/scripts/`, full ruleset in
  `references/schematic-drawing-rules.md`): `symbol_4edge.py` (pins → 4 edges, datasheet order, incl.
  stock connectors), `host_from_pinmap.py` (draw the MCU body from the pin-allocation CSV),
  `netlist_to_kicad_sch.py` (hybrid KiCad-native compose: discrete R/C as wired networks, buses by net
  label), `render_hybrid_sch.sh` (white-bg autocropped PNG via KiCad's engine). Deps: `kicad-cli`,
  `pip install cairosvg`. `netlist_to_schematic.py` (netlistsvg) is a quick connectivity preview only —
  not a deliverable (can't draw 4-edge symbols).
- **`assets/render_sch_png.sh`** — alternate PDF→PNG preview (`kicad-cli sch export pdf` + `pdftoppm`).
  Review artifact only — ERC stays the correctness gate.
- **Documentation engine** — `../../engines/kidoc/` (`ENGINE.md`): HDD / power-analysis /
  schematic-review / ICD packages, rendered SVGs, styled PDF.
- **`datasheets` skill** — IC pin/electrical/topology extraction; consumed by the analyzer for
  datasheet-backed findings.
- **`bom` skill** (+ `digikey` / `mouser` / `lcsc` / `element14`) — hand off the BOM for
  enrichment, pricing, stock, lifecycle, and fab BOM/CPL. Don't reimplement sourcing in C03.
- **`spice` / `emc`** — analog front-end and EMC pre-compliance *plans* here; *verdicts* in C06.
- **`drawmiat` / `kidoc`** — power-frontend, block, and bus diagrams.
- **`docx` / `xlsx` / `pdf` / `pptx` + `docxmcp` MCP** — for the BOM/netlist/pinmap spreadsheets
  and the design-definition document artifacts.
