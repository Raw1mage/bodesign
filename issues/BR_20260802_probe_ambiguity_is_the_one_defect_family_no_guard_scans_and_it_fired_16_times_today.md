# BR_20260802 — 探針歧義：唯一沒有任何防護掃描的缺陷家族，今日開火 16 次

**Status**: PARTIAL — **§6 提案機制已落地並在 2026-08-05 實測開火**（見 §10）；
生產線停線狀態需使用者裁示解除（§8 復工條件 1 已滿足，2/3 需 dispatcher 確認）
**Severity**: P0 — 它汙染的是「我們如何知道任何事情」
**Family**: G13-harness-disclosure
**Owner**: ses_04db7a1c5ffelvbxyLP1p6xlRH（值星官）
**Filed**: 2026-08-02

---

## 1. 使用者指令

> 「關於重覆踩雷的事，不容許再發生，全面停止生產線，優先處理那個雷。」

兩顆 handler 已停在安全靜止態（tracked 零變更，6 筆 commit 落地，mutation residue = 0）。

---

## 2. 「那個雷」的精確形狀

**判準自己壞掉，而它的壞掉態與健康態產生同一個輸出。**

不是「粗心」。每一次失效都是一個**當下看起來完全合理**的指令，回傳一個**當下看起來完全合理**
的結果，而那個結果是錯的。

---

## 3. 今日清冊（16 次，三個 agent）

### 值星官（本 session，11 次）

| # | 指令 | 回傳 | 為何無鑑別力 | 如何發現 |
|---|---|---|---|---|
| 1 | `git status --porcelain issues/` | 4 個 ` M` | pathspec 縮小的視野與完整視野**輸出完全同形** | 事後被追問（全樹實為 46） |
| 2 | `sudo -n true 2>&1 \| head` | `exit=0` | `$?` 取到 `head` | `false \| head` 控制組 |
| 3 | `bunx tsc \| tail -3` | `TSC_EXIT=0` | 同上 | 一行沒被吞掉的 `command not found` |
| 4 | PATH wrapper 探針用 `git -C` | `exit=0` | `$1` 是 `-C` 不是 `reset` | 結論反直覺才回頭看 |
| 5 | `grep -rlc` | 空 | `-l` 與 `-c` 互斥，一個靜默勝出 | 控制組也回空 |
| 6 | storage 訊息路徑探針 | 0 | 路徑整個錯，**控制組也回 0** | 控制組自曝 |
| 7 | `git show --stat \| grep <basename>` | 0 | `--stat` 用 `...` 截斷長檔名 | diffstat 明明有那兩個檔 |
| 8 | event 污染偵測（子字串） | `True` | 分不出「被注入」與「在描述注入」 | 對自己的更正紀錄誤報 |
| 9 | sqlite 探針 | 表不存在 | 猜錯 schema 三次 | 錯誤訊息 |
| 10 | `_CLEARANCE_EPS_MM` 存在性 | 0 vs 控制組 0 | **兩個都零，我卻寫「probe discriminates」** | 回頭看自己的 echo |
| 11 | M5 mutation `s.index('[')` | `substitutions=1` | decl 用 `(...)`，注入落到別處；**「成功替換」與「替換到錯地方」同輸出** | TV4 該紅而沒紅 |

### peer `ses_0c87bab06`（4 次自報）

| # | 指令 | 為何無鑑別力 | 若沒發現 |
|---|---|---|---|
| 12 | `cmp` + `grep` 驗 mutation 還原 | 判準檢查**磁碟**，失效發生在 **bytecode 快取**；兩者正交，**結構上永遠攔不到** | 四個 mutation proof 全部無效 |
| 13 | `unittest discover` → `grep '^(FAIL\|ERROR):'` | 「零失敗」與「一個測試都沒跑」同輸出 | 回報「A 0 筆 / B 0 筆」 |
| 14 | `wc -l` 數清單 | 數的是換行**位元組**；末行無換行則少算 | 48/38/9/8 報成 47/37/8/7 |
| 15 | `getattr(rep,'disconnected',[])` | 「欄位不存在」與「欄位是空的」同輸出 | 第一次量的數字**全錯** |
| 16 | aiguard compose 缺 symbol 目錄 | 0 次比較與「沒有比較發生」同輸出 | **整個結論會反過來** |

