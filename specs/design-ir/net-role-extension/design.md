# Design: design-ir_net-role-extension

## Context

`quality_verify-checker-skillification`（verified）盡職查核（event 2026-07-04
`t-b-12-stub-ir-native-land-backlog`）證實：6-8 個 verified placement 類 `control.*`
的判斷力清楚，卻卡在同一個 blocker——`packages/design-ir/bodesign_design_ir/contracts.py`
的 `Net` dataclass（line 24-29）只有 `name` / `connected_pads` / `constraints` /
`evidence_refs`，**沒有 role 欄**，checker 分不出哪條 net 是 power / ground / RF /
high-current。這些 control 全屬 placement/拓樸類，門檻語義都須先知 net 角色才能判
（「high-current via 要接 ground plane」「RF trace 旁要有 ground」「charger IC 供電拓樸」）。

目前唯一「解法」是靠 net 名 heuristic（VBUS/GND…）猜 role，這**直接違反 no-fabrication
天條**（bodesign AGENTS.md §2.1）——臆造沒有 datasheet/schematic 依據的分類。正解是讓 role
由上游 schematic net-class **明確供給**，成為 IR 一等公民欄位，並帶 provenance 對齊
`quality_verify-checker-skillification` DD-2 的 `ValidationEvidence` `source_anchor` 契約
（checker 讀 role 可回溯來源）。本 plan 是該 spec DD-7 揭示的兩筆上游工之一。

本設計採 **IDEF0-first**：先以 `idef0.json` 拆解功能流（供給 role → 對照閉集驗證 →
綁定 provenance → 曝露 role-aware 查詢），再由該分解導出下列架構決策。

## Goals / Non-Goals

**Goals**

- 在 `Net` dataclass 加 **明確、可選、schematic-grounded** 的 `role` 欄（閉集 enum）+ role
  provenance 欄，缺失時為 `None`（fail-fast，不預設、不猜）。
- 定義 schematic net-class / 使用者標註 → IR role 的**確定性明確映射路徑**（來源必為
  schematic/使用者標註，無 net 名 heuristic）。
- 提供 role-aware 讀取介面，讓 placement 類 checker 以 role 篩 net，解鎖 `ddr.ddr3-flyby-routing`、
  `protection.tvs-esd-layout`、`protection.reverse-polarity-layout`、`placement.power-stage-hot-loop`、
  `power.charger-ic-layout`、`power.current-sense-layout`、`power.high-current-via-ground`、
  `rf.transmission-line-ground` 這批 T-B control。
- 跨 spec 以 `extend` 把上述 T-B binding 掛入 `verify-checker-skillification` registry。

**Non-Goals**

- 不做 net 名 heuristic 猜 role（天條禁止；role 必須明確供給）。
- 不讓 LLM 參與 role 判定；role 來自確定性 net-class 映射或使用者明確標註。
- 不建平行 net 分類系統；role 是 `Net` 一等欄位、單一真相。
- 不改寫既有 `Net.constraints` / `connected_pads` 語義（只加欄，向後相容）。
- 不做 copper 幾何解析（`gerber-core_copper-geometry-parser` plan 範圍）。

## Decisions

### DD-1: `role` 為閉集 enum，OPTIONAL，default `None`

以 `Literal["power","ground","high_current","rf","signal","differential"] | None` 表達閉集，
default `None`。閉集邊界由這批待解鎖 T-B control 的語義決定（power/ground 供電拓樸、high_current
via-ground、rf transmission-line、differential/signal 一般訊號）。`slots=True` 下新增有 default
的欄位排在既有欄位後，**現有 positional/keyword 呼叫端全不受影響**（向後相容）。

拒絕替代方案：（a）開放 `str` role——無法 fail-fast，任何 typo 會靜默通過，違反確定性；
（b）獨立 `NetRole` Enum class——`Literal` 已足夠表達閉集且與既有 dataclass 風格一致，額外
Enum 型別徒增序列化複雜度。

### DD-2: role 缺失 = `None`（fail-fast，no-guess）

net-class 未供 role、或供的 token 不在閉集 → `role` 保持 `None`，**絕不套用預設或以 net 名推測**。
下游 role-gated checker 讀到 `None` 時直接 skip 該項檢查（回報「缺 role，不判」而非猜一個判）。
這是 no-fabrication 天條在本 schema 的落地：無依據不臆造。

拒絕替代方案：「net 名 heuristic 補洞」——正是 proposal 明列禁止項，臆造無 schematic 依據的分類。

