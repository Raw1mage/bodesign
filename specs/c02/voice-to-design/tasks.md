# Tasks: c02_voice-to-design

末端渲染（DD-3）已於 2026-06-14 完成（render_enclosure_model + c02_render_enclosure，閉環出圖實證）。
Phase 1-3 完成口述抽取/反問/編排全鏈閉環；Phase 4 完成品質細化（真切連接器孔 + 真螺柱孔）；Phase 5 完成 hull 立邊圓角（corner_radius_mm）。

## 5. 品質細化：hull 立邊圓角（2026-06-14）

- [x] 5.1 corner_radius_mm 契約：optional 第 5 參數，None/0=方角向後相容，超範圍（>min(w,h)/2）fail-fast 不靜默 clamp
- [x] 5.2 OpenSCAD hull 立邊圓角：_outer_shell_scad(radius)，outer cube → hull() 包 4 個內縮 cylinder($fn=48)，只圓立邊不圓頂底；difference/connector_cuts/mounting_posts 不變
- [x] 5.3 build123d 同步：_build_enclosure_part fillet part.edges().filter_by(Axis.Z) 只 fillet 4 條垂直邊，兩路不漂移
- [x] 5.4 voice 抽 corner_radius：_extract_gen_params 增 corner_radius_mm（圓角/倒角/rounded/fillet/chamfer keyword）；提到圓角無半徑 → DD-2 反問，沒提到不問不設
- [x] 5.5 dev restart + PoC：口述含「圓角 3mm」走 voice_to_design 全鏈 → .scad 確認 hull() 4 cylinder(r=3,$fn=48) + connector_cuts 仍在，渲染圖 inline 顯示
- [x] 5.6 收尾：tasks.md 勾選 + architecture sync + event log

## 1. 口述抽取 + 反問補全核心（workflow-core）

- [x] 1.1 在 c02_me_package.py 定義 C02FieldBinding（key/label/keywords/question/blocks_source/extractor）+ 8 欄位綁定表（對齊 assess_c02_constraint_readiness 的欄位）
- [x] 1.2 實作 regex 抽取策略：dimensions_wxh（板框 50×30）、height_mm（元件高 12mm/公釐）、connector（usb-c/側）、environment（室內/IP）
- [x] 1.3 實作 plan_c02_intent(spec_text, answers)：三態抽取 → draft 約束 + field_status + gen_params(wall/clearance/lid) + readiness + next_question + status；不猜尺寸，抽不到轉澄清問題
- [x] 1.4 單元測試：自然語句抽出對齊 schema 的約束草稿；數字+單位 regex；缺關鍵約束轉問題；次要約束缺失不擋

## 2. 編排閉環 + MCP 工具（server.py）

- [x] 2.1 _h_c02_plan_intent handler：呼叫 plan_c02_intent，回 IntentPlanResult
- [x] 2.2 _h_c02_voice_to_design handler：編排 plan_intent → (needs-clarification 回問題 | ready-for-approval 回約束集待確認 | approve=true 才 generate_openscad→export_stl→render_enclosure 出圖)；尊重 approval gate 不自動生
- [x] 2.3 註冊兩工具（handler+schema+me-group routing），c02_plan_intent 純 python 可留 core、c02_voice_to_design 因含 generate/stl/render 須 me-group
- [x] 2.4 server handler 測試（抽取/反問/approval gate 不自動生）

## 3. PoC 實證 + 收尾

- [x] 3.1 dev restart 生效，用真實口述案例走完整閉環：「我要一個 60×40 的盒子，裝一片板，最高元件 15mm，側面開 USB-C，室內用」→ 反問壁厚/間隙 → 確認 → 出圖
- [x] 3.2 取回渲染圖 inline 顯示，驗證口述→設計稿閉環
- [x] 3.3 event log + architecture sync + tasks 勾選

## 4. 品質細化：真切連接器孔 + 真螺柱孔（2026-06-14）