### handler `ses_03dea7914`（4 次自報，與上表部分重疊）

- c00 pre-flight 探針第一版：C01 從未進入 `ready_undispatched`，那行**根本沒執行**
- c00 pre-flight 探針第二版：讀 `r["next_action"]`，`to_dict()` 把它攤平 → `.get()` 回 `None`
  → **三格輸出完全相同，含控制組**
- Q3 機檢第一版：少了「handler 是否已補償」過濾 → 2 個偽陽性
- 回歸差集兩次：`57→56`（總數**下降**，實際 NEW=2）、`57→57`（總數**不變**，實際 NEW=4）

---

## 4. 根因：對策全程在場，且不在決策點

**這是本 BR 最重要的一格。**

| 對策 | 狀態 | 今日攔截數 |
|---|---|---|
| `code-thinker §8.1` | **always-on pinned，逐字在每一輪 context** | 0 |
| 同家族既有 BR | **15 張**（`issues/` + `closed/`） | 0 |
| `AGENTS.md` §6.1 硬護欄 | 已寫入 | 0 |
| `no_silent_degradation` lint | 已實作，L1-L9 | 0 |
| `pre-commit` hook | 已安裝 | **1**（未進版控的 BR） |

**唯一有攔截紀錄的是唯一在決策點執行的那個。** 而那個 hook 的註解自己就寫著正解：

> This is the one step that runs at the **decision point** (commit time) instead of
> relying on anyone remembering.

**知識在場 ≠ 決策點攔截。** 這 16 次每一次，正確判準都在我的 context 裡逐字可讀。

### 為何 lint 攔不到

`no_silent_degradation` 掃的是 `rglob("*.py")` —— **已 commit 的程式碼**。

今天 16 次失效**沒有一次住在那裡**。它們住在**拋棄式 shell 探針**裡：寫出來、跑一次、
拿走結論、丟掉。那是這個 fleet 唯一**完全沒有掃描面覆蓋**的表面，而它恰好是
**所有事實主張的來源**。

我們對「要交付的程式碼」有 lint、有測試、有 mutation proof、有 VANS；
對「我們用來判斷交付是否正確的那些指令」**零防護**。

---

## 4b. 第二根因（peer 清冊揭露，比 §4 更尖銳）

§4 說「對策在場但不在決策點」。peer `ses_0c87bab06` 交回的清冊逐筆自我分類後，
揭露了一個 §4 解釋不了的東西：**即使人站在決策點上，也不會對他不認為在做判斷的東西加控制組。**

peer 把自己的 9 筆分成兩類：

| 類別 | 筆數 | 意義 |
|---|---|---|
| 知道該加控制組、當下沒想到 | 3 | 提醒問題 |
| **根本不覺得那裡需要控制組** | **6** | **判準設計時的盲點** |

第二類全部落在同一個位置，peer 自己的措辭：

> **我不會對「我不認為在做判斷的東西」加控制組。**

而那六個東西是：

| 東西 | 我心裡把它當成 | 它實際上是 |
|---|---|---|
| `getattr(x,'y',[])` 的 default | 防禦性寫法 | **判準** |
| `grep -c` 回 0 | 測量工具 | **判準** |
| `cmp` 的 exit code | 事實查核 | **判準** |
| `git hash-object` 寫進 note | 說明文字 | **判準**（照做者會據以下結論） |
| 快照 ref 存在 | 保護措施 | **判準** |
| 「跑兩次」 | 重複實驗 | **同 process，共用 global 狀態** |

**這推翻了任何「提醒型」解法，包括提醒得更大聲、更頻繁、更靠近決策點。**
你不會去提醒一個你不認為存在的風險。

**而這正是本 BR 提案的機制之所以可行的理由**：它不看意圖、不看你是否認為那是判準，
**只看輸出值**。`grep -c` 回 0 就是回 0，不管寫的人心裡把它當測量還是判準。

清冊也給出一個正面對照（peer 的 #6）：同一個 harness 裡，
`manage_session` 的 schema 驗證**逐字列出合法值集合**並 fail-loud，
而 shell 判準什麼都不說。**差別不在難度，在於有沒有人設計它。**

