# BR_20260804e — `pkill -f <pattern>` 把呼叫者自己的命令列算進目標，靜默殺掉發出指令的 shell

- **Severity**: MEDIUM（不損毀資料，但**中斷整串指令且無任何輸出**；後續步驟看起來像「沒印東西」而非「沒執行」）
- **Component**: 操作面 / harness disclosure（`procps-ng 4.0.4` 的 `pkill`），非本 repo 程式碼
- **Family**: G13-harness-disclosure
- **Owner**: ses_03408d1faffeKuPkQZ9Zj6gWO2
- **Status**: FIXED（處方已採納）— 2026-08-05 重驗：本 BR 的核心處方**已寫進 `AGENTS.md §6.2`**
  （行 171，標題逐字為「`pkill -f` / `pgrep -f` 會把發出指令的 shell 算進目標（2026-08-04）」，
  含 `-A` 正解與量測表）。§Related 裡「建議把本條加進該表——需 dispatcher 裁示」**已完成**。
  CONTROL：同一支 grep 對 `reset --hard` 回 4、對 bogus token 回 0 ⇒ 探針有判別力。
  剩餘：`pkill` 本身的預設行為屬 `procps-ng` 上游，本 repo 不可修，也不需修。
- **Scheduled**: 未排（guard C 曝險量測途中踩到，當輪建檔不批次）
- **編號改過**: 2026-08-04 由 `d` 改為 `e`。handler 建檔當下，dispatcher 已在另一條線上
  將 `BR_20260804d` 給了 `load_symbol` 的 stale 2-tuple（`c8e7bd9`，且已被 `BR_20260804c:149`
  **以編號而非完整檔名引用**）。兩張同輪建檔、互不可見，碰撞在兩邊都是靜默的——
  `ls issues/` 照常列出兩張，而那個編號引用同時指向兩者。**這本身就是本 BR 的形狀：
  「編號唯一」與「編號撞車」共用同一個輸出。** 改 handler 這張是因為它尚未 commit 且
  無任何引用指向它（已驗：refs=0），成本最低。

---

## 1. 一句話

`pkill -f "foo"` 匹配的是**完整命令列**，而發出這道指令的 shell，其命令列**本身就含有 `foo`**——
於是 `pkill` 連同呼叫者一起殺。整串指令從該步之後停止執行，**且不印任何訊息**。

「殺了目標」與「殺了目標**並殺了自己**」共用同一個輸出：**沒有輸出**。

## 2. 量測（三格對照，可重跑）

**設計要點**：marker 必須**執行期生成**，否則它會出現在量測腳本自己的命令列裡而污染實驗
（我前三次嘗試都因此自殺——見 §5）。受測者是我 spawn 的子 shell，其 cmdline 含 marker，
忠實對應「人在終端機手打這道指令」。

```python
M = "zq" + 隨機10碼                      # 執行期生成，不出現在任何祖先的 cmdline
decoy = Popen(["bash","-c", f"exec -a {M} sleep 30"], start_new_session=True)
subprocess.run(["bash","-c", f'pkill -f {M}; echo SURVIVED > {OUT}'])
caller_survived = OUT 檔存在              # 沒寫成 => 那個 shell 在 echo 之前就死了
target_killed   = decoy.poll() is not None
```

```
variant                    caller       target     meaning
------------------------------------------------------------------------------
A  pkill -f M              KILLED-SELF  killed     目標死了，呼叫者也死了      <- 缺陷
B  pkill -A -f M           SURVIVED     killed     目標死了，呼叫者活著        <- 預期
C  no target exists        KILLED-SELF  n/a        沒有任何東西該被殺，呼叫者仍死
```

**C 是決定性的那格。** 它排除了「殺過頭」這個解釋：目標根本不存在，
`pkill` 仍然找到一個匹配——**它自己的呼叫者**。

B 證明判別力：同一支腳本、同一個 marker，只加 `-A` 就正常。

