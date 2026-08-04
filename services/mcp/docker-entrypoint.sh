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

  # HOME must be re-pointed BEFORE the drop
  # (BR_20260804_c02_export_stl_cannot_see_files_staged_into_its_own_token.md,
  # root cause 2).
  #
  # `setpriv` changes the credentials and NOTHING else: it does not consult
  # /etc/passwd and does not reset HOME, so the dropped process inherits the
  # root stage's HOME=/root while running as uid ${TARGET_UID}. /root is
  # drwx------ root, so any tool that unconditionally stats $HOME dies.
  # Measured 2026-08-04 on the me worker: openscad ABORTS (core dumped) on
  # `boost::filesystem::status: Permission denied "/root/.config/OpenSCAD"`
  # rather than degrading, surfacing to the caller as c02_export_stl
  # status=export_failed with an error naming a path nobody passed in.
  #
  # Measured, and the reason this is not obvious: `docker exec -u 1000 … env`
  # reports HOME=/home/ubuntu, because DOCKER sets HOME from passwd for an exec.
  # That is not this process's environment. The probe that reflects reality is
  #   setpriv --reuid <uid> --regid <gid> --init-groups env | grep ^HOME=
  # which returns HOME=/root. A decoy probe and an honest one disagree here.
  #
  # Resolve it from passwd so it tracks TARGET_UID instead of hardcoding a home
  # that is only correct while TARGET_UID happens to be 1000 (TARGET_UID is
  # settable via HOST_UID).
  #
  # ONE resolution, ONE policy for each outcome — an earlier revision of this
  # block resolved TARGET_HOME twice with CONTRADICTORY handling of the same
  # case (first "missing dir => FATAL", then "missing dir => mkdir"), and since
  # the first ran first the second was unreachable. Both halves were valid shell,
  # so `sh -n` was silent and every probe passed: they only disagree when the
  # passwd home does not exist, which is exactly the branch no probe covered.
  # See issues/BR_20260804j_*.md.
  #
  #   getent has no entry for the uid  -> FATAL. Nothing to guess from; a
  #     writable default would make "resolved the real home" and "could not
  #     resolve anything" produce the same startup, which is the defect class
  #     this whole change is about.
  #   passwd home does not exist yet   -> CREATE it. `getent` answering while the
  #     directory is not yet materialised is a normal first-boot state for a
  #     container, not an anomaly; the same mkdir+chown shape is already used for
  #     WRITABLE_PATHS above. A create failure IS fatal.
  TARGET_HOME="$(getent passwd "${TARGET_UID}" 2>/dev/null | cut -d: -f6)"
  if [ -z "${TARGET_HOME}" ]; then
    echo "bodesign-entrypoint: FATAL no passwd entry for uid ${TARGET_UID}; cannot resolve HOME. Refusing to guess — a wrong HOME makes toolchains (openscad, matplotlib, fontconfig) abort with permission errors that name a path nobody configured." >&2
    exit 1
  fi
  if ! mkdir -p "${TARGET_HOME}" 2>/dev/null; then
    [ -d "${TARGET_HOME}" ] || { echo "bodesign-entrypoint: FATAL cannot create HOME ${TARGET_HOME} for uid ${TARGET_UID}" >&2; exit 1; }
  fi
  chown "${TARGET_UID}:${TARGET_GID}" "${TARGET_HOME}" 2>/dev/null || true
  export HOME="${TARGET_HOME}"

  export BODESIGN_ENTRYPOINT_DROPPED=1
  exec setpriv --reuid "${TARGET_UID}" --regid "${TARGET_GID}" --init-groups \
       env HOME="${TARGET_HOME}" python /app/services/mcp/server.py "$@"
fi

# Already non-root (or re-exec) — run the server directly.
exec python /app/services/mcp/server.py "$@"
