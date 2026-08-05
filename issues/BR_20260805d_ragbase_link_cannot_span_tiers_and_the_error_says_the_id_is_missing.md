# BR_20260805d — `ragbase_link` 無法跨 tier 建邊，於是 promote 到 user tier 的物件成為孤島

- **Status**: OPEN — **經本 handler 重驗成立**（2026-08-05 @ `a183170`），但成因與原始回報的敘述不同，見 §5
- **Severity**: MEDIUM — 不產生錯誤結論（它 fail loud，錯誤訊息也精確），但它讓 promote 的**全部意義**（跨 repo 可查的一份知識圖）在圖層面失效：promote 過去的物件無法與來源 repo 的既有物件連邊
- **Owner repo**: specbase（本 repo 不可修；實作在 `~/projects/specbase/packages/lib/src/ragbase-lineage.ts`）
- **Family**: G13-harness-disclosure
- **Filed**: 2026-08-05 by `ses_04db7a1c5ffelvbxyLP1p6xlRH`（bodesign 值星官）
- **Provenance**: 原始現象由蒸餾員回報；**本建檔 handler 已獨立重驗**（§3 為 handler 親自跑出的實錄，非轉述）

**Related**:
- `BR_20260805e_ragbase_context_silently_accepts_unknown_arguments.md`
  （**同一子系統 ragbase 的同一輪重驗、同一 commit 建檔**；但兩者的揭露形狀**相反**：本張 fail loud
  但語意誤導，805e 則 fail silent。並列比對後才看得出「錯誤訊息正確 ≠ 讀者能得到正確結論」）
- `BR_20260802_probe_ambiguity_is_the_one_defect_family_no_guard_scans_and_it_fired_16_times_today.md`
  （**同一失敗類別**——「兩態共用同一個輸出」。本張的兩態是「這個 id 打錯了」與「這個 id 存在但不在我看得到的 DB 裡」）

---

## 1. Symptom

ragbase 的 `link` 動作無法在 **repo-tier 物件**與 **user-tier（central KB）物件**之間建邊。
跨 tier 呼叫一律以 `RB_LINEAGE_FK_VIOLATION` 失敗，錯誤訊息指稱該 id **不存在**。

## 2. 為什麼要記

知識蒸餾的價值在**圖**不在堆。promote 的全部意義是「這份知識跨 repo 可查」；
若 promote 到 user tier 之後就無法與 repo tier 的既有物件連邊，
那份跨 repo 可查的複本會是**孤島**——查得到節點，查不到它為什麼在那裡、它約束了誰。

## 3. Reproduction — 本 handler 的重驗實錄（measured 2026-08-05 @ `a183170`）

全程在 `$XDG_RUNTIME_DIR` 的 DB **複本**上跑，兩個真實 DB 的 mtime 在收工時確認未變（見 §4 D 組）。

```bash
SCRATCH="$XDG_RUNTIME_DIR/g13-brfiling"; mkdir -p -m 700 "$SCRATCH"
cp /home/pkcs12/projects/bodesign/.specbase/ragbase.sqlite "$SCRATCH/repo_tier.sqlite"
cp /home/pkcs12/projects/ragbase/.specbase/ragbase.sqlite  "$SCRATCH/user_tier.sqlite"
cd /home/pkcs12/projects/specbase
```

端點取樣（兩邊都是真實存在的物件）：

```
repo tier (bodesign)   concept.lifecycle-c00-c07        type=concept  scope=''        (526 objects)
user tier (ragbase)    longcare.concept.a-approved-plan type=concept  scope=longcare  (672 objects)
```

### A 組（TREATMENT）repo-tier → user-tier

```bash
export SPECBASE_RAGBASE_DB_PATH="$SCRATCH/repo_tier.sqlite"
bun skills/plan-builder/scripts/producer.ts ragbase_link \
  --repo /home/pkcs12/projects/bodesign \
  --arg source_id=concept.lifecycle-c00-c07 \
  --arg target_id=longcare.concept.a-approved-plan \
  --arg edge_type=references
```

**實際回應**：

```json
{
  "ok": false,
  "error": "RB_LINEAGE_FK_VIOLATION",
  "detail": { "missing": "longcare.concept.a-approved-plan", "role": "target_id" }
}
```
rc=1

### C 組 反向：user-tier → repo-tier

```bash
export SPECBASE_RAGBASE_DB_PATH="$SCRATCH/user_tier.sqlite"
bun skills/plan-builder/scripts/producer.ts ragbase_link \
  --repo /home/pkcs12/projects/ragbase \
  --arg source_id=longcare.concept.a-approved-plan \
  --arg target_id=concept.lifecycle-c00-c07 \
  --arg edge_type=references
```

**實際回應**：

```json
{
  "ok": false,
  "error": "RB_LINEAGE_FK_VIOLATION",
  "detail": { "missing": "concept.lifecycle-c00-c07", "role": "target_id" }
}
```
rc=1

⇒ **兩個方向都不成立**，且兩次都指稱「對面那顆不存在」。

## 4. Control（證明這個探針有判別力）

### B 組 同 tier 內連邊（正組）

```bash
export SPECBASE_RAGBASE_DB_PATH="$SCRATCH/repo_tier.sqlite"
bun skills/plan-builder/scripts/producer.ts ragbase_link \
  --repo /home/pkcs12/projects/bodesign \
  --arg source_id=concept.lifecycle-c00-c07 \
  --arg target_id=concept.honesty-provenance-model \
  --arg edge_type=references
```

