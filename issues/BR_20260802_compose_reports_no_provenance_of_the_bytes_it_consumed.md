# BR_20260802 — compose 的成功回報不含它讀了哪些位元組

Status: OPEN
Owner: 未定（bodesign-platform；本 repo 為 consumer，不在此修）
Filed: 2026-08-02 by ses_073a93d09ffeRTpR9TwIdofhb3（thesmart_products 值星官）
Family: no-silent-degradation（V-series 變體，見 bodesign `ragbase/control/no-silent-degradation/`）
Repo: bodesign（`packages/eda-bridge/bodesign_eda_bridge/composer.py`）

---

## 1. 一句話

`compose_schematic()` 回傳 `placed` / `nets` / `erc_errors` / `warnings`，但**不回報它實際讀了哪個路徑、哪個版本的位元組**。於是「compose 了你剛寫的檔」與「compose 了一份你早已取代的舊檔」產生**完全相同形狀的成功回報**。

---

## 2. 實測（2026-08-02，aiguard C03 修復現場）

`gen_ccm.py` 第 4 行硬編容器路徑：

```python
FB = "/work/aiguard/C03-EE/full_board"
```

而該路徑**不是 bind mount**。實測 `bodesign-pkcs12-bodesign-ee-1` 的 `/proc/1/mountinfo`，`/work` 底下只有一條真掛載：

```
/home/pkcs12/projects/bodesign/experiments  ->  /work/experiments   (ext4, bind)
```

`/work/aiguard` 落在容器 overlay 層，內容只能靠 `docker cp` 推進去。

### 決定性的那一刻

在我推檔之前，兩邊的狀態是：

| 位置 | gen_ccm.py |
|---|---|
| host 工作區（consumer 的真實檔案） | **20289** bytes（`ccm_nc` 已清空、UW1→J_WIFI 已轉換） |
| 容器 `$FB`（compose 實際會讀的） | **23682** bytes（修復前原版，169 筆 NC 仍在） |

**若在那一刻跑 compose，它會回傳一個結構完整、`unresolved_pins []`、看起來成功的結果——而那個結果描述的是 consumer 已經取代掉的檔案。** 回傳值裡沒有任何一格能讓呼叫端察覺這件事。

這不是假設。兩個尺寸都是我 `stat` 量到的，時間差約 2 分鐘。

---

## 3. 為什麼這是揭露缺陷，不是使用者操作不當

判準（AGENTS.md 歸責紀律）：**那一格的資訊，系統當下有沒有？**

**有。** composer 開檔的那一刻就握有完整路徑；要取 `st_mtime` 或 sha256 是零成本。它選擇不放進回傳值。

呼叫端要自行防守的話，必須在每次 compose 前後手動比對 host 與容器的檔案雜湊——**而那正是 composer 自己一行就能做完的事**。把這個責任推給每一個 consumer，等於保證它遲早被漏掉一次。

---

## 4. 同族形狀

這與本 repo `AGENTS.md §4.1` 記載的 FUSE stale-index 事故**是同一個形狀**：

| | 舊帳（git） | 本張（compose） |
|---|---|---|
| 工具 | `git commit` | `compose_schematic()` |
| 讀到的 | 三週前的 `.git/index` 快取副本 | 容器 overlay 裡的舊 `gen_ccm.py` |
| 回報 | 成功，產生一個 commit | 成功，`placed/nets/erc` 齊全 |
| 缺的那一格 | 「我序列化的是哪份 index」 | 「我 compose 的是哪份位元組」 |
| 後果 | 12 個活檔被記成 `D` | 綠燈描述一份已不存在的設計 |

兩者都符合 `code-thinker §8.1`：**缺席態與失敗態共用同一個輸出**。這裡更精確的說法是——**過期態與當前態共用同一個輸出**。

也直接連到 §8.1 的推論：**驗證必須落在你要交付的 artifact 上，而不是你餵給工具的輸入**。目前 compose 讓呼叫端連「工具究竟拿到了什麼輸入」都無從得知，於是連這條紀律都無法執行。

---

## 5. 修法建議（platform 側）

`compose_schematic()` 的回傳值增加 input provenance：

