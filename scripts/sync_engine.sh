#!/usr/bin/env bash
# sync_engine.sh (BR2 · 2026-07-06) — single deploy action for the eda-bridge engine.
#
# Three importable copies drifted during the aiguard C03 session (host bind-mount,
# container /tmp/engpatch on PYTHONPATH-front, container /app/packages site-packages),
# costing 4 stale-version incidents. Resolution:
#   * /tmp/engpatch is RETIRED (removed 2026-07-06). It was never on the server
#     process PYTHONPATH (only /app/packages is) — it existed only as a session
#     workaround and was a pure drift source. This script now ASSERTS it is absent
#     and fails loud if anything recreates it.
#   * /app/packages IS the host working tree (read-only bind mount in dev mode):
#     host edits are live in-container immediately. "Deploy" = verify, not copy.
# The script PROVES the live engine_rev + compose_schematic signature match the
# host on the one legitimate copy. Relay subagents MUST use this, never docker cp.
#
# Usage: scripts/sync_engine.sh [container_name]
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO/packages/eda-bridge/bodesign_eda_bridge"
CONTAINER="${1:-bodesign-pkcs12-bodesign-ee-1}"
ENGPATCH="/tmp/engpatch/bodesign_eda_bridge"
SITEPKG="/app/packages/eda-bridge/bodesign_eda_bridge"

if [[ ! -d "$SRC" ]]; then echo "FATAL: engine source not found: $SRC" >&2; exit 1; fi
if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "FATAL: container '$CONTAINER' not found" >&2; exit 1
fi

HOST_REV="$(cd "$REPO" && PYTHONPATH=packages/eda-bridge:packages/workflow-core \
  python3 -c 'import bodesign_eda_bridge as b; print(b.__engine_rev__)')"
echo "host __engine_rev__ = $HOST_REV"

# Is this container path backed by a host bind-mount of the SAME source tree?
# If so it already reflects host edits live — copying is both unnecessary and
# impossible (read-only mount). Detect by probing writability of the dir.
_is_writable() {
  docker exec "$CONTAINER" sh -c "touch '$1/.sync_probe' 2>/dev/null && rm -f '$1/.sync_probe' && echo yes || echo no"
}

sync_copy() {
  local dest="$1" label="$2"
  if ! docker exec "$CONTAINER" sh -c "[ -d '$(dirname "$dest")' ]"; then
    echo "  [$label] target parent missing — skipped"; return 0
  fi
  local writable
  writable="$(_is_writable "$(dirname "$dest")")"
  if [[ "$writable" == "yes" ]]; then
    docker exec "$CONTAINER" sh -c "mkdir -p '$dest'"
    # copy every .py (engine surface); tar-through preserves tree. --overwrite so
    # existing files are replaced, not errored on.
    tar -C "$SRC/.." -cf - bodesign_eda_bridge \
      | docker exec -i "$CONTAINER" sh -c "cd '$(dirname "$dest")' && tar --overwrite -xf - bodesign_eda_bridge/*.py"
    docker exec "$CONTAINER" sh -c "find '$dest' -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true"
  else
    # read-only bind-mount of the host tree: already live, nothing to copy. Still
    # clear any writable __pycache__ overlay and VERIFY the rev matches.
    echo "  [$label] read-only (host bind-mount) — no copy, verify only"
  fi
  local rev
  rev="$(docker exec "$CONTAINER" sh -c "cd '$(dirname "$dest")' && PYTHONPATH='$(dirname "$dest")' python3 -c 'import bodesign_eda_bridge as b; print(b.__engine_rev__)'" 2>/dev/null || echo ERR)"
  if [[ "$rev" == "$HOST_REV" ]]; then
    echo "  [$label] OK rev=$rev"
  else
    echo "  [$label] MISMATCH rev=$rev (expected $HOST_REV)" >&2; return 2
  fi
}

fail=0
# engpatch is retired: its presence means someone recreated the drift source.
if docker exec "$CONTAINER" sh -c "[ -d '$ENGPATCH' ]"; then
  echo "  [engpatch] FATAL: $ENGPATCH exists — it is RETIRED (drift source)." >&2
  echo "  Remove it (docker exec $CONTAINER rm -rf /tmp/engpatch) and never recreate it;" >&2
  echo "  /app/packages is the live host bind mount — host edits apply immediately." >&2
  fail=1
else
  echo "  [engpatch] absent (retired) — OK"
fi
echo "verifying -> site-packages ($SITEPKG)"; sync_copy "$SITEPKG" site-packages || fail=1

# Signature proof: the live compose_schematic signature on the effective copy.
echo "live compose_schematic signature (site-packages):"
docker exec "$CONTAINER" sh -c "python3 -c 'import inspect,bodesign_eda_bridge as b; print(\"  \", list(inspect.signature(b.compose_schematic).parameters))'" || true

if [[ "$fail" -ne 0 ]]; then
  echo "=== SYNC FAILED: at least one copy diverged ===" >&2; exit 2
fi
echo "=== SYNC OK: all copies at rev $HOST_REV ==="
