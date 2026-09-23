#!/usr/bin/env bash
#
# Start the Enterprise Knowledge Assistant.
#
#   ./start.sh              run on the default port
#   ./start.sh --port 9000  run on another port
#   ./start.sh --dev        auto-reload on file changes
#
# Checks the model backend, reports which embedding backend will be used, and
# frees the port if something is already bound to it.

set -euo pipefail
cd "$(dirname "$0")"

PORT=8950
HOST=127.0.0.1
RELOAD=""
MODEL_URL="${KA_API_BASE:-http://localhost:18790/v1}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --host) HOST="$2"; shift 2 ;;
    --dev)  RELOAD="--reload"; shift ;;
    -h|--help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done

bold() { printf "\033[1m%s\033[0m\n" "$1"; }
warn() { printf "\033[33m  ! %s\033[0m\n" "$1"; }
ok()   { printf "\033[32m  ✓ %s\033[0m\n" "$1"; }

bold "Enterprise Knowledge Assistant"

# --- dependencies ---------------------------------------------------
if ! python3 -c "import fastapi, uvicorn, openai, pydantic_settings, numpy" 2>/dev/null; then
  warn "missing dependencies — installing from requirements.txt"
  python3 -m pip install --quiet -r requirements.txt
fi
ok "dependencies"

# --- embeddings ------------------------------------------------------
# Reported at startup because it materially changes retrieval quality: the
# hashing fallback matches wording, not meaning.
EMBED=$(python3 -c "
from knowledge.embeddings import get_embedder
e = get_embedder()
print(f'{e.name}|{e.dims}|{e.semantic}')
" 2>/dev/null || echo "unknown|0|False")
NAME="${EMBED%%|*}"
SEMANTIC="${EMBED##*|}"
if [[ "$SEMANTIC" == "True" ]]; then
  ok "embeddings: $NAME (semantic)"
else
  warn "embeddings: $NAME (lexical only — synonyms will not match)"
  warn "  for semantic search: pip install sentence-transformers"
fi

# --- model backend ---------------------------------------------------
if curl -s -m 3 "${MODEL_URL}/models" >/dev/null 2>&1; then
  MODEL=$(curl -s -m 3 "${MODEL_URL}/models" \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['data'][0]['id'])" 2>/dev/null \
    || echo "unknown")
  ok "model backend: $MODEL"
else
  warn "model backend unreachable at ${MODEL_URL}"
  warn "  retrieval will still work; answers will not be generated"
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

exec python3 -m uvicorn knowledge.api:app --host "$HOST" --port "$PORT" $RELOAD
