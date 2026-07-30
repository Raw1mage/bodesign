# BR_20260730 — bodesign 的 `GET /skills` 服務 `.tar.gz` 並廣告檔名，偏離 R9.2 釘死的 `.zip`（且服務來源與 `skillPaths` 宣告來源不同源）

| Field | Value |
| --- | --- |
| Title | bodesign R9.2 格式偏離：`/skills` 廣告檔名 + 服務 `.tar.gz`，遠端 client 全數取不到 |
| Component | bodesign MCP HTTP introspection surface（`services/mcp/server.py`） |
| Reporter | ses_05b51c060（fleet R9 稽核，dispatcher 自驗） |
| Date | 2026-07-30 |
| Severity | high — 14 個 companion（含 `bodesign` 主 skill 894812B）全部對合規 client 不可取；且服務來源 `services/mcp/assets/skills/` 與 `mcp.json skillPaths` 宣告的 repo `skills/` **不同源** |
| Priority | P2 — 本機 opencode host 走 R9.1 本地半仍可取得；衝擊面限遠端 / 非 opencode client |
| Affected versions/tools/paths | bodesign 0.3.0；`mcp.json:14` `skillPaths:["skills"]`；`services/mcp/server.py:2869-2870`（route）、`:2733-2745`（list handler）、`:2760-2772`（download handler）、`:1932-1933`（`_assets_dir()`） |

```
State:
Fix: unfixed
Effect: n/a
Custody: unclaimed
Blocker: none
Disposition: accepted
Venue: bodesign
```

## 1.1 症狀（verbatim）

對活著的 bodesign server 撥號：

```
GET /skills                  -> 200
  {"service":"bodesign","count":14,"skills":[
     {"name":"bodesign-eda-skills-bundle.tar.gz","skill":"bodesign-eda-skills-bundle",
      "bytes":1100211,"url":"/skills/bodesign-eda-skills-bundle.tar.gz"},
     {"name":"bodesign.tar.gz","skill":"bodesign","bytes":894812, ...}, ...]}

GET /skills/bodesign.tar.gz  -> 200   894812 bytes   application/gzip
GET /skills/bodesign.zip     -> 404        <- R9.2 釘死的形狀不存在
```

兩件事同時偏離規範：

1. **payload 廣告檔名**（`"name":"bodesign.tar.gz"`）而非 bare skill name。`.zip` 屬於**端點**，不屬於名字。
2. **服務 `.tar.gz`** 於 `/skills/{name}`，而 R9.2 釘死 `GET /skills/<name>.zip`。

## 1.2 消費端實測（決定性）

用 opencode 的 R9.2 消費端（`packages/opencode/src/mcp/skill-fetch.ts`）撥號：

```
{"id":"bodesign","kind":"failed",
 "reason":"GET /skills/bodesign-eda-skills-bundle.tar.gz.zip returned HTTP 404"}
```

注意那個 `.tar.gz.zip` —— 這是 tolerant reader（R9.8）忠實取用 `name` 欄位後再依 R9.2 附加 `.zip` 的**必然結果**。對照組（同一支消費端、同一次執行）：

```
{"id":"docxmcp", "kind":"materialized","skills":["doc-workflow"]}
{"id":"drawmiat","kind":"materialized","skills":["flowchart-author","miatdiagram"]}
{"id":"pmsmcp",  "kind":"materialized","skills":["pmsmcp"]}
```

三個成功證明消費端有效。bodesign 的失敗**不是** client 的問題。

## 1.3 Findings

```
Findings:
F1 GET /skills 廣告 archive 檔名而非 bare skill name（違反 R9.2 名字語義） Fix: unfixed Disposition: accepted Venue: bodesign
F2 下載端點供 .tar.gz 於 /skills/{name}，無 R9.2 釘死的 /skills/<name>.zip Fix: unfixed Disposition: accepted Venue: bodesign
F3 服務來源 services/mcp/assets/skills/ 與 mcp.json skillPaths 宣告的 repo skills/ 不同源，無單一來源 assert Fix: unfixed Disposition: accepted Venue: bodesign
```

## 1.4 RCA

`services/mcp/server.py:2733-2745`（list handler）：

```python
skills_dir = (_assets_dir() / "skills")
for f in sorted(skills_dir.glob("*.tar.gz")):
    items.append({"name": f.name,            # <- f.name 是檔名，含 .tar.gz
                  "skill": f.name[:-len(".tar.gz")],   # <- bare name 在這裡，但沒被當成 name
                  ...})
```

`"skill"` 欄位**其實已經有 bare name**，但 R9.8 的 tolerant reader 讀的是 `name`（那是 fleet 各實作的共同鍵），於是取到檔名。

`:2760-2772`（download handler）只接受 `.tar.gz` 與 `MANIFEST.md`：

```python
if not target.is_file() or not (target.name.endswith(".tar.gz") or target.name == "MANIFEST.md"):
    return JSONResponse({"error": "not_found"}, status_code=404)
```

