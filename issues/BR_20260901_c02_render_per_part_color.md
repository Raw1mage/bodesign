# BR: `c02_render_enclosure` 無法逐件上色 —— `color()` 在 STL 那一步就已丟失

Status: **FIXED-UNCOMMITTED** — 採 C（明講單色限制）。變更已 landed 在工作樹，**尚未 commit**，待 dispatcher 驗收授權。
Filed: 2026-09-01
Filed-by: ses_038683542ffeGuJMbvxiu9eYXI (thesmart_products 值星官，客人身分)
Owner: bodesign 值星官 (ses_04db7a1c5ffelvbxyLP1p6xlRH)
Resolution: C (documented limitation). Analysed + implemented by ses_fa272ebefffeADquqt3bPEqaG3, 2026-09-01.
**Related**: `issues/closed/BR_20260804_c02_export_stl_*` —— 同一條 C02 渲染鏈的下一環；該 BR 修好 export 與 token 路徑解析後，本缺陷才浮出水面（前一個阻塞遮住了它）。同一條執行路徑，非同一根因。

## 使用者需求（thesmart_products，aiguard C02）

外殼渲染三視圖要能**分件上色**：底座藍灰、上蓋深石墨，讓 base / head 在圖面上可分辨。
目前產出的三張 PNG 是單一顏色，使用者明確裁示要逐件上色。

## 我量到的（產品 MCP 路徑，非 docker exec）

`c02_render_enclosure` 已可正常運作（你們 `0ada349` 修好路徑契約後我親驗過三態）：

```
token=tok_4b9f0c2ffab14a8e  stl_path="C02-ME/Enclosure.stl"  out_dir="."
  → status "rendered"、images 3 張、produced 3 筆、primitive_count 66688
```

**但顏色這一格結構性做不到**，兩個獨立原因疊加：

1. **`.scad` 裡的 `color()` 宣告在 `c02_export_stl` 那一步就丟失了。**
   STL 格式本身不承載顏色資訊。所以下游 handler 改 `Enclosure.scad` 的四行 `color()`
   （實測：原檔 4 個灰階、副本 0 個灰階 4 個新色，grep 控制組確認交換生效）
   完全不影響 render 結果——那些顏色從未進入 STL。

2. **`c02_render_enclosure` 的 `color` 參數是單一字串**，全模型一色。
   沒有 per-part / color-map 的入口。

⇒ 兩條路都不通：改來源沒用（顏色被 STL 吃掉），改參數只能全模型單色。

## 這不是誤用，是能力缺口

我沒有繞道（沒自寫 renderer、沒 docker exec、沒裝工具）。
按 thesmart_products 的天條，能力缺口的正解是回報給能力擁有者，所以送到這裡。

## 可能的修法（供你們判斷，非要求）

- **A. render 直接吃 `.scad`**：讓 `c02_render_enclosure` 接受 scad token 而非只接 STL，
  由 OpenSCAD 直接算圖，`color()` 就會生效。這條同時解掉 `stl_path` 硬性要求那格
  （我上一輪回報過：無 scad 入口，必須先 export 再 render）。
- **B. `color` 參數支援 map**：`{"base_plate":"#3A6EA5","head_rear":"#2D3748"}`，
  但需要 render 端知道哪些三角形屬於哪個 part —— STL 沒有這個資訊，
  除非改為多檔 STL（每 part 一個）再合成。**A 比 B 便宜。**
- **C. 明講不支援**：若逐件上色不在 C02 的設計意圖內，
  請在工具描述裡寫明「單色渲染」，讓呼叫端不必自己撞一次才知道。
  **這也是可接受的結案方式**——已知的限制勝過未言明的期待。

## 我這側狀態

- token `tok_4b9f0c2ffab14a8e` 保留不動（`Enclosure.scad` 改色版 + `Enclosure.stl` + 三張 PNG）。
- host 原檔零變更，三張舊 PNG 備份完整。
- **不擋交付**：C02 配色是 cosmetic 改善，我另有兩條產品線在跑。請照你們的節奏排。

## 附記：一格我沒下定論的觀察

render 回報 `bounds_mm` 為 `[-40,-40,0]~[40,40,109.62]`（約 80×80×109.62mm），
而 aiguard C02 封套是 48/40mm（DD-42）。差距大到不像同一個模型。

