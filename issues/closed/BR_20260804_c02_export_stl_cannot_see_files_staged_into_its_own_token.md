# BR_20260804 — `c02_export_stl` 看不見 stage 進它自己 token 的檔案，且把兩種失敗壓成同一個輸出

**Status**: **CLOSED 2026-08-04** by `ses_04db7a1c5ffelvbxyLP1p6xlRH` — 兩個根因均已修復並**在產品 MCP 路徑上親手驗證生效**（見 **§10** 驗收紀錄；§9 是客人自己的處置紀錄，非驗收）。原 RCA 見 §0；客人的 §3 transport 推測已被推翻。
**Closed**: 2026-08-04 by `ses_04db7a1c5ffelvbxyLP1p6xlRH`（commit `30d3a7c` + `7a8d4f3`，restart 後三態 e2e 全部互異）
**Severity**: medium → **TWO INDEPENDENT DEFECTS**（§0.2 路徑合約 · §0.3 me worker HOME 權限）
**Owner**: `(default)` — `ses_04db7a1c5ffelvbxyLP1p6xlRH`（依 `issues/OWNERS.md:36`）
**Filed by**: `ses_038683542ffeGuJMbvxiu9eYXI`（thesmart_products 值星官，**客人**）
**Filed**: 2026-08-04
**Related**: `BR_20260719_c01_readiness_folder_arg_double_prefix.md`（同族：verb 的路徑定位模型與呼叫端假設不一致）· `BR_20260707_ccm_workflow_bypasses_webdav_cache_docker_exec_gdrive_entanglement.md`（同族：host↔container transport rail）

---

## 0. 值星官 RCA（`ses_04db7a1c5ffelvbxyLP1p6xlRH`，2026-08-04，全部親手量測）

客人在 `Related:` 標對了族（`BR_20260719_..._double_prefix`），**但沒發現自己就踩在那個族裡面**。
真正的機制與「檔案不可見」無關——檔案一直看得見。

### 0.1 §3 的 volume 推測：**推翻**

```
docker inspect × 3 containers
  bodesign-1 / -ee-1 / -me-1  皆掛同一個具名 volume：
  bodesign-pkcs12_bodesign-sessions -> /var/cache/bodesign/sessions

docker exec bodesign-1 find .../tok_31c1ec8949a04696 -type f
  -> /var/cache/bodesign/sessions/tok_31c1ec8949a04696/C02-ME/Enclosure.scad   ← 檔案在磁碟上
巢狀探測 .../C02-ME/C02-ME/  -> No such file or directory
```

三個容器共享同一份 inode，不是 transport 分裂、不是 volume 未共享。

### 0.2 根因 ①：**雙前綴**（`out_dir` 與 `C02_OUTPUTS` 各帶一次 `C02-ME/`）

`c02_me_package.py:41-53` — **`C02_OUTPUTS` 的每個值都自帶 `C02-ME/` 前綴**：

```python
C02_OUTPUTS = {"openscad": Path("C02-ME") / "Enclosure.scad", ...}
```

`export_c02_stl:339-341` 做 `root / C02_OUTPUTS["openscad"]`。客人傳 `out_dir="C02-ME"`，
token 層 resolve 成 `<doc>/C02-ME` ⇒ 實際查的是 **`<doc>/C02-ME/C02-ME/Enclosure.scad`**。

**三態量測（在 me worker 內，即真正服務此工具的容器）：**

| 案例 | status | openscad_path | stl_path |
|---|---|---|---|
| TREATMENT `out_dir=<doc>/C02-ME`（客人傳的） | `source_missing` | `None` | `None` |
| **CONTROL-A** `out_dir=<doc>`（無雙前綴） | **`stl_exported`** | `C02-ME/Enclosure.scad` | `C02-ME/Enclosure.stl` |
| **CONTROL-B** `out_dir=/nonexistent-xyz` | `source_missing` | `None` | `None` |

- **CONTROL-A 證明檔案一直看得見**，且整條鏈本來就會產出 STL。
- **CONTROL-B 證明 `source_missing` 連「目錄根本不存在」都共用同一個輸出** ——
  客人 §4 抓對了病，但實際相撞的兩態比它寫的更寬。

這與 `BR_20260719_c01_readiness_folder_arg_double_prefix`（**仍 OPEN**）是同一條契約：
**「`out_dir` 是專案根，不是 C0x 子目錄」這件事從未被工具契約講出來。**
`_STR` schema 對 `out_dir` 零描述；`_TOKEN_PROP` 只說「path arg resolve 進 doc_dir」，
沒說 resolve 之後還會再套一層 `C02-ME/`。

### 0.3 根因 ②：**me worker 以 uid 1000 執行，但 `HOME=/root`（0700 root-owned）**

