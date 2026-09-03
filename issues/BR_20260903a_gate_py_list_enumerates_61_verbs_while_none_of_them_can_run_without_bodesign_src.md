# BR_20260903a — `gate.py --list` 列出 61 個 verb 且 rc=0，而在同一個環境下這 61 個 verb 一個都跑不起來

- **Status**: OPEN — 已由 bodesign handler 獨立重驗（三格＋四組控制組），修法未裁示。

| Field | Value |
| --- | --- |
| Title | The landing-verb roster prints successfully when the package root it depends on was never resolved, so "verb exists" and "verb is runnable" share one reassuring output |
| Component | `~/.local/share/opencode/skills/bodesign/scripts/gate.py:74-103`（`_resolve_src`）、`:908`（唯一呼叫點）、`SKILL.md:244-252` |
| Owner | 未指派（handler `ses_f9b3c1c20ffeHznP5iE1YLe38n` 立案，權責歸 bodesign 值星官 `ses_04db7a1c5ffelvbxyLP1p6xlRH`） |
| Reporter | `thesmart_products` 值星官 `ses_038683542`（客人，只報不動手），跑 `04.btdongle` C00–C04 交付物時撞出；由 bodesign handler 獨立重驗 |
| Date | 2026-09-03 |
| Severity | medium — 不影響 runtime 正確性。危害在**派工判斷**：cold-context agent 讀 `--list` 得到一份看似可用的 61 verb 名冊，據以規劃整套 C00–C04 工作，在第一次真正呼叫時才撞牆，而錯誤訊息的形狀讓人先懷疑自己路徑打錯 |
| Family | `G13-harness-disclosure` |
| Affected paths | `scripts/gate.py`（skill 發佈副本）、`SKILL.md`、`stages/*/GUIDE.md`（8 份，全部未提 `BODESIGN_SRC`） |

## 1. 症狀

XDG 安裝的 skill 副本（`~/.local/share/opencode/skills/bodesign/`）**不帶 `packages/`**，
而 `gate.py` 的 landing verb 全部靠 `packages/workflow-core` 等套件執行。
未設 `BODESIGN_SRC` 時：

- `gate.py --list` → **rc=0，`ok:true`，`count:61`**，完整列出 61 個 verb 的名稱、模組、必填參數與摘要。
- 同一環境下呼叫其中**任何一個** verb → **rc=1，`LANDING_PACKAGES_NOT_FOUND`**。

兩者之間沒有任何訊號。`--list` 不會提到 `packages/` 沒找到，也不會提到 `BODESIGN_SRC`。

## 2. 重驗（獨立於客人回報，2026-09-03）

環境：`BODESIGN_SRC` 在本 shell 未設（`printf 'BODESIGN_SRC=[%s]' "${BODESIGN_SRC-<unset>}"` → `[<unset>]`）。
每格用 `env -u BODESIGN_SRC` / `env BODESIGN_SRC=…` 在**同一次 bash 呼叫內**設定，
因為環境變數不跨 tool call 存活（分兩次呼叫會靜默地什麼都沒設）。

### 前置事實（決定性）

```
ls -ld ~/.local/share/opencode/skills/bodesign/packages
  → ls: cannot access ...: No such file or directory     (rc=2)
ls -ld /home/pkcs12/projects/bodesign/packages/workflow-core
  → drwxr-xr-x 3 pkcs12 pkcs12 4096 Jun  6 11:56 ...     (rc=0)
```

skill 副本無 `packages/`，repo 有。這排除了「客人環境特殊」這個解釋。

### 格 1 — `--list` 在未設變數時正常輸出

```
list_out=$(env -u BODESIGN_SRC python3 <skill>/scripts/gate.py --list 2>&1)
list_rc=0
list_bytes=16592
{"ok": true, "verb": "--list", "result": {"count": 61, "verbs": [...]}}
```

`count` 由我自己讀 JSON 得到 **61**，與客人回報一致（未引用其數字）。
輸出中出現 `always_required` 與 `not_landing`（40 個容器 tool 對照），**無任何 `packages/` 或 `BODESIGN_SRC` 字樣**。

### 格 2 — 同條件下 landing verb 不可執行（兩個 verb 各一次）

