# Observability: capability_refs-first-emitters

## Events

- emit 結果含 `refs_manifest` 摘要（source_count / authority_order / unadjudicated）——每次 emit 可稽核吃了哪些 refs
- readiness 結果含 `provenance_gaps[]`（item + reason + fix）——gap 可解釋、可行動

## Metrics

- `provenance_gaps` 數（目標 0 才 dod_ok）
- per-kind 分佈（refs / answer / derived 各幾項）——derived 比例高 = draft 未收斂訊號

## Debug checkpoints

- `RefsGateError.detail` 帶 layer + refs_root（定位哪個 stage 缺 SSOT）
- constraint JSON v2 頂層 `refs_manifest` 是 emit 當下快照，與 readiness 重算結果可對比（drift 可見）
