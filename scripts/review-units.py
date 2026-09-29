#!/usr/bin/env python3
"""Review every pending or lapsed work unit of one hydrated source.

A unit needs review when it has no review or its review lapsed (FILTER-023).  The
files that need a reviewer are the baseline primary-retained files whose bytes no
earlier review saw: every such file of a never-reviewed unit, and the changed or added
files of a lapsed unit.  The prior review's pinned snapshot names the manifest version
it saw; Git history of the manifest holds that version.  Exclusion rules whose files
are all unchanged are restated on exactly those files.

A unit with no file to review gets a mechanical review record.  Every other unit goes
to an opencode agent with read-only tools, which returns the summary, evidence, and new
exclusion rules.  `repository-review.py append` validates and appends each record; a
rejected record goes back to the agent with the validation errors.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
from typing import Any

from filtering_lib import ROOT
from repository_review_lib import (
    SCHEMA_VERSION,
    FileRecord,
    carried_review_exclusions,
    corpus_commit,
    load_review_history,
    load_unit_file_records,
    load_units,
    material_snapshot_sha256,
    unit_state,
    utc_now,
)

MODEL = "opencode/nemotron-3-ultra-free"
CALL_TIMEOUT_SECONDS = 15 * 60
ATTEMPTS = 4
RULE_POLICIES = [
    "FILTER-002", "FILTER-004", "FILTER-005", "FILTER-018", "FILTER-020",
    "FILTER-022", "FILTER-023", "FILTER-024", "FILTER-025",
]
BRIEF_POLICIES = ("FILTER-002", "FILTER-004", "FILTER-007", "FILTER-021", "FILTER-022", "FILTER-024", "FILTER-025")
# The free tier rejects a request whose tool list lacks a built-in tool, so the
# write, shell, and network tools stay listed and `opencode run` auto-rejects each call.
PERMISSIONS = {
    "permission": {
        tool: "ask" for tool in ("edit", "bash", "webfetch", "websearch", "task", "external_directory")
    }
}


def file_record(row: dict[str, Any]) -> FileRecord:
    return FileRecord(
        path=str(row["path"]),
        size_bytes=int(row["size_bytes"]),
        sha256=str(row["sha256"]),
        formal_source=bool(row["formal_source"]),
        active_decisions=tuple(row["active_decisions"]),
        baseline_primary_status=str(row["baseline_primary_status"]),
        current_primary_status=str(row["current_primary_status"]),
    )


def reviewed_manifest(unit: dict[str, Any], snapshot: str) -> dict[str, dict[str, Any]] | None:
    """The committed manifest version whose material snapshot is `snapshot`, by path."""
    manifest = unit["files_manifest"]
    commits = subprocess.run(
        ["git", "log", "--format=%H", "--", manifest], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.split()
    for commit in commits:
        shown = subprocess.run(["git", "show", f"{commit}:{manifest}"], cwd=ROOT, capture_output=True, text=True)
        if shown.returncode != 0:
            continue
        rows = [json.loads(line) for line in shown.stdout.splitlines() if line.strip()]
        if material_snapshot_sha256(file_record(row) for row in rows) == snapshot:
            return {str(row["path"]): row for row in rows}
    return None


def policy_text() -> str:
    text = (ROOT / "CONTRIBUTING.md").read_text()
    sections = re.split(r"(?m)^(?=### )", text)
    return "\n".join(section for section in sections if section.startswith(tuple(f"### {p} " for p in BRIEF_POLICIES)))


def brief(unit: dict[str, Any], to_review: list[dict[str, Any]], carried: list[dict[str, Any]], context: list[str]) -> str:
    lines = [
        "# Repository review of one work unit",
        "",
        f"Source `{unit['repository']}` ({unit['proof_assistant']}), unit `{unit['unit_id']}`,"
        f" scope `{unit['scope']['value']}`. Your working directory is the source checkout.",
        "",
        "The corpus indexes formal mathematics for search. Each file listed below is in the",
        "primary search index and no earlier review has seen its current bytes. Decide whether",
        "any of them must leave the primary index. The default is retain: a file stays",
        "searchable unless the policies below establish that it holds no formal mathematical",
        "content relevant to search. Most units have no exclusions; say so when that is the case.",
        "",
        "Inspect the files with your read, glob, grep, and list tools only. The shell, write, edit,",
        "and network tools are unavailable, and a call to one ends your turn. Read every file that",
        "you propose to exclude completely.",
        "",
        *context,
        "",
        "## Files to review (path, bytes)",
        "",
        *(f"- `{row['path']}` ({row['size_bytes']})" for row in to_review),
    ]
    if carried:
        lines += [
            "",
            "## Exclusions already in force",
            "",
            "These files are unchanged since an earlier review excluded them. Do not name them in a rule.",
            "",
            *(f"- `{path}`: {rule['rationale']}" for rule in carried for path in rule["selector"]["paths"]),
        ]
    lines += [
        "",
        "## Answer",
        "",
        "Your final message is the answer: one JSON object and nothing else. Do not write it to a file.",
        "",
        "```json",
        "{",
        '  "summary": "what you inspected and why the retained files stay searchable",',
        '  "review_evidence": ["one concrete observation per string, naming files you read"],',
        '  "rules": [',
        "    {",
        '      "paths": ["exact file paths from the list above"],',
        '      "rationale": "why exactly these files must not occupy formal-mathematics search",',
        '      "content_invariant": "why these files hold no definition, statement, proof, or interface that search needs",',
        '      "evidence": ["what you read in each file"]',
        "    }",
        "  ]",
        "}",
        "```",
        "",
        "`rules` is `[]` when every file stays searchable. A path may appear in one rule only.",
        "",
        "## Policies",
        "",
        policy_text(),
    ]
    return "\n".join(lines) + "\n"


def opencode(message: str, *, workdir: pathlib.Path, home: pathlib.Path, attachment: pathlib.Path | None, session: str | None) -> tuple[str | None, str]:
    """Run one agent turn. Returns the session id and the text of the final reply."""
    command = ["opencode", "run", message, "-m", MODEL, "--format", "json", "--dir", str(workdir)]
    if session:
        command += ["-s", session]
    if attachment:
        command += ["-f", str(attachment)]
    env = {key: value for key, value in os.environ.items() if key != "OPENCODE_API_KEY"}
    # A user opencode configuration makes the free tier refuse requests, so every run gets a clean home.
    env.update(
        HOME=str(home),
        XDG_CONFIG_HOME=str(home / ".config"),
        XDG_DATA_HOME=str(home / ".local/share"),
        XDG_STATE_HOME=str(home / ".local/state"),
        XDG_CACHE_HOME=str(home / ".cache"),
        OPENCODE_CONFIG_CONTENT=json.dumps(PERMISSIONS),
    )
    completed = subprocess.run(command, env=env, capture_output=True, text=True, timeout=CALL_TIMEOUT_SECONDS)
    events = [json.loads(line) for line in completed.stdout.splitlines() if line.startswith("{")]
    session_id = next((event["sessionID"] for event in events if "sessionID" in event), session)
    errors = [json.dumps(event["error"])[:500] for event in events if event.get("type") == "error"]
    if errors or completed.returncode != 0:
        raise RuntimeError(f"opencode exited {completed.returncode}: {errors or completed.stderr[-500:]}")
    texts = [event["part"]["text"] for event in events if event.get("type") == "text"]
    if not texts:
        rejected = sorted(set(re.findall(r"permission requested: (\w+)", completed.stderr)))
        if rejected:
            raise RuntimeError(
                f"your call to {', '.join(rejected)} was rejected because only read, glob, grep, and list are "
                "available. You have read the files; call no more tools and reply now with the JSON answer"
            )
        raise RuntimeError("your turn ended without a final message; call no more tools and reply now with the JSON answer")
    return session_id, texts[-1]


def parse_answer(text: str) -> dict[str, Any]:
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    body = fenced.group(1) if fenced else text[text.index("{") : text.rindex("}") + 1]
    return json.loads(body)


def answer_errors(answer: dict[str, Any], reviewable: set[str]) -> list[str]:
    errors: list[str] = []
    for key in ("summary", "review_evidence", "rules"):
        if key not in answer:
            errors.append(f"the answer lacks `{key}`")
    for number, rule in enumerate(answer.get("rules") or [], start=1):
        paths = rule.get("paths")
        if not isinstance(paths, list) or not paths:
            errors.append(f"rule {number}: `paths` must be a nonempty list")
            continue
        outside = sorted(set(map(str, paths)) - reviewable)
        if outside:
            errors.append(f"rule {number}: these paths are not in the list of files to review: {outside[:10]}")
    return errors


def append(record: dict[str, Any], workdir: pathlib.Path) -> list[str]:
    path = workdir / f"{record['review_id']}.json"
    path.write_text(json.dumps(record, indent=2))
    completed = subprocess.run(
        ["python", str(ROOT / "scripts" / "repository-review.py"), "append", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return [] if completed.returncode == 0 else completed.stderr.strip().splitlines()


def carried_rules(unit: dict[str, Any], history: list[dict[str, Any]], units: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """The lapsed review's rules that stay active, restated on their exact unchanged files."""
    if not history:
        return []
    files: dict[str, list[str]] = {}
    for (repository, path), exclusion in carried_review_exclusions(units, set()).items():
        if repository == unit["repository"] and exclusion["unit_id"] == unit["unit_id"]:
            files.setdefault(exclusion["rule_id"], []).append(path)
    previous = {rule["rule_id"]: rule for rule in history[-1].get("rules", [])}
    return [
        {
            "action": "primary-exclude",
            "selector": {"kind": "path-set", "paths": sorted(paths)},
            "rationale": previous[rule_id]["rationale"],
            "content_invariant": previous[rule_id]["content_invariant"],
            "evidence": [*previous[rule_id]["evidence"], f"Restated from {history[-1]['review_id']}: every selected file is byte-identical to the reviewed file."],
            "policies": RULE_POLICIES,
        }
        for rule_id, paths in sorted(files.items())
    ]


