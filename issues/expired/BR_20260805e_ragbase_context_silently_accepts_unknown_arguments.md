# BR_20260805e — `ragbase_context` 靜默吃未知參數，回 `ok:true` 且輸出逐字相同

- **Status**: OPEN — **經本 handler 重驗成立**（2026-08-05 @ `a183170`），並取得逐位元組相同的證據
- **Severity**: MEDIUM — 它不會弄壞資料，但它會讓呼叫端**以為自己下的條件生效了**；而條件沒生效的輸出與條件生效但無結果的輸出完全一樣
- **Owner repo**: specbase（本 repo 不可修；實作在 `~/projects/specbase/packages/lib/src/ragbase-context.ts`）
- **Family**: G13-harness-disclosure
- **Filed**: 2026-08-05 by `ses_04db7a1c5ffelvbxyLP1p6xlRH`（bodesign 值星官）
- **Provenance**: 原始現象由蒸餾員回報；**本建檔 handler 已獨立重驗**（§3 為 handler 親自跑出的實錄）

**Related**:
- `BR_20260805d_ragbase_link_cannot_span_tiers_and_the_error_says_the_id_is_missing.md`
  （**同一子系統 ragbase 的同一輪重驗、同一 commit 建檔**；且兩張是**同一根因家族的兩個相反端**：
  805d 是「fail loud 但訊息誤導」，本張是「fail silent 完全不提」。並列後才看得出這個家族的兩種偽裝）
- `BR_20260802_event_record_returns_ok_true_while_storing_shell_injected_content.md`
  （**同一失敗類別、同一子系統家族**：該張是 `event_record` 回 `ok:true` 但存進去的東西不是呼叫端以為的東西；
  本張是回 `ok:true` 但呼叫端給的條件根本沒被讀。兩者都是 specbase 家族的 producer/gate 動詞回成功而語意落空）
- `BR_20260802_probe_ambiguity_is_the_one_defect_family_no_guard_scans_and_it_fired_16_times_today.md`
  （**同一失敗類別**：該張界定的「缺席態與失敗態共用同一個輸出」；本張是該類別在**參數輸入面**的實例——
  前述各張多半發生在輸出面）

---

## 1. Symptom

`ragbase_context` 的 `--help` 只列 **`repo` 一個欄位**，但傳入未知參數時它
**靜默接受**、不警告、不報錯，回 `ok:true`。

| 讀者想分辨的兩態 | 實際輸出 |
|---|---|
| 這個參數不被支援，我傳了等於沒傳 | `ok:true` + 完整結果 |
| 這個參數被支援，只是沒有對應內容可回 | `ok:true` + 完整結果 |

## 2. 為什麼要記

呼叫端傳參數的目的就是**改變結果**。若一個未知參數被靜默丟棄，
呼叫端會以為自己已經下了條件，並據此解讀一份**未經該條件過濾**的結果。
這比報錯危險：報錯會讓人回頭看拼字，靜默成功不會。

## 3. Reproduction — 本 handler 的重驗實錄（measured 2026-08-05 @ `a183170`）

```bash
cd /home/pkcs12/projects/specbase

# E) 先確認宣告的參數面
bun skills/plan-builder/scripts/gate.ts ragbase_context --help
```

**實際回應**：

```
ragbase_context: no declared argSpec; inputSchema:
{
  "type": "object",
  "properties": {
    "repo": {
      "type": "string",
      "description": "Override target repo path; defaults to the resolved ctx repo / token doc_dir."
    }
  }
}
```

⇒ 宣告面只有 `repo`。（順帶：`no declared argSpec` 本身也是一個資訊——這個動詞沒有 argSpec 層的驗證。）

```bash
# F) TREATMENT：塞兩個確定不存在的參數
bun skills/plan-builder/scripts/gate.ts ragbase_context \
  --repo /home/pkcs12/projects/bodesign \
  --arg nonexistent_param=zzz --arg another_bogus=42
```

**實際回應**（節錄開頭）：

```json
{
  "ok": true,
  "data": {
    "repo": "/home/pkcs12/projects/bodesign",
    "specs": { "count": 34, "packages": [ { "slug": "aiguard_refs-ssot-build", "state": "living" }, ... ] }
```
rc=0

**沒有任何一行提到那兩個參數。** 沒有 warning、沒有 `unknown_args`、沒有 `ignored`。