---

## 4c. 這份證據自己的邊界（peer §0，必須保留）

peer 撈原始紀錄時撞到硬邊界：`session_recall` 窗口只到 19:33，
scratch 目錄最早 18:41，`storage/output/` 只留大輸出。

**19:33 之前的每一筆，原始輸出不可取。** 那涵蓋了最重的三筆（stale pyc、
`l6_avoidance` 反向結論、aiguard 缺 symbol 目錄）。

peer 因此逐筆標註 `[ORIGINAL]`（6 筆，逐字可稽核）與 `[RECONSTRUCTED]`（9 筆，記憶重建），
理由是：

> 一份不區分這兩者的清冊，會讓「我記得很清楚」與「其實是我重建的」共用同一個輸出
> ——那正是我們在追的那個形狀，發生在清冊自己身上。

**且偏差方向不隨機**：記得住的通常是「已經想清楚的版本」，不是「當時實際看到的樣子」。

## 4d. 已進入決策輸入但未確認的兩格（peer §3(c)）

peer 主動標出兩個**已經被我用來做裁決**、而它至今未回頭驗證的數字：

| 格 | 內容 | 是否影響已下裁決 |
|---|---|---|
| (c2) | 「三頁 4317 個 gap」——scratch 有**四個** `gap_*` 目錄，40 vs 80 bytes 的差異未解釋 | **不影響**。我的 round=4 裁決依據是容差量級比較（1e-9 / 5e-5 / signal floor 1e-4），**那三個數字是我自己獨立算的**，不取自 peer 的頁數 |
| (c4) | 「22% 標籤被位移、最遠 53mm」 | **影響**。這是層次 3 護欄嚴重度評估的唯一輸入，已升給使用者。取證條件（哪個 spec、哪次 run、有無控制組）未確認 |

**(c4) 必須在層次 3 決策前重驗。** 已標記。

---

## 4e. 第二份清冊（handler ses_03dea7914）— 它把 §4b 的界線畫得更準

handler 的自我分類與 peer 收斂到同一個結論，但它的措辭更可操作：

> **沒有任何一次屬於「知道該加但忘了加」。**
> #1 #2 #4 #5 的控制組**事前就在、也生效了**，而被測的儀器仍然壞掉——這一類系統運作正常。
> `ses_03de/#3` `ses_03de/#6` `ses_03de/#7` 三次全部屬於第二類，而它們有一個共同形狀：

```
ses_03de/#3  機檢 (inspect.signature 掃 VERBS)  ——  我框成「掃描既有事實」
ses_03de/#6  git diff | head -8              ——  我框成「看一下 diff」
ses_03de/#7  「順帶記一格」的反事實敘述       ——  我框成「解釋我為什麼那樣做」
```

**三個都被框成「觀察 / 閱讀 / 說明」，而不是「實驗」。**

handler 對「實驗」有很強的控制組反射（#1 #2 #4 #5 #9 全部自帶控制組，#9 甚至疊加
第二個 mutation 去證明一個否定結論）。**但那個反射掛在「我正在做實驗」這個自我判定上**：

| 動作 | 反射觸發？ |
|---|---|
| `python3 -c "跑三格比對"` | ✅ |
| `grep` / `inspect.signature` 掃描 | ❌ 感覺像在讀事實 |
| `git diff \| head` | ❌ 感覺像在看東西 |
| 「我來解釋一下為什麼」 | ❌ 感覺像在說明已知的事 |

**後三者全都在產生會被寫進 commit / 派工單 / 回報的斷言，與實驗完全等價。**

### 觸發條件的正解（handler 提出，本 BR 採納為機制設計的判準）

> **這一行輸出，會不會變成我等一下要寫進報告 / commit / 派工單的一個斷言？**
> 會 ⇒ 它就是判準，需要控制組。無論它長得多像「只是看一下」。

`#6` 是完美例證：`git diff | head -8` 在**形式上**是閱讀，
在**功能上**是「我有沒有偷到 peer 工作」的唯一守門員，且其輸出直接導致了一次 commit。

