#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
host="${FORMALIZATION_CORPUS_HOST:-zack@159.223.102.204}"
remote_root="${FORMALIZATION_CORPUS_REMOTE_ROOT:-/home/zack/lean-corpus}"

binary="$(mktemp)"
trap 'rm -f "$binary"' EXIT

(
  cd "$root/tools/sourcegraph__zoekt"
  GOOS=linux GOARCH=amd64 CGO_ENABLED=0 \
    go build -o "$binary" ./cmd/zoekt-webserver
)

rsync -a "$binary" "$host:$remote_root/bin/zoekt-webserver.stock"
ssh "$host" "mkdir -p '$remote_root/api' '$remote_root/systemd'"
rsync -a --delete --exclude .venv/ "$root/server/" "$host:$remote_root/api/"
rsync -a "$root/deploy/"*.service "$host:$remote_root/systemd/"

ssh "$host" "cd '$remote_root/api' && ~/.local/bin/uv sync --frozen --no-dev"

if ssh "$host" 'systemctl is-active --quiet formalization-corpus-api.service'; then
  # The process runs as zack. With Restart=always, terminating uvicorn is enough
  # for systemd to restart it on the newly deployed code without sudo.
  ssh "$host" "pkill -TERM -u zack -f '$remote_root/api/.venv/bin/uvicorn formalization_api.app:app' || true"
  echo "deployed and restarted formalization-corpus-api.service"
else
  cat <<EOF
staged API code, stock Zoekt binary, and systemd units on $host.

First-time activation requires root once:
  sudo install -m 0644 $remote_root/systemd/zoekt-webserver.service /etc/systemd/system/zoekt-webserver.service
  sudo install -m 0644 $remote_root/systemd/formalization-corpus-api.service /etc/systemd/system/formalization-corpus-api.service
  sudo systemctl daemon-reload
  sudo systemctl restart zoekt-webserver.service
  sudo systemctl enable --now formalization-corpus-api.service
EOF
fi
