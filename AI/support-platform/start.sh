#!/usr/bin/env bash
#
# Start the AI Support Platform.
#
#   ./start.sh              run on the default port
#   ./start.sh --port 9000  run on another port
#
# Does the things that are easy to forget: checks the model backend is up,
# verifies dependencies, frees the port if something is already bound to it,
# and prints the URL.

set -euo pipefail

cd "$(dirname "$0")"

PORT=8000
HOST=127.0.0.1
MODEL_URL="${SP_API_BASE:-http://localhost:18790/v1}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --host) HOST="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done

bold() { printf "\033[1m%s\033[0m\n" "$1"; }
warn() { printf "\033[33m  ! %s\033[0m\n" "$1"; }
ok()   { printf "\033[32m  ✓ %s\033[0m\n" "$1"; }

bold "AI Support Platform"

# --- dependencies ---------------------------------------------------
if ! python3 -c "import openai, pydantic_settings" 2>/dev/null; then
  warn "missing dependencies — installing from requirements.txt"
  python3 -m pip install --quiet -r requirements.txt
fi
ok "dependencies"

# --- model backend ---------------------------------------------------
# Not fatal: tickets still get created, but each one falls back to a
# "route to human" record with a connection error attached.
if curl -s -m 3 "${MODEL_URL}/models" >/dev/null 2>&1; then
  MODEL=$(curl -s -m 3 "${MODEL_URL}/models" \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['data'][0]['id'])" 2>/dev/null \
    || echo "unknown")
  ok "model backend: $MODEL"
else
  warn "model backend unreachable at ${MODEL_URL}"
  warn "  tickets will be accepted but every analysis will fall back to a human"
fi

# --- port ------------------------------------------------------------
if lsof -ti:"$PORT" >/dev/null 2>&1; then
  warn "port $PORT is in use — stopping the old process"
  lsof -ti:"$PORT" | xargs kill 2>/dev/null || true
  sleep 1
fi

echo
bold "  Dashboard  http://${HOST}:${PORT}"
echo "  Ctrl-C to stop"
echo

exec python3 -m support_platform.cli serve --host "$HOST" --port "$PORT"
