#!/usr/bin/env bash
# mcpctl.sh — control the bodesign MCP server container (G10b).
#   start | restart | rebuild | stop | status | log
# docker-compose-backed, per-user (project bodesign-${USER}).
#
# Dev loop (no image rebuild for code changes): set BODESIGN_DEV=1 to bind-mount the
# source (docker-compose.dev.yml); then `restart` reloads code in seconds.
#   BODESIGN_DEV=1 ./mcpctl.sh start      # build once + up with source mounted
#   BODESIGN_DEV=1 ./mcpctl.sh restart    # after a code edit — seconds, no rebuild
#   ./mcpctl.sh rebuild                    # only when deps (requirements/Dockerfile) change
#
# restart/rebuild/stop refuse to run while a worker is busy (see busy_report):
# they would kill a multi-hour route in flight and still report success.
#   ./mcpctl.sh busy                       # exit 3 if a restart would destroy work
#   BODESIGN_FORCE=1 ./mcpctl.sh restart   # override, with a loud warning
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.run"
SOCK="$RUN_DIR/bodesign.sock"
PROJECT="bodesign-${USER:-$(id -un)}"

# Inject the host uid/gid so the container entrypoint (docker-entrypoint.sh) drops
# privilege to the invoking user — bind-mounted products under .work/ and
# .run/vault stay host-writable, no sudo needed (BR_20260705_work_dir_root_owned).
export HOST_UID="$(id -u)"
export HOST_GID="$(id -g)"
COMPOSE=(docker compose -p "$PROJECT" -f "$ROOT_DIR/docker-compose.yml")
# BODESIGN_DEV=1 → bind-mount the live source so restart picks up code with no rebuild.
if [ "${BODESIGN_DEV:-}" = "1" ]; then
  COMPOSE+=(-f "$ROOT_DIR/docker-compose.dev.yml")
fi

# BODESIGN_WORKERS → responsibility-split deploy (lean core + me/ee workers; heavy
# CAD/EDA deps isolated per Dockerfile.core/.ee/.me). STICKY: once started in workers
# mode a marker in .run keeps every later restart/rebuild in workers mode, so an
# `mcpctl rebuild` never silently reverts to the monolith and orphans the workers
# (the regression this guards against). `BODESIGN_WORKERS=0` forces back to monolith
# and clears the marker; unset honours the marker.
WORKERS_MARKER="$RUN_DIR/.workers"
case "${BODESIGN_WORKERS:-}" in
  0) rm -f "$WORKERS_MARKER"; USE_WORKERS=0 ;;
  1) USE_WORKERS=1 ;;
  *) [ -f "$WORKERS_MARKER" ] && USE_WORKERS=1 || USE_WORKERS=0 ;;
esac
if [ "$USE_WORKERS" = "1" ]; then
  COMPOSE+=(-f "$ROOT_DIR/docker-compose.workers.yml")
fi
CONTAINER="${PROJECT}-bodesign-1"

# Persist workers mode so it survives later restart/rebuild (call after ensure_run_dir).
persist_mode() { [ "$USE_WORKERS" = "1" ] && touch "$WORKERS_MARKER" || true; }

# ---------------------------------------------------------------------------
# Busy gate (BR_20260729 §L).
#
# restart/rebuild/stop recreate the containers, which kills everything running
# inside them. A freerouting run on a real BGA board takes 30-165 minutes; a
# restart during one destroys it and then prints "bodesign MCP restarted" —
# reporting the outcome the command INTENDED, not the outcome it produced.
# That is exactly the silent-degradation shape this repo lints for in its
# Python (ragbase/control/no-silent-degradation), one layer down in ops.
#
# Two people sharing one ee worker cannot fix this with an agreement to "check
# first", because the check depends on someone remembering. So: detect, refuse,
# and name what would have been destroyed. BODESIGN_FORCE=1 overrides, loudly.
BUSY_MIN_SECS="${BODESIGN_BUSY_MIN_SECS:-30}"

