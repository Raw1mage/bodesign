# BR_20260802 — `routing.py` 的 freerouting jar 預設路徑與 `Dockerfile.ee` 安裝路徑不一致（且一份「已修復」紀錄從未落地）

- **Status**: OPEN

| Field | Value |
| --- | --- |
| Title | freerouting jar default resolves to a subdirectory that no image creates; the mismatch is masked only by an env var, and a sibling BR certifies this as already-fixed when it never landed |
| Component | `packages/eda-bridge` (`routing.py` autoroute probe + runner), `Dockerfile.ee` |
| Owner | **unassigned** — family `layout-route`（見 `issues/OWNERS.md`） |
| Reporter | ses_04db7a1c5（bodesign coordinator）— 在歸檔前的 stale-BR 複驗中由 `ses_03f060b48` 提出，coordinator 親手覆核 |
| Date | 2026-08-02 |
| Severity | medium — 不影響 ee worker 正常路徑（env var 蓋掉了預設值），但**閘門會在 jar 實際存在時回報「請安裝 jar」**，屬 false-red gate |
| Priority | P2 — 無 live 誤判回報，但失效態是靜默的：`jar_present:false` 與「真的沒裝」共用同一個輸出 |
| Affected paths | `packages/eda-bridge/bodesign_eda_bridge/routing.py:1737`、`:1829`；對照 `Dockerfile.ee:23`、`:91` |

```
State:
Fix: none
Effect: not started
Custody: bodesign
Blocker: none
Disposition: filed as a precondition for archiving BR_20260729_preflight — that BR's
  Explicitly-NOT-bugs section certifies this fix as already landed and to be preserved.
  Archiving it first would bury a false record in issues/closed/ where nobody re-reads it.
Venue: bodesign
Status: OPEN
```

## 1. Symptom（HEAD 上直接可讀，非推論）

同一個檔案在相隔 16 行處對同一個路徑給出兩個不同的值：

```
routing.py:1721  remedy 字串        →  "install freerouting.jar (FREEROUTING_JAR env or /opt/freerouting.jar); "
routing.py:1737  _probe_autoroute_env →  os.environ.get("FREEROUTING_JAR", "/opt/freerouting/freerouting.jar")
routing.py:1829  autoroute runner     →  os.environ.get("FREEROUTING_JAR", "/opt/freerouting/freerouting.jar")

Dockerfile.ee:23  實際安裝            →  wget -q -O /opt/freerouting.jar https://.../freerouting-1.9.0.jar
Dockerfile.ee:91  ENV                 →  FREEROUTING_JAR=/opt/freerouting.jar JAVA_BIN=java
```

`:1721` 用平路徑、`:1737`/`:1829` 用子目錄路徑。**同檔自相矛盾排除了「刻意選擇」的解釋**——若子目錄是有意的佈局，`:1721` 的 remedy 文字不會叫使用者去平路徑找。

Repo-wide 搜尋（`--include=*.py --include=*.sh --include=*.yml --include=Dockerfile*`，排除 `.venv`/`.git`）：子目錄形式**只出現在這兩行**，其餘全部使用平路徑。

## 2. RCA

`_probe_autoroute_env` 的 `jar_present` 判定拿一個**沒有任何 image 會建立的路徑**去 stat。它之所以在 ee worker 上不出事，純粹是 `Dockerfile.ee:91` 設了 `FREEROUTING_JAR`，讓 `os.environ.get` 的第二引數（預設值）永遠不被取用。

換句話說：**預設值是死的，而它死得很安靜**。任何不經過該 ENV 的路徑——裸 host、非 ee image、compose override 蓋掉 env、單元測試直接呼叫 `_probe_autoroute_env`——都會得到 `jar_present: false`，preflight 於是輸出「install freerouting.jar」，而那個 jar 就在磁碟上 `/opt/freerouting.jar`。

這正是 `ragbase/control/no-silent-degradation/` 記載的形狀：**閘門對「真的沒裝」與「裝了但我找錯地方」回報同一個結果**，呼叫端無從分辨。

### 2.1 二階發現——一份認證不存在之修復的紀錄（這才是本 BR 必須先於歸檔存在的理由）

`issues/BR_20260729_preflight_core_group_misrouting_and_net2pcb_silent_ic_drop.md:51-52` 的 Explicitly-NOT-bugs 段落寫著：

> platform 順修的 `routing.py` jar default 路徑（`/opt/freerouting/` → `/opt/freerouting.jar`）
> 是**另一個獨立的 latent bug，修得對**，但**不解本缺陷**…應保留

**該修復從未落地。** 證據不需 git 考古——`routing.py:1737`/`:1829` 當下的內容就是子目錄形式，即「應保留的修復後狀態」在 HEAD 上不存在。（補充佐證：`git log -S'"/opt/freerouting.jar"' -- packages/eda-bridge/bodesign_eda_bridge/routing.py` 回空；控制組 `git log -S'FREEROUTING_JAR'` 對同檔回兩筆 commit，證明 `-S` 對此檔有效。）

後果：BR_20260729_preflight 的其餘 §A–§L 十二節確實已修，該 BR 本身該歸檔；**但它一旦進 `issues/closed/`，這句「修得對、應保留」就成為一份沒人會再讀的錯誤紀錄**，而下一個讀它的人會相信路徑問題已解決。

## 3. Fix proposal

把 `routing.py:1737` 與 `:1829` 的預設值由 `/opt/freerouting/freerouting.jar` 改為 `/opt/freerouting.jar`，與 `:1721` 的 remedy 字串及 `Dockerfile.ee:23` 對齊。

**但只改預設值不夠**——那只是讓死的預設值變成活的正確值，`jar_present:false` 仍然無法區分「沒裝」與「找錯地方」。建議一併讓 probe 回報它**實際 stat 的路徑**（例如 `jar_path_probed`），使 remedy 訊息能顯示「我在 X 找過、沒有」而非只說「請安裝」。這樣缺席態與失敗態就不再共用同一個輸出。

## 4. Explicitly NOT bugs

- **`Dockerfile.ee` 的平路徑安裝不是缺陷**，不要改它去遷就 `routing.py`——`:1721` 的 remedy 與 `:91` 的 ENV 都已站在平路徑這邊，是 `:1737`/`:1829` 兩行落單。
- **ee worker 目前的 autoroute 功能沒有壞**，不需要緊急處置；本 BR 修的是閘門的判別力與一份錯誤紀錄，不是 runtime 功能。

## 5. Validation plan

1. 改後在**沒有** `FREEROUTING_JAR` env 的環境下呼叫 `_probe_autoroute_env`，且 `/opt/freerouting.jar` 存在 → `jar_present` 必須為 `true`。
2. **控制組（不可省略）**：把該檔案移走後重跑同一個呼叫 → `jar_present` 必須為 `false`。沒有這一步，第 1 步的綠燈不構成證據——一個永遠回 `true` 的 probe 也會通過第 1 步。
3. 修完後回頭修正 `BR_20260729_preflight` 的 `:51-52`，把「修得對、應保留」改為指向本 BR。

---

**Fix venue**: bodesign，family `layout-route`（`routing.py` + `Dockerfile.ee` 正是該 family 宣告的 fix surface）。該 family 目前 owner unassigned。
