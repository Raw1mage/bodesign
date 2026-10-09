# BR_20260901b — `ragbase_record_extract` 靜默丟棄合法的 `status` 值（驗證層跑了，賦值層沒接）

- **Status**: OPEN
**Severity**: MEDIUM (arg-layer disclosure defect — 每一筆用 verb 寫入的 extract 都被記成 `raw-only`，且無人會發現)
**Family**: G13-harness-disclosure / arg-layer-silent-drop（**缺席態與失敗態共用同一個輸出**，發生在參數層）
**Filed**: 2026-09-01 by ses_fa73bab76ffeM0Dhhz9pK0Xln2 (bodesign BRNS leaf handler，dispatcher `ses_04db7a1c5ffelvbxyLP1p6xlRH`)
**Owning repo**: **`~/projects/specbase`**（工具實作在那裡：`skills/plan-builder/scripts/producer.ts` → `@specbase/lib` 的 `ragbase_record_extract` handler）
**Discovered by**: `~/projects/bodesign`（本 repo 是**發現者兼 guest，不越權修別人的工具**）
**Originally hit by**: handler `ses_fa746a21d`（做知識蒸餾時撞到）

**Related**: 中央 KB `tooling-failmodes.failure-mode.an-empty-string-arg-is-read-as-omitted-and-silently-defaulted`
——**鄰居，不是同一則**。差異必須寫清楚，否則會被誤讀成重複建檔：

| | 該既有條目 | **本 BR** |
| --- | --- | --- |
| 送進去的值 | **空字串** `""` | **合法的 enum 值** `"reviewed"` |
| 為什麼被丟 | 空值在 falsy 判斷下與「沒送」不可分 | 值**通過了 enum 驗證**，之後才被丟 |
| 根因層 | 值 → 存在性判斷的塌陷 | **驗證層與賦值層之間斷開** |
| 呼叫端能做什麼 | 改送非空值即可規避 | **無法規避**——送什麼合法值都一樣 |

第 4 欄是關鍵：既有條目描述的失效**有一條可用的繞道**，本 BR 的**沒有**。
同一 family（`arg-layer-silent-drop`）的另一個已知形狀：`bun test <不存在的路徑>` 多 positional
靜默丟棄（同載於中央 KB `tooling-failmodes`）——同樣是「參數被吃掉且回傳 ok」。

---

## 1. 一句話

送 `{"status":"reviewed"}` 與**完全不送 `status`**，`ragbase_record_extract` 的回傳
**逐字相同**——都是 `ok:true` 且 `"extraction_status":"raw-only"`。
`--help` 明列 `status` 是合法可選參數且 `reviewed` 在 enum 內，但那個值從未落到輸出上。

## 2. 重現（本輪實跑，2026-09-01）

runner：`bun $HOME/projects/specbase/skills/plan-builder/scripts/producer.ts ragbase_record_extract --repo $HOME/projects/ragbase --json '{…}'`

**Step 0 — 契約自陳（`--help`，rc=0）**

```
ragbase_record_extract — arg contract (required/optional · type · enum · hint):
  asset_id         REQUIRED  string — asset object id this extract derives from
  kind             optional  string — text|table|ocr (free string; default text)
  path             optional  string — extract output path; empty ⇒ raw-only; …
  locator          optional  string — article/page/section pointer; …
  status           optional  string ∈ raw-only|extracted|reviewed|normalized      ← 明列
  doc_dir          optional  string — …
```

**Step 1 — 建立探針 fixture**（見 §5，這會產生真實資料列）

**三格對照**（同一個 `asset_id`，`kind` 各異以免 id 相撞）：

### CELL 1 — 送合法 enum 值 `status:"reviewed"`

```json
{ "ok": true,
  "data": {
    "id": "extract.asset.home.pkcs12.projects.bodesign.issues.readme.md.text",
    "type": "extract",
    "asset_id": "asset.home.pkcs12.projects.bodesign.issues.readme.md",
    "kind": "text",
    "path": "",
    "locator": "BR_PROBE_20260901_record_extract_status_DELETE_ME_CELL1_legal_reviewed",
    "extraction_status": "raw-only"          ← 送 reviewed，回 raw-only
  } }
```
`CELL1_rc=0`

### CELL 2 — **完全不送** `status`