# Print one TSV finding per non-idle container; empty output == idle.
# A container that is absent or stopped is genuinely idle. A container we
# CANNOT PROBE is NOT idle — an errored probe is reported as UNKNOWN and
# blocks, because "I could not look" must never be read as "nothing there".
#
# ZOMBIES ARE NOT WORK (BR_20260730b §M). A defunct process (ps STAT starting
# with 'Z') has already exited; it holds no CPU, no memory and no file handles,
# and survives only as an exit-status row until its parent reaps it. xvfb-run
# leaks one per freerouting run, so an ee worker accumulates them and — because
# a zombie's etimes keeps climbing — the original gate read three 12-hour-old
# corpses as "live work" and refused every restart INDEFINITELY, with no run to
# protect. That inverts the gate's own contract: it exists to stop a restart
# from destroying work in flight, and a restart cannot destroy a process that
# has already died. Left unfixed the only way out is BODESIGN_FORCE=1, which
# trains the operator to bypass the very guard that is supposed to protect
# them — so the gate's failure mode was teaching people to disarm it.
#
# This is deliberately NOT a relaxation of the fail-safe posture: UNKNOWN still
# blocks, and any live process still blocks. The asymmetry that justifies the
# UNKNOWN default (mis-blocking costs a wait, mis-allowing costs 165 minutes of
# routing) does not apply to a zombie, because there is no computation left to
# lose. Zombies are still REPORTED (as ZOMBIE rows by `busy`) so a leak stays
# visible instead of being silently filtered — the count is the signal that
# xvfb-run is not reaping, which is a real defect worth seeing.
busy_report() {
  local c state out
  for c in "$CONTAINER" "${PROJECT}-bodesign-me-1" "${PROJECT}-bodesign-ee-1"; do
    state="$(docker inspect "$c" --format '{{.State.Running}}' 2>/dev/null)" || continue
    [ "$state" = "true" ] || continue
    if ! out="$(docker exec "$c" ps -eo pid,stat,etimes,args --no-headers 2>&1)"; then
      printf '%s\tUNKNOWN\t-\t-\tprobe failed: %s\n' \
        "$c" "$(printf '%s' "$out" | head -1)"
      continue
    fi
    printf '%s\n' "$out" | awk -v c="$c" -v min="$BUSY_MIN_SECS" '
      { pid=$1; st=$2; et=$3; $1=""; $2=""; $3=""; sub(/^[ \t]+/,""); cmd=$0 }
      pid == 1        { next }   # the MCP server itself is not "work in flight"
      cmd ~ /ps -eo/  { next }   # this very probe
      st ~ /^Z/       { printf "%s\tZOMBIE\t%s\t%ss\t%s\n", c, pid, et, cmd; next }
      et+0 < min+0    { next }
      { printf "%s\tBUSY\t%s\t%ss\t%s\n", c, pid, et, cmd }
    '
  done
}

# The blocking subset of busy_report: ZOMBIE rows are informational only.
# guard_busy consults THIS, so a container holding nothing but corpses is idle.
blocking_report() {
  busy_report | awk -F'\t' '$2 != "ZOMBIE"'
}

# Refuse a destructive lifecycle action while work is in flight.
guard_busy() {
  local action="$1" report
  report="$(blocking_report)" || true
  [ -n "$report" ] || return 0
  if [ "${BODESIGN_FORCE:-}" = "1" ]; then
    {
      echo "WARNING: BODESIGN_FORCE=1 — proceeding with '$action' over live work:"
      printf '%s\n' "$report"
      echo "WARNING: the above will be killed."
    } >&2
    return 0
  fi
  {
    echo "REFUSING to $action: the bodesign workers are not idle."
    echo
    printf '%s\n' "$report"
    echo
    echo "BUSY    = a LIVE process older than ${BUSY_MIN_SECS}s that '$action' would kill."
    echo "UNKNOWN = the container could not be probed; treated as busy on purpose,"
    echo "          because a failed look is not evidence of an empty container."
    echo "ZOMBIE  = already dead (reaped-pending); NEVER blocks — a restart cannot"
    echo "          destroy a process that has already exited. Shown by 'busy' only."
    echo
    echo "Wait for it, or override with:  BODESIGN_FORCE=1 $0 $action"
  } >&2
  exit 3
}

ensure_run_dir() {
  # 0755 so a local gateway/user can reach the socket the container binds.
  mkdir -p "$RUN_DIR"
  chmod 755 "$RUN_DIR"
}