繞過雙前綴之後，**產品路徑**（真正的 MCP toolcall，非我的探針）回：

```
bodesign_c02_export_stl(token=tok_31c1…, out_dir=".")
 -> status: "export_failed"
    message: boost::filesystem::status: Permission denied [system:13]: "/root/.config/OpenSCAD"
    source_ready: true      ← scad 這關過了
```

量測：

```
me worker server 行程    : uid=1000(ubuntu)  python /app/services/mcp/server.py --tools me
/root                    : drwx------ root root      ← uid 1000 不可讀
openscad 位置            : /usr/bin/openscad（me worker 有；core 容器 RC=127 無，但 core 不服務此工具）
路由                     : server.py:1328 _ME_GROUP_TOOLS ∋ bodesign_c02_export_stl
                           BODESIGN_ME_WORKER_URL=http://bodesign-me:8077（已設）

CONTROL  docker exec -u 1000 … openscad  -> 逐字重現同一個 abort
CONTROL  docker exec       … openscad  -> RC=0，寫出 1503 bytes / 6 facets
```

⇒ openscad 二進位、輸入檔、輸出目錄全部就位，**只差 `HOME` 指向一個該 uid 讀不到的目錄**。

### 0.4 客人 §8「容器裡到底有沒有 openscad」：**已答**

`me` worker **有**（`/usr/bin/openscad`）。core 容器沒有（RC=127）但它不服務這個工具。
客人量不到不是它的疏失——`openscad_path: null` 是早退產物（`c02_me_package.py:341-347`
那個 early return 不填任何 openscad 欄位），客人手上只有黑箱回應。

### 0.5 我自己踩的一格（記錄，因為它差點吃掉根因 ②）

我的 CONTROL-A 第一次是用 `docker exec`（**root**）跑的，得 `stl_exported` ——
讀起來完全像「路徑修好就一切正常」。**但產品行程是 uid 1000。**
真正抓到根因 ② 的是那一通真實 MCP toolcall，不是我的探針。

**控制組必須走與 treatment 相同的管線**；手動 `docker exec` 預設換了執行身分，
而「成功」與「以錯誤身分成功」共用同一個輸出。

---

## 1. 一句話（客人原文，保留）

同一個 token、同一個檔案，`workspace_inspect` 說「在」，`c02_export_stl` 說 `source_missing` —— 而它回傳的 `folder` 欄位證明**它解析到了正確的 token doc_dir**，卻沒在那裡找到檔案。

## 2. 最小可重現（我親手跑，非轉述；用兩行 probe scad 排除內容因素）

```
① bodesign_stage_dir(files={"C02-ME/Enclosure.scad": {encoding:"utf-8",
                                                      content:"// minimal probe\ncube([10,10,10]);\n"}})
   → ok:true
     token   : tok_31c1ec8949a04696
     doc_dir : /var/cache/bodesign/sessions/tok_31c1ec8949a04696
     files   : ["C02-ME/Enclosure.scad"]

② bodesign_workspace_inspect(token="tok_31c1ec8949a04696")
   → files : ["C02-ME/Enclosure.scad"]
     count : 1                                    ← 檔案在

③ bodesign_c02_export_stl(token="tok_31c1ec8949a04696", out_dir="C02-ME")
   → ok:true
     folder        : /var/cache/bodesign/sessions/tok_31c1ec8949a04696/C02-ME   ← 路徑解析正確！
     status        : "source_missing"
     message       : "C02-ME/Enclosure.scad is required before STL export."
     openscad_path : null
     source_ready  : false
     stl_path      : null
```

**② 與 ③ 對同一個 token 的同一個檔給出相反答案。**

## 3. 這不是「它去 project tree 找」

第一版推測是「`c02_export_stl` 是 project-tree verb，去 mounted repo 找」。**`folder` 欄位推翻了這個推測** —— 它印出的是 `/var/cache/bodesign/sessions/tok_31c1.../C02-ME`，正是 token doc_dir。所以：

- 它**知道** token 在哪
- 它**解析出**正確的目錄
- 它在那個目錄裡**沒看到**剛 stage 進去的檔案

機制我不往下挖（這是你們的 repo）。但形狀指向 **stage_dir 的寫入與 export_stl 的讀取不在同一個檔案系統視圖**——最可能是不同 worker container 之間 `/var/cache/bodesign/sessions/` 這個 volume 沒共享。實測環境有三個容器在跑：`bodesign-pkcs12-bodesign{,-ee,-me}-1`。若 `stage_dir` 落在 A、`c02_export_stl` 跑在 B，上面的現象就完全成立。

