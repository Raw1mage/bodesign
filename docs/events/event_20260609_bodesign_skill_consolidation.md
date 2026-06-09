# Event: bodesign Skill Consolidation

## 需求

- 盤點 `bodesign` skill 的維護位置。
- 將制度/方法權威移回本名 repo 的 `skills/`，避免 plan-local skill 副本漂移。

## 範圍(IN)

- 盤點 `/home/pkcs12/projects/bodesign` 與既有 user-level skill 來源。
- 將既有完整 `bodesign` lifecycle skill 複製到本 repo 的 `skills/bodesign/`。
- 將 `skills/bodesign/` 打包成 `services/mcp/assets/skills/bodesign.tar.gz`，由 MCP HTTP server 的 `/skills/bodesign.tar.gz` 發布。
- 刪除 `plans/feature_doc-package-scaffold/skills/*/SKILL.md` 三份 plan-local skill 副本。
- 更新 plan 文件與 runtime template 中的 skill 引用，指向 `skills/bodesign/stages/*/GUIDE.md`。

## 範圍(OUT)

- 不修改 `/home/pkcs12/projects/skills` repo 內既有未關變更。
- 不重包 `services/mcp/assets/skills/bodesign-eda-skills-bundle.tar.gz`；該 bundle 維持 EDA companion skills，lifecycle skill 以獨立 `bodesign.tar.gz` 發布。

## 任務清單

- [x] 盤點 repo-local 與 user-level skill 來源。
- [x] 確認既有完整 lifecycle skill 已有 C00/C01/C02 stage guides。
- [x] 複製 canonical skill 到 `skills/bodesign/`，排除 `__pycache__`/`.pyc`。
- [x] 打包 `services/mcp/assets/skills/bodesign.tar.gz` 並更新 MCP landing/manifest；發布包排除 `__pycache__`、`.pyc`、`thesmart_products`/`openmv` worked-example symlink。
- [x] 刪除 plan-local C00/C01/C02 `SKILL.md` 副本。
- [x] 更新 plan/template 引用，避免再把 C00/C01/C02 描述成 plan-local skill。

## Key Decisions

- Canonical authority is now `skills/bodesign/` inside the `bodesign` repo.
- MCP HTTP server publishes that authority as `/skills/bodesign.tar.gz`; EDA companion downloads remain separate. The lifecycle tarball excludes private worked-example symlinks while retaining public workflow docs and companion-engine references.
- `plans/feature_doc-package-scaffold/skills/` 不再維護 C00/C01/C02 skill 副本。
- C00/C01/C02 方法內容應落在 `skills/bodesign/stages/c00-prd|c01-id|c02-me/GUIDE.md`，project plan 只保留歷史決策與 runtime 任務紀錄。

## Issues Found

- Plan-local C00/C01/C02 skill 副本與 lifecycle `bodesign` skill 同時存在，形成雙真相來源風險。
- 既有 `/home/pkcs12/projects/skills` 工作樹有多個未關變更；本次只讀取並複製 `bodesign` skill 內容，不在該 repo 直接改檔。

## Verification

- `glob **/SKILL.md` confirmed this repo originally only had C00/C01/C02 plan-local skill sources.
- `skills/bodesign/SKILL.md` and `skills/bodesign/stages/c00-prd|c01-id|c02-me/GUIDE.md` now exist in this repo.
- `services/mcp/server.py` lists `bodesign.tar.gz` as a featured lifecycle download and keeps `/skills/{name}` path-safety checks.
- `services/mcp/assets/skills/MANIFEST.md` documents installing `bodesign.tar.gz` separately from the EDA bundle.
- `tar -tf services/mcp/assets/skills/bodesign.tar.gz` verified the lifecycle package contains `bodesign/SKILL.md` and C00–C07 guides; follow-up tarball inspection excluded `thesmart_products`, `openmv`, `__pycache__`, and `.pyc` entries.
- `tar -tf services/mcp/assets/skills/bodesign-eda-skills-bundle.tar.gz` showed EDA companion skills, not the removed C00/C01/C02 plan-local skill copies.
- Architecture Sync: Updated. `specs/architecture.md` now records that `services/mcp` publishes installable skill downloads under `/skills/{name}`, including `bodesign.tar.gz` for the repo-local lifecycle skill.

## Remaining

- If the old user-level `/home/pkcs12/projects/skills/bodesign` copy should stop being authoritative, handle that repo separately after isolating unrelated dirty changes.