case "${1:-}" in
  start)
    ensure_run_dir; persist_mode
    echo "building image(s) [mode: $([ "$USE_WORKERS" = 1 ] && echo workers || echo monolith)] (streamed to $RUN_DIR/build.log)..."
    "${COMPOSE[@]}" build --progress=plain 2>&1 | tee "$RUN_DIR/build.log"
    "${COMPOSE[@]}" up -d --remove-orphans
    echo "bodesign MCP starting; socket -> $SOCK"
    ;;
  stop)
    guard_busy stop
    "${COMPOSE[@]}" down
    rm -f "$SOCK"
    ;;
  busy)
    # Ask whether a restart/rebuild/stop would destroy work in flight, WITHOUT
    # doing it. Exit 0 = idle, 3 = busy or unprobeable. Safe to call from a
    # peer session that shares these workers.
    report="$(busy_report)" || true
    blocking="$(blocking_report)" || true
    if [ -n "$report" ]; then
      printf '%s\n' "$report"
    fi
    if [ -z "$blocking" ]; then
      if [ -n "$report" ]; then
        echo "idle: the rows above are ZOMBIE (already dead) — they do NOT block a" >&2
        echo "      restart/rebuild/stop. A non-zero count means xvfb-run is leaking" >&2
        echo "      children without reaping them; worth fixing, but no work is at risk." >&2
      else
        echo "idle: no live process older than ${BUSY_MIN_SECS}s in the bodesign containers"
      fi
    else
      exit 3
    fi
    ;;
  restart)
    # Fast: recreate the container (re-runs server.py) WITHOUT rebuilding the image.
    # With BODESIGN_DEV=1 the bind-mounted source means this reloads code edits in seconds.
    guard_busy restart
    ensure_run_dir; persist_mode
    "${COMPOSE[@]}" up -d --force-recreate --remove-orphans
    if [ "${BODESIGN_DEV:-}" = "1" ]; then
      echo "bodesign MCP restarted (dev: live source, no rebuild); socket -> $SOCK"
    else
      echo "bodesign MCP restarted (baked image — use 'rebuild' to pick up code changes); socket -> $SOCK"
    fi
    ;;
  rebuild|reload|refresh)
    guard_busy rebuild
    ensure_run_dir; persist_mode
    echo "rebuilding [mode: $([ "$USE_WORKERS" = 1 ] && echo workers || echo monolith)]..."
    "${COMPOSE[@]}" build --progress=plain 2>&1 | tee "$RUN_DIR/build.log"
    "${COMPOSE[@]}" up -d --force-recreate --remove-orphans
    echo "bodesign MCP rebuilt + reloaded; socket -> $SOCK"
    ;;
  status)
    health="$(docker inspect "$CONTAINER" --format '{{.State.Health.Status}}' 2>/dev/null || echo missing)"
    echo "container: $CONTAINER"
    echo "mode:      $([ "$USE_WORKERS" = 1 ] && echo 'workers (core + me/ee; heavy-dep isolation)' || echo 'monolith (all tools in-process)')"
    echo "health:    $health"
    if [ -S "$SOCK" ]; then echo "socket:    $SOCK (present)"; else echo "socket:    $SOCK (absent)"; fi
    if [ "$USE_WORKERS" = "1" ]; then
      for w in bodesign-me bodesign-ee; do
        wh="$(docker inspect "${PROJECT}-${w}-1" --format '{{.State.Health.Status}}' 2>/dev/null || echo absent)"
        echo "  $w: $wh"
      done
    fi
    if [ "$health" = "healthy" ]; then
      curl -s --unix-socket "$SOCK" http://bodesign.local/healthz 2>/dev/null && echo || true
    fi
    ;;
  log|logs)
    shift || true
    "${COMPOSE[@]}" logs --tail "${1:-100}" -f bodesign
    ;;
  *)
    echo "usage: mcpctl.sh {start|restart|rebuild|stop|status|busy|log}" >&2
    echo "  dev loop:      BODESIGN_DEV=1 ./mcpctl.sh start   then  BODESIGN_DEV=1 ./mcpctl.sh restart" >&2
    echo "  workers mode:  BODESIGN_WORKERS=1 ./mcpctl.sh rebuild   (sticky; BODESIGN_WORKERS=0 reverts to monolith)" >&2
    echo "  busy check:    ./mcpctl.sh busy        (exit 3 if a restart would kill work in flight)" >&2
    echo "  override:      BODESIGN_FORCE=1 ./mcpctl.sh restart   (kills it anyway, loudly)" >&2
    exit 2
    ;;
esac
