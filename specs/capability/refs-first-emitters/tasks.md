# Tasks: capability_refs-first-emitters

## 1. Provenance 基建

- [x] 1.1 `provenance.py`：taxonomy dataclass/helpers（kind 枚舉、refs source 解析驗證、gap 描述），c01/c02 共用
- [x] 1.2 `emit_c01_rockbox_package` 入口接 `require_refs(out_dir, "C01")`；`RefsGateError` 原樣上拋
- [x] 1.3 `emit_c02_enclosure_package` 入口接 `require_refs(out_dir, "C02")`

## 2. C01 emitter

- [x] 2.1 `_component_list`：answers 項 → kind=answer；corpus 推導項 → kind=derived（含命中 keyword detail）；帶 source 的 dict 傳入 → kind=refs
- [x] 2.2 `_constraints`：schema 升 v2，per-item provenance + 頂層 refs_manifest 摘要
- [x] 2.3 variant 命名審計：slug 生成只用清洗後 product_name，emitter 不添 archetype/variant 字串

## 3. C02 emitter

- [x] 3.1 `_normalized_constraints`：約束項 provenance 標記（caller dict 無 attribution → derived）
- [x] 3.2 `constraint_status` 增 `provenance_gaps`

## 4. Readiness gates

- [x] 4.1 C01：readiness 解析 provenance，gap → `dod_ok:false` + `provenance_gaps[]`；v1 舊檔報 gap 並附修復指引
- [x] 4.2 C02：`assess_c02_constraint_readiness` 增 provenance blocker item（同語義）

## 5. 驗證

- [x] 5.1 `tests/test_refs_first_emitters.py`：TV-1~TV-5（gate fail-fast、tagging、BR §5a/§5b/§5c）
- [x] 5.2 既有 `test_c01_id_package.py` / `test_c02_me_package.py` / `test_readiness_invisible_path.py` 補 `01_refs/` fixture，全綠
- [x] 5.3 全 test suite 綠（PYTHONPATH 含全部 packages；期待 ~969+ tests）

## 6. 收尾

- [x] 6.1 `skills/bodesign/stages/c01-id/GUIDE.md`、`c02-me/GUIDE.md` 同步 refs-first 契約
- [x] 6.2 `specs/architecture.md` 全貌同步（C01/C02 emitter 段）
- [x] 6.3 event_record 收尾 + friction 掃描
