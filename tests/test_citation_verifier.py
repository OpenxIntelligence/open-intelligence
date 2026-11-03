"""Contract tests for the issue 117 citation verifier.

Covers the pure verifier in src/open_intelligence/citation_verifier.py
against a fixture catalog built in-process. No network, no live
source, no claim that a source supports a clinical statement.
"""

import json
import unittest
from pathlib import Path

from open_intelligence.citation_verifier import verify_all, verify_citation
from open_intelligence.evidence_catalog import build_index, load_records

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "evidence_catalog_fictional.json"


def make_conn():
    records = load_records(json.loads(FIXTURE.read_text()))
    conn = build_index(records)
    scope = {rec.id: rec.case_id for rec in records}
    return conn, scope


class TestCitationVerifier(unittest.TestCase):
    def test_valid_citation_ok(self):
        conn, scope = make_conn()
        result = verify_citation(conn, "FICT-CIVIC-EID-0001@v3", case_id="FICT-CASE-A", record_case_scope=scope)
        self.assertTrue(result.ok)
        self.assertEqual(result.reason, "ok")

    def test_malformed_citation(self):
        conn, scope = make_conn()
        result = verify_citation(conn, "xx:not-a-real-thing", case_id="FICT-CASE-A", record_case_scope=scope)
        self.assertEqual(result.reason, "malformed")

    def test_unknown_id(self):
        conn, scope = make_conn()
        result = verify_citation(conn, "FICT-CIVIC-EID-9999@v1", case_id="FICT-CASE-A", record_case_scope=scope)
        self.assertEqual(result.reason, "unknown_id")

    def test_version_mismatch(self):
        conn, scope = make_conn()
        result = verify_citation(conn, "FICT-CIVIC-EID-0001@v7", case_id="FICT-CASE-A", record_case_scope=scope)
        self.assertEqual(result.reason, "version_mismatch")

    def test_missing_version(self):
        conn, scope = make_conn()
        result = verify_citation(conn, "FICT-CIVIC-EID-0001", case_id="FICT-CASE-A", record_case_scope=scope)
        self.assertEqual(result.reason, "no_version")

    def test_superseded_version(self):
        conn, scope = make_conn()
        result = verify_citation(conn, "FICT-NCI-0001@v1", case_id="FICT-CASE-A", record_case_scope=scope)
        self.assertEqual(result.reason, "superseded")

    def test_cross_case(self):
        conn, scope = make_conn()
        result = verify_citation(conn, "FICT-CIVIC-EID-0001@v3", case_id="FICT-CASE-B", record_case_scope=scope)
        self.assertEqual(result.reason, "cross_case")

    def test_blocked_source(self):
        conn, scope = make_conn()
        result = verify_citation(conn, "FICT-NCCN-1@v1", case_id="FICT-CASE-A", record_case_scope=scope)
        self.assertEqual(result.reason, "blocked_source")

    def test_verify_all_with_one_bad(self):
        conn, scope = make_conn()
        results = verify_all(conn, ["FICT-CIVIC-EID-0001@v3", "FICT-CIVIC-EID-9999@v1"], case_id="FICT-CASE-A", record_case_scope=scope)
        self.assertFalse(all(r.ok for r in results))


if __name__ == "__main__":
    unittest.main()
