# BR_20260730d — `POST /invoke` executes tools with no authentication on a `0.0.0.0`-published port

| Field | Value |
| --- | --- |
| Title | Unauthenticated tool execution via `POST /invoke` on the externally-published TCP port |
| Component | bodesign MCP HTTP surface (`services/mcp/server.py` — the worker-forwarding entrypoint) |
| Reporter | ses_04db7a1c5 (bodesign coordinator), from an independent verification by ses_04d725f79 (gpt-5.6) |
| Owner | ses_04db7a1c5 (bodesign coordinator) — new family, not the R9 skill-shipping family |
| Date | 2026-07-30 |
| Severity | **high** — arbitrary tool dispatch, no credential, reachable from the LAN |
| Priority | P1 |
| Affected paths | `services/mcp/server.py:2793-2797` (`invoke` handler), `:2955` (route registration), `docker-compose.yml:15-17` (`--host 0.0.0.0` + `ports: 8077:8077`) |

```
State:
Fix: none yet
Effect: live on the running deployment
Custody: bodesign
Blocker: needs a product decision on the turnstile shape (see §4)
Disposition: accepted — reproduced from a non-loopback address
Venue: bodesign
Status: OPEN
```

## 1. Symptom (verbatim, reproduced by the owner)

From the host's **LAN** address, not loopback:

```
$ curl -s -X POST http://192.168.125.117:8077/invoke \
    -H 'Content-Type: application/json' \
    -d '{"name":"bodesign_init","arguments":{}}'
{"ok":true,"doctrine":"<!--\n  bodesign CANONICAL USAGE DOCTRINE  (R15 …
```

No credential was presented. The tool executed and returned its payload.

## 2. RCA

`services/mcp/server.py:2793-2797`:

```python
async def invoke(request: Request) -> Response:
    # Internal worker entrypoint: the core forwards a tool call here. Runs the
    # tool locally on this (worker) process against the shared session volume.
    body = await request.json()
    return JSONResponse(run_tool(body.get("name", ""), body.get("arguments") or {}))
```

Three facts compose into the defect:

1. **The handler is a direct, unmediated call into `run_tool`.** No identity is
   read, no session is required, no MCP protocol handshake is involved. It
   bypasses the `/mcp` mount entirely.
2. **The comment's assumption does not hold.** It says *"the core forwards a
   tool call here"* — the route was designed as an **internal** core→worker
   channel (`a90c28f`, 2026-06-07, worker split). But it is registered on the
   same Starlette app as the public endpoints, and that app is bound to
   `--host 0.0.0.0` with `ports: "8077:8077"` in `docker-compose.yml`. The
   "internal" premise was never enforced by anything.
3. **`run_tool` is write-capable.** The registry includes mutating verbs
   (`c00_scaffold_prd`, `c01_add_reference_image`, `c00_update_answers`, the
   vault ingest surface, …), so this is not a read-only information exposure.

Notably the *workers* do NOT publish a port (`docker ps` shows an empty port
column for `bodesign-ee`/`bodesign-me`) — only the core does, and the core is
the one that does not need to receive forwards.

## 3. Which rule this violates

`mcp-integration-standard` **R12.5** (turnstile for write-capable shared
services):

> A shared service that exposes any **write/mutate** tool MUST gate calls behind
> an identity turnstile. `auth: { type: none }` + a `0666` socket is conformant
> ONLY for a **read-only** shared service; for a write-capable one it is an open
> till. **This graduates R10 from "forward-looking" to REQUIRED for
> write-capable shared services.**

`mcp.json` declares `auth: {"type": "none"}`, which R10.3 permits as the fleet
default — but R12.5 withdraws that permission for a write-capable service. So
this is an R12.5 violation, not an R10 one.

## 4. Fix proposal (needs a decision, hence OPEN not in-flight)

The shapes, cheapest first:

- **(a) Don't publish the port.** If nothing outside the host needs TCP, drop
  `ports:` and keep the UDS. Zero code change, kills the exposure outright.
- **(b) Bind loopback.** `ports: "127.0.0.1:8077:8077"` — keeps host-local TCP
  clients working, removes LAN reach.
- **(c) Restrict the route to the worker plane.** Serve `/invoke` only on the
  UDS listener, or reject it when the request did not arrive over the internal
  network. Preserves the core→worker design intent.
- **(d) Real turnstile (R12.6).** Propagate the gateway's per-user identity, or
  `auth: {type: token}` read host-side per R10.2.

(a)/(b) are configuration and reversible. (c) is the one that matches the
route's stated purpose. **This is a product/topology decision — who is supposed
to reach 8077 from off-box? — so it is not the owner's to make unilaterally.**

## 5. Explicitly NOT bugs

- **`auth: {type:none}` in `mcp.json`** is not itself a defect — R10.3 makes it
  the conformant fleet default. The defect is that a *write-capable* service
  relies on it (R12.5).
- **The `/skills`, `/tools`, `/health` surfaces** are read-only introspection;
  publishing those is fine.
- **The UDS `0666` mode** is R7.3-mandated and correct for a local-IPC socket.
- **This is not a regression from `8f2e91e`.** `git log -S'Route("/invoke"'`
  puts the route's introduction at `a90c28f` (2026-06-07); `8f2e91e` only
  touched an adjacent line. Filing it under the R9 BR would have buried a P1
  auth hole inside a closed skill-shipping issue.

## 6. Validation plan

- Negative: `curl -X POST http://<lan-ip>:8077/invoke -d '{"name":"bodesign_init"}'`
  → connection refused (a/b) or typed 401/403 (c/d). **Never** `200 ok:true`.
- Accepting control: the legitimate caller still works — core→worker forwarding
  succeeds (exercise an ee/me-routed tool end to end), and `/health`, `/tools`,
  `/skills` stay 200. Without this control, "everything is refused" would pass
  the negative test while breaking the product.
- Regression: `GET /skills/bodesign.zip` → 200 (the R9 surface is unaffected).

## 7. Provenance

Found by an independent adversarial verification of BR_20260730 (session
`ses_04d725f79`, `codex/gpt-5.6-terra`) commissioned by ses_04db7a1c5. The
verifier flagged it as V8 "self-directed attack", explicitly out of the R9
scope it was asked to check. Reproduced from a non-loopback address by the
owner before filing.