```python
r.inputs = [
  {"path": "/work/aiguard/.../gen_ccm.py", "sha256": "...", "mtime": 1785650604, "bytes": 20289},
  {"path": ".../authentic_host/aiguard_U5.kicad_sym", "sha256": "...", ...},
  ...
]
```

有了這格，consumer 就能做一件目前做不到的事：**斷言「你 compose 的那份，就是我寫的那份」**。

**選配但更強**：`compose_schematic(expect_sha={path: sha})`，不符即 fail-fast。這把「查證」從 consumer 的自律變成工具的閘。

---

## 6. 附帶量測到的第二格（同一次 run，較次要）

同一次 compose 吐出 90 條：

```
POWER_PORT_INSIDE_SYMBOL_BODY: power-port endpoints fell inside a component symbol body
  (stub orientation defect — BR left-pin stub blind): VSYS@(154.94,10.16) inside U1; ... (+78 more)
```

warning 文字自承這是 **composer 的 stub 方向缺陷**，非呼叫端接線錯誤。它以 warning 形式出現、不影響 `erc_errors`，屬合理分級；記在此處僅供 platform owner 併案參考，**本張 BR 的主體是 §2**。

---

## 7. 對 aiguard 交付的實際影響

本次**未**造成錯誤結論——我在 compose 前先推檔並驗過落地位元組（`docker exec stat` 確認 20289），所以 `erc_errors 253 / components 78 / nets 368` 這組數字描述的是正確版本。

但那是**我恰好多做了一步**，不是系統保證的。同一天已有兩顆 handler 在這條 rail 上各自 stage 過容器，其中一顆跑出 `erc_errors 119`——**沒有任何機制能讓我事後判定那 119 是在哪個版本上量的**。它因此只能整筆作廢。

這就是缺乏 provenance 的真實代價：**不是產生錯誤答案，是讓正確答案與錯誤答案事後無法區分，於是全部得重做。**

---

## 8. 附錄：本次踩到的三個容器坑（給下一個 consumer）

不屬本 BR 主體，但同一條 rail 上必踩，記在此處避免重複損耗：

1. **必須用 `bodesign-ee-1`，不是 `bodesign-1`** — 後者無 `/usr/share/kicad/symbols`（KiCad 標準庫），`Conn_01x36` 必定 load 失敗。
2. **`authentic_host/` 須用 `authentic_lib/refetch_20260707/` 版** — 頂層 `authentic_lib/` 是舊料號（`aiguard_U3`=`MX25UM25645GMI00`、`aiguard_U5`=`TPS62826DMQR`），與 `gen_ccm.py` 要的 `MX25UM51245GXDI00`/`TPS62088YFPR` 不符 → `SymbolLoadError`。**兩個目錄同名同結構，錯的那個沒有任何標記。**
3. **`docker cp <目錄>` 巢狀放入而非覆蓋** — symbol 沉到深一層，composer 看不到，**症狀與「symbol 根本不存在」完全相同**。逐檔 cp。

第 2、3 點各自也是同族形狀（**錯的東西與對的東西外觀相同**），但屬操作面而非 API 面，故不獨立立案。

---

## 9. 實作與驗證（2026-08-02，`ses_0c87bab06fferQ0umBs2Nybb5U`）

### 修法

**`inputs` 恆存在，不在旗標後面。** 需要主動索取的 provenance，在問題真正浮現的那一刻不會在手上——
而那一刻永遠是事後，數字已經可疑、只剩作廢一途。回應固定帶：

```
inputs: {
  symbol_libraries: [{path, sha256, mtime, bytes}, ...],   # 真的開過的檔
  symbol_dirs_searched: [...],
  spec_sha256: "...",  spec_components: N,
  expect_sha_checked: [...]
}
```

**一處前提修正**：`compose_schematic` 從不讀 `gen_ccm.py`——它收的是 `spec: dict`（`composer.py:1741`）。
所以誠實的 provenance 是「它真的開過的檔」（symbol libraries）＋「它真的收到的 spec 的摘要」，
而不是回報一個它沒碰過的產生器腳本。`spec_sha256` 正是用來分辨「同一組數字但 spec 不同」的那一格，
也就是本 BR §2 描述的場景在 API 邊界上的實際形狀。

