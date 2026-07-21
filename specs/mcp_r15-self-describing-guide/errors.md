# Errors: mcp_r15-self-describing-guide

## Error Catalogue

| Code | Condition | Surface | Recovery |
| ---- | --------- | ------- | -------- |
| `DOCTRINE_SOURCE_MISSING` | `skills/bodesign/doctrine.md` absent inside container at startup | Startup exception; container refuses to boot (fail-fast, tiantiao 11) | Restore doctrine.md (Dockerfile COPY / dev bind-mount), rebuild/restart via `mcpctl.sh` |
| `DOCTRINE_SOURCE_EMPTY` | doctrine.md present but empty/whitespace-only | Startup exception; container refuses to boot | Populate doctrine.md with R15.2 four-class content, restart |
| `unknown tool` | `tools/call` with a name other than a registered tool | Standard MCP tool-not-found error from `run_tool` dispatch | Call `bodesign_init` (or `tools/list` to enumerate) |
| `unknown prompt` | `prompts/get` with a name other than `bodesign_init` | Standard MCP prompt-not-found from `get_prompt` handler | Call `prompts/list` then `prompts/get bodesign_init` |

Design note: there is **no silent-fallback path** — a missing/empty doctrine source
never degrades to an empty-doctrine guide (that would be byte-identical to no
contract). The only recovery is restoring the source and restarting.
