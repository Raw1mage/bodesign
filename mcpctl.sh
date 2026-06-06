#!/usr/bin/env bash
# mcpctl.sh — control the bodesign MCP server container (G10b).
#   start | stop | reload | status | log
# docker-compose-backed, per-user (project bodesign-${USER}).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.run"
SOCK="$RUN_DIR/bodesign.sock"
PROJECT="bodesign-${USER:-$(id -un)}"
COMPOSE=(docker compose -p "$PROJECT" -f "$ROOT_DIR/docker-compose.yml")
CONTAINER="${PROJECT}-bodesign-1"

ensure_run_dir() {
  # 0755 so a local gateway/user can reach the socket the container binds.
  mkdir -p "$RUN_DIR"
  chmod 755 "$RUN_DIR"
}

case "${1:-}" in
  start)
    ensure_run_dir
    "${COMPOSE[@]}" up -d --build
    echo "bodesign MCP starting; socket -> $SOCK"
    ;;
  stop)
    "${COMPOSE[@]}" down
    rm -f "$SOCK"
    ;;
  reload|restart|refresh)
    ensure_run_dir
    "${COMPOSE[@]}" up -d --build --force-recreate
    echo "bodesign MCP reloaded; socket -> $SOCK"
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
    echo "usage: mcpctl.sh {start|stop|reload|status|log}" >&2
    exit 2
    ;;
esac
