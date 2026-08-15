set shell := ["zsh", "-eu", "-o", "pipefail", "-c"]

# Update existing source and tool repositories without changing their toolchains.
sync:
    #!/usr/bin/env zsh
    while IFS=$'\t' read -r url path; do
      if [[ -d "$path/.git" ]]; then
        git -C "$path" pull --ff-only
      else
        git clone --depth 1 --filter=blob:none "$url" "$path"
      fi
    done < <(cat repos.tsv tools.tsv)

# Register every nested repository with gita.
register:
    uvx --from gita gita add --recursive --group lean-reference-corpus .

# Build the reusable lexical and structural search tools.
build-tools:
    cd tools/sourcegraph__zoekt && go build -o ../../bin/zoekt-git-index ./cmd/zoekt-git-index
    cd tools/sourcegraph__zoekt && go build -o ../../bin/zoekt ./cmd/zoekt
    cd tools/Julian__tree-sitter-lean && tree-sitter build --output ../../.ast-grep/lean.so

# Incrementally index every mathematical reference repository.
index:
    #!/usr/bin/env zsh
    while IFS=$'\t' read -r _ path; do
      ./bin/zoekt-git-index -index .zoekt "$path"
    done < repos.tsv

# Search declarations and source text across the corpus.
search query:
    ./bin/zoekt -index_dir .zoekt -r "{{query}}"

# Run a Lean syntax-tree pattern across the corpus.
ast pattern:
    ast-grep run --config sgconfig.yml --lang lean --pattern "{{pattern}}" --no-ignore vcs --globs '*.lean' .

# Prove that the custom parser supports Lean metavariable queries.
test-commit:
    printf 'def formedModuleAnswer : Nat := 42\n' | ast-grep run --config sgconfig.yml --lang lean --pattern 'def $NAME : $TYPE := $VALUE' --stdin --json=compact | jq -e 'length == 1 and .[0].text == "def formedModuleAnswer : Nat := 42"' >/dev/null
