# BR_20260804j — 驗證層自己沒有驗證層：同一輪內五個實例

**Status**: OPEN
**Severity**: HIGH (meta-instrument defect — 它讓**整份 mutation proof 靜默失效**，而失效的輸出與通過逐字相同)
**Family**: G13-harness-disclosure / verification-methodology
**Filed**: 2026-08-04 by ses_0330e7869ffev0nZL0XqoXSp78 (readiness-contract handler)
**Fix surface**: 無單一檔案 —— 這是**方法論缺陷**，處方是驗證程序本身（見 §4）

**Related**:
- `issues/BR_20260804f_power_port_intrusions_is_a_declared_but_never_assigned_result_field.md`
  (same failure class — 一個**被 docstring 背書**的欄位從未被賦值，讀者拿到的空清單與「沒有缺陷」
  不可區分。本張是同一個病移到**驗證工具自己身上**：被 mutation proof 背書的測試從未真的被
  挑戰過，讀者拿到的 OK 與「測試有判別力」不可區分)
- `issues/BR_20260804b_guard_c_inset_inverts_the_box_for_narrow_bodies_so_intrusion_check_is_blind.md`
  (same failure class — 檢查器在該報警時靜默回「乾淨」；差別是 804b 的盲區在**被測程式**，
  本張的盲區在**證明被測程式的那套工具**)
- `issues/BR_20260804e_pkill_f_self_matches_and_silently_kills_the_calling_shell.md`
  (same failure class + same round — 工具知道自己是誰、也有 `-A` 可用，但預設不揭露；
  殺了 N 個與殺了 N 個並自殺共用同一個空輸出)

---

## 1. 一句話

被測程式有 mutation proof 擋著，而**證明它的那套工具沒有任何東西擋著** —— 同一輪內
五個實例，全部讓「驗證通過」與「驗證從未發生」產生逐字相同的輸出。

## 2. 五個實例（全部發生在 2026-08-04 單一輪內，皆已量測）

| # | 實例 | 「壞了」的輸出 | 與它共用輸出的「好了」 |
|---|---|---|---|
| ① | `readiness_common.py` 有**兩份** `stage_dir_arg_detail`，後者遮蔽前者，mutation 打在死碼上 | 測試 `OK` | 測試 `OK`（真的有判別力） |
| ② | 只刪函式定義、留下呼叫端 | `import` 完全成功 | `import` 成功（符號真的在） |
| ③ | `cp` 一個**已經是空檔**的備份，還原時覆蓋真檔成 0 bytes | `exit 0` | `exit 0`（備份真的有內容） |
| ④ | `.pyc` 快取：磁碟已還原而記憶體仍是 mutant | `cmp`/`grep`/`sha` 全說「已還原」 | 同樣的「已還原」（真的在跑還原後的碼） |
| ⑤ | `docker-entrypoint.sh` 有**兩塊** `TARGET_HOME` 解析，策略互相矛盾，第二塊不可達 | `sh -n` OK + 四格探針全綠 + 端對端成功 | 完全相同（程式碼真的只有一塊） |
| ⑥ | mutation 探針本身卡在更早的 `FATAL cannot create writable path /work`，從未走到待測區域 | baseline 與 mutant 輸出**逐字相同** | 相同（mutation 真的無效果） |
| ⑦ | dispatcher 的 harness 用 shell 函式做 `setpriv` stub，**而 `exec` 繞過函式查找** | 跑的是真 `setpriv` | 相同（stub 真的生效了） |

### ⑥⑦ 是探針自己就是診斷對象的那一層

兩者都不是「被測程式有缺陷」，而是「**負責判定的那支探針自己先壞了，而它壞掉的樣子與它成功的樣子一模一樣**」。

- **⑥**（本 handler）：測 entrypoint 的 mutation 時，整支腳本在抵達待測區域**之前**就已經
  `exit 1`（`/work` 在 host 上建不出來）。baseline 與 mutant 因此輸出逐字相同——
  而那正是「mutation 真的無效果」的長相。加 `mkdir` stub 讓探針真的走到 drop 之後，
  M5c 才願意變紅。
- **⑦**（dispatcher 自陣）：harness 定義了 `setpriv()` shell 函式當 stub，但
  **`exec` 繞過 shell 函式查找**，所以跑的是真 `setpriv`。「stub 生效了」與
  「stub 被繞過但結果看起來一樣」共用同一個輸出。

**兩格被救回來的方式相同：一個負向控制組。** ⑥ 靠的是「baseline 本身應該要有
不同輸出」，⑦ 靠的是 T3（getent 回空 ⇒ `dir-exists-after=NO`）證明 T1 的 `YES` 不是恆真。
不是靠探針寫得比較仔細。

### ④ 特別惡毒，因為它讓收尾斷言本身變成假的

CPython 用 **(source mtime 的秒數, source size)** 判斷 `.pyc` 失效。等長的
mutate + restore 在同一秒內完成 ⇒ `.pyc` 不失效 ⇒ 磁碟上 `cmp` 說「已還原」而記憶體裡
跑的還是 mutant。

