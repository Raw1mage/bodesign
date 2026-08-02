# BR: C01 photoreal 表皮渲染路徑非引擎一級能力（軸A）

- Status: OPEN — **2026-08-02 重寫**：憑證抱怨已失效並移除，能力缺口全數存續
- Re-verified: 2026-08-02 by ses_04db7a1c5（coordinator），逐條對照 HEAD
- Owner: **unassigned** — family `readiness-contract`（見 `issues/OWNERS.md`）
- 原始立案: 2026-07-19，aiguard C01 consumer

## 症狀

C01 CMF/尺度感 photoreal 渲染（幾何以 OpenSCAD 渲染為據、AI 生圖**上皮**）在 aiguard C01
已兩輪實戰有效（owner 打回「糊成一團」後靠此路徑過審），但這條路徑**在 bodesign 引擎裡不存在**。

**已解決、不再是症狀的部分（2026-08-02 覆核）**：原始 BR 抱怨的端點與 OAuth 借用
（`aiplatform.googleapis.com` + gemini-cli access_token、~1h 過期即斷炊）**已不成立**。
`bodesign_c01_generate_concept_image` 已改為 server 端解析憑證
（`c01_id_package.py:1092-1116`，env → opencode `accounts.json`），端點改為
`generativelanguage.googleapis.com`（`:1121`），且帳號型別非 `api` 時明確 raise（`:1113`）。
用的是 API key 而非原文要求的 refresh token——不合字面，但**無過期問題，斷炊抱怨已被治好**。

**仍然是症狀的部分——而且比那四條子項更根本**：

shipped 的 `generate_c01_concept_image(out_dir, prompt, model, api_key)`
（`c01_id_package.py:635-640`；schema `services/mcp/server.py:1183` = `{out_dir, prompt, model}`）
是 **text-to-image**。本 BR 要的路徑是 **image-to-image**——「幾何以 OpenSCAD 渲染為據、
AI 生圖上皮」必須吃一張參考 render 當輸入。**現有工具連接收那張圖的參數都沒有**，
所以這不是「verb 名字不同」，是整條路徑不存在。

## 期望

一級 verb（如 `c01_photoreal_skin(ref_png, cmf_spec, lighting_profile)`）：

| # | 項目 | 2026-08-02 狀態 | 證據 |
|---|---|---|---|
| 0 | verb 本身（吃 `ref_png` 的 image-to-image 路徑） | **未做** | 全 repo grep `photoreal\|lighting_profile\|ref_png\|cmf_spec`（`packages/ services/`）→ 空 |
| 1 | 封裝端點/認證 | **已達成**（API key，非 refresh token） | `c01_id_package.py:1092-1121` |
| 2 | 內建 lighting profile 預設（high-key studio + rim light——深色 SKU 反糊成一團的關鍵） | **未做** | `_concept_prompt` `:1168-1180` 只附加通用 disclaimer |
| 3 | 429 退避重試 | **未做** | `grep "429\|retry\|backoff\|time.sleep"` on `c01_id_package.py` → exit 1（控制組：同檔 `grep -c "def \|prompt"` → 83，證明檔案讀得到，零命中是真的沒有）。`_call_google_image_api:1130-1137` 遇 `HTTPError` 直接 raise |
| 4 | 幾何忠實 QA 掛鉤（對照 ref render 的 fresh-eyes 迴圈） | **未做** | 無 `ref_png` 參數，同上 grep 為空 |

## 佐證

- thesmart_products event log scope=aiguard_c01-c04-autonomous-delivery（2026-07-19 R1'' 修正輪 2 筆）
- 成功參數樣本：`/run/user/1000/c01-redo/{p_g,p_i,p_scale_front,p_scale_iso}.txt`
  （⚠ `$XDG_RUNTIME_DIR` 開機即清空，此樣本很可能已不存在；lighting profile 規格
  目前**只活在 event log**，這正是第 2 項要沉澱的東西）

軸別：**軸A**（能力缺口——工具不存在，非用錯）。此判定在 2026-08-02 仍成立。