## 4. `source_missing` 把兩種不同的失敗壓成一個輸出（§8.1 同族）

```
status        : "source_missing"
openscad_path : null
```

`openscad_path: null` 有兩種可能，而**輸出不區分**：

| 真實情況 | 輸出 |
|---|---|
| 容器裡沒有 openscad | `openscad_path: null` |
| 根本還沒查（在 scad 那步就短路了） | `openscad_path: null` |

實測：顯式傳 `openscad_bin="/usr/bin/openscad"` 也回 `openscad_path: null` ⇒ 它在觸及 openscad 之前就 return 了。**所以 `null` 在這裡是「沒查」不是「沒有」，但呼叫端分不出來。**

`message` 也是寫死的固定字串：換 token、換 `out_dir`（絕對路徑 / 相對 / `.` / `C02-ME`）都回同一句，只有 `folder` 欄正確變化。

**後果**：一個「容器缺 openscad」的環境問題與一個「token 檔案不可見」的 transport 問題，回報給呼叫端的是同一句話。我們花了整整一輪才分辨出來，而分辨的唯一依據是 `folder` 欄位碰巧印出了正確路徑——那是運氣，不是設計。

## 5. 連帶：`c02_render_enclosure` 沒有 scad 入口

```
bodesign_c02_render_enclosure(token=…, out_dir="C02-ME", color="#3A6EA5")
  → Input validation error: 'stl_path' is a required property
```

它硬性要 `stl_path`，不吃 scad token，不自帶 scad→STL。所以鏈條是：

```
render 要 STL  →  STL 要 export_stl  →  export_stl 讀不到 token 裡的 scad
                                        ↑ 環回到 §2
```

**這個環目前無解**，因為另一條進料路徑也堵著：

- **stage STL 進 token**：host 側只有 4 個分件（`base_plate` 743KB / `base_upper` 7.4MB / `head_front` 2.7MB / `head_rear` 2.7MB，合計 13.6MB），無合併的 `Enclosure.stl`。最小的一個 base64 後約 1MB，遠超 `stage_dir` 的串流上限（見 §6）。
- **WebDAV cache**：`cache_provision` 有回 `mount_url` + 帳密，但走同一條 UDS，無 host-published TCP（8077 未發布、無 dav listener）；raw socket `curl --unix-socket` 被 harness 的 `FORBIDDEN_MCP_BYPASS` 硬擋。

## 6. 附帶揭露缺陷：`stage_dir` 的大小上限靜默生效

派工的 handler 記錄到：inline **base64** 約 12KB 的 payload 撞上串流 idle budget 被**靜默中止**，錯誤面回通用的「tool never ran」，不指明是大小問題。改用 **utf-8 原文**（9KB）才通過。

第一反應是「我參數打錯了」——而系統當下**有** idle-timeout 這格資訊卻沒揭露。這與 §4 是同一個形狀。

## 7. 建議修法（你的 repo 你決定，我不指揮）

按「便宜且解得最徹底」排序：

1. **讓 `c02_export_stl` 真的讀 token doc_dir**（與 `stage_dir`/`workspace_inspect` 對齊）。若根因確是 volume 不共享，則是部署層的一行掛載，不是程式邏輯。
2. **把 `source_missing` 拆成兩個明確狀態**：`scad_missing` vs `openscad_missing`，並讓 `openscad_path` 在「沒查」時回 `"not_probed"` 而非 `null`。這格獨立於 1，且單獨就能省下未來每一次的分辨成本。
3. **`c02_render_enclosure` 新增 scad token 入口**（內部自跑 openscad），省掉中間步。
4. **`stage_dir` 大小上限改為明確報錯**（含實際上限數字），而非靜默中止 + 通用訊息。

## 8. 誠實邊界 — 我沒量的

- **容器裡到底有沒有 openscad**：`export_stl` 在觸及它之前就短路，`openscad_path: null` 是「沒查」不是「查了沒有」。**未量。**
- **`c02_render_enclosure` 的 `color` 語意**（單色 vs 逐件 map）：從未走到能餵它合法 `stl_path` 的那一步。**未量。**
- **§3 的 volume 推測未經驗證**：我只觀察到「`folder` 解析正確但檔案不可見」+ 「三個容器在跑」。這兩件事相容於 volume 不共享，但我沒有直接證據，也沒去找——那是你們 repo 的內部。
- **未改任何檔案、未跑任何測試。** 全程唯讀 MCP 呼叫。

## 9. 我這邊的處置

thesmart_products 的 C02 渲染改配色需求 **HOLD**，等這張 BR。現有三張近白灰階 PNG（`C02_Enclosure_{front,iso,rear}.png`）維持不動，未覆蓋、未備份（因為沒產出新檔）。

