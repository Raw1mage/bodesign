---
id: BR_20261009_dockerlab_readme_describes_tls_and_basic_auth_that_the_shipped_nginx_conf_does_not_implement
title: deploy/dockerlab README describes TLS and basic-auth ingress that the shipped nginx.conf does not implement
date: 2026-10-09
status: closed
severity: medium
priority: P2
component: deploy/dockerlab/{README.md,docker-compose.yml,nginx.conf}
reporter_session: ses_04db7a1c5ffelvbxyLP1p6xlRH
edges:
  - to: issues/BR_20261006_dockerlab_compose_omits_vault_dir_so_served_vault_tools_return_e002.md
    type: same-family
    reason: Same deploy/dockerlab mirror; both are deploy-doc vs deployed-reality drift.
---
# deploy/dockerlab README describes TLS and basic-auth ingress that nginx.conf does not implement

- **Status**: CLOSED — option (a) applied 2026-10-09 (worker ses_ee02d0ab7, officer-verified diff); README §3 Exposure Boundary added, TLS/htpasswd steps removed, compose comment corrected

## 1. Symptom (verbatim)

`deploy/dockerlab/README.md` (tracked since S19 `0acb0e6`):

```
22: ├── .htpasswd
23: ├── ssl/
35: 2. Generate or place TLS certificates in `/opt/bodesign/ssl/` (e.g. SAN IP `192.168.100.141`):
42:    htpasswd -bc /opt/bodesign/.htpasswd <username> <secure_password>
```

`deploy/dockerlab/docker-compose.yml:3`:

```
# Port 8177 allocated via central port_registry for authenticated TLS MCP ingress.
```

`deploy/dockerlab/nginx.conf` — the only ingress actually shipped:

```
12: listen 8177;                  # no `ssl`
19: location /invoke { return 403 ... }
24: proxy_pass http://bodesign:8077;
```

No `ssl_certificate`, `auth_basic`, or `.htpasswd` reference exists in nginx.conf or
docker-compose.yml (grep on 2026-10-09: zero hits outside README/comment).

Deployed reality (officer-verified 2026-10-09, CT105 `192.168.100.141:8177`): plain HTTP,
no auth, `/invoke` 403, `/healthz` and `/mcp` open on LAN. Clients
(`~/.config/opencode/mcp-apps.json`) point at `http://…:8177/mcp/`.

## 2. RCA

The README and compose comment were authored for an intended TLS+basic-auth design;
the nginx.conf that was actually rolled out (S19) is the LAN-plain variant. The
mirror was committed as-is to track what CT105 runs, and the doc was not reconciled.
A reader following README steps 2–3 creates `ssl/` and `.htpasswd` that nothing
consumes — a silent no-op that reads as "secured".

## 3. Proposed remediation

Single ruling needed first (officer → user): **(a)** doc follows reality — rewrite
README/compose comment to state LAN-plain HTTP, no auth, `/invoke` 403, and the
boundary rule (AGENTS.md §3.1 天條 2: external exposure requires an auth-bearing
gateway in front); or **(b)** reality follows doc — add `ssl` + `auth_basic` to
nginx.conf, re-roll CT105, update clients to `https://`.

Default recommendation: (a). CT105 is LAN-only today and (b) is a deployment change,
not a doc fix.

## 4. Acceptance criteria

- `grep -n -i 'tls\|ssl\|htpasswd\|auth_basic\|authenticated' deploy/dockerlab/` returns
  either only negation/boundary statements ("no TLS", "no auth", "unauthenticated …
  blocked") (option a) or hits that are all backed by directives in nginx.conf (option b).
  Measured after fix: README:27 and docker-compose.yml:3 are negations; nginx.conf:18 is
  the pre-existing `/invoke` block comment. No affirmative TLS/auth claim remains.
- README tree listing matches `ls /opt/bodesign/` on CT105.
- Control: a deliberately re-inserted `ssl/` line in README is caught by the same grep.