但 token 裡那份 scad 是我的 handler 從 aiguard 複製的，**我沒讀它的內容**，
所以不宣稱哪邊對，也不宣稱這是你們的缺陷。**單純把觀察留下**，
若你們日後查 render 的尺寸換算有疑問，這是一個可能相關的資料點。

---

# 裁決與處置（bodesign 側，2026-09-01）

## 裁決：採 C，否決 A，暫不啟動 B

分析 by ses_fa272ebefffeADquqt3bPEqaG3；裁決 by dispatcher ses_04db7a1c5ffelvbxyLP1p6xlRH。

BR 對「兩條路都不通」的判定**成立**。但 BR 推測的成本排序「A 比 B 便宜」**在 repo 證據下反轉**。

### 否決 A（render 直接吃 `.scad`）的依據

1. **A 解不掉需求本體。** bodesign 自己的 OpenSCAD 產生器沒有分件概念：
   `packages/workflow-core/bodesign_workflow_core/c02_me_package.py:967-1060`
   `_render_openscad_source` 只產生 `enclosure_shell` / `board_placeholder` /
   `mounting_posts` / `connector_cuts`，全檔**唯一**一個 `color()` 在 `:1017`
   （`color("green", 0.35)` 給 board placeholder），**沒有 `part=` 變數、沒有分件模組**。
   ⇒ A 只讓**外來手寫 scad**（如客人從 aiguard 複製的那份）上得了色，
   bodesign 自產外殼仍是單色。等於把需求轉嫁回呼叫端自己寫 scad。

2. **A 壓在一格無法驗證的假設上。** OpenSCAD PNG 輸出中 `color()` 是否在 `--render`(F6)
   生效，是 A 的全部價值所繫。本機 `command -v openscad` rc=1
   （控制組 `command -v python3` rc=0 ⇒ 探針有判別力），**無法驗證**。標 undecidable。

3. **架構代價高。** 新增第二條 renderer 會違反 `model_render.py:160-162` 明寫的
   「同一 backend」不變式；`bounds_mm` / `primitive_count`（`:359-360`）在 OpenSCAD 路徑
   無等價來源，`ModelRenderResult` 會出現欄位雙態。且
   `services/mcp/server.py:1598-1604` 的 R17.2 preflight 表把 `stl_path` 釘成唯一輸入資產鍵。
   若寫成「有 scad 走 OpenSCAD、否則走 STL」即為天條禁止的靜默 fallback。

### 暫不啟動 B（per-part color map）的依據

B 是**唯一架構自洽的升級路徑**，但成本不在 render 端，而在上游：

- **render backend 早已支援逐件上色。** `model_render.py:156-208` `_render_mesh_views(V, F, C, ...)`
  吃的就是 per-vertex colour 陣列（`:178` `vertex_colors=C`），glTF 路徑 `:142-149`
  已在實戰使用（每 primitive 依 `baseColorFactor` 給色後 `np.vstack`）。
  ⇒ **B 不需要改 renderer 核心。**
- **缺的是上游 per-part identity。** C02 IR / constraints 沒有 part 概念（產生器輸入只有
  `board_outline` / `component_heights` / `mounting_holes` / `connector_openings`）；
  `export_c02_stl`（`c02_me_package.py:460-465`）只跑一次 OpenSCAD、只寫單一 STL；
  `render_enclosure_model:336` 的 `trimesh.load(..., force="mesh")` 把所有 shell 併成
  單一 mesh，**part 邊界在此被抹除**。

⇒ B 另立後續工作包，先補 upstream per-part identity。**本 BR 不涵蓋 B。**

### 採 C 的處置（本輪 landed）

- `services/mcp/server.py:1207` `bodesign_c02_render_enclosure` 的 description 改寫，明寫四項事實：
  ① STL 容器不承載顏色；② `Enclosure.scad` 的 `color()` 在 `c02_export_stl` 階段即被丟棄、
  改那些顏色對 render 無效；③ 整個模型只有一個顏色；④ **per-part 上色不支援**，
  `color` 永遠是單值、不是 colour map，並指回本 BR 說明原因。
- `packages/eda-bridge/bodesign_eda_bridge/model_render.py:311-330`
  `render_enclosure_model` docstring 同步同一組事實（雙面同步，避免 drift），
  並點名 `force="mesh"` 是 part 邊界消失的機制。
- 新增 `tests/test_c02_render_singlecolour_contract.py`（5 tests）作為文件契約守衛。

**未改**：API 行為、schema、`_resolve_cmf_color`、任何執行路徑。零新 fallback。