**F3 是更深的一層**：`_assets_dir()` 是 `Path(__file__).resolve().parent / "assets"`（`:1932-1933`），即 `services/mcp/assets/skills/`——那裡有 14 個預先打包的 tarball。而 `mcp.json skillPaths:["skills"]` 指的是 **repo 根的 `skills/`**（內含 `bodesign`、`bodesign-kb` 兩個目錄）。兩個來源之間沒有任何一致性斷言，所以本地半與遠端半可以無聲漂移。

`issues/BR_20260721_mcp_r17_r0.6_conformance_gap.md:91` 自己已預警過這點：「`GET /skills`（`assets/skills/*.tar.gz`）… 三者**很可能**同一 companion 但無單一來源 assert；parity/drift test **仍可能失敗**」。本 BR 把該預警坐實。

## 1.5 Mandatory History Review

| Aspect | Finding |
| --- | --- |
| Same-family BRs | `yes（最近親，同面向但非同症狀）：issues/BR_20260721_mcp_r17_r0.6_conformance_gap.md`（**open**）。該 BR `:35` 已記「R17.5（部分）… skillPaths `mcp.json:14-16`、`GET /skills` `:2316-2328`」，`:91` 更明點 tar.gz 來源與 parity drift 風險——**已預警但未坐實遠端拿不到**。其餘命中（`BR_20260705_landing_verb…`、`closed/issue_20260623_c06_analyzer_engines…`、`closed/issue_20260623_analyze_emc…`）為 skill engine 掛載 / 本機 mirror 路徑，屬旁系。掃描 pattern：`skillPaths`/`/skills`/`skill.?ship`/`companion`/`SKILL_NOT_SHIPPED`/`HALF_SHIPPED`/`R9`/`zip`/`tar.gz`（`R9` 有誤命中 `BR_20260730c_export_bom…:119` 的「R9 標記 in_bom=no」，已排除）。 |
| Recurrence | `no（此精確症狀）／但已被自己預警` — 格式偏離（`.tar.gz` vs `.zip`）先前未被修過；`BR_20260721:91` 標為「parity/drift test 仍可能失敗」的待補項。 |
| Event log / KB hits | `none — event_search q="skill shipping companion remote" → []；wiki_search q="skillPaths companion skill R9" → []`（`.specbase/` 存在、runner 正常）。 |
| Owning spec / contract | `specs/mcp_r15-self-describing-guide/`（companion 單一來源 doctrine，`design.md:16/:45`、`proposal.md:36` R15.5 one-source：guide / prompts / companion skill 同源）——**F3 直接違反這條 one-source**。`BR_20260721` 宣告要新開 R17 spec 但尚無獨立 spec 目錄。**無任何本 repo spec 管 `GET /skills` 的 archive 格式**；格式契約只存在 fleet SSOT `opencode/specs/mcp-integration-standard/` R9.2，這是它得以偏離而不被自檢的結構原因。 |
| Isomorphic failures | `yes（同 repo）` — F3 本身就是同形失敗：宣告來源 ≠ 服務來源。同 fleet 內 specbase（零 route）、patentmcp（缺 list）、formmcp（空目錄）同屬「R9 遠端半只做一半」家族，機制各異。 |

## 2. 修復方向（venue: bodesign）

規範要求（`mcp-integration-standard` R9.2 / R9.8 / R9.4.1）：

1. **F1**：list payload 的 `name` 改為 bare skill name（現成的 `"skill"` 欄位值）。可保留 `file`/`bytes` 等額外欄位——R9.8 容忍額外鍵，只要 `name` 是 bare name。
2. **F2**：新增 `GET /skills/<name>.zip`（zip 格式）。既有 `.tar.gz` 路徑可保留作為 back-compat，但**必須另外**提供 `.zip`，否則合規 client 取不到。
3. **F3**：對 `mcp.json skillPaths` 宣告的來源與 `assets/skills/` 服務的來源加一個 parity 斷言（測試或啟動時檢查），讓兩者不能無聲漂移。這是 `mcp_r15-self-describing-guide` R15.5 one-source 的既有要求。
4. R9.7.1 producer 端：zip 內不得有絕對路徑、`..` 片段、symlink。

可參考同 fleet 已合格的 Python 實作：`docxmcp/bin/_skill_shipping.py` + `docxmcp/bin/mcp_server.py:7123-7124`。

## 3. 驗證計畫

- 正向：`GET /skills` 的每個 `name` 皆為 bare（無 archive 後綴）；逐個 `GET /skills/<name>.zip` 回 200 且 bytes > 0
- 負向：未知名 → typed 404（非 500、非 200 空 archive）；traversal → 403/404（既有 `path_escape` 檢查已有，需回歸）
- 回歸：既有 `.tar.gz` 路徑若保留，仍須可用
- F3：parity 測試證明宣告來源與服務來源一致（或明文記錄兩者的映射關係）
- 端到端：`McpSkillFetch.materialize` 對本服務回 `kind:"materialized"`
- 機檢：`McpConformanceProbe.run()`（opencode `76d58bb64`）對 bodesign 的 14 個 `MCPSTD_SKILL_LISTED_NOT_SERVED` 消失
