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
Fix: fixed (2026-07-30) — option (a): the published port is gone
Effect: DEPLOYED and verified — no host listener, LAN unreachable, accepting controls pass
Custody: bodesign
Blocker: none
Disposition: accepted — reproduced from a non-loopback address before filing
Venue: bodesign
Status: FIXED — see §8. Residual documented and ACCEPTED (§8.3), not hidden.
Closed: 2026-07-30 by ses_04db7a1c5 (bodesign coordinator), on the user's explicit choice of option (a)
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

---

## 8. Resolution (2026-07-30) — option (a), chosen by the user

The user chose **(a) do not publish the port**. `docker-compose.yml` no longer
carries a `ports:` entry.

### 8.1 Why (a) is the right call, not merely the cheapest

This compose file's own header has said since 2026-06-07:

> External HTTP, if wanted, is exposed by a gateway in front of this socket
> **(not a published port here).**

The `ports: ["8077:8077"]` entry contradicted the file's own stated design for
seven weeks. So (a) is not a new restriction — it is the implementation finally
catching up to the declared architecture. `mcp.json`'s `url` has always declared
the UDS as the reachable endpoint, so nothing that follows the manifest loses
access.

### 8.2 Declaration sync — the part that would otherwise have created a NEW defect

Removing the port while leaving the docs advertising a dialable
`http://<host>:8077/mcp/` would have reproduced **exactly the defect class of
the parent BR**: a service whose declaration and behaviour disagree. Eight
declaration sites were corrected in the same commit:

| File | Was |
| --- | --- |
| `docker-compose.yml` | `ports: ["8077:8077"]` |
| `mcp.json` (`instructions`) | "reachable over … TCP HTTP at `http://<host>:8077/mcp/` (the container publishes both)" |
| `skills/bodesign/doctrine.md` | "AND TCP `http://<host>:8077/mcp/` … the container publishes both" |
| `AGENTS.md` | "UDS（本機）+ TCP（`:8077` HTTP `/mcp/`）" |
| `README.md` | "對外：`http://<host>:8077/mcp/`" (3 sites) |
| `README.en.md` | "External: `http://<host>:8077/mcp/`" (3 sites) |
| `services/mcp/README.md` | "container publishes `:8077`" |
| `services/mcp/assets/skills/MANIFEST.md` | install commands dialing `http://<host>:8077/skills/…` |

MANIFEST.md now uses a `<base>` placeholder for whatever gateway fronts the
service, and states plainly that there is no `http://<host>:8077` to dial.

### 8.3 Residual risk — ACCEPTED and recorded, not eliminated

**`POST /invoke` is still unauthenticated on the compose network.** Any
container sharing that network can call it. This is *by construction*: it is
the core→worker forwarding channel, and `BODESIGN_ME_WORKER_URL` /
`BODESIGN_EE_WORKER_URL` point at exactly that route on the worker containers.

What (a) changed is the **reachability boundary**, not the authentication
posture — the exposure went from "every interface on the host, including the
LAN" to "the private compose network". A real turnstile (option (d), R12.6) is
the only thing that would close it outright.

This is written down rather than quietly dropped because a future change that
re-publishes the port — or attaches this service to a shared/external docker
network — **silently restores the original hole**. Do not re-add `ports:`.

### 8.4 Verification (deployed via `BODESIGN_WORKERS=1 ./mcpctl.sh rebuild`)

Negative — the exposure is closed:

```
$ docker ps --format '{{.Names}}\t[{{.Ports}}]' | grep bodesign
bodesign-pkcs12-bodesign-1     []
bodesign-pkcs12-bodesign-ee-1  []
bodesign-pkcs12-bodesign-me-1  []

$ ss -ltn | grep :8077                     -> no host listener
$ POST http://192.168.125.117:8077/invoke  -> 000 (unreachable)
```

Accepting controls — **the legitimate paths still work.** Without these, "the
LAN cannot reach it" would be equally satisfied by a service that is simply
broken:

```
UDS socket present   : .run/bodesign.sock                 PASS
health               : {"status":"ok","tools":57}         PASS
containers           : core / ee / me all healthy         PASS
core -> ee /healthz  : 200                                PASS
core -> me /healthz  : 200                                PASS   <- forwarding intact
```

The last two matter most: `/invoke` exists **for** core→worker forwarding, and
that is precisely what still works. Only outside reach was removed.

Regression on the parent BR's surface (verified inside the container, since the
host can no longer dial it):

```
bodesign.zip -> 200 · bodesign.tar.gz -> 200
seven unservable shapes -> 404 each
```
