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
ssh "$host" "mkdir -p '$remote_root/api' '$remote_root/systemd' '$remote_root/metadata-index'"
rsync -a --delete --exclude .venv/ "$root/server/" "$host:$remote_root/api/"
ssh "$host" "mkdir -p '$remote_root/api/data'"
rsync -a "$root/filtering/duplicate-aliases.json" "$host:$remote_root/api/data/duplicate-aliases.json"
rsync -a "$root/filtering/current.jsonl" "$host:$remote_root/api/data/filter-state.jsonl"
rsync -a "$root/deploy/"*.service "$host:$remote_root/systemd/"

# The compatibility root unit has a tight memory cgroup sized for the primary
# index. Keep the small documentation backend in its own user cgroup instead of
# making it compete with primary Zoekt for MemoryHigh/MemoryMax headroom.
ssh "$host" "mkdir -p ~/.config/systemd/user"
rsync -a "$root/deploy/zoekt-metadata-webserver.user.service" \
  "$host:~/.config/systemd/user/zoekt-metadata-webserver.service"

ssh "$host" "cd '$remote_root/api' && ~/.local/bin/uv sync --frozen --no-dev"

if ssh "$host" 'systemctl is-active --quiet formalization-corpus-api.service'; then
  # The process runs as zack. With Restart=always, terminating uvicorn is enough
  # for systemd to restart it on the newly deployed code without sudo.
  ssh "$host" "pkill -TERM -u zack -f '$remote_root/api/.venv/bin/uvicorn formalization_api.app:app' || true"
  echo "deployed and restarted formalization-corpus-api.service"
elif ssh "$host" "systemctl cat zoekt-webserver.service 2>/dev/null | grep -Fq '$remote_root/bin/zoekt-webserver' && systemctl cat zoekt-webserver.service 2>/dev/null | grep -Fq '127.0.0.1:6070'"; then
  # Compatibility migration for the original root-owned unit. The unit keeps
  # its existing ExecStart, but that path becomes a supervisor which runs stock
  # Zoekt on 6071 and FastAPI on 6070. SIGKILL makes Restart=on-failure reload
  # the replacement executable without requiring root access.
  rsync -a "$root/deploy/zoekt-api-compat-launcher.sh" "$host:$remote_root/bin/zoekt-webserver"
  ssh "$host" "pid=\$(systemctl show -p MainPID --value zoekt-webserver.service); test \"\$pid\" -gt 0; kill -KILL \"\$pid\""
  # The old compatibility launcher may itself own port 6072. Reload the root
  # unit first so that child exits, then start documentation Zoekt in a separate
  # user cgroup with independent memory accounting.
  ssh "$host" "systemctl --user daemon-reload && systemctl --user enable --now zoekt-metadata-webserver.service && systemctl --user restart zoekt-metadata-webserver.service"
  echo "deployed FastAPI through the existing zoekt-webserver.service compatibility entrypoint"
else
  cat <<EOF
staged API code, stock Zoekt binary, and systemd units on $host.

First-time activation requires root once:
  systemctl --user disable --now zoekt-metadata-webserver.service
  sudo install -m 0644 $remote_root/systemd/zoekt-webserver.service /etc/systemd/system/zoekt-webserver.service
  sudo install -m 0644 $remote_root/systemd/zoekt-metadata-webserver.service /etc/systemd/system/zoekt-metadata-webserver.service
  sudo install -m 0644 $remote_root/systemd/formalization-corpus-api.service /etc/systemd/system/formalization-corpus-api.service
  sudo systemctl daemon-reload
  sudo systemctl restart zoekt-webserver.service
  sudo systemctl restart zoekt-metadata-webserver.service
  sudo systemctl enable --now formalization-corpus-api.service
EOF
fi
