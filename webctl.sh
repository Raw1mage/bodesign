#!/usr/bin/env bash
# webctl.sh — MCP-Integration-Standard (R7) lifecycle surface for bodesign.
#
# The standard verb set every conformant service exposes (mirrors
# docxmcp/patentmcp/drawmiat webctl.sh):
#   start | stop | restart | refresh | health | clean | purge
#
# This is the canonical front door the opencode gateway (/toggle, /health) and
# scripts/bodesign-self-heal.sh drive. It composes the SAME per-user compose
# project as mcpctl.sh (`-p bodesign-${USER}`) and honours the same overlays, so
# the two never fight:
#   BODESIGN_DEV=1       → bind-mount live source (docker-compose.dev.yml)
#   BODESIGN_WORKERS=1   → lean core + me/ee workers (docker-compose.workers.yml)
#                          (sticky via .run/.workers, same marker mcpctl.sh uses)
#
# For the richer dev loop (rebuild/log/status, sticky workers marker management)
# use mcpctl.sh; webctl.sh is the standardized lifecycle contract.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.run"
SOCKET="$RUN_DIR/bodesign.sock"
PROJECT="bodesign-${USER:-$(id -un)}"
CONTAINER="${PROJECT}-bodesign-1"

COMPOSE=(docker compose -p "$PROJECT" -f "$ROOT_DIR/docker-compose.yml")
[ "${BODESIGN_DEV:-}" = "1" ] && COMPOSE+=(-f "$ROOT_DIR/docker-compose.dev.yml")
# Honour the sticky workers marker mcpctl.sh writes, plus an explicit override.
WORKERS_MARKER="$RUN_DIR/.workers"
case "${BODESIGN_WORKERS:-}" in
    1) USE_WORKERS=1 ;;
    0) USE_WORKERS=0 ;;
    *) [ -f "$WORKERS_MARKER" ] && USE_WORKERS=1 || USE_WORKERS=0 ;;
esac
[ "$USE_WORKERS" = "1" ] && COMPOSE+=(-f "$ROOT_DIR/docker-compose.workers.yml")

# R7.1 — socket parent dir 0755 so any local user / the rootful-docker gateway
# can reach the socket (R7.3; the socket file itself is relaxed to 0666 by the
# server once uvicorn binds it).
ensure_socket_dir() {
    [ -d "$RUN_DIR" ] || mkdir -p "$RUN_DIR"
    chmod 755 "$RUN_DIR" 2>/dev/null || true
}

# R7.2 — wait until the container reports healthy (healthcheck = socket exists).
wait_healthy() {
    local timeout=90 elapsed=0 status
    while [ $elapsed -lt $timeout ]; do
        status="$(docker inspect "$CONTAINER" --format '{{.State.Health.Status}}' 2>/dev/null || echo missing)"
        [ "$status" = "healthy" ] && return 0
        [ -S "$SOCKET" ] && return 0  # workers/overlay container name may differ; socket is truth
        sleep 2; elapsed=$((elapsed + 2))
    done
    printf 'webctl: timeout waiting for bodesign (%s) to become healthy\n' "$CONTAINER" >&2
    return 1
}

case "${1:-}" in
    start)
        ensure_socket_dir
        "${COMPOSE[@]}" up -d
        wait_healthy
        ;;
    stop)
        "${COMPOSE[@]}" stop
        ;;
    restart|refresh)
        ensure_socket_dir
        "${COMPOSE[@]}" up -d --build --force-recreate --remove-orphans
        wait_healthy
        ;;
    health)
        [ -S "$SOCKET" ]
        ;;
    clean)
        "${COMPOSE[@]}" down --remove-orphans
        ;;
    purge)
        # DESTRUCTIVE — drops the token store + Component Vault named volumes.
        "${COMPOSE[@]}" down --remove-orphans -v
        ;;
    *)
        echo "usage: $0 {start|stop|restart|refresh|health|clean|purge}" >&2
        exit 2
        ;;
esac
