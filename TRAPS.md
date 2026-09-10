# Traps

Behaviour of zoekt, the shell, and the hosting path that cost time here. Each
entry is a thing that failed silently or reported success while doing nothing.

## zoekt

**The JSON API is gated on `-rpc`, not on `-html`.** `web/server.go` registers
`/api/` under `if s.RPC`, so `zoekt-webserver -html=false` without `-rpc`
serves no HTML *and* no API: every `/api/search` returns 404, while `/healthz`
answers and the process looks healthy. CORS headers are emitted on the 404,
which makes it look like a routing problem in the caller.

**`Stats` is embedded in `Result`, not nested under it.** The reply is
`{"Result": {"Files": [...], "FileCount": 122, "MatchCount": 483, "Duration":
28853571, ...}}`. Reading `result.Stats.FileCount` yields `undefined` in JS
with no error — every counter renders blank and the page still looks like it
works. `Duration` is nanoseconds.

**`ChunkMatch.Content` is base64 of raw bytes, and `Ranges` are byte offsets
into the whole file.** To mark matches inside a chunk, subtract
`ContentStart.ByteOffset` from each range. Decoding the base64 with `atob`
alone corrupts every non-ASCII character, which in this corpus means most
mathematical notation (`ℍ`, `≃ₗᵢ[ℝ]`, `𝕜`): map the binary string to bytes and
run it through `TextDecoder`.

**`sym:` queries need ctags at index time.** `zoekt-index` without ctags
available produces shards with no symbol data, and `sym:Anything` then returns
zero matches rather than an error. Silent, and indistinguishable from "this
symbol does not exist" — which is the one conclusion this corpus exists to
support, so it is worse than a crash.

**`zoekt-webserver` watches its shard directory** (`NewDirectorySearcherFast`),
so `just publish` needs no restart and no privileged step. Do not add one.

**The index is far larger than the sources.** 45k Lean files plus 8.9k Rocq and
Agda files produce 4.6 GB of shards across 864 files. It cannot be hosted
anywhere static: GitHub Pages caps a published site at 1 GB.

## Hosting

**Test the deployed URL, not a tunnel.** A page published on GitHub Pages calls
the production endpoint. Verifying it against `localhost` through an ssh
tunnel, with a hand-started server and a matching `-cors_origin`, tests a
configuration that will never exist again. `curl -X POST
https://<host>/api/search` takes two seconds and is the only check that means
anything.

**Cloudflare wildcard DNS hides the missing vhost.** Every `*.dzackgarza.com`
name already resolves, so a subdomain with no nginx server block still answers
200 from the default vhost. A working DNS lookup and a 200 on `/` prove
nothing about whether the service exists.

**The origin certificate does not cover new subdomains.** It is a single
certbot cert with an explicit SAN list; a new name needs `certbot --nginx
--expand --cert-name dzackgarza.com` naming *every* existing `-d` as well, or
the others are dropped.

## Shell

**`pgrep -f <pattern>` matches its own invoking shell.** The command line
containing the pattern is itself a process, so `pgrep -f 'just sync'` inside a
script that mentions `just sync` always finds a match. Two failures here: a
guard loop `while pgrep -f 'sync-manifest|just sync'; do :; done` spun forever
and the indexing step it guarded never ran, and `pkill -f` repeatedly killed
the wrapper shell before doing its work (exit 144, no output, target still
alive). Use `pgrep -x <binary>`, or match on the absolute path.

**Interactive aliases break non-interactive scripts on this machine.** `ls` is
`eza`, so `ls | wc -l` counts a `total` header line and shard counts come out
one too high; `cp` is `cp -i`, so an overwrite silently aborts on a prompt
nothing answers; `tr 'A-Z' 'a-z'` dies with an `--icons` error. Use `command
ls -1`, `command cp -f`, `/usr/bin/tr`.
