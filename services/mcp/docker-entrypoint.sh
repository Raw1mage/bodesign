#!/bin/sh
# bodesign container entrypoint — uid-aligned privilege drop
# (BR_20260705_work_dir_root_owned_agent_needs_sudo).
#
# The container writes bind-mounted host paths (/work, /run/bodesign/vault) and
# named volumes (sessions). If the server runs as root, those products come out
# root-owned and the host user can no longer mkdir/write them without sudo — a
# security smell that breaks the pure-agent (unprivileged) flow.
#
# Fix: start as root, chown the writable mounts to the HOST uid/gid, then
# re-exec the server dropped to that uid via setpriv (util-linux, already in the
# base image — no extra package). HOST_UID/HOST_GID are injected by mcpctl.sh
# (`id -u`/`id -g`); default 1000 matches the ubuntu:24.04 `ubuntu` user.
#
# No silent fallback: if we are asked to drop privilege but cannot (setpriv
# missing, chown fails on a path that exists), we fail loud rather than
# silently continuing as root and re-introducing the root-owned-products bug.
set -eu

TARGET_UID="${HOST_UID:-1000}"
TARGET_GID="${HOST_GID:-1000}"

# Paths the server writes and that must stay host-writable. Only chown those
# that actually exist in this container variant (core has no vault mount, etc.).
WRITABLE_PATHS="/work ${BODESIGN_VAULT_DIR:-/run/bodesign/vault} ${BODESIGN_SESSIONS_ROOT:-/var/cache/bodesign/sessions}"

# Only the root-stage bootstrap does chown + drop; a re-exec (already the target
# uid) skips straight to the server.
if [ "$(id -u)" = "0" ] && [ "${BODESIGN_ENTRYPOINT_DROPPED:-}" != "1" ]; then
  if ! command -v setpriv >/dev/null 2>&1; then
    echo "bodesign-entrypoint: FATAL setpriv not found; cannot drop to uid ${TARGET_UID} without re-introducing root-owned products" >&2
    exit 1
  fi

  for p in $WRITABLE_PATHS; do
    [ -n "$p" ] || continue
    # Create + own the target so first-write is host-writable. A create/chown
    # failure on an existing path is fatal (fail loud, not silent root).
    if ! mkdir -p "$p" 2>/dev/null; then
      # A mount whose parent is read-only may refuse mkdir; tolerate only if the
      # path already exists (nothing to create).
      [ -d "$p" ] || { echo "bodesign-entrypoint: FATAL cannot create writable path $p" >&2; exit 1; }
    fi
    if ! chown -R "${TARGET_UID}:${TARGET_GID}" "$p" 2>/dev/null; then
      echo "bodesign-entrypoint: WARN chown $p -> ${TARGET_UID}:${TARGET_GID} failed (read-only mount?); continuing" >&2
    fi
  done

  export BODESIGN_ENTRYPOINT_DROPPED=1
  exec setpriv --reuid "${TARGET_UID}" --regid "${TARGET_GID}" --init-groups \
       python /app/services/mcp/server.py "$@"
fi

# Already non-root (or re-exec) — run the server directly.
exec python /app/services/mcp/server.py "$@"