def review_unit(unit: dict[str, Any], units: dict[str, dict[str, Any]], workdir: pathlib.Path, home: pathlib.Path) -> None:
    uid = unit["unit_id"]
    short = uid.split("-", 1)[1]
    history = load_review_history(unit["repository"], uid)
    rows = load_unit_file_records(unit)
    primary = [row for row in rows if row["baseline_primary_status"] == "primary-retained"]
    seen = reviewed_manifest(unit, history[-1]["unit_snapshot_sha256"]) if history else None
    carried = carried_rules(unit, history, units)
    if seen is None:
        to_review = primary
        context = ["No earlier review of this unit saw these files."]
    else:
        to_review = [row for row in primary if seen.get(row["path"], {}).get("sha256") != row["sha256"]]
        removed = sorted(set(seen) - {row["path"] for row in rows})
        context = [
            f"Review {history[-1]['review_id']} saw an earlier version of this unit; its summary:",
            f"> {history[-1]['summary']}",
            f"Since then {len(to_review)} primary files changed or were added and {len(removed)} files were removed.",
        ]
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "review_id": f"RRV-{short}-r{len(history) + 1}",
        "unit_id": uid,
        "repository": unit["repository"],
        "source_revision": unit.get("source_revision"),
        "unit_snapshot_sha256": unit["snapshot_sha256"],
        "supersedes": history[-1]["review_id"] if history else None,
        "status": "reviewed",
        "default_action": "retain",
        "source_action": None,
    }

    def finish(summary: str, evidence: list[str], new_rules: list[dict[str, Any]]) -> list[str]:
        rules = [*carried, *new_rules]
        for number, rule in enumerate(rules, start=1):
            rule["rule_id"] = f"RRX-{short}-{number}"
        record.update(
            summary=summary,
            review_evidence=evidence,
            rules=rules,
            recorded_at=utc_now(),
            corpus_git_commit=corpus_commit(),
        )
        return append(record, workdir)

    if not to_review:
        basis = (
            "The unit has no baseline primary-retained file"
            if not primary
            else f"Every baseline primary-retained file is byte-identical to a file that {history[-1]['review_id']} reviewed"
        )
        errors = finish(
            f"{basis}, so no unreviewed content can enter the primary index; the unit retains its material.",
            [f"Mechanical review: {len(primary)} primary-retained files, {len(carried)} restated exclusion rules."],
            [],
        )
        if errors:
            raise RuntimeError("; ".join(errors))
        print(f"{uid}: recorded mechanical review")
        return

    brief_path = workdir / f"{uid}.md"
    brief_path.write_text(brief(unit, to_review, carried, context))
    reviewable = {row["path"] for row in to_review}
    message = "Review the work unit described in the attached brief and answer as it specifies."
    session: str | None = None
    attachment: pathlib.Path | None = brief_path
    failures: list[str] = []
    for attempt in range(1, ATTEMPTS + 1):
        try:
            session, text = opencode(message, workdir=unit_root(unit), home=home, attachment=attachment, session=session)
            answer = parse_answer(text)
            errors = answer_errors(answer, reviewable)
            if not errors:
                new_rules = [
                    {
                        "action": "primary-exclude",
                        "selector": {"kind": "path-set", "paths": sorted(map(str, rule["paths"]))},
                        "rationale": rule.get("rationale"),
                        "content_invariant": rule.get("content_invariant"),
                        "evidence": rule.get("evidence"),
                        "policies": RULE_POLICIES,
                    }
                    for rule in answer["rules"]
                ]
                errors = finish(answer["summary"], answer["review_evidence"], new_rules)
        except (RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
            errors = [str(exc)]
        if not errors:
            print(f"{uid}: recorded agent review with {len(answer['rules'])} new rules")
            return
        failures.append(f"attempt {attempt}: {errors[:5]}")
        print(f"{uid}: {failures[-1]}", file=sys.stderr)
        if session is not None:
            message = "Your answer was rejected:\n" + "\n".join(errors) + "\nReply with the corrected JSON object only."
            attachment = None
    raise RuntimeError(f"{uid}: no valid review after {ATTEMPTS} attempts")


def unit_root(unit: dict[str, Any]) -> pathlib.Path:
    catalogue = json.loads((ROOT / unit["catalogue_file"]).read_text())
    return ROOT / catalogue["directory"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repository", required=True)
    parser.add_argument("--stop-after", type=float, metavar="MINUTES", help="start no new unit after this many minutes")
    args = parser.parse_args()
    deadline = None if args.stop_after is None else time.monotonic() + args.stop_after * 60
    units = load_units(active_only=True)
    pending = [
        unit
        for unit in units.values()
        if unit["repository"] == args.repository
        and unit_state(unit, (load_review_history(unit["repository"], unit["unit_id"]) or [None])[-1]) in {"pending", "lapsed"}
    ]
    if pending and not unit_root(pending[0]).is_dir():
        raise SystemExit(f"{args.repository}: source is not hydrated")
    failed: list[str] = []
    with tempfile.TemporaryDirectory() as scratch:
        workdir = pathlib.Path(scratch)
        home = workdir / "opencode-home"
        for unit in sorted(pending, key=lambda item: item["unit_id"]):
            if deadline is not None and time.monotonic() >= deadline:
                print(f"{args.repository}: stopped at the deadline")
                failed.append(unit["unit_id"])
                break
            try:
                review_unit(unit, units, workdir, home)
            except RuntimeError as exc:
                print(exc, file=sys.stderr)
                failed.append(unit["unit_id"])
    if failed:
        print(f"{args.repository}: {len(failed)} of {len(pending)} units unreviewed: {' '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
