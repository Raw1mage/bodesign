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