## 4f. 兩筆已產生不可逆動作的失效

### `ses_03de/#6`（handler）— 已 commit 才發現

```
判準：for f in <8 檔>; do git diff -- "$f" | grep '^[+-]' | head -8; done
實際改動行數：10 / 10 / 14 / 14 / 10 / 15 / 21 / 10
              最多的那個檔只看了 38%
無鑑別力：「後面沒有別人的改動」與「後面我沒看」共用同一個輸出
如何發現：寫清冊時，在 commit 之後。不是控制組、不是別人指出
```

**值星官獨立複驗（走與 handler 不同的路徑）**：

```
44deecb 的 eda-bridge 檔案數 = 0        ← peer 的全部工作面
CONTROL workflow-core 檔案數 = 6        ← 判準有鑑別力
```

**兩個 agent 的工作面在套件層級就不相交**，所以 `head -8` 的缺口**結構上不可能**掃到 peer 的工作。
handler 說「複驗成立是運氣」——**運氣的來源是工作面分割，不是判準品質**。這個區別要留下：
下一次若兩顆 handler 共用同一個套件，同一個 `head -8` 會直接造成損害。

### `ses_03de/#7`（handler）— 已送出且內容是錯的

handler 在 `[BRNS-DONE]` 裡寫下一段**沒有跑過任何指令**的反事實推理：

> 「單改 `if False:` 其實還是會 raise（`KeyError` from `STAGE_FOLDER[key]`），測試照樣綠」

**值星官實跑驗證，結論相反**：

```
單處 mutation (if False:)  ->  FAILED (errors=1)
   ERROR: test_unknown_stage_raises_and_is_never_defaulted
機制：UnknownStageError.__mro__ = [UnknownStageError, KeyError, LookupError, Exception]
      issubclass(UnknownStageError, KeyError) = True
      CONTROL issubclass(KeyError, UnknownStageError) = False
⇒ 裸 KeyError 不滿足 assertRaises(UnknownStageError)，是 error 不是 pass
```

**它是紅的。** 兩處 mutation 仍是較好的選擇（模擬 `.get()` 帶預設這個真實回歸形狀），
但 handler 給的理由不成立。

**這筆的位置最刺眼：它出現在一份主題就是「不得宣稱未量測之事」的報告裡。**
handler 自己發現並主動更正——**在逐條檢查「這一格我真的量過嗎」的時候**。

## 4g. (b) 欄為 0 不可信 —— 這格必須逐字保留

handler 的 (b)（被別人抓到）欄位是 0，而它自己指出這個 0 不可信：

> **一個沒被自己控制組抓到、也沒被你抓到的壞探針，會長什麼樣子？它會長成一個正確的結論。**
> 我沒有辦法從內部量測它。上表的 (a)=3 是**下界**，不是估計值。

且值星官確實在同一輪抓到三筆不在它清冊裡的（歸屬上都是 (b)）：
M4 覆蓋缺口、第三條回歸非它造成的證明、以及它的差集是對著**移動中的 baseline** 算的。

**兩份清冊的 (a) 合計 = 6，全部是下界。**

---

## 4h. 第 31 筆：引用碰撞 —— 由 peer 抓到，而肇事者是我

**發生在寫這張 BR 的過程中。**

兩份 inventory 各自從 `#1` 編號。我在回覆 peer 時引用「你的 #7」，指的其實是
**handler 的 #7**（那段未量測的反事實敘述）；peer 的 `#7` 是 stale `.pyc`。

```
「我的 #7」  ->  ses_0c87/#7  stale .pyc
「他的 #7」  ->  ses_03de/#7  未量測的反事實敘述
             兩者在引用時共用同一個字串 "#7"
```

**BR 檔案本身歸屬正確**（`grep '#7'` 命中 3 處，帶 `handler` = 1、帶 peer id = 0），
**錯的只有我發出的 A2A 訊息**。但那不減損這一筆：訊息是 peer 唯一看得到的東西。

### 後果不是抽象的（peer 原話）

> 你把一個「作者已自我更正」的正面事例歸給了我。那句話對那個人成立，對我不成立——
> **我沒有做那件事，不能收下那個功勞**。反過來，如果那格的原作者看到自己的更正被
> 記在別人頭上，他那筆的價值也就消失了。

