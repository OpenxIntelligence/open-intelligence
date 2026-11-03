"""Contract tests for the issue 117 evidence catalog.

Covers the pure catalog in src/open_intelligence/evidence_catalog.py
only: load, blocked-source, version, rights, exact-bool, and FTS
lookup rules. No network, no live source, no vector index.
"""

import json
import unittest
from pathlib import Path

from open_intelligence.evidence_catalog import (
    build_index,
    fts5_available,
    load_records,
    lookup,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "evidence_catalog_fictional.json"

ALLOWED = {"metadata": {"store": "allowed", "display": "allowed"}}


def record(**overrides):
    base = {
        "id": "FICT-CIVIC-EID-0001",
        "source_kind": "civic",
        "version": "v3",
        "title": "Fictional marker zeta evidence record",
        "terms": ["fictional marker zeta"],
        "licence": "CC0-1.0",
        "link": "https://example.invalid/civic/FICT-CIVIC-EID-0001/v3",
        "permissions": ALLOWED,
    }
    base.update(overrides)
    return base


class TestEvidenceCatalog(unittest.TestCase):
    def test_fixture_loads_and_lookup_returns_granted_hit(self):
        if not fts5_available():
            self.skipTest("FTS5 unavailable")
        records = load_records(json.loads(FIXTURE.read_text()))
        conn = build_index(records)
        hits = lookup(conn, "fictional marker zeta")
        self.assertEqual(len(hits), 1)
        hit = hits[0]
        self.assertEqual(hit.id, "FICT-CIVIC-EID-0001")
        self.assertEqual(hit.version, "v3")
        self.assertEqual(hit.licence, "CC0-1.0")
        self.assertEqual(hit.availability, "available")
        self.assertEqual(hit.rights_status, "granted")
        self.assertEqual(set(hit.__dict__), {"id", "version", "licence", "availability", "link", "rights_status", "title"})

    def test_blocked_nccn_record_rejected_at_load(self):
        with self.assertRaises(ValueError):
            load_records([record(source_kind="nccn", id="FICT-NCCN-1", link="https://example.invalid/nccn/FICT-NCCN-1/v1")])

    def test_blocked_id_prefix_rejected_at_load(self):
        with self.assertRaises(ValueError):
            load_records([record(id="FICT-ONCOKB-1")])

    def test_missing_version_rejected_at_load(self):
        with self.assertRaises(ValueError):
            load_records([record(version="")])

    def test_unknown_licence_is_hold_not_lookup_hit(self):
        if not fts5_available():
            self.skipTest("FTS5 unavailable")
        conn = build_index(load_records([record(licence="UNKNOWN")]))
        self.assertEqual(lookup(conn, "fictional marker zeta"), [])

    def test_metadata_store_unknown_not_indexed(self):
        if not fts5_available():
            self.skipTest("FTS5 unavailable")
        conn = build_index(load_records([record(permissions={"metadata": {"store": "unknown", "display": "allowed"}})]))
        self.assertEqual(lookup(conn, "fictional marker zeta"), [])

    def test_display_denied_returns_title_none(self):
        if not fts5_available():
            self.skipTest("FTS5 unavailable")
        conn = build_index(load_records([record(permissions={"metadata": {"store": "allowed", "display": "denied"}})]))
        hits = lookup(conn, "fictional marker zeta")
        self.assertEqual(len(hits), 1)
        self.assertIsNone(hits[0].title)

    def test_nonbool_revoked_treated_as_revoked(self):
        if not fts5_available():
            self.skipTest("FTS5 unavailable")
        conn = build_index(load_records([record(revoked=1)]))
        self.assertEqual(lookup(conn, "fictional marker zeta"), [])

    def test_fts_injection_query_is_phrase_not_error(self):
        if not fts5_available():
            self.skipTest("FTS5 unavailable")
        conn = build_index(load_records([record()]))
        hits = lookup(conn, 'zeta" OR *')
        self.assertEqual(hits, [])

    def test_fixture_ids_all_fictional(self):
        raw = json.loads(FIXTURE.read_text())
        for item in raw:
            self.assertTrue(item["id"].startswith("FICT-"))


if __name__ == "__main__":
    unittest.main()
