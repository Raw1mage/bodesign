#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$ROOT_DIR/.run"
LOG_DIR="$ROOT_DIR/.logs"
PID_FILE="$RUN_DIR/bodesign-api.pid"
HOST="${BODESIGN_HOST:-127.0.0.1}"
PORT="${BODESIGN_PORT:-8765}"
PYTHON="${BODESIGN_PYTHON:-$ROOT_DIR/.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
  PYTHON="python3"
fi

ensure_dirs() {
  mkdir -p "$RUN_DIR" "$LOG_DIR"
}

is_running() {
  if [ ! -f "$PID_FILE" ]; then
    return 1
  fi
  local pid
  pid="$(cat "$PID_FILE")"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

port_alive() {
  "$PYTHON" - "$HOST" "$PORT" <<'PY'
import socket
import sys
host = sys.argv[1]
port = int(sys.argv[2])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(0.5)
    raise SystemExit(0 if sock.connect_ex((host, port)) == 0 else 1)
PY
}

port_pid() {
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti TCP:"$PORT" -sTCP:LISTEN | head -n 1
  elif command -v fuser >/dev/null 2>&1; then
    fuser -n tcp "$PORT" 2>/dev/null | tr ' ' '\n' | head -n 1
  fi
}

start() {
  ensure_dirs
  if is_running; then
    echo "bodesign already running on $HOST:$PORT"
    return 0
  fi
  if port_alive; then
    echo "bodesign already reachable on $HOST:$PORT"
    return 0
  fi
  command -v "$PYTHON" >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 1; }
  "$PYTHON" - <<'PY'
import importlib.util
import sys
if importlib.util.find_spec("uvicorn") is None:
    print("uvicorn is required; run: python3 -m venv .venv && .venv/bin/python -m pip install -r services/api/requirements.txt", file=sys.stderr)
    raise SystemExit(1)
PY
  BODESIGN_HOST="$HOST" BODESIGN_PORT="$PORT" nohup "$PYTHON" -m services.api >"$LOG_DIR/bodesign-api.log" 2>&1 &
  echo "$!" > "$PID_FILE"
  echo "bodesign started on $HOST:$PORT"
}

stop() {
  if ! is_running; then
    rm -f "$PID_FILE"
    if port_alive; then
      local existing_pid
      existing_pid="$(port_pid || true)"
      if [ -n "$existing_pid" ]; then
        kill "$existing_pid"
        echo "bodesign stopped on $HOST:$PORT pid=$existing_pid"
        return 0
      fi
      echo "bodesign is reachable on $HOST:$PORT but no pid/port owner was found; leaving it running"
      return 0
    fi
    echo "bodesign is not running"
    return 0
  fi
  local pid
  pid="$(cat "$PID_FILE")"
  kill "$pid"
  rm -f "$PID_FILE"
  echo "bodesign stopped"
}

status() {
  if is_running; then
    echo "running $HOST:$PORT pid=$(cat "$PID_FILE")"
  elif port_alive; then
    echo "running $HOST:$PORT pid=unknown"
  else
    echo "stopped"
    return 1
  fi
}

case "${1:-status}" in
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) status ;;
  *) echo "Usage: $0 {start|stop|restart|status}" >&2; exit 2 ;;
esac