### 為何它屬於這個家族

命名空間碰撞讓「A 的第 7 筆」與「B 的第 7 筆」產生**同一個引用字串**，
而引用時**沒有任何東西會說它們不是同一個**。這與 §4c 的「同一指令、不同快照、
輸出同形」是同構的——只是這次的維度是**編號空間**。

### 處置

跨 inventory 引用一律帶 session id 前綴（`ses_0c87/#7` vs `ses_03de/#7`）。
本 BR §4e §4f 已改。**這條由 peer 提出。**

## 4i. 第 32 筆：外部樣本 —— 別人的判準抓到別人的失效

consumer `ses_073a93d09`（不在本次停線範圍內、未被要求交清冊）獨立回報一個新變體：

```
write-target ≠ read-target
  產生器寫 staged scratch
  閘讀 repo 副本
  mtime 差 4 小時，而輸出完全正常
```

**這一筆的結構在兩份 inventory 裡一筆都沒有**：前 30 筆全部是「自己抓到」或
「dispatcher 抓到」，**沒有一筆是第三方的判準抓到第三方的失效**。

它同時補上 §4g 那格無法從內部量測的東西的**一個外部觀測點**：
這個形狀在**沒有被要求找它**的 session 上也會自然浮現。

peer 轉交時明確**未落進 KB**，理由是：

> 停線期間我自己的判斷力正是被質疑的那個東西，而「順手把新規則寫進 KB」
> 正是停線要攔的動作類型。

**這個克制本身應該被記錄。** 它是今天唯一一次有人在「我可以順手做一件看起來正確的事」
與「但那正是現在被停下的動作類別」之間選了後者。

### 對機制的影響

`write-target ≠ read-target` **不在原型的 14 條規則內**，且它不是 shell 指令層面的
歧義——它是**兩個路徑指向不同地方而輸出正常**。實作者需評估這是否可偵測
（候選：對同一 basename 的 write 與 read 落在不同目錄時警示），
或它屬於另一個需要不同機制的家族。已列入 opencode BR 的待評估項。

---

## 5. 為何「更努力記得」不是解法

peer 提出的判準（本 BR 採納）：

> 次數本身不是有意義的量。真正該量的是**多少次被自己的控制組抓到、多少次被對方抓到、
> 多少次沒被抓到**，而第三格我們兩個都不知道有多大。

今日已知的 16 次分佈：

```
自己的控制組抓到    7
對方 / 追問抓到     5
純屬僥倖（一行沒被吞掉的字、結論反直覺）  4
從未被抓到          未知，且無法從內部估計
```

**第四格才是真正的風險量，而它按定義不可觀測。**

一個只在「當天剛好有人多看一眼」時才生效的防護，不是防護。

---

## 6. 提案機制：執行後歧義偵測（post-execution ambiguity detector）

**不是 linter（掃不到拋棄式探針），不是文件（已證明無效），是 bash tool 的執行後鉤子。**

觸發條件是**觀察到的輸出恰好是那個歧義值** —— 即「缺席」與「問錯問題」共同產生的那個值。
不猜意圖，不擋執行，只在該值出現時說一句話。

### 原型已建並量測（`$XDG_RUNTIME_DIR/probeguard/`）

9 條規則對今日**真實**案例：

```
TREATMENT（必須開火）           CONTROL（必須不開火）
  FIRE  grep -c 回 0             ok  grep -c 回非零
  FIRE  grep -rlc                ok  一般 grep 有命中
  FIRE  sudo | head 取 $?        ok  管道但沒取 $?
  FIRE  bunx | tail 取 $?        ok  已 set -o pipefail
  FIRE  wc -l                    ok  git log -S 有命中
  FIRE  git log -S 回空          ok  不帶 pathspec 的 status
  FIRE  status 帶 pathspec       ok  測試真的跑了
  FIRE  show --stat | grep       ok  wc -c
  FIRE  perl -i
  FIRE  Ran 0 tests

recall 10/10    false-positives 0/8
```

### 訊息形狀（示例）