**「還原後測試 OK」這個收尾斷言的用途，正是證明「mutation 是唯一變數」** —— 而它恰好是
最容易被這格擊穿的一句。**檢查與失效機制正交**：檢查看內容，失效看 (mtime 秒, size)。

### ⑤ 揭露了 ① 為什麼被抓到而它沒有

兩者是**同一個缺陷類別**（同一檔案內重複的等價區塊），只差一個檔案。

- ① 被抓到，因為有一個**可數的判準**：`grep -c '^def stage_dir_arg_detail'` 回 2。
- ⑤ 沒被抓到，因為**沒有人去數** `TARGET_HOME=` 出現幾次。

**差別不是仔細程度，是有沒有人想到要數。** 而且：

- `sh -n` 對它完全沉默（兩塊都是合法語法）
- 四條 mutation 全部打在 Python 側，entrypoint 這條路徑上**只有正向證明**
  （HOME 變成 `/home/ubuntu`），而正向證明對「多做了一次無害的重複工作」是盲的
- 所有探針都跑在 `TARGET_UID=1000` + `/home/ubuntu` **存在**的情境下，
  **兩塊在那個情境下行為恰好相同** —— 矛盾只在「passwd home 不存在」時顯現，
  而那正是被標為「未實機驗證」的分支

## 3. 為什麼這是缺陷而不是「不夠仔細」

「agent 不夠仔細」可以解釋以上全部五個，**正因如此它什麼都沒解釋**，而且讓修復無處著手。
逐一問「那一格資訊，系統當下有沒有？」：

| # | 系統知不知道 | 有沒有揭露 |
|---|---|---|
| ① | 知道（module namespace 裡就是後者贏） | 沒有。Python 對重複 `def` 不警告 |
| ② | 知道（型別系統可推） | 沒有。`import` 只證明可載入，不證明符號存在 |
| ③ | 知道（`cp` 讀得到來源大小） | 沒有。`cp` 一個空檔與 1MB 檔同樣 `exit 0` |
| ④ | 知道（它自己算了 mtime 與 size） | 沒有。載入 stale `.pyc` 與重新編譯沒有任何輸出差異 |
| ⑤ | 知道（shell 解析時看得到兩次賦值） | 沒有。`sh -n` 只驗語法 |

五格全部是**揭露缺陷**，不是個人特質。

## 4. 處方（可複用，不是「小心一點」）

### 4.1 每條 mutation 先跑 liveness 證明

改完之後、跑測試之前，**直接呼叫被改的函式並印出 mutant 下的實際回傳值**。
看到那個值才採信後續的紅/綠。

```
M2  stage_dir_arg_detail -> return None
      SUBSTITUTIONS=1                <- 改了幾處（獨立於探針）
      LIVENESS: helper -> None       <- 直接呼叫，證明 mutant 是活的
      -> FAILED                      <- 這時才採信
```

### 4.2 `SUBSTITUTIONS=N` 必須與 liveness **並存**，因為它們的失效模式不同

dispatcher（`ses_04db7a1c5ffe…`）在覆核本輪工作時踩到這格並回報：它第一版的 liveness
探針 `stage_dir_arg_detail(root, stage)` 少傳一個參數，得 `TypeError`。

**那個 `TypeError` 讀起來像「mutation 沒套用」，實際上是探針簽章錯。**
救它的是同一份輸出裡的 `SUBSTITUTIONS=1` —— 那格獨立於探針。

⇒ **liveness 證明本身也會壞。** 「直接數改了幾處」與「直接呼叫看回傳值」必須並存；
兩個獨立訊號指向同一件事，其中一個壞掉時另一個還在。

### 4.3 備份要驗**內容**，不看 exit code

```
cp "$F" "$BAK" && cmp -s "$F" "$BAK" && [ -s "$BAK" ] || { echo BACKUP FAILED; exit 1; }
```

`cp` 一個空檔同樣 `exit 0`。**還原前再驗一次**，因為備份可能在建立之後才被別的步驟清空
（③ 的真實成因）。

### 4.4 `import` / `sh -n` 不是健康檢查

- `import` 證明模組**可載入**，不證明**符號存在**（呼叫時才 `NameError`）
- `sh -n` 證明**語法合法**，不證明**沒有重複或不可達區塊**

### 4.5 Python mutation ~~一律 `python3 -B`，或~~ **每次切換清 `__pycache__`**

否則 ④ 會讓整份證明失效而毫無跡象。

> **⚠ 更正（2026-08-05，`ses_030847a3affev5QmJelNWqSK41` 實測）：`-B` 在這裡沒有保護力。**
> `-B` 只阻止**寫入** bytecode，**不阻止讀取既有的 `.pyc`**。在 ④ 的情境
> （pyc 已存在且被判定 valid）下，`python3 -B` 與預設**回傳完全相同的 stale 值**：
> ```
> disk=1e-3 | 預設 1e-09 | -B 1e-09 | rm -rf __pycache__ 後 0.001（唯一正確）
> ACCEPTING CONTROL：無既有 pyc 時 -B 讀 disk 正確 = 4.2（探針有判別力）
> ```
> ⇒ **清 `__pycache__` 是唯一有效處置**；`-B` 只能當「不留 pyc 給下一次」的預防。
> 本 BR 主題是「驗證層自己沒有驗證層」，而**本節開的處方自己就是一個未驗證的斷言**——
> 詳見 `BR_20260802_stale_pyc_silently_invalidated_a_mutation_proof.md` §Correction。

