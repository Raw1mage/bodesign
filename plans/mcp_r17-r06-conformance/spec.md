# Spec: mcp_r17-r06-conformance

## Purpose

bodesign MCP server 對 fleet `mcp-integration-standard` 的 R17（minimum operational
toolset + host mediation）與 R0.6（companion-skill wall-nudge）達 fully conformant：
common lifecycle 收斂成小而可預測的工具家族，delivery-oriented 操作能對成品做
machine-checkable 斷言，錯誤在 action boundary 附「正確 primitive + 該載的 skill」remedy。
所有新閘一律 fail-fast + 顯式報錯 + 缺項清單（bodesign no-silent-fallback 天條），且
對 bare MCP client（tools/call + resources/read + prompts/get）可用。

## Requirements

### Requirement: Machine-readable capability summary (R17.1.1/.1.2)

`bodesign_init` SHALL return, in addition to the prose doctrine, a structured
`capabilities` object covering transport, file ingress/egress, WebDAV state,
companion skill, and conditional tool families, and SHALL distinguish
service/container endpoints from host-visible endpoints such that a container
socket path is not presented as host-executable.

#### Scenario: init capability summary is test-branchable

- **WHEN** a client calls `bodesign_init`
- **THEN** the response carries `capabilities.transport.service_endpoints[]` each
  with a `host_executable: false` flag on container UDS paths, and a conformance
  test executes a decision from that structured payload (not merely asserts text exists)

### Requirement: Portable resource egress (R17.2.2)

The server SHALL expose `resources/list` + `resources/read` so every token-produced
blob is retrievable as `bodesign://files/<token>/<rel>` by a bare MCP client with no
host-private extension (HTTP blob / WebDAV / UDS curl).

#### Scenario: bare client retrieves a deliverable

- **WHEN** a stdio-only client reads `bodesign://files/<token>/<rel>`
- **THEN** the server returns the blob bytes via `TokenStore.safe_join`, with a
  traversal guard, and no HTTP transport is required

### Requirement: Workspace inspection before transform (R17.2.3)

The server SHALL provide a list/status tool enumerating a token namespace tree so a
caller can prove expected assets exist before a mutation/render.

#### Scenario: inspect proves assets exist

- **WHEN** a caller calls `bodesign_workspace_inspect(token)`
- **THEN** it returns `{token, doc_dir, files[], count}` with no mutation

### Requirement: Typed asset preflight + content assertion (R17.2.4/.2.5)

Before mutation/render/assemble the server SHALL reject unresolved paths, missing
media, paths outside the token namespace, and host-only absolute references with a
typed error + R0.5 remedy; and delivery-oriented operations SHALL evaluate
machine-checkable content assertions such that a transport-valid but empty artifact
is NOT reported as delivery-ready.

#### Scenario: empty artifact is refused

- **WHEN** a render/emit tool produces a transport-valid but empty artifact and the
  caller requested `non_empty`/`expected_*` assertions
- **THEN** the server returns `ASSERTION_EMPTY` NOT-delivery-ready, never `ready=true`

#### Scenario: unresolved media is refused before render

- **WHEN** a render/assemble call declares an asset path that does not resolve inside
  the token namespace
- **THEN** preflight returns a typed `PREFLIGHT_*` error + remedy line before the
  handler runs (fail-fast, no silent continue)

### Requirement: Companion-skill wall-nudge (R0.6)

The server SHALL detect a skipped-companion-skill wall from the toolcall itself
(never by querying caller skill-state) and, on the error it already returns, append a
single-source remedy naming the correct primitive + the companion skill, projected
onto the portable `content` text; a silent `ok=true` no-op at a hard wall SHALL be
converted to a loud failure.

#### Scenario: hard wall enriches the failure

- **WHEN** a toolcall exhibits a bad-shape id or a grain-mismatch zero-element edit
- **THEN** the tool fails loud and the error `content` carries the single-source
  nudge (`skill(bodesign)` + correct primitive), and a previously silent no-op is
  now a loud failure

#### Scenario: advisory wall never blocks

- **WHEN** a first unbounded sweep of a large workspace has no prior recon
- **THEN** a non-blocking advisory hint is attached to the otherwise-successful
  result (success is never converted to failure)

### Requirement: Companion-skill parity (R17.5)

`mcp.json.skillPaths`, `GET /skills`, `bodesign_init`, and the companion skill SHALL
identify the same companion from one source, and the guide's first-use section SHALL
name the concrete baseline/conditional tools.

#### Scenario: parity holds across three faces

- **WHEN** a drift test reads the companion identity from skillPaths, GET /skills,
  and bodesign_init
- **THEN** all three resolve to the same `COMPANION_SKILL` constant

## Acceptance Checks

- [ ] `bodesign_init` returns structured `capabilities` with endpoint flags; test branches on it
- [ ] `resources/list` + `resources/read` serve `bodesign://files/<token>/<rel>` bytes portably
- [ ] `bodesign_workspace_inspect` returns the token tree without mutation
- [ ] preflight rejects unresolved/missing/out-of-namespace/host-only paths with remedy
- [ ] content-assertion refuses empty artifacts as delivery-ready
- [ ] `_skill_nudge` produces single-source hard/advisory remedy projected to content text
- [ ] R17.6 (a)-(e) five scenarios each have a test proving they no longer silent-pass
- [ ] R17.5 parity/drift test passes across three faces
- [ ] full pytest suite + live UDS/MCP smoke pass