## 3. 為什麼這是揭露缺陷而非操作失誤

判準（AGENTS.md「歸責紀律」）：**那一格的資訊，系統當下有沒有？**

**有，而且它已經用了一半：**

```
man pkill:203   "The running pgrep, pkill, or pidwait process will never report itself"
man pkill:133   -A, --ignore-ancestors   Ignore all ancestors of pgrep, pkill, or pidwait
```

`pkill` **知道**哪個 pid 是它自己（明文排除），也**知道**祖先是誰（`-A` 就是幹這個的）。
它只是**預設不排除祖先**——而祖先正是那個「命令列裡含有 pattern」的 shell。

所以缺的不是知識，是**預設值 + 揭露**：

- 沒有任何警告說「本次匹配包含你的祖先行程」
- 殺了 N 個與殺了 N 個並自殺，回傳與輸出完全相同
- `-A` 存在但要先知道它存在才會去用；而**會去查 man 的前提是先察覺出事了**

## 4. 處方

```bash
pkill -f "[f]oo"          # bracket trick：pattern 匹配 foo，但字面上不是 foo
pkill -A -f "foo"         # 顯式排除祖先（procps-ng ≥ 3.3.x）
pgrep -a -f "foo"         # 先看清楚要殺誰，再殺
```

**通則（比 `pkill` 本身重要）**：任何「以命令列文字為條件」的批次動作，
**條件本身會出現在下條件的那個行程的命令列裡**。同族：`ps | grep foo`（永遠多一列 grep 自己）、
`kill $(pgrep -f foo)`、`docker ps | grep`。

## 5. 這條 BR 的量測過程本身踩了三次同一個坑

值得記錄，因為它顯示這個缺陷**在你正在研究它的時候仍然會咬你**：

| 嘗試 | 失敗方式 |
|---|---|
| 1 | `pkill -f "guardc-scan/scan.py"` — 原始事故，整串指令靜默中斷，我以為是檔案沒寫成功 |
| 2 | 把 pattern 寫進 heredoc 腳本 — **heredoc 內容是父 shell 命令列的一部分**，照樣自殺 |
| 3 | 加了 `absent` 控制組（「什麼都不該殺」）— 那格的字面 pattern 也在我的命令列裡，**控制組自己也自殺** |

第 3 次最值得留意：**我的控制組與 treatment 死於同一個原因**，
所以它當時無法證明任何事——這正是 code-thinker §8 那條的實例
（判準與被測對象共用同一個失效模式時，判別力歸零）。

## 6. 明確不建議

- **不要**把 `-A` 當萬靈丹寫進所有腳本。它排除祖先，但不排除**兄弟** shell
  （例如同一個 harness 開的另一個工具呼叫）。bracket trick 更精確，因為它從根本上讓字面不匹配。

## Related

- `issues/BR_20260804_bus_route_docstring_promises_a_channel_router_the_code_does_not_implement.md`
  （**同族 failure class**：宣稱存在的護欄實際不生效，讀者因此停止尋找防護。
  前者是 docstring 承諾 code 沒有的演算法；本 BR 是 `-A` 存在但預設不啟用，
  兩者都讓「看起來安全」與「真的安全」共用同一個表面）
- `AGENTS.md §6.1` 共用工作樹紀律的危險指令表
  （**同一形狀，不同指令**：該表的 `git reset --hard` 是「靜默執行、exit 0、什麼都不印」，
  本 BR 的 `pkill -f` 是「靜默自殺、無輸出」。**建議把本條加進該表**——
  需 dispatcher 裁示，因為 `AGENTS.md` 在我的 fix surface 之外）
- `issues/BR_20260804b_guard_c_inset_inverts_the_box_for_narrow_bodies_so_intrusion_check_is_blind.md`
  （**時序因果**：本缺陷是在執行 804b 的曝險量測、要換掉一支跑太久的背景掃描時踩到的）
