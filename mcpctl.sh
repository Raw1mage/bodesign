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
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.run"
SOCK="$RUN_DIR/bodesign.sock"
PROJECT="bodesign-${USER:-$(id -un)}"
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
    "${COMPOSE[@]}" down
    rm -f "$SOCK"
    ;;
  restart)
    # Fast: recreate the container (re-runs server.py) WITHOUT rebuilding the image.
    # With BODESIGN_DEV=1 the bind-mounted source means this reloads code edits in seconds.
    ensure_run_dir; persist_mode
    "${COMPOSE[@]}" up -d --force-recreate --remove-orphans
    if [ "${BODESIGN_DEV:-}" = "1" ]; then
      echo "bodesign MCP restarted (dev: live source, no rebuild); socket -> $SOCK"
    else
      echo "bodesign MCP restarted (baked image — use 'rebuild' to pick up code changes); socket -> $SOCK"
    fi
    ;;
  rebuild|reload|refresh)
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
    echo "usage: mcpctl.sh {start|restart|rebuild|stop|status|log}" >&2
    echo "  dev loop:      BODESIGN_DEV=1 ./mcpctl.sh start   then  BODESIGN_DEV=1 ./mcpctl.sh restart" >&2
    echo "  workers mode:  BODESIGN_WORKERS=1 ./mcpctl.sh rebuild   (sticky; BODESIGN_WORKERS=0 reverts to monolith)" >&2
    exit 2
    ;;
esac
