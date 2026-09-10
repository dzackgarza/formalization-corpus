set shell := ["zsh", "-eu", "-o", "pipefail", "-c"]

# Update existing source and tool repositories without changing their toolchains.
sync:
    #!/usr/bin/env zsh
    while IFS=$'\t' read -r url dir; do
      if [[ -d "$dir/.git" ]]; then
        if git -C "$dir" symbolic-ref --quiet HEAD >/dev/null; then
          git -C "$dir" pull --ff-only
        else
          git -C "$dir" fetch --prune origin
        fi
      else
        git clone --depth 1 --filter=blob:none "$url" "$dir"
      fi
    done < <(cat repos.tsv tools.tsv)

# Clone or update every Lean Reservoir package from reservoir.tsv.
sync-reservoir:
    ./sync-manifest.zsh reservoir.tsv

# Clone or update the Rocq and Agda libraries the reuse gate treats as port sources.
sync-port-sources:
    ./sync-manifest.zsh port-sources.tsv '/**/*.v' '/**/*.agda' '/**/*.lagda*'

# Register every nested repository with gita.
register:
    uvx --from gita gita add --recursive --group lean-reference-corpus .

# Build the reusable lexical and structural search tools.
build-tools:
    cd tools/sourcegraph__zoekt && go build -o ../../bin/zoekt-index ./cmd/zoekt-index
    cd tools/sourcegraph__zoekt && go build -o ../../bin/zoekt ./cmd/zoekt
    cd tools/Julian__tree-sitter-lean && tree-sitter build --output ../../.ast-grep/lean.so

# Incrementally index every reference repository: Lean, Reservoir, port sources.
index:
    #!/usr/bin/env zsh
    mkdir -p .zoekt
    while IFS=$'\t' read -r _ dir; do
      [[ -d "$dir" ]] || continue
      ./bin/zoekt-index -index .zoekt "$dir"
    done < <(cat repos.tsv reservoir.tsv port-sources.tsv)

# Report repositories named in SOURCES.md that no manifest checks out.
check-sources:
    #!/usr/bin/env zsh
    manifests=$(cat repos.tsv reservoir.tsv port-sources.tsv tools.tsv | cut -f1 | sed 's|\.git$||' | tr '[:upper:]' '[:lower:]' | sort -u)
    # A source table row names its repository in the first cell; later links are prose.
    linked=$(grep -oE '^\| \[[^]]*\]\(https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+' SOURCES.md \
      | grep -oE 'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+' | tr '[:upper:]' '[:lower:]' | sort -u)
    missing=$(comm -23 <(echo "$linked") <(echo "$manifests"))
    if [[ -z "$missing" ]]; then
      echo "SOURCES.md and the manifests agree."
    else
      echo "Named in SOURCES.md, checked out by no manifest:"
      echo "$missing"
    fi

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
