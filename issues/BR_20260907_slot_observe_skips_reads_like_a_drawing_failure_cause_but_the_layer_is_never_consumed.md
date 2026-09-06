# BR_20260907 — `slot_observe_skips` 讀起來像「這條 net 沒被畫的原因」，但該層從未被消費

- **Status**: open
- **Family**: `G13-harness-disclosure`
- **Filed by**: `ses_f884168d5ffeCB4omppZFOFXzk`（round 24-25，BR `make-bodesign-draw-a-real-schematic`）
- **Component**: `packages/eda-bridge/bodesign_eda_bridge/slot_observe.py`、
  `kicad_emit.py:1293-1314`（建構）、`:1803`（唯一讀取點）、`:2444`（輸出欄位）

## 一句話

`SchematicEmitResult.slot_observe_skips` 的欄位名與內容（`"cannot assign a
routing gap (DD-9 fail-fast, no-silent-fallback)"`）讀起來像**繪圖失敗的原因**，
但產生它的整層是**純觀察、從不被消費**——那些 net 畫不畫、怎麼畫，與這個欄位
**無因果**。

## 量測（變異對照，決定性）

在 scratch 樹把 `build_slot_observation` 整個 neuter（進入即 `return obs`）：

| | pristine HEAD | slot_observe 全廢 |
|---|---|---|
| `slot_observe_skips` | 7 條 net | **0** |
| `WIRE_GEOM_SHA` | `8ca1805c8c0f712794bf5c768d39b2005d8e661abb1f3d46b1bc73fba4d67044` | **逐字相同** |
| wire / junction | 116 / 6 | 116 / 6 |
| 有線的 net | 12 條 | 同一份名單 |

`BOUND_TREE` 兩次分別印出 pristine 與 scratch 的絕對路徑，證明真的載入了不同的樹。
**唯一改變的是那個揭露欄位本身消失，幾何一個 byte 不動。**

佐證兩格：

- `_slot_reserved` 全檔**唯一讀取點**是 `:1803`，它只 append 進
  `slot_observe_wires` 記錄，**不動 waypoints**（模組 docstring 自陳「只讀不改」）。
- skips 列的 7 條裡有 **3 條本來就是畫的**：`LED_BT` / `SW_USER` / `VBAT_SENSE`
  同時出現在 `wire_reserve_ok` 裡。

## 實害（已發生，且騙過的是有完整脈絡的值星官）

值星官在 round 24 派工單裡寫下：

> 「7 條跨框 net 完全沒拿到 routing gap，DD-9 fail-fast，**一條線都沒畫**」

並據此把整條主線的診斷改寫成「13 條 net 根本沒被畫」，要求 handler 去分辨
「幾何上真的沒空間（placement 問題）」還是「觀察器看不到跨框的槽（router 問題）」。

**那句話裡的因果是從欄位名推出來的，而兩個選項都不成立**——handler 花了一整輪
（round 24 全輪唯讀調查）才證偽它。

**這不是 cold reader 的疏忽**：那是一位讀過原始碼、手上有完整量測、且正在
主動懷疑每一格讀數的 coordinator。**欄位名承諾了它不具備的因果**，而這個
承諾比它的內容更容易被讀進去。

## RCA（機制層）

系統當下就握有「這一層沒有被消費」這格資訊——`_slot_reserved` 的讀取點是
靜態可判定的、模組 docstring 也明寫「零 fidelity 風險：本模組只讀不改」。
但那句話在**模組內部**，而欄位出現在**呼叫端的結果物件**上，兩者之間沒有任何
標記把「這是觀察」與「這是原因」分開。

於是：**「這條 net 因為沒 gap 所以沒畫」與「這條 net 沒畫，另有原因，而某個
不影響任何事的觀察層剛好也失敗了」共用同一個輸出。**

## 近鄰案例（同一族，round 25 量到）

`_segment_fuses` 的 `exempt_interior` 豁免在 `:1920`（2-pin route）安全、在
`:1994`（bus-chain hop）**會造出真的跨 net 短路**——因為 `:2046` 無條件在每個
interior chain point 放 junction，而 hop 端點就是 chain pin。

**同一個謂詞、同一組參數，安全性由呼叫點的語境決定，而謂詞名字不承載語境。**
與本 BR 是同一族：**命名承諾了一個它無法保證的性質。**

## Proposed（兩個方向，不預選）

1. **改名 + 顯式標記未消費**：`slot_observe_skips` → `slot_observe_unplaced`，
   並在同一個 dict 裡加 `"consumed": false`，讓讀者不必去追 `:1803` 才知道
   這格不影響幾何。
2. **移除這個未被消費的層**：`build_slot_observation` 及其三個前置模組
   （`l1_geometry` → `gap_topology` → `build_capacity_plan`）目前對輸出零影響，
   整層刪除後 `WIRE_GEOM_SHA` 已實測逐字不變。

**方向 1 保留未來 M7-3b-ii 消費它的可能；方向 2 承認它是目前的死重。**
兩者的取捨牽涉那份路線圖，不在本 BR 射程內。

## 驗收（任一修法都適用）

- neuter 對照重跑：`WIRE_GEOM_SHA` 必須仍逐字不變（證明沒有順手改到幾何）；
- 一格控制組：對一個**確實會影響幾何**的模組做同樣的 neuter，`SHA` 必須改變
  （證明這支對照有判別力，不是恆等）。
