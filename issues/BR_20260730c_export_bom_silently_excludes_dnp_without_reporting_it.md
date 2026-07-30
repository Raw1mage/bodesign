# BR_20260730c — `export_bom` 靜默排除 DNP 料，回傳值無任何欄位反映它

- Status: FILED-UNFIXED（RCA 完成，**未修**；與 BR_20260730b 不同關注點，獨立 file 以免污染該 BR 的 scope）
- Filed by: `ses_0c87bab06fferQ0umBs2Nybb5U`（platform owner；在 §O 之後做全 repo facade 可達性盤查時順手發現）
- Family: `control.quality.no-silent-degradation`（**V5** 判決未帶產生它的預算/基準）
- Fix venue: `/home/pkcs12/projects/bodesign`
- Priority: 中——不擋任何進行中工作，但下游是**採購**，誤讀代價是缺料

---

## 症狀

`export_bom(schematic_path, out_dir)` 的預設值 `exclude_dnp=True` 會把 DNP（Do Not Populate）料**從 BOM 中移除**：

```python
# packages/eda-bridge/bodesign_eda_bridge/bom_export.py:68-69
if exclude_dnp:
    cmd.append("--exclude-dnp")     # 真實傳給 kicad-cli 的旗標
```

而 `BomResult` 的欄位是：

```python
# bom_export.py:21-28
status: str
csv_path / xlsx_path / netlist_path: str | None
line_count: int          # 排除「之後」的行數
component_count: int
warnings: list[str]
```

**沒有任何欄位說明「排除了什麼」或「排除了幾筆」。**

## 為什麼這是缺陷

呼叫端拿到一份 BOM 與 `line_count=42`，**無法從回傳分辨**：

- 這塊板就是 42 個零件；
- 還是有 5 個 DNP 料被靜默濾掉，實際 47 個。

兩者的 `status="ok"`、`line_count=42` **完全相同**。這正是本 control 的 invariant 判別句：

> **呼叫端只讀一個數就會得出錯誤結論 = 違反。**

DNP 的語意本身讓它更危險：DNP 料通常是**刻意不焊但保留 footprint** 的選配／除錯／替代件。它在板上有 footprint、有 pad、佔面積，只是不上件。一份「乾淨」的採購 BOM 確實不該包含它們——**所以預設值 `True` 是對的**，錯的是「排除這件事沒有留下痕跡」。

下游是採購。若有人拿這份 CSV 直接下單，DNP 料不會出現在缺料清單上——而它們的 footprint 仍在板上，後續要補焊時才發現從未被叫料。

## 這與 §J / V5 是同一形狀

`autoroute` 的 `unconnected` 曾經同時是「板子的屬性」與「搜尋預算的屬性」，修法是 echo `passes_limit`。這裡的 `line_count` 同時是「板子有幾個零件」與「過濾規則排除了多少」，修法對稱：

| §J | 本件 |
|---|---|
| `unconnected` 不帶 `passes_limit` | `line_count` 不帶 `exclude_dnp` 與被排除清單 |
| 判決未帶產生它的**搜尋預算** | 判決未帶產生它的**過濾規則** |

## Fix proposal

1. **回傳 `exclude_dnp` 的實際值**（呼叫端傳的、或預設的）——判決帶著產生它的規則。
2. **回傳被排除的 refs 清單**（`excluded_dnp: [refs]`），比照 `plane_layers_applied` / `removed_stubs` 的 positive pattern：**呼叫端能稽核到底排除了什麼，而不是相信一個計數**。
   - 取得方式：以 `exclude_dnp=False` 再跑一次 kicad-cli 取全集後做差集，或直接解析 schematic 的 DNP 屬性。前者簡單但多一次 CLI 呼叫；後者需要 schematic 解析。**實作前需量測 kicad-cli 的成本**。
3. **facade 暴露 `exclude_dnp`**（目前 schema 未宣告，見下），且 description 明說預設會排除 DNP 料。

## 附帶：facade 可達性（§O 同族，但這筆是 by-design 邊界待裁）

全 repo 盤查（`services/mcp/server.py` 的 handler ↔ 目標函式簽章 AST 對照）顯示 13 個工具有「目標函式參數在 facade 上觸及不到」。**逐筆取證後只有本件符合 §O 的形狀**，其餘均為合理設計：

| 工具 / 參數 | 判定 |
|---|---|
| `api_key`（c01 concept image） | **絕不該進 schema**（憑證） |
| `kicad_skill` / `emc_skill` / `spice_skill` | 內部引擎路徑覆寫，非呼叫端旋鈕 |
| `footprint_dir`（emit_layout） | facade 已用 `fpdir` / `fp_dirs` 暴露，**只是名字不同**，非不可達 |
| `columns` / `page_scale` / `macro_compact` … （compose 11 個） | 排版旋鈕；省略只是用預設樣式，不改變電氣判決 |
| `ps_per_mm` / `z0` / `rs`（si_check） | **已有 `effective` 回傳實際採用值**——正是 §J 的 positive pattern |
| `mpns` / `repo` / `category_of`（materialize_model_cards） | 內部呼叫鏈，非 MCP 入口 |
| `exclude_dnp`（export_bom） | **本件** |

**這個盤查本身值得記**：13 筆裡 12 筆是合理設計。若把「參數沒暴露」當成缺陷判準直接報 13 筆，就是 cry-wolf——正確判準是 §O 的形狀：**省略它會靜默停用一條驗證規則、或改變交付物內容**。

## Explicitly NOT bugs

1. **`exclude_dnp=True` 這個預設值本身沒錯**。乾淨的採購 BOM 不該含 DNP 料。缺陷是排除沒有留下痕跡，不是排除。
2. **`si_check` 的 `ps_per_mm` 等參數未進 schema 不是缺陷**——它 echo `effective`，呼叫端讀得到實際採用值。這是正解，不是漏洞。
3. **`api_key` 未進 schema 是資安要求**，不得「修正」。

## Validation plan

1. 建一份含 DNP 料的 schematic fixture。
2. `export_bom` 預設呼叫 → 斷言回傳帶 `exclude_dnp=True` 與非空 `excluded_dnp` 清單，且清單內容與 fixture 的 DNP refs 逐筆相符。
3. **反向鑑別力**：`exclude_dnp=False` → `excluded_dnp` 必須為空且 `line_count` 增加對應筆數。少了這條，一個恆回空清單的實作會通過上一條。
4. 無 DNP 料的 schematic → `excluded_dnp` 為空但欄位仍存在（**「沒有東西被排除」與「沒有檢查」必須可分辨**）。

## Source evidence

- `packages/eda-bridge/bodesign_eda_bridge/bom_export.py:44-53`（簽章）、`:68-69`（旗標）、`:21-28`（`BomResult` 欄位）、`:74`（`line_count` 取自排除後的 CSV）
- `services/mcp/server.py` — `bodesign_export_bom` 的 schema 未宣告 `exclude_dnp` / `fields` / `labels`

## Related

- `BR_20260730b` §O — facade 可達性（本件由該盤查發現，但屬不同關注點）
- `BR_20260729` §J — 判決必須帶著產生它的預算（同一 invariant 的前一個實例）
- `ragbase/control/no-silent-degradation/README.md` — V5 變體
