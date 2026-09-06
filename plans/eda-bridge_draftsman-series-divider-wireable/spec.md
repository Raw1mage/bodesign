# Spec: eda-bridge_draftsman-series-divider-wireable

## Purpose

bodesign 必須提供一個入口，讓 agent **宣告**電路拓樸——串聯、並聯、分壓、去耦、
上拉、限流、接地、電源——並在入口處回答「這份宣告完整嗎」。今天沒有這個入口：
61 個 verb 全部假設電路已經存在。本 spec 的保證是：**agent 宣告的每一條連接都被
忠實落地成 `compose_schematic` 吃的 spec，每一個 node 可回溯到唯一一條宣告，
而任何不完整之處在入口處以缺項清單 fail-fast，不靜默續跑。**

本 spec **不**保證電路是對的。它保證的是「這份宣告內部一致且完整」——
兩者的差別在 `errors.md` §「語法合法但電路錯誤」逐格列出，不得混讀。

## Requirements

### Requirement: 宣告原語覆蓋設計者語彙

系統 SHALL 接受六個宣告原語（`connect` / `bridge` / `series` / `divider` /
`rail` / `no_connect`），且 SHALL 能表達使用者列舉的全部形狀：
「電阻、電感、電容、地線、火線、各種被動元件，透過並聯、串聯、各種組合」。

並聯 SHALL NOT 有獨立原語——它是兩個 `bridge` 掛在同一對 net 上。

#### Scenario: 串聯分壓

- **WHEN** agent 宣告 `{kind:"divider", top:"BATT", bottom:"GND", tap:"VBAT_SENSE",
  r_top:"R13", r_bottom:"R14", load:"U2.31"}`
- **THEN** 產出三條 net，其中 `VBAT_SENSE` 恰含 `["R13.2","R14.1","U2.31"]`，
  且該 spec 餵入 `compose_schematic` 後該子電路被畫成連通實線並帶 junction

#### Scenario: 去耦電容跨兩條 rail

- **WHEN** agent 宣告 `{kind:"bridge", part:"C8", between:["+3V3","GND"]}`
- **THEN** `+3V3` 增加 node `C8.1`、`GND` 增加 node `C8.2`，不新增第三條 net

#### Scenario: 串聯鏈的中間節點自動具名

- **WHEN** agent 宣告 `{id:"d7", kind:"series", chain:["+3V3","R9","D3","GND"]}`
- **THEN** 中間節點命名為 `d7_n1`（穩定、可被下游引用），
  **而非**匿名或序號名——重跑同一份宣告 SHALL 產出同一個名字

### Requirement: 完整性 gate 在入口 fail-fast

系統 SHALL 檢查每一支已宣告元件的每一支腳恰好出現在某條 net 或 `nc[]` 中一次。
出現 0 次 SHALL 報 `E_PIN_UNASSIGNED`；出現 >1 次 SHALL 報 `E_PIN_MULTI_NET`。
錯誤 SHALL 一次列出全部缺項，不 SHALL 只報第一個。

#### Scenario: 某支腳漏接

- **WHEN** 宣告了 8 腳的 U1 但只指派了 U1.1
- **THEN** `status="rejected"`，`errors[]` 含 `E_PIN_UNASSIGNED` 且列出全部 7 支未指派的腳

#### Scenario: 同一支腳落在兩條 net

- **WHEN** `R1.1` 同時被宣告在 `CC1` 與 `VBUS_CON`
- **THEN** `status="rejected"`，`E_PIN_MULTI_NET`，且 detail 同時指名兩條 net

### Requirement: 產出可回溯（No fabrication 的機檢形式）

系統 SHALL 為每一個輸出的 net node 記錄產生它的宣告 id。
`set(all_nodes) == set(provenance.keys())` SHALL 恆真；
任何無主 node SHALL 報 `E_PROVENANCE_ORPHAN` 且 SHALL NOT 放行。

#### Scenario: 引擎自己多產了一個 node

- **WHEN** 展開器因 bug 產出一個沒有對應宣告的 node
- **THEN** 內部斷言失敗，`status="rejected"`，且該 node **不**出現在輸出 spec 中

### Requirement: 結束狀態值域封閉且五類齊備

系統 SHALL 回傳 `status ∈ {ok, rejected, not_run, empty, indeterminate}`。
`empty` SHALL NOT 與 `ok` 共用同一個值；`indeterminate` SHALL NOT 被塌成
`ok` 或 `rejected`。每個狀態的排放點見 `errors.md` §Outcome Codomain。

#### Scenario: 空宣告

- **WHEN** `declarations: []`
- **THEN** `status="empty"`（**不是** `ok`）——理由是 `BR_20260730b` 記載的
  「空 spec 四閘齊綠」，若此格回 `ok` 則本包複製了它要修的那張 BR

#### Scenario: symbol 載不到

- **WHEN** 某元件的 symbol 無法解析，pin 清單未知
- **THEN** `status="indeterminate"`，`unknown[]` 指名該 ref 與理由——
  不 SHALL 假裝完整（`ok`），也不 SHALL 冤枉宣告者（`rejected`）

### Requirement: 畫法意圖可被宣告，且與預設值可分辨

`rail` SHALL 接受 `render ∈ {global_label, local_star, daisy_chain}`。
缺席時 SHALL 落到 `global_label` 並在 `render_plan` 標記 `source:"default"`；
顯式給值時標記 `source:"declared"`。**兩者 SHALL NOT 共用同一個輸出。**

#### Scenario: 未宣告畫法

- **WHEN** `{kind:"rail", name:"GND", nodes:[...]}` 未帶 `render`
- **THEN** `render_plan.GND == {render:"global_label", source:"default"}`，
  行為與今日一致（byte-stable）

### Requirement: 輸出直接相容既有 compose 契約

`declare_circuit` 的 `spec` 欄 SHALL 可**不經任何轉換**餵入 `compose_schematic`。
系統 SHALL NOT 新增第二條 emit 路徑。

#### Scenario: 端到端無轉換層

- **WHEN** 取 `declare_circuit(...).spec` 直接作為 `compose_schematic(spec=...)` 的引數
- **THEN** compose 正常執行，且既有四層驗證（ERC / fidelity / crosscheck / SPICE）
  的判準完全不需修改

## Acceptance Checks

- [ ] TV-1 通過：btdongle 分壓宣告 → `status="ok"` → compose 後該子電路 `junction > 0`
- [ ] TV-2（TV-1 的控制組）通過：抽頭接回自己 → `status="rejected"` +
      `E_DIVIDER_TAP_DEGENERATE`。**沒有這格，TV-1 的 ok 不構成證據**
- [ ] TV-4 通過：漏接的腳被一次全部列出，不只第一支
- [ ] TV-5 通過：同腳雙 net 在入口被擋（`BR_20260802_spec_declares_six_pins...` 的預防）
- [ ] TV-6 通過：空宣告回 `empty` 而非 `ok`（`BR_20260730b` 的預防）
- [ ] TV-7 通過：symbol 載不到回 `indeterminate` 而非塌成二值
- [ ] TV-8 通過：`set(all_nodes) == set(provenance.keys())` 恆真
- [ ] TV-11 / TV-12 成對通過：`source:"default"` 與 `source:"declared"` 可分辨
- [ ] TV-14 通過：輸出無需轉換即可餵 compose
- [ ] `errors.md` §Outcome Codomain 的五個狀態各自有**可指名的排放點**，
      且每個排放點在測試中至少被觸發一次
