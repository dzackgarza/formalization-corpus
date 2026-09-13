set shell := ["zsh", "-eu", "-o", "pipefail", "-c"]

# Update the routine formalization-source set and tool repositories.
sync:
    #!/usr/bin/env zsh
    SYNC_GROUP=routine ./sync-manifest.zsh sources.tsv
    while IFS=$'\t' read -r url dir; do
      if [[ -d "$dir/.git" ]]; then
        git -C "$dir" pull --ff-only
      else
        git clone --depth 1 --filter=blob:none "$url" "$dir"
      fi
    done < tools.tsv

# Refresh the large secondary source set without making it part of routine sync.
sync-bulk:
    SYNC_GROUP=bulk ./sync-manifest.zsh sources.tsv

# Compatibility spelling for the historical ingestion source.
sync-reservoir: sync-bulk

# Refresh sources maintained in proof assistants other than Lean.
sync-cross-prover:
    SYNC_GROUP=cross-prover ./sync-manifest.zsh sources.tsv

# Compatibility spellings kept for old local commands.
sync-ports: sync-cross-prover
sync-rocq-agda: sync-cross-prover

# Register every nested repository with gita.
register:
    uvx --from gita gita add --recursive --group formalization-corpus .

# Build the reusable lexical and structural search tools.
build-tools:
    cd tools/sourcegraph__zoekt && go build -o ../../bin/zoekt-index ./cmd/zoekt-index
    cd tools/sourcegraph__zoekt && go build -o ../../bin/zoekt ./cmd/zoekt
    cd tools/sourcegraph__zoekt && go build -o ../../bin/zoekt-webserver ./cmd/zoekt-webserver
    cd tools/Julian__tree-sitter-lean && tree-sitter build --output ../../.ast-grep/lean.so

# Incrementally index every formalization source.
index:
    #!/usr/bin/env zsh
    mkdir -p .zoekt
    tail -n +2 sources.tsv | while IFS=$'\t' read -r _ dir _ _ _ _; do
      [[ -d "$dir" ]] || continue
      ./bin/zoekt-index -index .zoekt "$dir"
    done

# Incrementally index only the cross-prover sync group.
index-cross-prover:
    #!/usr/bin/env zsh
    mkdir -p .zoekt
    awk -F'\t' 'NR > 1 && $5 == "cross-prover"' sources.tsv \
      | while IFS=$'\t' read -r _ dir _ _ _ _; do
          [[ -d "$dir" ]] || continue
          ./bin/zoekt-index -index .zoekt "$dir"
        done

index-ports: index-cross-prover

# Validate the hydrated corpus and regenerate public source/proof-assistant/topic totals.
metrics:
    python scripts/build-metrics.py

# Regenerate the committed static source and subject metadata.
site:
    python scripts/build-site.py
    python scripts/build-topics.py

# Deploy the static site to nginx's *.localhost preview root.
# Metrics runs first so invalid corpus entries fail instead of becoming UI copy.
preview: metrics site
    mkdir -p /var/www/static-sites/formalization-corpus-preview
    rsync -a --delete site/ /var/www/static-sites/formalization-corpus-preview/
    @echo "http://formalization-corpus-preview.localhost/"

# The origin address, not formalization-corpus.dzackgarza.com: that name resolves to
# Cloudflare, which proxies HTTP and would not carry ssh.
host := "zack@159.223.102.204"

# Ship the validated local index to the search host and verify exact source parity.
publish: metrics
    rsync -a --delete --partial --info=stats1 .zoekt/ {{host}}:lean-corpus/index/
    python scripts/check-published.py
    ssh {{host}} "pkill -TERM -u zack -f '/home/zack/lean-corpus/api/.venv/bin/uvicorn formalization_api.app:app' || true"
    @echo "https://formalization-corpus.dzackgarza.com"

# Deploy the public FastAPI adapter and stock Zoekt backend binary. The first
# migration requires one root systemd activation; later adapter deploys restart
# the user-owned uvicorn process through systemd's Restart=always policy.
deploy-api:
    ./scripts/deploy-api.sh