```json
{ "ok": true,
  "data": {
    "id": "extract.asset.home.pkcs12.projects.bodesign.issues.readme.md.probe.cell2.omitted",
    "type": "extract",
    "asset_id": "asset.home.pkcs12.projects.bodesign.issues.readme.md",
    "kind": "probe-cell2-omitted",
    "path": "",
    "locator": "BR_PROBE_20260901_record_extract_status_DELETE_ME_CELL2_omitted",
    "extraction_status": "raw-only"          ← 與 CELL 1 逐字相同
  } }
```
`CELL2_rc=0`

> **CELL 1 與 CELL 2 在 `extraction_status`／`ok`／rc 三個欄位上完全不可區分。**
> 呼叫端無論如何都拿不到「你給的值被丟了」這個訊號。

### CELL 3 — **決定性控制組**：送**非法** enum 值 `status:"zzqq"`

```json
{ "ok": false,
  "error": "invalid_args",
  "detail": {
    "missing": [],
    "invalid": [
      { "field": "status", "got": "zzqq",
        "allowed": ["raw-only", "extracted", "reviewed", "normalized"] }
    ] } }
```
`CELL3_rc=1`（**fail-loud**，並先把完整 arg contract 印了出來）

## 3. 這格控制組決定了根因分類（本 BR 的核心結論）

派工單指出：非法值報錯 vs 非法值也靜默，兩者根因不同、修法不同。**實測是前者。**

```
非法值 zzqq  → ok:false / invalid_args / rc=1   ⇒ status 這個欄位【確實被讀取了】
                                                 ⇒ 而且【被拿去比對 enum 白名單】
合法值 reviewed → ok:true / extraction_status=raw-only ⇒ 比對通過之後，值【沒有被寫進去】
```

**⇒ 根因是「驗證層跑了，賦值層沒接」，不是「整個參數從未被讀取」。**

這個區分是可操作的，不是措辭差異：

- 若是「從未被讀取」，修法在**參數解析**（arg 沒有進到 handler 的 payload）；
- 實際是「讀了、驗了、沒賦值」，修法在 **handler 內部**——欄位已經在手上，
  只是建構 extract 物件時沒有把 `args.status` 帶進 `extraction_status`（或帶進去的是寫死的預設）。

**這也讓缺陷更嚴重而非更輕**：一個會驗證你的值的介面，比一個明顯忽略參數的介面**更值得信任**，
所以呼叫端更不會去複驗回傳。驗證行為本身變成了誤導的來源。

## 4. 為什麼是揭露缺陷而非操作失誤（G13）

系統當下**握有**這格資訊：

- 它知道 `status` 被送了（CELL 3 證明它讀得到、比得動）；
- 它知道最終寫入的是 `raw-only`（它**自己把 `extraction_status` 印在回傳裡**）。

兩者都在手上，卻沒有任何一處說「你給的 `reviewed` 沒有被採用」。
`ok:true` 同時代表「照你說的做了」與「沒照你說的做但也沒壞」——**成功態與退化態共用同一個輸出**。

## 5. 我製造了幾筆探針資料（依派工單要求記錄；**未嘗試刪除**）

ragbase 沒有 delete verb，硬刪 sqlite 是禁區。**共 4 筆**寫入 `~/projects/ragbase`：

| # | type | id | 備註 |
| --- | --- | --- | --- |
| 1 | source | `source.br.probe.20260901.record.extract.status.delete.me` | 探針 batch，`scope` 已標 probe-only |
| 2 | asset | `asset.home.pkcs12.projects.bodesign.issues.readme.md` | 指向 `issues/README.md`（隨手可得的真實檔，`bytes_stored:false`） |
| 3 | extract | `extract.asset.home.pkcs12.projects.bodesign.issues.readme.md.text` | CELL 1，`locator` 含 `…_CELL1_legal_reviewed` |
| 4 | extract | `extract.asset.home.pkcs12.projects.bodesign.issues.readme.md.probe.cell2.omitted` | CELL 2，`locator` 含 `…_CELL2_omitted` |

CELL 3 **未產生資料列**（它 `ok:false`，這正是它作為控制組的價值）。
全部 4 筆的 `locator`／`name` 皆含可 grep 的 `BR_PROBE_20260901_record_extract_status_DELETE_ME`。

## 6. 影響面（為什麼值得修）

`ragbase_distill` 的 FK 鏈要求 `record_extract` 先行（`code-thinker` §10 的四步蒸餾鏈）。
**每一個照規約做蒸餾的 agent，寫進去的 extract 都被標成 `raw-only`**，
即使它實際上已經 reviewed。於是：

