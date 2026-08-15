#!/usr/bin/env zsh
# Hydrate or update Lean Reservoir packages from a manifest.
# Usage: sync-reservoir.zsh [manifest.tsv]   (default: reservoir.tsv)
# Mirrors the sparse-checkout convention of the main corpus:
#   keep *.lean, lakefile.*, lean-toolchain, lake-manifest.json, README*
# Logs failures to <manifest-basename>-missing.now for inspection.
# Multiple workers can run in parallel on sharded manifests.
set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT" || exit 1
MANIFEST="${1:-reservoir.tsv}"
MANIFEST="$(realpath "$MANIFEST")"
FAIL_LOG="${MANIFEST%.tsv}-missing.now"
: > "$FAIL_LOG"
COUNT=0
FAILED=0
while IFS=$'\t' read -r url dir; do
  [[ -z "$url" ]] && continue
  COUNT=$((COUNT + 1))
  # GitHub https URLs carry an anonymous rate limit; ssh does not.
  url="${url/https:\/\/github.com\//git@github.com:}"
  if [[ -d "$dir/.git" ]]; then
    if git -C "$dir" symbolic-ref --quiet HEAD >/dev/null 2>&1; then
      git -C "$dir" pull --ff-only --depth 1 >/dev/null 2>&1 || echo "$url	$dir	UPDATE-FAIL" >> "$FAIL_LOG"
    else
      git -C "$dir" fetch --prune origin >/dev/null 2>&1 || echo "$url	$dir	FETCH-FAIL" >> "$FAIL_LOG"
    fi
    continue
  fi
  if timeout 90 git clone --depth 1 --filter=blob:none "$url" "$dir" >/dev/null 2>&1; then
    git -C "$dir" sparse-checkout set --no-cone '/*' '!/*/' '/**/*.lean' '/lakefile.*' '/lean-toolchain' '/lake-manifest.json' '/README*' >/dev/null 2>&1 \
      || echo "$url	$dir	SPARSE-FAIL" >> "$FAIL_LOG"
  else
    FAILED=$((FAILED + 1))
    echo "$url	$dir	CLONE-FAIL" >> "$FAIL_LOG"
  fi
done < "$MANIFEST"
echo "processed=$COUNT failed=$FAILED log=$FAIL_LOG"