### 4.6 ⭐ 上位處方：**凡在同一檔案的同一區域多次編輯，收尾前數一次該符號/賦值的出現次數**

這是 ① 與 ⑤ 的共同解，而且它是**可機械執行的**，不依賴任何人「想到要數」：

```
grep -c '^def <name>'        # Python 函式
grep -c '<VAR>='             # shell 賦值
grep -c 'class <Name>'       # 類別
```

**判準：只要我在一個檔案裡做過 ≥2 次編輯，就數。** 不問「我覺得有沒有可能重複」——
那個判斷正是失效的那一環。

### 4.7 正向證明對「重複但無害」是盲的 —— 需要 mutation

⑤ 通過了全部正向證明。**要抓到它，必須有一條打在那個檔案上的 mutation**（刪掉其中
一塊，看行為是否改變）。

⇒ **每個被修改的檔案至少要有一條 mutation 打在它身上**，不能靠「另一個檔案的
mutation 全紅」外推。

### 4.8 備援機制會讓逐條 mutation 全部變綠 —— 而那個綠燈讀起來等同於「沒判別力」

本輪實測（entrypoint 的 HOME carrier）：

```
M5a  只刪 `env HOME="${TARGET_HOME}"`   -> DROPPED-PROCESS-HOME 仍正確  （沒紅）
M5b  只刪 `export HOME="${TARGET_HOME}"` -> DROPPED-PROCESS-HOME 仍正確  （沒紅）
M5c  兩者都刪                            -> DROPPED-PROCESS-HOME=/root  （紅）
```

兩個 carrier 互為備援（一個管 exec 環境、一個管本 shell），所以**單條 mutation 不紅是正確行為**。

但它的輸出與「測試對這個機制完全沒有判別力」**逐字相同**。若只跑 M5a 就收手，
會得到完全錢誤的結論：「拿掉 carrier 也不紅 ⇒ 我的驗證拓不到這個」。

⇒ **單條 mutation 的綠燈不構成「無判別力」的證據。** 下結論前先問：
**被測物有沒有第二條路徑？** 有就必須跑組合 mutation（全部拿掉）才能判定。

與 4.7 互補：**4.7 管覆蓋率（每個檔案都要有人打），4.8 管綠燈的可讀性（打不紅不等於白打）。**

## 4.9 一個正例：揭露機制生效時長什麼樣子

本 BR 到這裡全是反例，而**一份只有反例的 BR 讀者無從判斷「修好之後該是什麼樣」**。
本輪恰好有一組對照：

| 同一個操作失誤：跟 runner 要一個不存在的測試模組 | 輸出 |
|---|---|
| `python3 -m unittest tests.test_readiness_common` | `ModuleNotFoundError` + 計入 errors、**大聲** |
| `bun test <不存在的路徑>`（全域 AGENTS.md 實錄） | 靜默丟棄 + exit 0、**綠燈** |

**同一個錯，在一個 runner 上是 loud error，在另一個上是綠燈。差別不在使用者，在 runner 揭不揭露。**

這就是本 repo `AGENTS.md` 歸責紀律的完整陳述，也是本 BR 所有處方的目標形狀：
**把「缺席態」從「成功態」裡拆出來，讓它自己發出聲音。**

## 5. 本輪的實際代價

| 實例 | 代價 |
|---|---|
| ① | 一次假的 mutation proof（M2 回 OK 而 mutation 從未生效），靠「不信那個 OK」才抓到 —— **自律不是機制** |
| ② | 一次 `NameError`，`import` 全綠 |
| ③ | `readiness_common.py` 被寫成 0 bytes，靠更早的備份救回 |
| ④ | dispatcher 覆核時發現；若未發現，本輪全部 mutation 結論皆不可信 |
| ⑤ | **交付到 dispatcher 手上才被抓到** —— 通過了我全部的驗證，包含端對端 |

⑤ 是最貴的一格：它證明**在被測程式上做到位的紀律，沒有自動延伸到驗證工具與另一種語言**。

## 6. 建檔者自陳

本 BR 的處方 §4.6 是在**第五個實例被 dispatcher 抓到之後**才寫下的。前四個實例發生時，
我抓到了 ①（因為有可數的判準）、②③（因為它們立刻炸），**而 ⑤ 我沒有抓到**。

**正在寫某條規則不構成該規則的豁免** ——
`issues/BR_20260802_reset_hard_silently_destroyed_uncommitted_work_on_shared_tree.md`
的肇事者在事故前 30 分鐘才剛立案一張同族警告。本張的 ⑤ 與 ①，中間隔的正是我寫下
「重複定義會讓 mutation 打在死碼上」那段話的時間。