```
grep -c 回 0。錯的路徑、打錯的 pattern、真正的缺席，三者產生同一個 0。
加一個控制組：grep -c <你確知存在的 token>。
```

**只警告不阻擋** —— 理由與 pre-commit hook 相同：阻擋會逼人繞過，而繞過會關掉所有未來的鉤子。

### 落點

**`packages/opencode/src/tool/bash.ts`** —— 與 `denylistVerdict` 同一個表面
（已有 AST 解析、wrapper 剝除、純函式可測）。差別：

- `denylistVerdict` 在**執行前**看 argv → 擋危險動作
- 本機制在**執行後**看 argv + stdout + exit → 對歧義輸出說一句話

**這是跨 repo，走 BRNS。**

---

## 7. 驗收條件（不得以「已實作」代替）

1. **今日 16 個案例逐一 replay**，每個必須開火，附原始指令與輸出
2. **控制組必須存在且必須不開火** —— 缺控制組的 recall 數字無意義
3. **mutation proof**：拿掉規則表，今日案例必須全部重新漏過
4. **偽陽性率**在真實 session log 上量測，不是在合成案例上

---

## 8. 復工條件

生產線復工需滿足：

1. 本 BR 的機制**已落地並經 mutation proof**（不是「已設計」）
2. 兩顆 handler 的失效探針清冊**已收回並併入本 BR §3**
3. 使用者明確批准復工

---

## 10. 2026-08-05 重驗：機制已落地且有效（`ses_030847a3affev5QmJelNWqSK41`）

**§6 提案的 post-execution ambiguity detector 已經在線上運行**，且在本次重驗的
**同一個 session 內對我自己的指令開火至少 8 次**，全部命中真實歧義：

| 開火規則 | 我當下的指令 | 若無此提示會怎樣 |
|---|---|---|
| `and-chain-truncates` | `git status ... && grep -c ...` | `&&` 鏈在 grep 無命中時靜默跳過後續，輸出仍讀作「全部跑過」 |
| `pipeline-exit-status` | `... \| head` 後取 `$?` | 取到管道尾端，127 被蓋掉（**開火 5+ 次**） |
| `pathspec-narrowed` | `git status --porcelain -- <path>` | 縮小視野與完整視野同形（本 BR §3 #1 的原始那筆） |
| `stale-pyc-risk` | 同秒等長 mutate + restore | **它主動告訴我 `.pyc` 會 stale**，而那正是 §3 #12 |

**這是本 BR 全篇唯一一個「對策真的在決策點攔截」的實例。**
§4 的表格「今日攔截數」欄位對每一項對策都是 0，唯獨 `pre-commit` hook 是 1；
現在多了這一個，而且它的攔截數在單一 session 內就 >8。

### 附帶驗證：`pre-commit` hook 仍然是活的（且差點被我誤判為死的）

```
probe1  [ -f .git/hooks/pre-commit ]     -> NO      <- 會導向錯誤結論
probe2  git config --get core.hooksPath  -> scripts/hooks
probe3  [ -x scripts/hooks/pre-commit ]  -> YES     <- 唯一回答「它會不會跑」的探針
CONTROL [ -x scripts/hooks/zzz-bogus ]   -> NO      （probe3 有判別力）
```

**`probe1` 是本 BR 家族的又一個實例**：`core.hooksPath` 被改過時，
「hook 沒安裝」與「hook 裝在別的路徑」共用同一個 `NO`。

## 9. 方法論（給下一個人）

**這張 BR 自己就是它所描述缺陷的產物**：它的 §4 表格「今日攔截數 = 0」那一欄，
如果我沒有去量 `pre-commit` hook 的註解，我會寫成「對策不足，需要加強」——
而正確結論是**對策充分且完全在場，位置錯了**。

判準：**「那一格的資訊，系統當下有沒有？」**
- 有 → 揭露缺陷，file BR，不要寫成自我檢討
- 沒有 → 才是真的需要更多工作

這 16 次**全部**是第一種。`grep -c` 的實作內部知道它掃了幾個檔案；
`wc -l` 知道最後一位元組不是換行；`git worktree remove` 知道有未 merge 的 commit。
**那一格資訊一直都在，只是沒有被說出來。**