**`expect_sha` 是承重的那一半。** 只回報位元組，仍把「查證」留給呼叫端的自律，
而依賴有人記得的檢查，終究會有一次沒做。宣告摘要把檢查移進工具本身：

```python
compose_schematic(..., expect_sha={path: sha256})
  → 不符即 InputProvenanceMismatch，且在任何工作發生之前
```

**解析單一真相來源**：新增 `kicad_emit.resolve_symbol_library()`，`load_symbol` 改為呼叫它。
provenance 回報與實際載入走同一條解析路徑，**回報的路徑無法與載入的路徑漂移**——
一份可能與它所描述的位元組不一致的 provenance 記錄，比沒有更糟，因為它會被信任。

`_file_provenance` 讀位元組算 sha256，**不信 mtime**：網路/FUSE 掛載上 mtime 可以來自
write-back cache 而內容已不同，那正是本 BR 要揭露的故障模式。讀不到的檔記成帶 `error` 的條目
而非省略——省略會讀成「這個輸入沒被用到」，把 unread 與 unreadable 混為一談。

### 驗證

`tests/test_compose_input_provenance.py` **12/12**，含四條反向鑑別力：

| 測試 | 沒有它會怎樣 |
|---|---|
| `spec_digest_changes_when_the_spec_changes` | 摘要恆定＝識別不了任何東西 |
| `identical_specs_produce_the_identical_digest` | 摘要恆變＝同樣識別不了 |
| `mismatched_digest_refuses` | 閘可以接受任何值而其他測試照樣全綠 |
| `refusal_happens_before_any_work` | 事後才拒絕＝已經付出整次 compose |
| `a_missing_declared_path_is_a_mismatch_not_a_pass` | 缺席與相符共用結果 |
| `reads_bytes_rather_than_trusting_mtime` | mtime 相同而內容不同時靜默通過 |

**真 MCP client 實測**（非 curl——curl 繞過 client 序列化層，是 §P 的教訓）：

```
compose(spec)                     → inputs.symbol_libraries[0].sha256 = bf466eecad72…
                                    與 host `sha256sum` 逐字相符
                                    spec_sha256 = 343a6dc54421…  spec_components = 2
compose(spec, expect_sha={lib:0×64}) → ok:false
    InputProvenanceMismatch: COMPOSE_INPUT_SHA_MISMATCH: … expected 000000000000…
    but read bf466eecad72… (2218424 bytes, mtime 1778093993)
```

部署以 pid1 `09:59:24Z` > 最新 src mtime `09:58:42Z` 確認。

### 阻塞：這份修復無法在 HEAD 上執行

`composer.py` 在 HEAD 匯入 `_vendor_sym_scale` 等三個 `kicad_emit` 未定義的符號，
**整個 `bodesign_eda_bridge` 套件在 HEAD 無法 import**。
見 `issues/BR_20260802_composer_imports_a_symbol_that_never_existed…`（我已於 `f7f46c0` 更正其根因：
那些符號存在過，被 `reset --hard` 摧毀，已從懸空 blob 復原並錨定在 `refs/recovered/kicad_emit_full`）。

本修復目前與該還原一起活在工作區，並已快照為 `refs/recovered/ses0c87_wip_provenance`（防 `reset --hard`）。

**未 commit 的原因**：`packages/eda-bridge/` 是 `schematic-engine` family 的 fix surface，
該 family 目前 unassigned，依 `issues/OWNERS.md` §4.3.2 路由至 `(default)` owner。
等待授權；證據與量測已備齊，授權後 commit 即可。

### 附帶：§6 的 90 條 POWER_PORT warning

未併案。它是 `kicad_emit` 的 stub 方向缺陷，屬 `schematic-engine` 的 fix surface，
與本 BR 的 API 揭露面不同根因——共用檔案不是歸族依據。

---

## Round 2 — 同族的上一層：`inputs` 說了讀哪些位元組，沒說**是誰在讀**

Consumer（`ses_073a93d09`）在複驗 round 1 時報回一格更上層的缺口，實測成立：