```json
{ "ok": true, "data": { "source_id": "concept.lifecycle-c00-c07",
  "target_id": "concept.honesty-provenance-model",
  "edge_type": "references", "edge_inserted": true } }
```
rc=0

⇒ **同一支指令、同一個 source_id、同一個 edge_type**，只換 target 的 tier：
同 tier 成功、跨 tier 失敗。故 A/C 組的失敗**不是**參數寫法錯、不是 edge_type 不合法、
不是 `source_id` 有問題——**唯一變數是 target 落在哪個 tier**。

### D 組 無污染確認

```
/home/pkcs12/projects/bodesign/.specbase/ragbase.sqlite   mtime Aug 5 10:45（重驗前後未變）
/home/pkcs12/projects/ragbase/.specbase/ragbase.sqlite    mtime Aug 5 10:46（重驗前後未變）
```
⇒ 全部寫入落在 scratch 複本，真實 KB 零污染。

## 5. Why this is a disclosure gap, not operator error

**那一格資訊，系統當下有沒有？——有，而且是最關鍵的那一格。**

讀原始碼（`~/projects/specbase/packages/lib/src/ragbase-lineage.ts` §`ragbaseLink`）可見成因：

```ts
const db = openRagbaseForRepo(ctx.repo)          // 只開「一個」DB
const typeOf = (id) => db.query("SELECT type FROM ragbase_objects WHERE id=?").get(id)?.type
if (!sourceType) return rbFail("RB_LINEAGE_FK_VIOLATION", { missing: sourceId, ... })
if (!targetType) return rbFail("RB_LINEAGE_FK_VIOLATION", { missing: targetId, ... })
```

`openRagbaseForRepo(repo)` 解析到**單一** DB 檔（`<repo>/.specbase/ragbase.sqlite`，
可被 `SPECBASE_RAGBASE_DB_PATH` 覆寫）。lineage 表與物件表**同屬一個 DB 檔**，
所以一條邊在物理上不可能跨越兩個 DB 檔——**這是資料模型層的限制，不只是缺個功能**。

而揭露缺陷在於**錯誤訊息說的不是這件事**。系統當下明確知道：
「我開的是 `<這個路徑>` 這一個 DB，你給的 id 不在裡面」。它把這件事壓成了 `missing: <id>`：

| 讀者想分辨的兩態 | 實際輸出 |
|---|---|
| 這個 id 我打錯了／根本不存在 | `RB_LINEAGE_FK_VIOLATION { missing: X }` |
| 這個 id 完全存在，只是在另一個 tier 的 DB，而 link 從設計上就開不到 | `RB_LINEAGE_FK_VIOLATION { missing: X }` |

於是呼叫端得到的第一結論必然是「我 id 打錯了」，然後去反覆核對一個**完全正確**的 id。
這正是判準②所描述的形狀：摩擦被誤讀成操作失誤，而系統手上握有能立刻澄清的那一格。

**與原始回報的落差（如實記錄）**：蒸餾員回報為「`ragbase_link` 不支援跨 tier」。
重驗結果：**現象成立，但層次不同**——不是「支援與否」的功能缺口，而是
**單 DB 資料模型 ＋ 一個掩蓋該事實的錯誤訊息**。修法因此也不同（見 §6）。

## 6. Proposed fix（提議，未決定）

分兩層，且**第一層應優先，因為它便宜且立刻止血**：

1. **（揭露層，本 family 的本分）錯誤訊息說出真相**：
   `RB_LINEAGE_FK_VIOLATION` 的 detail 加上 `db_path: <實際開的 DB>` 與
   `hint: "lineage edges live in the same DB as their endpoints; cross-tier ids are not visible here"`。
   若 id 帶有已知的 central domain 前綴（如 `longcare.`），再加一句
   `looks_like_central_tier_id`。**這一層完全在現有程式的知識範圍內，不需任何資料模型變更。**

2. **（模型層，需設計裁示）跨 tier 邊怎麼存**：
   選項包含（a）central DB 內存一份「外部參照邊」並記錄來源 repo；
   （b）promote 時把來源 repo 的相關端點一併帶過去（本地化子圖）；
   （c）明文宣告「跨 tier 邊不存在，關聯只由 id 命名慣例承載」——
   若選 (c)，那就必須在 `ragbase_promote` 的輸出裡明講，否則 promote 的使用者會持續期待一個不存在的能力。

**注意**：`ragbase_promote` 的既有程式碼中已有一段相關 hint
（`ragbase-promote.ts`：「these control/workflow/failure-mode objects have no distilled_from→extract edge
to carry; ragbase_link the evidence in the SOURCE repo first, then retry promote」），
顯示設計意圖是「邊在來源 repo 內建好，promote 時整包搬」。
若這就是官方立場，則本張的修法應偏向 §6.1 ＋ 文件澄清，而非新增跨 tier 邊。**此判斷須由 specbase owner 裁示，本張不代決。**

## 7. 量了什麼 / 沒量什麼

- **量了**：A/B/C/D 四組，全部親自執行、輸出逐字貼上。
- **沒量**：未測 `ragbase_link_batch` 的跨 tier 行為（推測同源，但**未驗證**）。
- **沒量**：未測 `ragbase_promote` 實際跑一次後、邊是否被帶過去。
- **沒量**：未測 `SPECBASE_RAGBASE_DB_PATH` 指向 central DB 時，能否以「把 repo 端點也 promote 過去」的方式繞過。
  以上三項**不得被讀成已驗證**。
