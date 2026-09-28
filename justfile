set shell := ["zsh", "-eu", "-o", "pipefail", "-c"]

# Refresh every stale source: hydrate it, rebuild its review and filtering evidence
# when its revision changed, rebuild and verify its shards, then release the checkout.
# Commit the regenerated evidence under filtering/ afterwards.
sync:
    python scripts/index-source.py refresh

# Refresh only the sources of one sync group (routine, bulk or cross-prover).
sync-group group:
    python scripts/index-source.py refresh --group "{{group}}"

# Refresh one source.
index-source repository:
    python scripts/index-source.py refresh --source "{{repository}}"

# Check every shard against sources.tsv, the committed evidence and the index provenance.
index-verify:
    python scripts/index-source.py verify

# Verify the index, then remove the checkouts that sources.tsv can hydrate again.
release-checkouts:
    python scripts/index-source.py release

# Update the tool repositories. Run build-tools afterwards; a new Zoekt revision
# makes the next sync rebuild every shard.
sync-tools:
    #!/usr/bin/env zsh
    while IFS=$'\t' read -r url dir; do
      if [[ -d "$dir/.git" ]]; then
        git -C "$dir" pull --ff-only
      else
        git clone --depth 1 --filter=blob:none "$url" "$dir"
      fi
    done < tools.tsv

# Register every nested repository with gita.
register:
    uvx --from gita gita add --recursive --group formalization-corpus .

# Build the reusable lexical and structural search tools.
build-tools:
    cd tools/sourcegraph__zoekt && go build -o ../../bin/zoekt-index ./cmd/zoekt-index
    cd tools/sourcegraph__zoekt && go build -o ../../bin/zoekt ./cmd/zoekt
    cd tools/sourcegraph__zoekt && go build -o ../../bin/zoekt-webserver ./cmd/zoekt-webserver
    cd tools/Julian__tree-sitter-lean && tree-sitter build --output ../../.ast-grep/lean.so

# Regenerate the public source, proof-assistant and topic totals from sources.tsv.
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

# Ship only the validated primary formalization index. The separate metadata
# index is deliberately not published or queried by the public site.
publish: filter-validate index-verify metrics
    rsync -a --delete --partial --info=stats1 .zoekt/ {{host}}:lean-corpus/index/
    python scripts/check-published.py
    if ssh {{host}} 'systemctl is-active --quiet formalization-corpus-api.service'; then ssh {{host}} "pkill -TERM -u zack -f '/home/zack/lean-corpus/api/.venv/bin/uvicorn formalization_api.app:app' || true"; else echo 'FastAPI adapter inactive; filtered index published to the currently active search backend'; fi
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

# Audit the material fed to search before attributing ranking failures to retrieval.
audit-search-data output="/tmp/formalization-corpus-data-audit.json":
    python evaluation/search/audit_corpus_data.py --output "{{output}}"

# Validate catalogue coverage, review history, snapshot freshness, and selectors.
repository-review-validate:
    python scripts/repository-review.py validate

# Show the complete repository-review frontier.
repository-review-status:
    python scripts/repository-review.py status

# Show one deterministic review batch.
repository-review-batch batch:
    python scripts/repository-review.py status --batch "{{batch}}"

# Replay and validate the append-only filtering ledger against derived snapshots.
filter-validate: repository-review-validate
    python scripts/validate-filter-state.py

# Search declarations and source text across the corpus.
search query:
    ./bin/zoekt -index_dir .zoekt -r "{{query}}"

# Search the separate maintainer-only metadata/navigation index.
search-metadata query:
    ./bin/zoekt -index_dir .zoekt-metadata -r "{{query}}"

# Run a Lean syntax-tree pattern across the corpus.
ast pattern:
    ast-grep run --config sgconfig.yml --lang lean --pattern "{{pattern}}" --no-ignore vcs --globs '*.lean' .

# Prove that the custom parser supports Lean metavariable queries.
test-commit:
    printf 'def formedModuleAnswer : Nat := 42\n' | ast-grep run --config sgconfig.yml --lang lean --pattern 'def $NAME : $TYPE := $VALUE' --stdin --json=compact | jq -e 'length == 1 and .[0].text == "def formedModuleAnswer : Nat := 42"' >/dev/null
    python scripts/check-policy-codes.py
    python scripts/repository-review.py validate
    python scripts/validate-filter-state.py
    python evaluation/search/evaluate.py --validate-only
    python -m unittest discover -s evaluation/search -p 'test_*.py'
    python evaluation/search/lablog.py validate
    cd server && uv run --frozen pytest -q

# Archive a completed clean retrieval report in the immutable scientific record.
record-search-run report stage="candidate":
    python evaluation/search/lablog.py run "{{report}}" --stage "{{stage}}"

# Inspect the chronological search-quality laboratory record.
search-lablog:
    python evaluation/search/lablog.py show

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
