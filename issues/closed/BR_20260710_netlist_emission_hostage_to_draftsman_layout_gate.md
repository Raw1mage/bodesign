# BR: netlist/ERC 匯出被 draftsman layout gate 綁架（無 ERC-only entrypoint）

**Date**: 2026-07-10
**Severity**: workflow-blocker（C03 電氣迭代被圖面層 gate 阻斷）
**Found by**: aiguard A6a（CCM 被動件網路補全，thesmart_products plan aiguard_c04-full-board-gerber）

## Symptom

`compose_schematic` 是 netlist/ERC 匯出的唯一路徑，而它強制通過 draftsman 圖面機檢
（`POWER_PORT_INSIDE_SYMBOL_BODY` 等 layout gate）。當電氣定義新增 ~24 顆去耦 cap 時，
naive-grid/draftsman placement 把 power-port stub 放進大型 BGA symbol body 內，layout gate
FAIL → **netlist 無法匯出、ERC 無法執行**——即使電氣 spec 本身 clean（92 comps/171 nets、
0 dup、0 footprint gap，離線驗證通過）。

Intrusion hosts 實測：U1×6、U6×3、U2×2、U3×1（+10）＝23 處。兩種 style（draftsman/netlist）
皆撞同一 gate，兩輪 stop-loss 停手。

## Root cause

分層缺陷：**電氣真值層（netlist/ERC）與圖面呈現層（schematic layout）耦合在單一 compose 管線**。
netlist 的正確性不依賴 symbol 擺位，但匯出路徑強制先過 layout 機檢。engine bridge 已有
`export_netlist(schematic_path)` / `validate_kicad_schematic`，但都需要 composed `.kicad_sch`
——compose 正是被卡的那一步。

## Ask

1. 提供 **ERC-only / netlist-only entrypoint**：從 component+net spec 直接產 netlist + 跑 ERC，
   跳過（或降級為 warn）純視覺類 layout gate（`POWER_PORT_INSIDE_SYMBOL_BODY` 屬視覺，
   不影響電氣連通）。
2. 或者：compose 的 layout gate 分級——電氣類（wire 誤連、pin 錯位）保持 hard fail，
   視覺類（stub 疊 symbol body、silk 重疊）降 warn，讓 netlist 匯出不被視覺缺陷阻斷。
3. 長期：draftsman placement 對高密度 BGA 周邊被動件的避讓（power-port stub 自動外推）。

## Evidence

- thesmart_products event log scope=aiguard_c04-full-board-gerber（2026-07-10 A6a event）
- 驗證過的 spec dump：container `/tmp/ccm_spec_a6a.json`（92 comps/171 nets）
- gen_ccm.py（電氣 SSOT，已含補全定義）

## Resolution (2026-07-10, closed)

**Fix = Ask 2 (gate 分級), which structurally delivers Ask 1 (ERC-only path).**

`POWER_PORT_INSIDE_SYMBOL_BODY` was an unconditional `raise ValueError` in
`kicad_emit.py` — a purely-VISUAL layout defect (a power-port glyph drawn over a
symbol body) that does NOT affect net connectivity, yet it aborted netlist/ERC
emission. Downgraded it to a **caller-controlled gate**, mirroring the existing
`wire_body_intrusions` observation pattern.

### Changes
- `packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py`
  - `SchematicEmitResult`: new field `power_port_intrusions: list[str]` (observation
    record, empty on the fail-loud path or when no intrusion).
  - `emit_kicad_schematic(...)`: new param `power_port_gate: str = "error"`.
  - The guard-C block (was `raise ValueError(...)`) now: `power_port_gate == "warn"`
    → append the message to `warnings` (observation); otherwise → `raise` (unchanged).
- `packages/eda-bridge/bodesign_eda_bridge/composer.py`
  - `compose_schematic(...)`: new param `power_port_gate: str = "error"`, threaded
    into the `emit_kicad_schematic(...)` call.

**Back-compat rail:** default `"error"` = byte-identical to prior behaviour; every
existing caller and the draftsman page-render path still fail-loud. Only an
explicit `power_port_gate="warn"` opt-in downgrades it. Electrical-class gates
(NC-resolution T1 fail-fast, wire mis-connect, pin-not-placed) are UNTOUCHED and
remain hard-fail.

**ERC-only path (Ask 1) is now:**
`compose_schematic(spec, style="netlist", power_port_gate="warn")` →
`export_netlist(sch)` → `validate_kicad_schematic(sch)` — no draftsman layout
validity required.

### Validation (container `bodesign-pkcs12-bodesign-ee-1`, live engine_rev 967f63fb644e)
Ran on the exact blocker spec `/tmp/ccm_spec_a6a.json` (92 comps / 171 nets).
`nc` was dropped for the isolation run because the spec carries a SEPARATE,
pre-existing T1 `no_connect`-resolution defect (169 NC entries reference pins the
emitter does not place — an A6a spec-construction issue, NOT this gate; see
Left-over below):
- `gate="error"` (default): composes; guard-C still active (back-compat proven).
- `gate="warn"`: composes → placed 248 / nets 171 → **`export_netlist` = ok,
  83 comps, 1595 lines** → **`validate_kicad_schematic` = validated,
  309 violations / 2 errors**. Real ERC ran — emission no longer held hostage.

Engine copy: `/app/packages` is the read-only host bind-mount (per
`scripts/sync_engine.sh` contract — "deploy = verify, not copy"), so the host
edits are live in-container immediately; no `docker cp`.

### Left over (not this BR)
- **Ask 3** (draftsman auto-avoidance of power-port stubs around dense BGA
  peripherals) is placement R&D — deliberately NOT done here.
- The 92-comp spec's **169 unresolved `nc` entries** are an A6a spec-side T1
  blocker upstream of this gate; the ERC-only path is now unblocked but A6a must
  still fix its NC list (or route it via the emitter's actual placed-pin set)
  before a clean netlist. Flagged back to the aiguard A6a thread.