```
env -u BODESIGN_SRC python3 gate.py agent_registry --repo /home/pkcs12/projects/bodesign
rc=1
landing_verb_error verb=agent_registry code=LANDING_PACKAGES_NOT_FOUND
{"ok": false, "verb": "agent_registry", "error": {"code": "LANDING_PACKAGES_NOT_FOUND",
 "message": "could not find bodesign packages/ (looked for packages/workflow-core); tried:
 /home/pkcs12/.local/share/opencode/skills/bodesign/scripts,
 /home/pkcs12/.local/share/opencode/skills/bodesign,
 /home/pkcs12/.local/share/opencode/skills,
 /home/pkcs12/.local/share/opencode, /home/pkcs12/.local/share, /home/pkcs12/.local,
 /home/pkcs12, /home, /. Set BODESIGN_SRC=/path/to/bodesign repo.",
 "hint": "export BODESIGN_SRC=<bodesign repo root containing packages/*>"}}

env -u BODESIGN_SRC python3 gate.py package_readiness --repo /home/pkcs12/projects/bodesign
rc=1  同一 code，同一 tried 清單
```

`agent_registry` 是 `--list` 排序後的**第一個** verb 且 `required_args: []`——
挑它排除了「參數給錯」這個競爭解釋。

### 格 3 — 設了變數後同一個 verb 可執行

```
env BODESIGN_SRC=/home/pkcs12/projects/bodesign python3 gate.py agent_registry --repo /home/pkcs12/projects/bodesign
rc=0  bytes=6440
landing_verb_start verb=agent_registry repo=/home/pkcs12/projects/bodesign
landing_verb_ok verb=agent_registry
{"ok": true, "verb": "agent_registry", "result": {"schema": "bodesign.agent_registry.v1",
 "source_path": "/home/pkcs12/projects/bodesign/packages/workflow-core/.../doc_architecture.template.json", ...}}

同上，package_readiness → rc=0, ok:true, readiness_pct:67
```

**三格合起來才是證明**：格 1 單獨只證明「`--list` 會輸出東西」。
格 2 證明同一環境下 verb 不可執行，格 3 證明差異的唯一自變數就是 `BODESIGN_SRC`。

### 控制組（證明探針有牙）

| 控制組 | 指令 | 結果 | 它排除了什麼 |
| --- | --- | --- | --- |
| 負控制 A — verb 名錯 | `env BODESIGN_SRC=<repo> gate.py zzz_bogus_verb --repo <repo>` | rc=1，`VERB_UNKNOWN` | 排除「所有失敗都回同一個 code」——`LANDING_PACKAGES_NOT_FOUND` 是**特定**於 packages 解析失敗的 |
| 負控制 B — 變數指向沒有 packages 的目錄 | `env BODESIGN_SRC=/home/pkcs12 gate.py agent_registry --repo <repo>` | rc=1，`LANDING_PACKAGES_NOT_FOUND`，`tried: /home/pkcs12`（**只有一項**） | 證明 `BODESIGN_SRC` 確實被讀取且走 early-return 分支（tried 清單從 9 項變 1 項），排除「設了也沒差、格 3 的成功另有原因」 |
| 正控制 A | `env BODESIGN_SRC=<repo>` 下兩個不同 verb 皆 rc=0 | `agent_registry` / `package_readiness` 都 `ok:true` | 排除「這支 gate.py 本來就跑不動」 |
| 正控制 B | 未設變數下兩個不同 verb 皆 rc=1 同 code | 同上兩個 verb | 排除「只有那一個 verb 壞掉」 |

## 3. 根因（讀原始碼，非引述回報）

`scripts/gate.py:74-103`：

```python
def _resolve_src():
    tried = []
    env = os.environ.get("BODESIGN_SRC")
    if env:
        cand = os.path.realpath(env)
        tried.append(cand)
        if os.path.isdir(os.path.join(cand, "packages", "workflow-core")):
            return cand
    else:
        here = os.path.dirname(os.path.realpath(__file__))
        cur = here
        while True:
            tried.append(cur)
            if os.path.isdir(os.path.join(cur, "packages", "workflow-core")):
                return cur
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
    raise LandingError(LANDING_PACKAGES_NOT_FOUND, ...)
```

它只從 `gate.py` 自身位置往上走。XDG 發佈副本位於
`~/.local/share/opencode/skills/bodesign/scripts/`，往上走到 `/` 都沒有 `packages/workflow-core`
（實測 tried 清單逐字列出這 9 層）。真正的套件在 `/home/pkcs12/projects/bodesign/packages/`。