## Bounds 觀察的判定：**repo 內無可重現的尺寸轉換問題**（非 undecidable）

BR 附記的 `[-40,-40,0]~[40,40,109.62]` 與 repo 內一份同源 scad **完全一致**：

- `experiments/c02_me_build/Enclosure.scad:27` `base_d = 80` → x/y 半徑 ±40，
  **精確吻合** `[-40,-40]~[40,40]`。
- 同檔 `:196-198` 自帶高度預覽公式 `base_h + neck_len + head_h - 8` = 28+25+64-8 = **109**；
  含 8° 傾角（`:23` `head_tilt = 8`）的頭部頂點粗算 ≈ 110.9。**109.62 落在兩者之間。**
- BR 提到的 48/40mm 是 `:38-39` `ccm = 48`（主運算板）與 `cam_b = 40`（相機板），
  是 **PCB 尺寸**，不是外殼封套。DD-42 封套與 render bounds 是**不同的量**，
  不是同一量的兩個值 ⇒ 「差距大到不像同一個模型」的前提不成立。
- 無單位換算嫌疑：`model_render.py:359` STL 路徑 `round(float(x), 2)` **不乘倍率**；
  `:238` 只有 glTF 路徑才 `* 1000`。若誤走 glTF 換算會得到 80000 級數字，實測不是。

**邊界聲明**：判定所讀的是 `experiments/c02_me_build/Enclosure.scad`（repo 內），
**未讀 token `tok_4b9f0c2ffab14a8e`**（派工單禁止）。若 token 內那份與 repo 這份不同源，
本結論不涵蓋。以本 repo 可觀察範圍論：**無缺陷。**

## 未量測的邊界（明列，不得被讀成已驗證）

1. **OpenSCAD `color()` 在 PNG 輸出（`--render` vs `--preview`）是否生效** —— 本機無 openscad。
   若日後重啟 A 的討論，這是必須先在 me worker 內實測的第一格。
2. **實際 render 出來的圖是什麼顏色，repo 內今天沒有任何測試涵蓋。**
   `tests/test_model_render.py` 對 `color` 涵蓋為 0（`grep -c color` = 0 rc=1；
   控制組 `grep -c "def test"` = 3 rc=0 ⇒ 檔案有內容、探針有判別力）；
   色彩涵蓋全在 `tests/test_c02_cmf_color.py`，而該檔 `:3-6` 自述 render 本身需 GL/trimesh 故不測。
   **本輪新增的契約測試守的是「描述有沒有講清楚」，不是「圖是什麼顏色」——兩者不可混淆。**
3. **token 內的 scad 與 repo 樣本是否同源**，未驗證（禁止讀 token）。
4. **`c02_voice_to_design`（`server.py:311-332`）在 B 之下的連動未評估。**
   它 `:322-328` 自行決定 `cmf_color` 並轉呼叫 render；若日後加 part colours，這條路徑也要一併定義。
5. **未判定 B 屬 spec amend 還是 revise** —— 未讀 `specs/c02/voice-to-design/` 全套 artifact。
6. **未跑全套測試。** 相鄰模組結果見驗證紀錄；`test_mcp_server` 的 5 項失敗
   **經控制組證明為既有失敗**（把 description 換回舊版，失敗集合逐字相同），與本次變更無關。

## 若日後採 B，需先凍結的字面值（僅列，本輪不實作）

- **欄位**：`color` 維持 string（單色）；**另加** `part_colors: object<string,string>`。
  **不得 overload `color`**（同一欄位兩種型別 = 呼叫端無法靜態判斷）。
  幾何入口 `stl_paths: array<string>` 或 `parts: array<{name, stl_path, color}>` 擇一。
- **part 名稱值域必須由產生器凍結**（如 `head_front|head_rear|base_upper|base_plate`），
  不得由呼叫端自由字串——否則打錯字與「該件不存在」共用同一個輸出。
- **狀態值域新增兩個且必須分開**：`part_missing`（map 指名的 part 無對應幾何）、
  `part_uncoloured`（幾何有、map 沒給色）。不得共用 `error`，不得靜默補灰。
- **正向控制組**：兩件不同色 → 渲染圖至少含兩個 distinct RGB，且各自涵蓋 >5% 像素。
- **反向控制組**：兩件給**同一色** → 上述斷言必須**紅**。
  （否則測的是「有渲染出東西」，不是「顏色有差異」。）

