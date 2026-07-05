# Tasks: quality_deterministic-preplacement

## 1. 規則表與純核心

- [x] 1.1 `placement_rules.py`：R1/R4/R8/R16 子集落盤，每條帶 source 錨點 + value + unit
- [x] 1.2 `preplace.py` 資料模型：`PartGeom`（ref/w/h/pads/value/kind）、`PreplaceResult`（placement/violations/effective）
- [x] 1.3 錨定 + pin 歸屬分群（DD-7：主 IC、decap、crystal C、上拉、連接器板緣帶、自由層）
- [x] 1.4 環帶格點貪婪初擺（R4 大到小排序、歸屬距離最小化、AABB 不重疊）
- [x] 1.5 固定 seed SA 微調（DD-8 能量函數、平移/旋轉/互換移動集、echo 生效參數）
- [x] 1.6 擺後檢查器：R1 距離、R8 die-shadow proxy，違反清單帶錨點

## 2. 接線與 fail-fast

- [x] 2.1 `routing.py`：`net2pcb_board` 加 `strategy`/`seed` 參數；pcbnew 幾何抽取 adapter；缺幾何 fail fast 列缺項
- [x] 2.2 `__init__.py` export + `services/mcp/server.py` schema 補參數與描述
- [x] 2.3 grid 路徑回歸不變（預設 strategy=grid）

## 3. 驗證

- [x] 3.1 `tests/test_preplace.py`：確定性（兩次執行相等）、分群正確性、貪婪不重疊、SA 收斂方向
- [x] 3.2 checker 已知違反案例測試（帶錨點輸出）
- [x] 3.3 LED driver 案基線對比（16 零件 10 net 合成重現）：deterministic vs grid 的 decap 距離 / HPWL / 重疊數，量化記錄
  - 量測（seed=42, board 50×40mm）：decap C1→U1.1 距離 grid=17.53mm → det=**2.50mm**（R1 限 3.0mm 內）；HPWL grid=336.2mm → det=**102.3mm**（-70%）；violations=0；overlap_pairs=0
- [x] 3.4 全 test suite 綠：969 tests OK (skipped=30)。原文： 全 test suite 綠（PYTHONPATH 含全部 packages）

## 4. 收尾

- [x] 4.1 KiCad-Autoplace spike 結論回填 design.md DD-2（REJECT-vendor，自研；參考實作引用）
- [x] 4.2 `skills/bodesign/stages/c04-layout/GUIDE.md` 擺件段落已同步（strategy/seed/board_mm 參數與 fail-fast 契約）
- [x] 4.3 event_record 收尾已寫（scope quality/deterministic-preplacement）+ architecture.md EDA-bridge 段全貌同步