```
composer.py  grep: engine_version | __version__ | git_describe | BUILD_SHA  → 0 命中
/app/packages  ←  ro,bind  ←  /home/pkcs12/projects/bodesign/packages   （/proc/1/mountinfo）
container kicad_emit.py sha = fe85249fcee83183
worktree                    = fe85249fcee83183   ← 一致
HEAD                        = 8194fa18a6d6157e   ← 不同
```

**容器跑的引擎綁的是 host 工作區，不是任何 commit。**

### 為什麼這比 round 1 更嚴重

| | 失去的東西 | 爆炸半徑 |
|---|---|---|
| round 1（`inputs` 缺席） | **輸入**過期，讀者分不出來 | 一次 compose 的數字作廢 |
| round 2（`engine` 缺席） | **引擎**未 commit，讀者分不出來 | 任何人在這棵樹上 `git checkout` / `reset --hard`，**所有先前的驗證永久不可重現** |

而這不是假想情境：同一天同一棵樹，`reset --hard` 已摧毀 46 檔未 commit 修改
（`BR_20260802_reset_hard_silently_destroyed_uncommitted_work_on_shared_tree`），
且本 BR 的實作本身就依賴從懸空 blob 復原的 `kicad_emit.py`。
**那兩起事故的爆炸半徑，完整覆蓋 consumer 當天的全部交付。**

Consumer 的自曝值得逐字保留，因為它指出 receipt discipline 漏掉的那一格：

> 我 commit 時逐條驗了 landed bytes、跑了 mutation proof、自建 fixture、控制組全上——
> **但整條驗證鏈跑在一個沒有 commit 的引擎上。**
> 我驗了交付物，沒驗**產生驗證的那個工具本身的可重現性**。

歸責判準（那一格資訊系統當下有沒有）：**有**。模組被 import 的那一刻 `__file__` 就在，
取 sha 是零成本。它選擇不放進回應。

### 修法

`inputs.engine`：

```python
_ENGINE_MODULE_FILES = ("composer.py", "kicad_emit.py")

def _engine_provenance() -> dict:
    here = Path(__file__).resolve().parent
    mods = [_file_provenance(here / name) for name in _ENGINE_MODULE_FILES]
    unreadable = [m["path"] for m in mods if m.get("sha256") is None]
    return {"modules": mods,
            "status": "measured" if not unreadable else "incomplete",
            "unreadable": unreadable, "note": ...}
```

三個刻意的設計選擇：

1. **複用 `_file_provenance`**，不另寫一份雜湊邏輯——兩份會漂移，而漂移後的那份
   仍會回傳看起來正確的 hex 字串。
2. **不 shell out 問 git**。容器裡沒有 repository，`git describe` 會在**正好需要它的那條路徑上**
   失敗、而在 host 上成功。一個「存在與否取決於在哪裡跑」的欄位比沒有欄位更糟——
   它會讓讀者以為「這次沒印 commit 是因為沒事」。content hash 到處都可比對
   （`git hash-object` / `sha256sum`），且它才是真正識別程式碼的東西。
3. **`status` + `unreadable` 而非靜默漏欄位**。量不到的模組必須大聲說量不到；
   少一個 entry 的清單仍然讀起來像一次乾淨的量測——**那正是本 BR 要消滅的形狀，
   在修復自身內部重演**。

### 驗證（17/17）

```
獨立雜湊器交叉比對    composer.py / kicad_emit.py 逐檔 MATCH
mutation proof        內容改變 → sha 改變（否則欄位是裝飾品）
反向鑑別力            檔案不可讀 → status=incomplete + entry 保留 + error 具名
                                   modules 長度不變（不靜默縮短）
不報 commit id        assertNotIn("commit") / assertNotIn("git_describe")
facade 可達           compose_schematic().inputs["engine"] 在回傳值裡
```

回歸：`test_composer` 的 `erc_errors 0 != 1` 經 stash A/B **逐字相同**，既有基線非本輪引入。

### 給呼叫端的用法

```
engine.modules[].sha256   對比  git hash-object <file>
  相符 → 這次跑的是已 commit 的程式碼，結果可重現
  不符 → 跑的是工作區版本，**在那棵樹被 checkout 之前**保存證據
```
