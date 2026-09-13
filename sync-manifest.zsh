#!/usr/bin/env zsh
# Hydrate or update the repositories of a manifest.
# Usage: sync-manifest.zsh [manifest.tsv] [proof-text-glob ...]
#   default manifest: reservoir.tsv
#   default globs:    /**/*.lean plus the Lake build files
# A four-column manifest may instead name the prover and transport:
#   URL<TAB>DIR<TAB>KIND<TAB>TRANSPORT
# In that form the proof-text globs are selected per row. TRANSPORT is `git`,
# `gitlab`, or `web-dir`; the latter is used for the current Mizar MML, whose
# authoritative distribution is an HTTP directory rather than a current git
# mirror.
# Logs failures to <manifest-basename>-missing.now for inspection.
# Multiple workers can run in parallel on sharded manifests.
set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT" || exit 1
MANIFEST="${1:-reservoir.tsv}"
shift 2>/dev/null || true
CLI_GLOBS=("$@")
MANIFEST="$(realpath "$MANIFEST")"
FAIL_LOG="${MANIFEST%.tsv}-missing.now"
: > "$FAIL_LOG"
COUNT=0
FAILED=0
while IFS=$'\t' read -r url dir kind transport; do
  [[ -z "$url" ]] && continue
  COUNT=$((COUNT + 1))
  kind="${kind:-lean}"
  transport="${transport:-git}"

  if (( ${#CLI_GLOBS} )); then
    PROOF_GLOBS=("${CLI_GLOBS[@]}")
  else
    case "$kind" in
      lean)      PROOF_GLOBS=('/**/*.lean' '/lakefile.*' '/lean-toolchain' '/lake-manifest.json') ;;
      rocq)      PROOF_GLOBS=('/**/*.v') ;;
      agda)      PROOF_GLOBS=('/**/*.agda' '/**/*.lagda*') ;;
      isabelle)  PROOF_GLOBS=('/**/*.thy') ;;
      hol-light) PROOF_GLOBS=('/**/*.ml' '/**/*.hl') ;;
      hol4)      PROOF_GLOBS=('/**/*.sml' '/**/*.sig') ;;
      mizar)     PROOF_GLOBS=('/**/*.miz') ;;
      metamath)  PROOF_GLOBS=('/**/*.mm' '/**/*.mm0' '/**/*.mm1') ;;
      acl2)      PROOF_GLOBS=('/**/*.lisp' '/**/*.lsp' '/**/*.acl2') ;;
      pvs)       PROOF_GLOBS=('/**/*.pvs' '/**/*.prf') ;;
      twelf)     PROOF_GLOBS=('/**/*.elf') ;;
      *)
        FAILED=$((FAILED + 1))
        echo "$url	$dir	UNKNOWN-KIND:$kind" >> "$FAIL_LOG"
        continue
        ;;
    esac
  fi

  if [[ "$transport" == "web-dir" ]]; then
    mkdir -p "$dir"
    case "$kind" in
      mizar)
        listing="$(mktemp)"
        if ! curl -fsSL --retry 3 --connect-timeout 20 --max-time 120 \
             "$url" -o "$listing"; then
          command rm -f "$listing"
          FAILED=$((FAILED + 1))
          echo "$url	$dir	WEB-SYNC-FAIL" >> "$FAIL_LOG"
          continue
        fi
        files=("${(@f)$(grep -oE 'href="[^"]+\.miz"' "$listing" \
          | sed -E 's/^href="//; s/"$//' | sort -u)}")
        command rm -f "$listing"
        if (( ${#files} == 0 )); then
          FAILED=$((FAILED + 1))
          echo "$url	$dir	WEB-SYNC-FAIL" >> "$FAIL_LOG"
          continue
        fi
        if ! printf '%s\n' "${files[@]}" \
          | xargs -P "${SYNC_WEB_JOBS:-16}" -I{} sh -c '
              base=$1; out=$2; name=$3
              tmp="$out/.${name}.part.$$"
              if curl -fsSL --retry 3 --retry-delay 1 --connect-timeout 20 \
                   --max-time 120 "${base}${name}" -o "$tmp"; then
                mv -f "$tmp" "$out/$name"
              else
                rm -f "$tmp"
                exit 1
              fi
            ' _ "$url" "$dir" '{}'; then
          FAILED=$((FAILED + 1))
          echo "$url	$dir	WEB-SYNC-FAIL" >> "$FAIL_LOG"
          continue
        fi
        typeset -A current_web_files
        for name in "${files[@]}"; do current_web_files[$name]=1; done
        for existing in "$dir"/*.miz(N); do
          [[ -n "${current_web_files[${existing:t}]:-}" ]] || command rm -f "$existing"
        done
        unset current_web_files
        ;;
      *)
        FAILED=$((FAILED + 1))
        echo "$url	$dir	UNSUPPORTED-WEB-DIR:$kind" >> "$FAIL_LOG"
        continue
        ;;
    esac
    continue
  fi

  if [[ -d "$dir/.git" ]]; then
    # These are public read-only checkouts. The laptop has sometimes carried a
    # global `url.*.insteadOf` rule that rewrites GitHub HTTPS back to SSH; that
    # is especially bad for partial clones because `checkout` performs a lazy
    # blob fetch. Keep the recorded origin canonical and ignore global rewrites
    # for every network/materialization command in this synchronizer.
    if [[ "$url" == https://github.com/* ]]; then
      git -C "$dir" remote set-url origin "$url" >/dev/null 2>&1 || true
    fi
    if git -C "$dir" symbolic-ref --quiet HEAD >/dev/null 2>&1; then
      branch="$(git -C "$dir" symbolic-ref --short HEAD)"
      if ! GIT_CONFIG_GLOBAL=/dev/null timeout "${SYNC_UPDATE_TIMEOUT:-60}" \
           git -C "$dir" pull --ff-only --depth 1 >/dev/null 2>&1; then
        # A depth-1 mirror can look "diverged" as soon as upstream advances
        # beyond the one visible commit: pull cannot see the common history.
        # These are read-only corpus mirrors, so a clean shallow checkout may
        # be refreshed directly to the current remote branch tip. Never reset
        # a dirty checkout; preserve it and report the failure instead.
        if [[ "$(git -C "$dir" rev-parse --is-shallow-repository 2>/dev/null)" == true ]] && \
           [[ -z "$(git -C "$dir" status --porcelain=v1 2>/dev/null)" ]] && \
           GIT_CONFIG_GLOBAL=/dev/null timeout "${SYNC_UPDATE_TIMEOUT:-60}" \
             git -C "$dir" fetch --prune --depth 1 origin "$branch" >/dev/null 2>&1 && \
           GIT_CONFIG_GLOBAL=/dev/null git -C "$dir" reset --hard FETCH_HEAD >/dev/null 2>&1; then
          :
        else
          FAILED=$((FAILED + 1))
          echo "$url\t$dir\tUPDATE-FAIL" >> "$FAIL_LOG"
        fi
      fi
    else
      if ! GIT_CONFIG_GLOBAL=/dev/null timeout "${SYNC_UPDATE_TIMEOUT:-60}" \
           git -C "$dir" fetch --prune origin >/dev/null 2>&1; then
        FAILED=$((FAILED + 1))
        echo "$url\t$dir\tFETCH-FAIL" >> "$FAIL_LOG"
      fi
    fi
    if ! GIT_CONFIG_GLOBAL=/dev/null git -C "$dir" sparse-checkout set --no-cone \
         '/*' '!/*/' "${PROOF_GLOBS[@]}" '/README*' >/dev/null 2>&1 || \
       ! GIT_CONFIG_GLOBAL=/dev/null timeout "${SYNC_CHECKOUT_TIMEOUT:-600}" \
         git -C "$dir" checkout -q >/dev/null 2>&1; then
      FAILED=$((FAILED + 1))
      echo "$url	$dir	SPARSE-FAIL" >> "$FAIL_LOG"
    fi
    continue
  fi

  if ! GIT_CONFIG_GLOBAL=/dev/null timeout "${SYNC_CLONE_TIMEOUT:-300}" \
       git clone --depth 1 --filter=blob:none --no-checkout "$url" "$dir" >/dev/null 2>&1; then
    command rm -rf "$dir"
    FAILED=$((FAILED + 1))
    echo "$url	$dir	CLONE-FAIL" >> "$FAIL_LOG"
    continue
  fi
  if GIT_CONFIG_GLOBAL=/dev/null git -C "$dir" sparse-checkout set --no-cone \
       '/*' '!/*/' "${PROOF_GLOBS[@]}" '/README*' >/dev/null 2>&1 && \
     GIT_CONFIG_GLOBAL=/dev/null timeout "${SYNC_CHECKOUT_TIMEOUT:-600}" \
       git -C "$dir" checkout -q >/dev/null 2>&1; then
    :
  else
    FAILED=$((FAILED + 1))
    echo "$url	$dir	SPARSE-FAIL" >> "$FAIL_LOG"
  fi
done < "$MANIFEST"
echo "processed=$COUNT failed=$FAILED log=$FAIL_LOG"