`grep -n '_resolve_src' gate.py` → 只有兩處：`:74` 定義、`:908` 唯一呼叫點。
**`--list` 的程式路徑不經過 `:908`**——這就是為什麼名冊列得出來而 verb 跑不起來。

`_resolve_src()` 是唯一知道「`packages/` 找不到」的地方，而 `--list` 從不問它。

## 4. 為什麼歸 `G13-harness-disclosure` 而非文件缺口

**系統當下就握有那格資訊**：`_resolve_src()` 只要被呼叫就會立刻知道 packages 不可解析，
錯誤訊息裡連 9 層 tried 清單和 `hint` 都寫好了。缺的不是資訊，是**揭露時機**——
它只在讀者已經撞牆之後才說，而讀者做派工決策的時刻是在讀 `--list` 的那一刻。

「61 個 verb 都能用」與「61 個 verb 都不能用」共用同一個 `{"ok": true, "count": 61}`。

文件面同時也缺，但那是次要症狀：

```
grep -rn 'BODESIGN_SRC' <skill>/stages/           → 0 命中
grep -rn 'BODESIGN_SRC' <skill> --include='*.md'  → 1 命中：SKILL.md:251
grep -rln 'LANDING_PACKAGES_NOT_FOUND' <skill>    → SKILL.md, scripts/gate.py, gate.pyc  ← 正控制，探針有牙
```

`SKILL.md:251` 確實寫了「When the skill is projected outside the bodesign checkout (XDG install), set
`BODESIGN_SRC=<bodesign repo>` explicitly」——**所以「完全沒有記載」這句不成立，這一點與客人回報不同，
本張據實記為「只記載在 SKILL.md 一處、8 份 stage GUIDE.md 全部未提」**。
但它位於 SKILL.md 第 251 行的一段散文中間，且**未說明未設時 `--list` 仍會成功**。
一個從 stage GUIDE 進場的 caller（客人正是如此）在原理上不會讀到它。

## 5. 兩個修法方向（**本輪不修**，供 dispatcher 裁決）

- **A（較佳）— `--list` 自我揭露**：`--list` 路徑先試 `_resolve_src()`，失敗時在同一個 JSON envelope
  裡帶 `packages_resolved:false` + `hint`，或直接把 `count` 標成 unverified。
  理由：把資訊放在讀者當下會看到的地方，且它把「名冊可讀」與「verb 可執行」拆成兩個不同的輸出。
- **B（互補）— GUIDE 載明**：在 8 份 `stages/*/GUIDE.md` 首次出現 landing verb 之處寫明前置條件。
  單獨採 B 不足：它依賴讀者讀到那一段，而 `--list` 仍會在讀者沒讀到時給出令人安心的輸出。

## 6. 沒量到什麼

- 未量測非 XDG 安裝（skill 就在 bodesign checkout 內）時的行為——按 `_resolve_src()` 邏輯它會往上走到 repo root 而成功，但**未實測**。
- 未量測容器內 MCP tool 路徑是否有同類問題（landing verb 與容器 tool 是兩條路徑）。
- 未量測其餘 59 個 verb（只測 `agent_registry` 與 `package_readiness` 兩個）。tried 清單相同、失敗發生在 verb dispatch 之前，但**逐一實測未做**。
- 未修改任何檔案（派工單明令 step 3 不修）。

**Related**:
- `issues/BR_20260902_status_checker_reads_line_3_only_so_warn_zero_means_line_3_conforms_not_ledger_consistent.md`
  — 同一具名失效類別 `G13-harness-disclosure`，且是**同一個形狀**：工具的實際視窗（該張是「只掃 line 3」，本張是「`--list` 不經過 `_resolve_src()`」）比讀者以為的窄，
  而窄視窗下的成功輸出（該張 `WARN=0`、本張 `ok:true count:61`）與寬視窗下的成功輸出逐字相同。已讀該張 header 確認 Family 欄逐字為 `G13-harness-disclosure`。
- `issues/closed/BR_20260901_c02_render_enclosure_token_relative_path_never_resolved.md`
  — 同 family（該張 header 逐字寫 `Family: G13-harness-disclosure — success state and failure state sharing one output`），
  且同為**路徑解析參考框不一致**：該張是 guard 與被 guard 程式在不同 frame 解析同一輸入；本張是 `gate.py` 以「自身檔案位置」為 frame 解析套件根，而發佈副本的位置與套件根已分離。

