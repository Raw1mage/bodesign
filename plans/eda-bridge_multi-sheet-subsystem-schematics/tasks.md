# Tasks: eda-bridge_multi-sheet-subsystem-schematics

> 每個 `- [x]` 必須指名可機器驗證的產物（`artifact:` 欄，寫在同一行行尾）。
> 本包內的檔用**裸檔名**（`design.md`），不寫 repo 路徑。

## 1. 跨檔連通性驗證（(c-verify)，必須第一個做）

**理由**：整包其餘工作都預設「同名 global_label 跨檔連得起來」。這件事**從未被測過**——
我們只有一個檔，所以「同一張紙上同名連得起來」是平凡的，它與「跨檔連得起來」共用
「有 global_label 原語」這個外觀。若這格不成立，(a)(b)(d) 全部白做。

- [ ] 1.1 手工組一份最小 root + 2 葉，兩葉各 1 個**同名** global_label — artifact: none (scratch only — 產物在 $XDG_RUNTIME_DIR，不進 repo)
- [ ] 1.2 `kicad-cli sch export netlist` 匯出，確認兩端落在**同一條** net — artifact: test-vectors.json
- [ ] 1.3 **控制組**：同一份改成**不同名**，必須落在**兩條不同** net — artifact: test-vectors.json
- [ ] 1.4 把 1.2/1.3 固化成迴歸測試（兩格都要，缺控制組的 PASS 分不出「跨檔連通」與「netlist 把所有東西併成一條」） — artifact: tests/test_multisheet_global_label_link.py

## 2. 元件→sheet 分派（(d)）

- [ ] 2.1 決定 `group` 語意（Q1：C-1 合一 vs C-2 新增 `sheet` 欄）— **待使用者裁決，不得自行選定** — artifact: none (decision only — see design.md DD-1)
- [ ] 2.2 純函式 `partition_components(spec) -> SheetMap`，嚴格 partition — artifact: packages/eda-bridge/bodesign_eda_bridge/partition.py
- [ ] 2.3 `E_UNASSIGNED_REFS` / `E_REF_ON_MULTIPLE_SHEETS` 兩個 fail-fast，各配一組負向控制 — artifact: tests/test_sheet_partition.py
- [ ] 2.4 `not-run` / `empty` 分支入口計數器（不是結果欄位） — artifact: packages/eda-bridge/bodesign_eda_bridge/partition.py
- [ ] 2.5 用真板第 5 欄驗證分派結果為 22/9/14、Σ=distinct=45 — artifact: tests/test_sheet_partition.py

## 3. 多檔容器（(a)）

- [ ] 3.1 寫檔點從單數擴為一組（現況 1 處，`kicad_emit.py:2452-2453`） — artifact: packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py
- [ ] 3.2 **N=1 byte-stable**：與 HEAD 的 `WIRE_GEOM_SHA` 逐字相同 — artifact: tests/test_multisheet_single_bytestable.py
- [ ] 3.3 `files` 清單只列磁碟上真實存在的檔（repo 天條 §2.2） — artifact: tests/test_multisheet_files_manifest.py
- [ ] 3.4 `E_LEAF_WRITE_FAILED` 時清除半套檔組，不留殘骸 — artifact: tests/test_multisheet_files_manifest.py

## 4. root sheet block（(b)）

- [ ] 4.1 逐欄對照真板 root 寫出 `(sheet …)` 產生器 — artifact: packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py
- [ ] 4.2 `E_ROOT_SHEET_BLOCK_INVALID` 缺欄檢查 — artifact: tests/test_root_sheet_block.py
- [ ] 4.3 `kicad-cli` 能開啟 root 並匯出涵蓋全部葉紙的 netlist — artifact: tests/test_root_sheet_block.py
- [ ] 4.4 回答 Q2（`page` 從 2 起算是 KiCad 強制或作者選擇）— 目前只有一份樣本 — artifact: design.md

## 5. 政策 sheet-aware（(e)）

**射程已縮小**：K8 測得放寬政策在多 sheet 下交叉數仍達 80%，`M6-8d` **存活**。
本 Phase **只做「判定範圍降到 sheet 層級」，不含「鬆綁政策」**。

- [ ] 5.1 三條政策加 `scope` 參數（`whole` 預設 / `sheet`），`E_SCOPE_UNKNOWN` 不得靜默退回 — artifact: packages/eda-bridge/bodesign_eda_bridge/composer.py
- [ ] 5.2 **兩處實作都要改**：`composer.py:2175-2231` 與 `kicad_emit.py:1274-1282` 會 OR 回去（舊包 `errors.md` ⑤） — artifact: packages/eda-bridge/bodesign_eda_bridge/kicad_emit.py
- [ ] 5.3 K9 的 **8** 條單紙 net 在 `scope="sheet"` 下是否改為 drawn，逐條列名 — artifact: test-vectors.json（**不是 9**：round 41 成因判準把 `ENPPB` 移出，它是 anti-fusion 不是政策）
- [ ] 5.4 `policy_evaluated` 分支入口計數器，正控制必須先見非零才可信 — artifact: packages/eda-bridge/bodesign_eda_bridge/composer.py

## 6. 驗收與回歸

- [ ] 6.1 五組子系統各自成為一張可獨立閱讀的葉紙（AC-5） — artifact: test-vectors.json
- [ ] 6.2 既有 153 個測試模組逐 test-id 比對 NEW RED / NEW GREEN（**讀 `Ran N tests` 的 N，不讀 rc**） — artifact: none (measurement — 結果寫入 design.md §Impact)
- [ ] 6.3 回答 Q3 剩下的一格：29 處 `result.schematic_path` 在 N=1 保持原義是否真的免改 — artifact: design.md
- [ ] 6.4 同步 `specs/architecture.md`（C03 輸出從單檔變檔組） — artifact: specs/architecture.md
