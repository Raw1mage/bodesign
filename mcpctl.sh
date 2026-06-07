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
CONTAINER="${PROJECT}-bodesign-1"

ensure_run_dir() {
  # 0755 so a local gateway/user can reach the socket the container binds.
  mkdir -p "$RUN_DIR"
  chmod 755 "$RUN_DIR"
}

case "${1:-}" in
  start)
    ensure_run_dir
    echo "building image (streamed to $RUN_DIR/build.log)..."
    "${COMPOSE[@]}" build --progress=plain 2>&1 | tee "$RUN_DIR/build.log"
    "${COMPOSE[@]}" up -d
    echo "bodesign MCP starting; socket -> $SOCK"
    ;;
  stop)
    "${COMPOSE[@]}" down
    rm -f "$SOCK"
    ;;
  restart)
    # Fast: recreate the container (re-runs server.py) WITHOUT rebuilding the image.
    # With BODESIGN_DEV=1 the bind-mounted source means this reloads code edits in seconds.
    ensure_run_dir
    "${COMPOSE[@]}" up -d --force-recreate
    if [ "${BODESIGN_DEV:-}" = "1" ]; then
      echo "bodesign MCP restarted (dev: live source, no rebuild); socket -> $SOCK"
    else
      echo "bodesign MCP restarted (baked image — use 'rebuild' to pick up code changes); socket -> $SOCK"
    fi
    ;;
  rebuild|reload|refresh)
    ensure_run_dir
    "${COMPOSE[@]}" build --progress=plain 2>&1 | tee "$RUN_DIR/build.log"
    "${COMPOSE[@]}" up -d --force-recreate
    echo "bodesign MCP rebuilt + reloaded; socket -> $SOCK"
    ;;
  status)
    health="$(docker inspect "$CONTAINER" --format '{{.State.Health.Status}}' 2>/dev/null || echo missing)"
    echo "container: $CONTAINER"
    echo "health:    $health"
    if [ -S "$SOCK" ]; then echo "socket:    $SOCK (present)"; else echo "socket:    $SOCK (absent)"; fi
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
    echo "  dev loop: BODESIGN_DEV=1 ./mcpctl.sh start  then  BODESIGN_DEV=1 ./mcpctl.sh restart" >&2
    exit 2
    ;;
esac
