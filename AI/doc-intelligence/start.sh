#!/usr/bin/env bash
#
# Start the Document Intelligence API.
#
#   ./start.sh              run on the default port
#   ./start.sh --port 9000  run on another port
#   ./start.sh --dev        auto-reload on file changes
#
# Does the things that are easy to forget: checks the model backend is up,
# verifies dependencies, frees the port if something is already bound to it,
# and prints the URLs.

set -euo pipefail

cd "$(dirname "$0")"

PORT=8900
HOST=127.0.0.1
RELOAD=""
MODEL_URL="${DI_API_BASE:-http://localhost:18790/v1}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --host) HOST="$2"; shift 2 ;;
    --dev)  RELOAD="--reload"; shift ;;
    -h|--help)
      sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done

bold() { printf "\033[1m%s\033[0m\n" "$1"; }
warn() { printf "\033[33m  ! %s\033[0m\n" "$1"; }
ok()   { printf "\033[32m  ✓ %s\033[0m\n" "$1"; }

bold "Document Intelligence"

# --- dependencies ---------------------------------------------------
if ! python3 -c "import fastapi, uvicorn, openai, pydantic_settings" 2>/dev/null; then
  warn "missing dependencies — installing from requirements.txt"
  python3 -m pip install --quiet -r requirements.txt
fi
ok "dependencies"

# --- OCR (optional) --------------------------------------------------
if command -v tesseract >/dev/null 2>&1; then
  LANGS=$(tesseract --list-langs 2>/dev/null | tail -n +2 | tr '\n' ' ')
  if [[ "$LANGS" == *"ara"* ]]; then
    ok "OCR ready (eng + ara)"
  else
    warn "OCR has English only — Arabic scans will be rejected."
    warn "  fix: brew install tesseract-lang"
  fi
else
  warn "tesseract not installed — images and scanned PDFs will be rejected"
  warn "  fix: brew install tesseract tesseract-lang"
fi

# --- model backend ---------------------------------------------------
# Not fatal: the API still starts, but every extraction would fail. Better to
# say so now than to have uploads mysteriously error later.
if curl -s -m 3 "${MODEL_URL}/models" >/dev/null 2>&1; then
  MODEL=$(curl -s -m 3 "${MODEL_URL}/models" \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['data'][0]['id'])" 2>/dev/null \
    || echo "unknown")
  ok "model backend: $MODEL"
else
  warn "model backend unreachable at ${MODEL_URL}"
  warn "  the UI will load, but every extraction will fail"
fi

# --- port ------------------------------------------------------------
if lsof -ti:"$PORT" >/dev/null 2>&1; then
  warn "port $PORT is in use — stopping the old process"
  lsof -ti:"$PORT" | xargs kill 2>/dev/null || true
  sleep 1
fi

echo
bold "  UI    http://${HOST}:${PORT}"
bold "  Docs  http://${HOST}:${PORT}/docs"
echo "  Ctrl-C to stop"
echo

exec python3 -m uvicorn doc_intel.api:app --host "$HOST" --port "$PORT" $RELOAD
