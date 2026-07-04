# Control → Checker 可執行性分類（57 objects）

> design.md DD-1 的完整落地表。判準見 DD-1；partial/todo 一律 T-C（no-fabrication 天條）。
> 「可讀」= 門檻涉及的量能從 design-ir dataclass（`ComponentInstance.placement` x/y、`footprint`、`value`；
> `Net.connected_pads`；`GeometryPrimitive` x/y；`BoardObject.geometry`）或**現成 parser 已解析的 artifact**
> （ERC/DRC report → `classify_erc_report`；`.net` → `prd_bom_crosscheck`；gerber aperture/flash/draw →
> `gerber-core`；IPC-D-356A net/pad/via → `reverse-core`；`Mechanical_Constraint_Export.json`）取得。

## 統計摘要（關鍵發現）

| Tier | 數量 | 意義 |
|---|---|---|
| **T-A** machine-checkable（現在可硬 gate） | **3** | 乾淨可執行極少——瓶頸不在 checker 撰寫 |
| **T-B** verified 但 artifact/IR gap | **29** | **大宗**：規則清楚、但拿不到要檢的量（parser/IR 覆蓋不足） |
| **T-C** 定性 / partial / todo | **25** | 定性準則(12) + partial(10) + todo(3) |

**這張表本身就是給使用者的核心 signal**：技能化的真正瓶頸是 **design-ir/artifact parser 覆蓋**，不是「把知識寫成 checker」。29 個 T-B 的知識判斷力清楚，但 bodesign 目前的 IR 太薄、gerber-core 只到 summary 級、board outline / stackup buildup / copper spacing 尚無 parser，導致大量 verify 規則「知道該檢什麼、卻讀不到要檢的量」。

---

## T-A（3）— verified + 量化門檻 + 現成可讀

| control id | 門檻/裁決 | 讀取來源 | 落點 |
|---|---|---|---|
| `control.verify.kicad-default-severities` | ERC/DRC violation → severity 分桶裁決 | ERC/DRC report（`classify_erc_report` 已解析） | core，延伸既有 checker |
| `control.verify.kicad-dru-rule-language` | 生成/驗證 `.kicad_dru` 自訂規則 | 確定性規則檔生成（無需外部量） | core |
| `control.power.decoupling-pdn-strategy` | decoupling cap 到供電 IC pin 距離 ≤ 門檻 | **純 IR**：`placement` x/y + `Net.connected_pads` | core，IR-native 示範 |

> `decoupling-pdn` 是唯一純 IR-native 的乾淨 T-A（不需任何 artifact parser）——最能示範「知識→IR checker」路徑；門檻「靠近距離」需綁 datasheet 值（DD-3 threshold block）。

## T-B（29）— verified，規則清楚但 artifact/IR gap

需新 parser 或 IR 擴充才能取到門檻量。掛帳為 backlog，**不硬編假欄位**。

**幾何/spacing 類（需 copper/gerber 深解析，gerber-core 目前僅 summary）**：
`ipc-clearance-voltage`、`ipc-annular-tolerance-stack`、`ipc-fillet-land-pattern`、`safety.creepage-clearance`、`safety.functional-spacing-formula`、`si.spacing-via-return-path`、`si.stackup-impedance-control`、`mfg.stencil-aperture-ratio`、`mfg.assembly-courtyard`、`mfg.panelization-geometry`、`test.ict-testpoint-geometry`

**placement/拓樸類（需 placement 幾何 + 拓樸分析）**：
`ddr.ddr3-flyby-routing`、`esd.tvs-placement-routing`、`protection.tvs-esd-layout`、`protection.reverse-polarity-layout`、`placement.power-stage-hot-loop`、`power.charger-ic-layout`、`power.current-sense-layout`、`power.high-current-via-ground`、`rf.antenna-keepout`、`rf.transmission-line-ground`

**元件電氣參數類（需 vault datasheet 值比對）**：
`protection.fuse-ptc-derating`、`protection.mov-surge-selection`、`protection.ntc-inrush-selection`

**機構/板框/製程類（需 board outline / drill+copper / 製程參數）**：
`mech.board-edge-keepout`、`mech.mounting-hole-clearance`、`flex.bend-area-geometry`、`flex.transition-keepout`、`env.conformal-coating-thickness`

## T-C（25）— 定性 / partial / todo → advisory only

**定性準則 verified（12）→ G2 design-review 結構化提示**：
`datasheet-grounded-claims`、`design-review-g2`、`deterministic-validation-before-fab`、`no-fabrication`、`no-silent-fallback`、`pcb-false-complete-dfm-gates`、`tool-landed-redirect`（← 這 7 個是 meta/policy 準則）；
`dfa.part-count-reduction`、`mech.snap-fit-geometry`、`mech.tolerance-stackup`、`requirements.prd-quality-characteristics`、`si.crystal-oscillator-layout`（← 這 5 個是 PCB 定性準則，可作結構化 review 提示）

**partial（10）→ no-fabrication 強制 T-C，待知識升 verified 才可重分類**：
`dfm.injection-molding-geometry`、`dfm.ipc-trace-width-current`、`emc.stitching-shielding-plane`、`esd.tvs-electrical-selection`、`fab.cpl-pnp-alignment`、`mech.connector-mechanical-keepout`、`safety.creepage-clearance-spacing`、`si.diff-pair-impedance-geometry`、`si.length-match-skew`、`thermal.via-array-jarray-network`

**todo（3）→ 知識未實 → T-C**：
`dfm.jlcpcb-ipc-thresholds`、`geometry.fab-short-gates`、`placement.post-place-quality-checks`

---

## 對規劃的含意

1. **首批試點改選乾淨 T-A**（見 design.md DD-6 修正）：`kicad-default-severities`（延伸既有）+ `decoupling-pdn-strategy`（IR-native）+ 一個 T-B 掛帳示範（`mech.board-edge-keepout`，暴露 board-outline gap）。
2. **T-B 是主戰場**：技能化真正產值在於「補 parser/IR → 解鎖 29 個 verified 規則」。建議 implementing 階段優先攻「一個 parser 解鎖多個 control」的槓桿點（如 copper-spacing parser 一次解鎖 clearance/creepage/spacing 多個）。
3. **T-C advisory 也有價值**：12 個定性準則變成 G2 結構化 review 提示，比無提示強；但誠實標示為 advisory，不偽裝硬 gate。
