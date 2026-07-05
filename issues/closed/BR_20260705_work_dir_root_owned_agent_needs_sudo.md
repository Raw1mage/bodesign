# BR_20260705 — `.work/` 容器寫入產物為 root/ubuntu 所有，host 使用者與 agent 無法 mkdir/寫入，被迫 sudo

- **Scope**: bodesign runtime — docker-compose `.work` / work-dir mount uid ownership
- **Severity**: MEDIUM（每次動到 `.work/<project>/` 都撞權限；agent 需 sudo 繞過，違反最小權限 + 妨礙純 agent 流程）
- **Discovered during**: `aiguard/refs-ssot-build` Phase 1 harvest（建 `01_refs/`）與 Phase 3（建 `C03-EE/`）

## 現象（硬證據）

1. `.work/aiguard/` 及其子目錄為 **root:root**：
   `drwxr-xr-x 10 root root .work/aiguard`、`drwxr-xr-x 2 root root .work/aiguard/C00-PRD`（mtime Jun 15，先前容器以 root 身分寫入）。
2. Phase 3 host 端 `mkdir -p .work/aiguard/C03-EE` → `mkdir: cannot create directory '.work/aiguard/C03-EE': Permission denied`。
3. 被迫 `sudo mkdir -p .work/aiguard/C03-EE && sudo chown -R $USER:$USER .work/aiguard/C03-EE` 才能續作。
4. Phase 1 subagent 亦以同手法（sudo + chown）才建得了 `01_refs/`。
5. 容器內對應路徑 `/run/bodesign/vault` owner 為 `ubuntu:ubuntu`（container uid），與 host `pkcs12` 不一致。

## RCA

bodesign 容器行程以容器內 uid（root 或 `ubuntu`）寫入 bind-mounted `.work` / `./.run`。該 uid 與 host 使用者 `pkcs12` 不同，且無 uid 映射（無 `user:` 或 `--user $(id -u)`，dev overlay `${BODESIGN_WORK_DIR:-./.work}:/work` 也未設 uid）。結果：容器產生的檔案/目錄 host 使用者不可寫，agent 只能 sudo 繞過——這既是安全味道（agent 動用 sudo），也讓「純 agent、無特權」流程斷裂。

## 建議修復

- compose 對 bodesign（及 me/ee worker）加 `user: "${HOST_UID:-1000}:${HOST_GID:-1000}"`，或 entrypoint 以 host uid drop-privilege；`mcpctl.sh` 啟動時注入 `HOST_UID=$(id -u) HOST_GID=$(id -g)`。
- 或在 `mcpctl.sh` 提供一次性 `fix-perms`（`sudo chown -R $USER .work .run/vault`）作為 documented escape，但治本仍是 uid 對齊。
- 確保 `.work/<project>/` 與 `./.run/vault` 產物 host 可讀寫，agent 無需 sudo。

## 影響範圍

- 任何驅動真實 project folder 走 `.work/` 的流程（C00–C06 全鏈、E2E、本 plan 的 harvest/regen）。
- agent 自動化被迫 sudo（權限升級味道），或直接卡死在 Permission denied。

## 驗證手段

- 加 uid 對齊後：host `mkdir -p .work/<proj>/<stage>` 與寫檔**無需 sudo**成功。
- 容器啟動後 `ls -ld .work/<proj>` owner = host 使用者。
- 迴歸：容器仍能正常讀寫 `.work` / vault（功能不退）。
