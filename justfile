set shell := ["zsh", "-eu", "-o", "pipefail", "-c"]

# Update existing source and tool repositories without changing their toolchains.
sync:
    #!/usr/bin/env zsh
    ./sync-manifest.zsh repos.tsv
    while IFS=$'\t' read -r url dir; do
      if [[ -d "$dir/.git" ]]; then
        git -C "$dir" pull --ff-only
      else
        git clone --depth 1 --filter=blob:none "$url" "$dir"
      fi
    done < tools.tsv

# Clone or update every Lean Reservoir package from reservoir.tsv.
sync-reservoir:
    ./sync-manifest.zsh reservoir.tsv

# Clone or update the registered non-Lean formalization sources.
sync-ports:
    ./sync-manifest.zsh port-sources.tsv

# Compatibility spelling kept for old local commands.
sync-rocq-agda: sync-ports

# Register every nested repository with gita.
register:
    uvx --from gita gita add --recursive --group formalization-corpus .

# Build the reusable lexical and structural search tools.
build-tools:
    cd tools/sourcegraph__zoekt && go build -o ../../bin/zoekt-index ./cmd/zoekt-index
    cd tools/sourcegraph__zoekt && go build -o ../../bin/zoekt ./cmd/zoekt
    cd tools/Julian__tree-sitter-lean && tree-sitter build --output ../../.ast-grep/lean.so

# Incrementally index every reference repository: Lean, Reservoir, port sources.
index:
    #!/usr/bin/env zsh
    mkdir -p .zoekt
    while IFS=$'\t' read -r _ dir _ _; do
      [[ -d "$dir" ]] || continue
      ./bin/zoekt-index -index .zoekt "$dir"
    done < <(cat repos.tsv reservoir.tsv port-sources.tsv)

# Incrementally index only the cross-prover sources after `just sync-ports`.
index-ports:
    #!/usr/bin/env zsh
    mkdir -p .zoekt
    while IFS=$'\t' read -r _ dir _ _; do
      [[ -d "$dir" ]] || continue
      ./bin/zoekt-index -index .zoekt "$dir"
    done < port-sources.tsv

# Recompute exact corpus-reach metrics from hydrated sources and Zoekt shards.
metrics:
    python scripts/build-metrics.py

# Regenerate the committed static source metadata from the manifests.
site:
    python scripts/build-site.py
    python scripts/build-subjects.py

# Deploy the static site to nginx's *.localhost preview root.
preview: site
    mkdir -p /var/www/static-sites/formalization-corpus-preview
    rsync -a --delete site/ /var/www/static-sites/formalization-corpus-preview/
    @echo "http://formalization-corpus-preview.localhost/"

# The origin address, not formalization-corpus.dzackgarza.com: that name resolves to
# Cloudflare, which proxies HTTP and would not carry ssh.
host := "zack@159.223.102.204"

# Ship the local index to the search host; the server hot-reloads replaced shards.
publish:
    rsync -a --delete --partial --info=stats1 .zoekt/ {{host}}:lean-corpus/index/
    @echo "https://formalization-corpus.dzackgarza.com"

# Report repositories named in SOURCES.md that no manifest checks out.
check-sources:
    #!/usr/bin/env zsh
    manifests=$(cat repos.tsv reservoir.tsv port-sources.tsv tools.tsv | cut -f1 | sed 's|\.git$||' | tr '[:upper:]' '[:lower:]' | sort -u)
    # A source table row names its repository in the first cell; later links are prose.
    linked=$(grep -oE '^\| \[[^]]*\]\(https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+' SOURCES.md \
      | grep -oE 'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+' | tr '[:upper:]' '[:lower:]' | sort -u)
    missing=$(comm -23 <(echo "$linked") <(echo "$manifests"))
    port_missing=$(while IFS=$'\t' read -r url _; do
      normalized="${url%/}"
      grep -Fiq "$normalized" SOURCES.md || echo "$url"
    done < port-sources.tsv)
    duplicate_urls=$(cat repos.tsv reservoir.tsv port-sources.tsv | cut -f1 | sed 's|/$||' | tr '[:upper:]' '[:lower:]' | sort | uniq -d)
    duplicate_names=$(cat repos.tsv reservoir.tsv port-sources.tsv | cut -f2 | awk -F/ '{print $NF}' | sort | uniq -d)
    if [[ -n "$missing" ]]; then
      echo "Named in SOURCES.md, checked out by no manifest:"
      echo "$missing"
      exit 1
    fi
    if [[ -n "$port_missing" ]]; then
      echo "Named in port-sources.tsv, documented nowhere in SOURCES.md:"
      echo "$port_missing"
      exit 1
    fi
    if [[ -n "$duplicate_urls" || -n "$duplicate_names" ]]; then
      echo "Duplicate source identity across manifests:" >&2
      [[ -n "$duplicate_urls" ]] && printf 'URLs:\n%s\n' "$duplicate_urls" >&2
      [[ -n "$duplicate_names" ]] && printf 'names:\n%s\n' "$duplicate_names" >&2
      exit 1
    fi
    echo "SOURCES.md and the manifests agree."

# Search declarations and source text across the corpus.
search query:
    ./bin/zoekt -index_dir .zoekt -r "{{query}}"

# Run a Lean syntax-tree pattern across the corpus.
ast pattern:
    ast-grep run --config sgconfig.yml --lang lean --pattern "{{pattern}}" --no-ignore vcs --globs '*.lean' .

# Prove that the custom parser supports Lean metavariable queries.
test-commit:
    printf 'def formedModuleAnswer : Nat := 42\n' | ast-grep run --config sgconfig.yml --lang lean --pattern 'def $NAME : $TYPE := $VALUE' --stdin --json=compact | jq -e 'length == 1 and .[0].text == "def formedModuleAnswer : Nat := 42"' >/dev/null

# Same verification as test-commit; the push gate requires this name.
test-push: test-commit

# Reservoir names packages, not repositories: the printed URL is the source
# repository, and each link must be resolved before it enters the registry.
# List Mathlib-dependent Reservoir packages not yet named in SOURCES.md
source-sweep:
    #!/usr/bin/env bash
    set -euo pipefail
    idx="$(mktemp -d)/reservoir-index"
    git clone -q --depth 1 https://github.com/leanprover/reservoir-index "$idx"
    grep -oE 'github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+' SOURCES.md | sed 's#github.com/##' | tr '[:upper:]' '[:lower:]' | sort -u > "$idx/../linked.txt"
    for d in "$idx"/*/*/; do
        [ -f "$d/metadata.json" ] || continue
        jq -r '[.data[0].dependencies[]?.name] | index("mathlib") != null' "$d/versions.json" 2>/dev/null | grep -q true || continue
        jq -r '[(.sources[0].repoUrl // ("https://github.com/" + .fullName)), (.stars|tostring), (.description // "" | gsub("[\\t\\n]";" "))] | @tsv' "$d/metadata.json"
    done | sort -t"$(printf '\t')" -k2,2nr | while IFS=$'\t' read -r url stars desc; do
        key="$(printf '%s' "${url#https://github.com/}" | tr '[:upper:]' '[:lower:]')"
        grep -qx "$key" "$idx/../linked.txt" || printf '%s\t%s\t%s\n' "$url" "$stars" "$desc"
    done
