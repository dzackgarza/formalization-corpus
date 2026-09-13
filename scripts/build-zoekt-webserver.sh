#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_repo="$root/tools/sourcegraph__zoekt"
patch_file="$root/patches/zoekt-openapi.patch.txt"
output="${1:-$root/bin/zoekt-webserver}"

if [[ ! -d "$source_repo/.git" ]]; then
  echo "missing Zoekt checkout: $source_repo" >&2
  exit 1
fi

build_dir="$(mktemp -d)"
trap 'rm -rf "$build_dir"' EXIT

git -C "$source_repo" archive HEAD | tar -x -C "$build_dir"
(
  cd "$build_dir"
  decoded_patch="$build_dir/zoekt-openapi.patch"
  sed -e 's/^|~$/ /' -e 's/^|//' "$patch_file" > "$decoded_patch"
  git apply --check "$decoded_patch"
  git apply "$decoded_patch"
  go test ./internal/json
  mkdir -p "$(dirname "$output")"
  go build -o "$output" ./cmd/zoekt-webserver
)