- [x] 4.1 定義 connector opening 切削幾何契約 {face, width_mm, height_mm, z_mm, offset_mm?} + 座標系（角落原點，east=+X/west=-X/north=+Y/south=-Y 牆，floor top 在 z=wall）
- [x] 4.2 OpenSCAD + STEP 兩路真切連接器孔：共用 _normalize_face + _connector_cut_geometry helper，OpenSCAD 從 //註解 → connector_cuts() 差集穿牆，build123d 用同 helper 做 Box(SUBTRACT)，兩路不漂移
- [x] 4.3 OpenSCAD 螺柱孔對齊 STEP 路：marker 凸點 → mounting_posts()（standoff boss dia+3 + pilot hole dia 貫穿），standoff_h 比照 STEP 路
- [x] 4.4 voice 抽取器：connector 有幾何 → stated 結構化 item；只有關鍵字無幾何 → needs_geometry 反問（face/寬高/離底高），DD-2 不猜；W×H regex 排除 board-context 避免誤抓板框尺寸
- [x] 4.5 dev restart + PoC 實跑：connector_openings:[{face:east,width:9,height:3.5,z:4}] → STL → render，.scad 確認 connector_cuts() 真差集 + mounting_posts() 真 standoff，渲染圖 inline 顯示
- [x] 4.6 收尾：tasks.md 勾選 + architecture sync + event log

## 5. 品質細化：hull 立邊圓角（2026-06-14）

- [x] 5.1 corner_radius_mm 契約：optional 第 5 參數，None/0=方角向後相容，超範圍 fail-fast
- [x] 5.2 OpenSCAD hull 立邊圓角（_outer_shell_scad → hull 4 cylinder $fn=48）
- [x] 5.3 build123d 同步：fillet Axis.Z 4 垂直邊，兩路不漂移
- [x] 5.4 voice 抽 corner_radius + DD-2 反問
- [x] 5.5 dev restart + PoC 圓角盒 + inline 顯示
- [x] 5.6 收尾：tasks.md 勾選 + architecture sync + event log

## 6. 品質美化：CMF 單色上色（2026-06-14）

- [x] 6.1 render_enclosure_model 加 color 參數（RGB/hex），替換寫死 grey；None 維持 neutral grey 向後相容（_resolve_cmf_color）
- [x] 6.2 voice 抽 CMF 顏色：_extract_gen_params / plan_c02_intent 從口述抽顏色關鍵字（白/黑/灰/紅/藍/銀…+ hex），存進 gen_params.cmf_color
- [x] 6.3 c02_render_enclosure handler + c02_voice_to_design 編排把 cmf_color 往下傳到 render
- [x] 6.4 測試：color 參數→vertex_colors 正確；None→grey；voice 抽色
- [x] 6.5 dev restart + PoC：口述含顏色 → 上色渲染圖 inline 顯示（poc2 iso/top PNG）
- [x] 6.6 收尾：tasks.md 勾選 + architecture sync + event log

## 7. 2D 向量：3D 投影出 SVG（取代獨立 c01_design-vector，2026-06-14）

- [x] 7.1 export_c02_projection_svg（workflow-core）：projection wrapper scad（projection() import Enclosure.stl）→ openscad -o Enclosure.svg，同款 subprocess 管線；無 OpenSCAD CLI → export_unavailable fail-fast；cut 參數可選
- [x] 7.2 MCP tool c02_project_svg（server.py handler+registration+me-group routing）
- [x] 7.3 c02_voice_to_design 編排可選輸出 projection SVG（pipeline.projection key）
- [x] 7.4 測試：projection wrapper 生成正確；無 CLI fail-fast；SVG 為幾何路徑非碎片
- [x] 7.5 dev restart + PoC：口述 → STL → 投影 SVG（poc2 Enclosure.svg，66×46mm 幾何路徑含圓角 arc），inline 顯示確認乾淨向量輪廓
- [x] 7.6 收尾：tasks.md 勾選 + architecture sync + event log（記 c01_design-vector superseded）