### DD-3: role 必帶 provenance，對齊 `source_anchor` 契約

role 非裸值：設 `role` 時必同時提供其來源錨點。以既有 `EvidenceRef`（來自 `bodesign_shared`）
承載，新增 `role_evidence: EvidenceRef | None = None`。語義約束：`role is not None` ⇔
`role_evidence is not None`（有 role 必有出處；建構期以工廠/驗證函式強制，schema 層以此不變式描述）。
這對齊 `verify-checker-skillification` DD-2 `ValidationEvidence` 的 `source_anchor` grounding——
checker 讀 role 產出的 verdict 可一路回溯到 schematic net-class / 使用者標註來源。

拒絕替代方案：把來源塞進既有 `evidence_refs: list`——那是 net 整體證據，混入會讓「role 從哪來」
無法乾淨定位；獨立 `role_evidence` 讓 provenance 一對一可查。

### DD-4: 明確供給映射路徑（schematic net-class → IR role）

上游 IR 生成器（schematic → IR builder）讀 schematic 的 **net-class 標籤 / 使用者顯式標註**，
以一張**確定性對照表**（net-class 名 → role enum + 來源錨點）填 `role` + `role_evidence`。
對照表本身即 provenance 來源（映射規則有據可查）。net-class 未列於表、或 net 無 class → `role=None`
（DD-2）。此路徑純確定性、零 LLM、零 net 名字串比對。

拒絕替代方案：讓 LLM 從 net 名/上下文推 role——違反 Non-Goals 與天條。

### DD-5: role-aware 查詢介面

於 `design-ir` 提供 `nets_with_role(design, role)` 類查詢：回傳 `BoardDesign.nets` 中
`net.role == role` 的子集（`role is None` 的 net **永不**出現在任何 role 查詢結果）。placement
checker 以此取代 net 名 heuristic 篩選。純 python、無 worker-only 依賴、確定性（同輸入 byte-identical
輸出）。落點 `design-ir` package。

拒絕替代方案：在每個 checker 各自遍歷 `nets` 比對 role——重複邏輯、易漂移；集中一個查詢介面單一真相。

### DD-6: 跨 spec `extend` 綁定進 verify-checker registry

本 plan 只交付 IR 能力；對應 T-B control 的 checker 由 `quality_verify-checker-skillification`
spec 以 `extend`/`amend` 模式把 binding 由 `status=stub` 改為 `landed`（DD-4 registry
`ir_fields[]` 指向 `Net.role` / `Net.role_evidence`）。本 plan **不** 在此寫 checker 實作，
只確立 IR 契約供其消費，避免跨 spec 責任混淆。

## Risks / Trade-offs

- **閉集 enum 未涵蓋未來 net 角色（如 clock、analog-sensitive）** — mitigation：閉集刻意窄，
  對齊當前待解鎖 T-B；擴集走正式 `amend`（加值到 `Literal`），不開放 `str` 逃生門。
- **`role`/`role_evidence` 不變式（有 role 必有 provenance）需建構期強制，dataclass 本身不擋** —
  mitigation：於 IR builder 映射路徑（DD-4）強制，spec 以 acceptance check 驗；schema 層以不變式文件化。
- **跨 spec extend 的時序耦合（IR landed 前 checker 無法 land）** — mitigation：本 plan 為明確上游，
  DD-6 劃死責任邊界；verify-checker spec 消費端在 IR 契約穩定後才 flip stub→landed。
- **既有 `Net` 序列化/相等性受新欄位影響** — mitigation：兩欄皆 optional + default，既有無 role 資料
  反序列化得 `role=None`（與 DD-2 語義一致），無破壞性遷移。

## Critical Files

- `packages/design-ir/bodesign_design_ir/contracts.py` — `Net` dataclass（line 24-29）加
  `role`（閉集 enum，default `None`）+ `role_evidence`（`EvidenceRef | None`）；本 plan 唯一
  IR schema 落點。`slots=True` 下新欄置於既有欄後保向後相容。
- `packages/design-ir/bodesign_design_ir/` — role-aware 查詢介面（DD-5）落點；純 python。
- `plans/quality_verify-checker-skillification/`（DD-2 `ValidationEvidence` / DD-4 registry /
  DD-7 上游解鎖）— 消費端 spec，以 extend 掛 T-B binding（DD-6），非本 plan 直接改。
- 上游 schematic → IR builder 生成路徑 — DD-4 net-class → role 確定性映射的實作處。