### 逐位元組比對（本張最硬的一格證據）

```bash
gate.ts ragbase_context --repo <bodesign>                                   > ctx_clean.json
gate.ts ragbase_context --repo <bodesign> --arg nonexistent_param=zzz \
                                          --arg another_bogus=42           > ctx_bogus.json
diff -q ctx_clean.json ctx_bogus.json
```

**結果**：

```
IDENTICAL — bogus args produce byte-identical output
13748  ctx_clean.json
13748  ctx_bogus.json
```

⇒ 兩份輸出**逐位元組相同、同為 13748 bytes**。
「有傳未知參數」與「完全沒傳」在輸出層面**零差異**——呼叫端無從察覺。

## 4. Control（證明這個探針有判別力）

### 正組：`diff` 確實抓得到真差異

```bash
gate.ts ragbase_context --repo /home/pkcs12/projects/specbase > ctx_other.json
diff -q ctx_clean.json ctx_other.json
```
→ `CONTROL OK: diff detects a real difference (different repo)`

⇒ 同一支 `diff`，在**該偵測到差異時確實偵測到**。所以 §3 的 `IDENTICAL` 不是 diff 壞掉。

### 負組：這個 runner 在該報錯時確實會報錯

```bash
gate.ts ragbase_notatool --repo /home/pkcs12/projects/bodesign
```
→ `unknown tool "ragbase_notatool"`，rc=2

⇒ 這條路徑**有能力**拒絕不認得的東西——它拒絕不認得的**動詞**，
卻靜默接受不認得的**參數**。兩者落在同一支 runner、同一次呼叫，故差異不是「這層沒有驗證機制」。

（本節存在的理由見 `BR_20260804j`：一個從未在真負例上變紅的檢查與壞掉的檢查不可區分。
上面兩組就是本張的紅／綠對照。）

## 5. Why this is a disclosure gap, not operator error

**那一格資訊，系統當下有沒有？——有，而且已經算出來了。**

證據就在 §3 的 `--help`：這條路徑**能列印出 `inputSchema`**，也就是說在處理呼叫的當下，
它手上握著「這個動詞認得哪些 key」的完整清單。同一次呼叫裡它也握著呼叫端實際傳了哪些 key。
兩個集合都在手上，**做一次差集是零成本的**——它只是沒做，或做了沒說。

再者 §4 負組證明這層**願意**在不認得時拒絕（不認得的動詞就被拒了）。
所以這不是「架構上做不到」，是「參數這一格被漏掉」。

呼叫端這邊則完全沒有補救管道：輸出逐位元組相同，
連「拿兩次結果比對」這種最笨的自保手段都無效。

## 6. Proposed fix（提議，未決定）

依侵入性由低到高：

1. **回應加 `ignored_args`**：`{ ok:true, data:{...}, ignored_args:["nonexistent_param","another_bogus"] }`。
   完全不改變既有成功語意，純加一格，向下相容。**最便宜、應優先。**
2. **runner 層 warn**：`gate.ts` 在把 args 交給 handler 前，
   對照該動詞的 `inputSchema.properties` 做差集，未知 key 印 stderr warning（不 block）。
   這一層可**一次覆蓋所有 gate 動詞**，不只 `ragbase_context`。
3. **嚴格模式**：未知參數直接 `invalid_args` 失敗。語意最乾淨，但會打到既有呼叫端，
   宜作為 opt-in（如 `--strict`）而非預設。**是否採用需 specbase owner 裁示。**

另外：`ragbase_context: no declared argSpec` 這一行本身值得處理——
有 argSpec 的動詞至少還有一層可對照的宣告，沒有的則連 (2) 都無從實作，
只能退回 `inputSchema.properties`。

## 7. 量了什麼 / 沒量什麼

- **量了**：`--help` 宣告面、TREATMENT 未知參數、逐位元組 diff、diff 自身的判別力、runner 對未知動詞的拒絕。全部親自執行、輸出逐字貼上。
- **沒量**：未測**其他** gate 動詞（`ragbase_query` / `wiki_search` / `event_search` …）是否有同樣行為。
  §6.2 的「一次覆蓋所有動詞」是**推測其普遍性**，**未經驗證**。
- **沒量**：未測 MCP over-the-wire 路徑（本次全走 `gate.ts` 本地 runner）。
  MCP 那條路的 schema 驗證行為**未知**，不得被讀成相同。
