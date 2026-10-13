#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sqlite3
import sys
import tempfile
import unittest
import hashlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import corpus_fts5  # noqa: E402
import evaluate_corpus_fts5  # noqa: E402


class CorpusFts5Tests(unittest.TestCase):
    def make_db(self) -> tuple[tempfile.TemporaryDirectory[str], pathlib.Path, sqlite3.Connection]:
        temporary = tempfile.TemporaryDirectory()
        path = pathlib.Path(temporary.name) / "test.sqlite"
        db = sqlite3.connect(path)
        corpus_fts5.create_schema(db)
        rows = [
            ("source_a", "Algebra/HenselLemma.lean", "complete discrete valuation ring hensel root lifting"),
            ("source_b", "Topology/Covering.lean", "fundamental group covering space monodromy"),
            ("source_c", "Misc/Valuation.lean", "valuation ring arithmetic"),
        ]
        for number, (repository, file_name, content) in enumerate(rows, start=1):
            db.execute(
                "INSERT INTO docs_meta(rowid, repository, path, sha256, proof_assistant, source_revision) "
                "VALUES (?, ?, ?, ?, 'lean', 'rev')",
                (number, repository, file_name, f"hash-{number}"),
            )
            db.execute(
                "INSERT INTO docs(rowid, source, path, content) VALUES (?, ?, ?, ?)",
                (number, repository, file_name, content),
            )
        db.commit()
        return temporary, path, db

    def test_manifest_replays_current_filter_state_over_frozen_review_status(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        try:
            root = pathlib.Path(temporary.name)
            files = root / "filtering/repository-review/files/example"
            files.mkdir(parents=True)
            file_manifest = files / "RRU-test.jsonl"
            file_manifest.write_text(
                '{"formal_source":true,"path":"Keep.lean","sha256":"keep","size_bytes":10,'
                '"current_primary_status":"primary-retained"}\n'
                '{"formal_source":true,"path":"LaterExcluded.lean","sha256":"drop","size_bytes":20,'
                '"current_primary_status":"primary-retained"}\n'
                '{"formal_source":false,"path":"README.md","sha256":"readme","size_bytes":30,'
                '"current_primary_status":"unindexed-nonformal"}\n'
            )
            source_catalogue = root / "filtering/repository-review/catalogue-example.json"
            source_catalogue.write_text(
                '{"work_units":[{"files_manifest":'
                '"filtering/repository-review/files/example/RRU-test.jsonl"}]}'
            )
            catalogue = root / "filtering/repository-review/catalogue.jsonl"
            catalogue.write_text(
                '{"repository":"example","proof_assistant":"lean","source_revision":"rev",'
                '"catalogue_file":"filtering/repository-review/catalogue-example.json"}\n'
            )
            filter_state = root / "filtering/current.jsonl"
            filter_state.write_text(
                '{"repository":"example","file":"LaterExcluded.lean","primary":"exclude"}\n'
            )
            rows = list(
                corpus_fts5.iter_manifest_files(
                    root=root,
                    catalogue=catalogue,
                    filter_state=filter_state,
                )
            )
            self.assertEqual(
                [(row.repository, row.path) for row in rows],
                [("example", "Keep.lean")],
            )
        finally:
            temporary.cleanup()

    def test_bm25_all_finds_matching_owner(self) -> None:
        temporary, _path, db = self.make_db()
        try:
            results = corpus_fts5.query_index(
                db,
                terms=["hensel", "complete", "dvr"],
                top=10,
                mode="bm25-all",
            )
            self.assertEqual(results[0]["Repository"], "source_a")
            self.assertEqual(results[0]["FileName"], "Algebra/HenselLemma.lean")
        finally:
            db.close()
            temporary.cleanup()

    def test_path_prefix_rrf_recovers_camelcase_module_tokens(self) -> None:
        temporary, _path, db = self.make_db()
        try:
            results = corpus_fts5.query_index(
                db,
                terms=["hensel"],
                top=10,
                mode="bm25-path-prefix-rrf",
            )
            self.assertEqual(results[0]["Repository"], "source_a")
            self.assertIn("path-prefix", results[0]["FieldRanks"])
        finally:
            db.close()
            temporary.cleanup()

    def test_fielded_rrf_preserves_path_and_content_evidence(self) -> None:
        temporary, _path, db = self.make_db()
        try:
            results = corpus_fts5.query_index(
                db,
                terms=["covering", "fundamental", "group"],
                top=10,
                mode="fielded-rrf",
            )
            self.assertEqual(results[0]["Repository"], "source_b")
            self.assertIn("path", results[0]["FieldRanks"])
            self.assertIn("content", results[0]["FieldRanks"])
        finally:
            db.close()
            temporary.cleanup()

    def test_source_hierarchy_promotes_owner_inside_best_matching_repository(self) -> None:
        results = [
            {"Repository": "source_a", "FileName": "mention.lean", "Score": 9.0},
            {"Repository": "source_b", "FileName": "other.lean", "Score": 8.0},
            {"Repository": "source_a", "FileName": "owner.lean", "Score": 7.0},
        ]
        ranked = evaluate_corpus_fts5.add_fts5_source_hierarchy(
            results,
            rrf_constant=60,
        )
        self.assertEqual(
            [(item["Repository"], item["FileName"]) for item in ranked],
            [
                ("source_a", "mention.lean"),
                ("source_a", "owner.lean"),
                ("source_b", "other.lean"),
            ],
        )
        owner = ranked[1]
        self.assertEqual(owner["SourceHierarchyRank"], 1)
        self.assertEqual(
            owner["FirstStageRankEvidence"],
            {"corpus-fts5": 3, "source-hierarchy": 1},
        )

    def test_fts_match_quotes_terms_and_rejects_unknown_fields(self) -> None:
        self.assertEqual(
            corpus_fts5.fts_match(["foo", 'bar"baz'], field="path"),
            'path : "foo" OR path : "bar""baz"',
        )
        with self.assertRaises(ValueError):
            corpus_fts5.fts_match(["foo"], field="unknown")

    def test_exact_zoekt_pattern_anchors_root_level_file(self) -> None:
        self.assertEqual(
            corpus_fts5._exact_quoted_pattern("doc.lisp"),
            '"^doc\\\\.lisp$"',
        )

    def test_decode_file_distinguishes_zoekt_noncontent_sentinel(self) -> None:
        raw = b"NOT-INDEXED: exceeds the maximum size limit"
        item = {
            "Repository": "example",
            "FileName": "Huge.lean",
            "Content": __import__("base64").b64encode(raw).decode(),
        }
        fetched = corpus_fts5._decode_file(
            item,
            expected_repository="example",
            expected_path="Huge.lean",
            expected_sha256="0" * 64,
        )
        self.assertEqual(fetched.raw, raw)
        self.assertTrue(fetched.representation.startswith("zoekt-sentinel:"))

    def test_decode_file_rejects_unexplained_hash_mismatch(self) -> None:
        raw = b"different source bytes"
        item = {
            "Repository": "example",
            "FileName": "Changed.lean",
            "Content": __import__("base64").b64encode(raw).decode(),
        }
        with self.assertRaisesRegex(ValueError, "content hash mismatch"):
            corpus_fts5._decode_file(
                item,
                expected_repository="example",
                expected_path="Changed.lean",
                expected_sha256=hashlib.sha256(b"expected").hexdigest(),
            )

    def test_decode_file_accepts_relative_git_symlink_target(self) -> None:
        raw = b"../../../../tutorial/problems/wordcountProofScript.sml"
        item = {
            "Repository": "example",
            "FileName": "wordcountProofScript.sml",
            "Content": __import__("base64").b64encode(raw).decode(),
        }
        fetched = corpus_fts5._decode_file(
            item,
            expected_repository="example",
            expected_path="wordcountProofScript.sml",
            expected_sha256=hashlib.sha256(b"dereferenced source").hexdigest(),
        )
        self.assertEqual(fetched.raw, raw)
        self.assertEqual(fetched.representation, "git-symlink-target")

    def test_schema_v1_rows_are_migrated_as_verified_source_content(self) -> None:
        db = sqlite3.connect(":memory:")
        try:
            db.execute(
                "CREATE TABLE docs_meta ("
                "rowid INTEGER PRIMARY KEY, repository TEXT NOT NULL, path TEXT NOT NULL, "
                "sha256 TEXT NOT NULL, proof_assistant TEXT NOT NULL, "
                "source_revision TEXT NOT NULL, UNIQUE(repository, path))"
            )
            db.execute(
                "INSERT INTO docs_meta(repository,path,sha256,proof_assistant,source_revision) "
                "VALUES ('example','A.lean','abc','lean','rev')"
            )
            db.commit()
            corpus_fts5.create_schema(db)
            row = db.execute(
                "SELECT indexed_sha256, representation FROM docs_meta"
            ).fetchone()
            self.assertEqual(row, ("abc", "source-content"))
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