- `extraction_status` 這個欄位在整個 KB 裡**沒有判別力**（全都是同一個值）；
- 任何未來想靠它做「哪些 extract 已複核」的查詢，會拿到一個看起來乾淨的空結果——
  而空結果與「真的沒有任何 reviewed extract」不可區分。**本 BR 的失效正在製造下一個同型失效。**

## 7. 建議修法（給 specbase owner，我們是 guest 不動手）

擇一，但**必須是二選一而非兩者皆非**：

- **(A) 接上賦值**：handler 建構 extract 時把已驗證的 `args.status` 寫入 `extraction_status`。
- **(B) 若 `raw-only` 是刻意的**（例如 `path` 為空時強制降級——`--help` 確實寫了
  `path … empty ⇒ raw-only`），則**必須在回傳裡說出來**，例如
  `"extraction_status":"raw-only", "status_override_reason":"path empty"`。
  沉默地覆蓋呼叫端明示的值，不論理由多正當，都是本 BR 所指的缺陷。

> 注意 (B) 這個可能性本身尚**未被排除**：`--help` 的 `path` 說明暗示了一條降級規則。
> 但即使降級是**對的**，「沒有說」仍然是缺陷。本 BR 主張的是**揭露**，不預設賦值一定該生效。

## 8. 驗收判準（給未來修這張的人）

1. 送 `status:"reviewed"` + 非空 `path` → 回傳 `extraction_status` **不得**是 `raw-only`；
   或回傳明確帶出覆蓋理由欄位。
2. **控制組（必跑）**：同一次驗收中，`status:"zzqq"` 仍須 `ok:false`
   ——證明修 (A) 沒有把 enum 驗證一起拆掉。
3. **控制組（反向，必跑）**：完全不送 `status` 時仍為 `raw-only`
   ——證明第 1 點的變化來自我送的值，不是預設值被整體改掉。

## 9. 本輪沒有量什麼

- 沒有讀 specbase / `@specbase/lib` 的原始碼定位到具體那一行（**boundary：guest 不進別人 repo 改檔**，
  本輪連讀都限制在 `--help` 這個公開介面，故根因分類止於「驗證層 vs 賦值層」這一層粒度）。
- 沒有測試 `path` 非空時的行為（§7(B) 的降級假說**未被驗證也未被排除**）。
- 沒有測試其他 enum 值（`extracted` / `normalized`）；只測了 `reviewed`。
- 沒有嘗試刪除 §5 的 4 筆探針資料。

## 10. 已知殘留（dispatcher 裁決 2026-09-01：保留不清）

§5 的 4 筆探針資料列**留在 `~/projects/ragbase` 未清除**，這是**經裁決的刻意保留**，
不是被遺忘的污染。完整 id 如下，供未來要清的人直接取用、不必重新考古：

| # | type | 完整 id |
| --- | --- | --- |
| 1 | source | `source.br.probe.20260901.record.extract.status.delete.me` |
| 2 | asset | `asset.home.pkcs12.projects.bodesign.issues.readme.md` |
| 3 | extract | `extract.asset.home.pkcs12.projects.bodesign.issues.readme.md.text` |
| 4 | extract | `extract.asset.home.pkcs12.projects.bodesign.issues.readme.md.probe.cell2.omitted` |

全部 4 筆的 `name` / `locator` 皆含可 grep 的標記字串
`BR_PROBE_20260901_record_extract_status_DELETE_ME`。
CELL 3（非法 enum `zzqq`）**未產生資料列**——它 `ok:false`，這正是它作為控制組的價值。

**不清的三個理由**（dispatcher `ses_04db7a1c5ffelvbxyLP1p6xlRH` 裁決）：

1. **verb 層沒有刪除能力**——這正是 `BR_20260901c` 所證明的缺口的同一個面向。
   要清就得繞過工具層直接動 `.specbase/ragbase.sqlite`，而那是禁區
   （硬刪 sqlite 會破壞 FK 鏈，且 `source → asset → extract` 三者互為外鍵錨點）。
2. **以 guest 身分為了清自己的污染去動別人 repo，代價高於留著**。
   bodesign 對 specbase / ragbase 只有發現者身分，不是 owner。
3. **這 4 筆不進 concept 查詢視野**——它們是 `source` / `asset` / `extract` 三類 FK 錨點，
   而 `ragbase_query` 的一般檢索面對的是 distilled concept 物件。
   它們不會污染任何人的 recall 結果。

**要清的人請注意**：清除順序必須是 extract → asset → source（FK 反向），
且**在 specbase 長出刪除 verb 之後**再做。在那之前，本節就是這 4 筆存在的唯一說明。
