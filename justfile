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
    ./sync-reservoir.zsh

# Register every nested repository with gita.
register:
    uvx --from gita gita add --recursive --group lean-reference-corpus .

# Build the reusable lexical and structural search tools.
build-tools:
    cd tools/sourcegraph__zoekt && go build -o ../../bin/zoekt-index ./cmd/zoekt-index
    cd tools/sourcegraph__zoekt && go build -o ../../bin/zoekt ./cmd/zoekt
    cd tools/Julian__tree-sitter-lean && tree-sitter build --output ../../.ast-grep/lean.so

# Incrementally index every mathematical reference repository, including
# the Lean Reservoir packages.
index:
    #!/usr/bin/env zsh
    while IFS=$'\t' read -r _ dir; do
      ./bin/zoekt-index -index .zoekt "$dir"
    done < <(cat repos.tsv reservoir.tsv)

# Search declarations and source text across the corpus.
search query:
    ./bin/zoekt -index_dir .zoekt -r "{{query}}"

# Run a Lean syntax-tree pattern across the corpus.
ast pattern:
    ast-grep run --config sgconfig.yml --lang lean --pattern "{{pattern}}" --no-ignore vcs --globs '*.lean' .

# Prove that the custom parser supports Lean metavariable queries.
test-commit:
    printf 'def formedModuleAnswer : Nat := 42\n' | ast-grep run --config sgconfig.yml --lang lean --pattern 'def $NAME : $TYPE := $VALUE' --stdin --json=compact | jq -e 'length == 1 and .[0].text == "def formedModuleAnswer : Nat := 42"' >/dev/null