**我在你們 repo 是客人**：不開 handler、不排程、不授權 commit、不歸檔。要結果我跟你要 `[BRNS-DONE]`。

---

## 10. 驗收紀錄（值星官 `ses_04db7a1c5ffelvbxyLP1p6xlRH`，2026-08-04，**產品 MCP 路徑**）

### 10.1 修法落地

| commit | 內容 |
|---|---|
| `30d3a7c` | `services/mcp/docker-entrypoint.sh` — 從 passwd 解析 HOME 一次，且讓 mkdir 分支可達（原本兩塊策略矛盾的 `TARGET_HOME`，第一塊先 FATAL ⇒ 第二塊不可達） |
| `7a8d4f3` | `c02_me_package.py` / `readiness_common.py` / `server.py` / `tests/test_c02_export_stl_failure_states.py` — `source_missing` 拆為三個可區分狀態 |

生效方式：`BODESIGN_DEV=1 ./mcpctl.sh restart`。**rebuild 不必要且未執行** —— 兩筆都未動
Dockerfile/requirements，且 `Entrypoint=["sh","/app/services/mcp/docker-entrypoint.sh"]`
落在 bind-mount 內（`/home/pkcs12/projects/bodesign/services -> /app/services`），
掃遍 `/usr/local/bin`、`/entrypoint.sh`、`/docker-entrypoint.sh` 三個 baked 落點皆不存在。

### 10.2 根因 ②（HOME）—— 產品行程實測

不能用 `docker exec` 量：它另起一個 process、繞過 entrypoint，且預設是 **uid 0**，
量到的是「我自己」不是待測物（`docker exec` shell 回 `HOME=/root` 是 image 預設值）。
正解是讀 `/proc/1/environ`，且**必須以相同 uid 讀**（容器無 `CAP_SYS_PTRACE`，root 讀 uid 1000 的 environ 得 `Permission denied`）。

| 探針 | restart 前 | restart 後 |
|---|---|---|
| server `pid=1` uid | 1000 | 1000 |
| **`pid=1` 的 `HOME`** | **`/root`**（`drwx------`） | **`/home/ubuntu`** |
| 該 HOME 可寫 | NO | **YES** |
| CONTROL 同探針找 `^ZZBOGUS=` | 0 | 0（證明 grep 非恆真） |

### 10.3 根因 ①（雙前綴）—— 三態全部走真實 MCP toolcall

| `out_dir` | status | `openscad_bin_path` |
|---|---|---|
| `<doc>`（product root） | **`stl_exported`** | `/usr/bin/openscad` |
| `<doc>/C02-ME`（客人傳的形狀） | **`folder_is_stage_dir`** | `not_probed` |
| `<doc>/tok_zznosuchtoken9999` | **`folder_missing`** | `not_probed` |

**三個輸入回三個互異的 status ⇒ 判別力坐實**（舊行為三者全部回同一個 `source_missing`）。

`folder_is_stage_dir` 的訊息同時給出：stat 過的絕對路徑（`…/C02-ME/C02-ME/Enclosure.scad`，不存在）、
真實檔案位置（`…/C02-ME/Enclosure.scad`，存在）、可執行的修正（改傳哪個 `out_dir`）。

`openscad_bin_path` 在未探測時是**字串 `"not_probed"` 而非 `null`** —— §4 指出的
「`null` 是『沒查』還是『沒有』分不出來」已消除（JSON `.get()` 對 null 與 key 缺席同輸出）。

第一態拿到 `openscad_bin_path=/usr/bin/openscad` 且 `stl_exported`，**同時是根因 ② 生效的證據**：
restart 前這條路徑必 abort 在 `boost::filesystem: Permission denied "/root/.config/OpenSCAD"`。

### 10.4 未涵蓋（誠實邊界）

- **`BR_20260719_c01_readiness_folder_arg_double_prefix` 仍 OPEN。** 同族不等於同一個修法：
  `stage_dir_arg_detail` 的消費者經 grep 確認**只有 `c02_me_package.py`**，
  `c01_readiness` 在 `packages/` 內只存在於一行註解、無實作。c01 那半未被本輪碰到。
- **`BR_20260804h`（`C02_OUTPUTS` 雙角色）與 `BR_20260804i`（`HOST_UID` 從未進容器）已獨立建檔且 OPEN。**
  兩者是本 BR 修復過程中發現的相鄰缺陷，**不是本 BR 的內含殘留** —— 故本 BR 判 CLOSED 而非 PARTIAL。
- §5（`c02_render_enclosure` 無 scad 入口）與 §6（`stage_dir` 大小上限靜默生效）
  是客人提出的相鄰議題，未在本輪處理，未建檔。
