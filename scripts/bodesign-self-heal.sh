#!/usr/bin/env bash
# bodesign self-heal — idempotent health probe + targeted recovery (R7.4).
#
# Complements webctl.sh. Probes the UDS socket the container binds; when
# unhealthy, recreates ONLY bodesign's own per-user compose project. Never
# spawns a competing daemon — recovery always flows through docker compose with
# the exact `-p bodesign-${USER}` project (and the same overlays) webctl.sh uses.
#
#   --check   exit 0 if healthy (socket present), non-zero otherwise. No mutation.
#   --heal    if unhealthy, `docker compose -p bodesign-${USER} up -d` (idempotent).
#   --help    usage.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$HERE")"          # repo root (where docker-compose.yml lives)
RUN_DIR="$ROOT_DIR/.run"
SOCKET="$RUN_DIR/bodesign.sock"
PROJECT="bodesign-${USER:-$(id -un)}"

COMPOSE=(docker compose -p "$PROJECT" -f "$ROOT_DIR/docker-compose.yml")
[ "${BODESIGN_DEV:-}" = "1" ] && COMPOSE+=(-f "$ROOT_DIR/docker-compose.dev.yml")
WORKERS_MARKER="$RUN_DIR/.workers"
case "${BODESIGN_WORKERS:-}" in
    1) USE_WORKERS=1 ;;
    0) USE_WORKERS=0 ;;
    *) [ -f "$WORKERS_MARKER" ] && USE_WORKERS=1 || USE_WORKERS=0 ;;
esac
[ "$USE_WORKERS" = "1" ] && COMPOSE+=(-f "$ROOT_DIR/docker-compose.workers.yml")

usage() {
    cat <<EOF
usage: $0 {--check|--heal|--help}

  --check   Probe health (UDS socket exists). Exit 0 healthy, 1 unhealthy. Read-only.
  --heal    Probe; if unhealthy, recreate only the ${PROJECT} compose project (idempotent).
  --help    Show this message.

Health signal: existence of the bound Unix socket at
  ${SOCKET}
(same readiness check as webctl.sh health). --heal never spawns a competing
daemon; it brings up bodesign's own per-user compose project.
EOF
}

is_healthy() { [ -S "$SOCKET" ]; }

heal() {
    if ! command -v docker >/dev/null 2>&1; then
        printf 'bodesign-self-heal: docker not found in PATH; cannot heal\n' >&2
        return 2
    fi
    [ -d "$RUN_DIR" ] || mkdir -p "$RUN_DIR"
    chmod 755 "$RUN_DIR" 2>/dev/null || true
    # Idempotent: `up -d` is a no-op when already running+healthy; recreates the
    # container when it is gone/stopped. Scoped to bodesign's own project only.
    ( cd "$ROOT_DIR" && "${COMPOSE[@]}" up -d )
    local elapsed=0
    while [ $elapsed -lt 30 ]; do
        is_healthy && return 0
        sleep 2; elapsed=$((elapsed + 2))
    done
    printf 'bodesign-self-heal: socket still absent after heal (%s)\n' "$SOCKET" >&2
    return 1
}

case "${1:---check}" in
    --check)
        if is_healthy; then
            printf 'bodesign-self-heal: healthy (socket %s)\n' "$SOCKET"
            exit 0
        fi
        printf 'bodesign-self-heal: UNHEALTHY (no socket at %s)\n' "$SOCKET" >&2
        exit 1
        ;;
    --heal)
        if is_healthy; then
            printf 'bodesign-self-heal: already healthy; nothing to do\n'
            exit 0
        fi
        printf 'bodesign-self-heal: unhealthy; recreating %s\n' "$PROJECT" >&2
        heal
        ;;
    --help|-h)
        usage
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac
