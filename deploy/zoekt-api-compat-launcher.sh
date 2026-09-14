#!/usr/bin/env bash
set -euo pipefail

# Compatibility entrypoint for hosts whose root-owned systemd unit still starts
# /home/zack/lean-corpus/bin/zoekt-webserver on port 6070. The durable target
# deployment uses separate systemd units, but this launcher preserves that old
# unit while moving stock Zoekt privately to 6071 and putting FastAPI on 6070.
root="${FORMALIZATION_CORPUS_REMOTE_ROOT:-/home/zack/lean-corpus}"
stock="$root/bin/zoekt-webserver.stock"
uvicorn="$root/api/.venv/bin/uvicorn"

stock_pid=""
metadata_pid=""
api_pid=""

cleanup() {
  trap - EXIT INT TERM
	[[ -n "$api_pid" ]] && kill "$api_pid" 2>/dev/null || true
	[[ -n "$metadata_pid" ]] && kill "$metadata_pid" 2>/dev/null || true
	[[ -n "$stock_pid" ]] && kill "$stock_pid" 2>/dev/null || true
	[[ -n "$api_pid" ]] && wait "$api_pid" 2>/dev/null || true
	[[ -n "$metadata_pid" ]] && wait "$metadata_pid" 2>/dev/null || true
	[[ -n "$stock_pid" ]] && wait "$stock_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

"$stock" \
  -index "$root/index" \
  -listen 127.0.0.1:6071 \
  -html=false \
  -rpc &
stock_pid=$!

"$stock" \
  -index "$root/metadata-index" \
  -listen 127.0.0.1:6072 \
  -html=false \
  -rpc &
metadata_pid=$!

ZOEKT_BACKEND_URL=http://127.0.0.1:6071 \
ZOEKT_DOCUMENTATION_BACKEND_URL=http://127.0.0.1:6072 \
DUPLICATE_ALIASES_PATH="$root/api/data/duplicate-aliases.json" \
PYTHONDONTWRITEBYTECODE=1 \
"$uvicorn" formalization_api.app:app \
  --app-dir "$root/api" \
  --host 127.0.0.1 \
  --port 6070 \
  --workers 1 \
  --proxy-headers \
  --forwarded-allow-ips 127.0.0.1 &
api_pid=$!

set +e
wait -n "$stock_pid" "$metadata_pid" "$api_pid"
set -e

# Either child exiting is unexpected while this compatibility unit is running.
# Exit nonzero so the existing Restart=on-failure policy restarts the pair.
cleanup
exit 1