# Check static source-table invariants and cross-prover documentation.
check-sources:
    #!/usr/bin/env zsh
    cross_prover_missing=$(awk -F'\t' 'NR > 1 && $5 == "cross-prover" {print $1}' sources.tsv \
      | while read -r url; do normalized="${url%/}"; grep -Fiq "$normalized" SOURCES.md || echo "$url"; done)
    duplicate_urls=$(tail -n +2 sources.tsv | cut -f1 | sed 's|/$||' | tr '[:upper:]' '[:lower:]' | sort | uniq -d)
    duplicate_names=$(tail -n +2 sources.tsv | cut -f2 | awk -F/ '{print $NF}' | sort | uniq -d)
    if [[ -n "$cross_prover_missing" ]]; then
      echo "Cross-prover source documented nowhere in SOURCES.md:"
      echo "$cross_prover_missing"
      exit 1
    fi
    if [[ -n "$duplicate_urls" || -n "$duplicate_names" ]]; then
      echo "Duplicate source identity in sources.tsv:" >&2
      [[ -n "$duplicate_urls" ]] && printf 'URLs:\n%s\n' "$duplicate_urls" >&2
      [[ -n "$duplicate_names" ]] && printf 'names:\n%s\n' "$duplicate_names" >&2
      exit 1
    fi
    echo "sources.tsv has unique identities and all cross-prover sources are documented."

# Evaluate the current public query behavior against the frozen retrieval gold set.
eval-search:
    python evaluation/search/evaluate.py --provider local --variant frontend_lexical_v2

# Regression check against the deployed lexical-v2 baseline. Requires the same local Zoekt index.
test-search-quality:
    python evaluation/search/evaluate.py --provider local --variant frontend_lexical_v2 --compare evaluation/search/baselines/frontend_lexical_v2.json

# Reproduce the measured multi-query + Cohere reranker experiment (network/API key required).
eval-search-rerank:
    python evaluation/search/evaluate_rerank.py --candidate-pool 30 --output evaluation/search/experiments/reports/gemini_multiquery_rrf_cohere_v4_fast_v1.json

# Rebuild the TREC-style top-10 relevance-judgment pool from the measured runs.
build-search-pool:
    python evaluation/search/build_pool.py evaluation/search/baselines/frontend_lexical_v1.json evaluation/search/experiments/reports/normalized_path_content_v1.json evaluation/search/experiments/reports/gemini_multiquery_rrf_v1.json evaluation/search/experiments/reports/gemini_multiquery_rrf_cohere_v4_fast_v1.json --depth 10 --output evaluation/search/pools/initial_top10_pool.json

# Search declarations and source text across the corpus.
search query:
    ./bin/zoekt -index_dir .zoekt -r "{{query}}"

# Run a Lean syntax-tree pattern across the corpus.
ast pattern:
    ast-grep run --config sgconfig.yml --lang lean --pattern "{{pattern}}" --no-ignore vcs --globs '*.lean' .

# Prove that the custom parser supports Lean metavariable queries.
test-commit:
    printf 'def formedModuleAnswer : Nat := 42\n' | ast-grep run --config sgconfig.yml --lang lean --pattern 'def $NAME : $TYPE := $VALUE' --stdin --json=compact | jq -e 'length == 1 and .[0].text == "def formedModuleAnswer : Nat := 42"' >/dev/null
    python evaluation/search/evaluate.py --validate-only
    python evaluation/search/test_evaluate.py
    cd server && uv run --frozen pytest -q

# A push also refreshes the exact static tree served at *.localhost.
test-push: test-commit preview

# Reservoir names packages, not repositories: the printed URL is the source
# repository, and each link must be resolved before it enters the registry.
# List Mathlib-dependent Reservoir package repositories absent from sources.tsv
source-sweep:
    #!/usr/bin/env bash
    set -euo pipefail
    idx="$(mktemp -d)/reservoir-index"
    git clone -q --depth 1 https://github.com/leanprover/reservoir-index "$idx"
    tail -n +2 sources.tsv | cut -f1 | sed -E 's#https://github.com/##; s#\.git$##; s#/$##' \
      | tr '[:upper:]' '[:lower:]' | sort -u > "$idx/../linked.txt"
    for d in "$idx"/*/*/; do
        [ -f "$d/metadata.json" ] || continue
        jq -r '[.data[0].dependencies[]?.name] | index("mathlib") != null' "$d/versions.json" 2>/dev/null | grep -q true || continue
        jq -r '[(.sources[0].repoUrl // ("https://github.com/" + .fullName)), (.stars|tostring), (.description // "" | gsub("[\\t\\n]";" "))] | @tsv' "$d/metadata.json"
    done | sort -t"$(printf '\t')" -k2,2nr | while IFS=$'\t' read -r url stars desc; do
        key="$(printf '%s' "${url#https://github.com/}" | tr '[:upper:]' '[:lower:]')"
        grep -qx "$key" "$idx/../linked.txt" || printf '%s\t%s\t%s\n' "$url" "$stars" "$desc"
    done
