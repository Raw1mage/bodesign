# Container boundary — host paths vs the file model

bodesign MCP runs **inside a Docker container** (per-user compose project `bodesign-${USER}`,
managed only via `./mcpctl.sh`). The container's mount namespace is narrow on purpose. Before you
pass any host path to a `bodesign_*` tool, know which side of this boundary it is on.

## What the container can see

The only host paths mounted into the container are:

- `<repo>/.run` → `/run/bodesign` (the UDS lives here)
- the **sessions** volume
- the **vault** volume

Everything else on the host — your project folder, a Google-Drive/FUSE mount, `/home/...`,
`/tmp` — is **not** in the container's mount namespace and is therefore **invisible** to every
tool. A path being readable from your shell says nothing about whether the container can see it.

> **Scope (≥ 0.2.0 / R13):** this boundary applies to the **compute-plane MCP tools** only. The ~52
> landing verbs (readiness family, scaffolds, orchestration spine — run host-side via `gate.py`)
> read the host filesystem directly; no container-visibility question arises for them.

## The failure this prevents

Passing an invisible/typo'd path to the readiness family used to return a syntactically clean
`readiness_pct: 0` with every deliverable `missing` — indistinguishable from a genuinely-empty
folder, and it has nearly caused an agent to regenerate real, hand-written deliverables.

That is now a **loud, distinguishable** signal. Every readiness check (`package_readiness`,
`c00..c06_readiness` — since R13 these are **landing verbs run host-side via `gate.py`**, not MCP
tools, so for them "visible" means visible on the HOST) returns, for an invisible root:

```json
{ "root_visible": false, "warnings": ["Folder not found / not visible ..."], "next_step": "Folder not visible to the bodesign container: ... use the file model ..." }
```

`root_visible: false` is the check. **Never** treat a `readiness_pct: 0` as "deliverables missing"
without first confirming `root_visible` is `true`.

## Decision rule

1. Is the path under one of the mounts above? → pass the host path directly as `folder`.
2. Otherwise → use the **file model**: upload the tree as a tarball to `POST /files` (or call
   `bodesign_stage_dir` with an inline `{relpath:{content,encoding}}` map) → you get
   `{token, doc_dir}`. Then call the tool in ONE of two equivalent ways:
   - **`token` + relative path** (preferred — portable): e.g. `bodesign_c00_emit_prd_docx(token="tok_…", folder=".")`.
     The server resolves every path arg inside the token's tree; `folder="."` is the tree root,
     `folder="C00-PRD"` a subdir. Produced files come back as `/files/{token}/blob/{rel}`.
   - **absolute `doc_dir`**: `bodesign_c00_emit_prd_docx(folder="/var/cache/bodesign/sessions/tok_…")`.

   Do **not** pass a bare `tok_…` string as `folder` — that is treated as a literal path and reports
   `root_visible:false`. The token goes in the `token` arg (or use the full `doc_dir` as `folder`).

You should never need `docker inspect` / `docker exec` to discover this — it is the boundary,
documented here, and the tool schemas (`folder` description + optional `token`) carry the same rule
at call time.

## Big-tree uploads (upload only what the tool reads)

(Readiness scoring is host-side since R13 — no upload is needed for it at all.) When a compute tool
does need a project tree, **exclude the heavy binaries** — `.glb`, `*_viewer.html`, PNG/JPG,
generated KiCad output. A full 46 MB tree times out on upload twice; the text/json subset is tens
of KB and uploads instantly. Stage the lightweight subset and only upload binaries when a tool
genuinely needs them.
