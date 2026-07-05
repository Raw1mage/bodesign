# Errors: capability_refs-derived-design

## Error Catalogue

| Code | Condition | Surface | Recovery |
| ---- | --------- | ------- | -------- |
| REFS_SSOT_MISSING | 下游生成 verb 呼叫時對應層 `01_refs/` SSOT 不存在 | typed error envelope `{ok:false, error_code, missing[]}`，exit≠0 | 逆向拆解 owner 來源建該層 SSOT 後重試 |
| REFS_ANCHOR_MISSING | SSOT 存在但某筆資料無 owner 來源錨點（No fabrication 天條 2） | typed error + 無錨點欄位清單 | 補來源錨點（doc/page/region）；無來源不硬編碼 |
| UPSTREAM_CONSTRAINT_MISSING | placement/castellated verb 缺上游凍結約束 JSON（切面 4） | typed error `{error_code:"UPSTREAM_CONSTRAINT_MISSING"}` | 由上游 stage 凍結 face-layout/envelope 後重試 |
| CONNECTOR_FACE_CONFLICT | C04 嘗試移動連接器至非上游指定面/邊（切面 2 DD-4） | typed error + 衝突面向 | 遵從 C01 face-layout；面向非 C04 自由度 |
| BOARD_SURGERY_UNSAFE_PATH | castellated 生成走已知 segfault path（如 SetTextSize 直呼，切面 3 DD-5） | typed error，拒絕執行 | 走 S-expression text-layer 注入 wrapper |
| DOD_TRACEBACK_FAILED | 交付物含 SSOT 無法追溯項（憑空發明，切面 5） | BLOCKING report + untraceable[] | 移除憑空項或補 SSOT 回溯鏈 |
