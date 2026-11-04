"""Adversarial regression for the reused #224 metadata contract.

Independently authored fictional metadata only. These tests exercise the real
in-memory reference index and pure contract; they make no biomedical claims.
"""

from dataclasses import replace
import unittest

from open_intelligence import citation_verifier, evidence_catalog

from open_intelligence.citation_verifier import verify_citation
from open_intelligence.evidence_catalog import (
    build_index, load_records, lookup, rights_status,
)


def fictional_record(**changes):
    result = {
        "id": "FICT-RECORD-1", "source_kind": "fictional", "version": "v1",
        "title": "Independent fictional evidence metadata",
        "terms": ["fictional alpha"], "licence": "fictional-project-fixture",
        "link": "https://example.invalid/fictional/FICT-RECORD-1/v1",
        "permissions": {"metadata": {"store": "allowed", "display": "allowed"}},
    }
    result.update(changes)
    return result


class CatalogBoundaryRegressionTests(unittest.TestCase):
    def index(self, *records):
        conn = build_index(load_records(list(records)))
        self.addCleanup(conn.close)
        return conn

    def test_stored_case_scope_blocks_verification_without_external_map(self):
        conn = self.index(fictional_record(case_id="FICT-CASE-A", organization="FICT-ORG-A"))
        result = verify_citation(conn, "FICT-RECORD-1@v1", case_id="FICT-CASE-B")
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "cross_case")

    def test_external_scope_map_cannot_replace_stored_case_scope(self):
        conn = self.index(fictional_record(case_id="FICT-CASE-A", organization="FICT-ORG-A"))
        result = verify_citation(
            conn, "FICT-RECORD-1@v1", case_id="FICT-CASE-B",
            record_case_scope={"FICT-RECORD-1": "FICT-CASE-B"},
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "cross_case")

    def test_lookup_without_context_never_discloses_case_bound_metadata(self):
        conn = self.index(fictional_record(case_id="FICT-CASE-A", organization="FICT-ORG-A"))
        self.assertEqual(lookup(conn, "fictional alpha"), [])

    def test_search_terms_resolve_only_the_exact_matching_version(self):
        conn = self.index(
            fictional_record(),
            fictional_record(version="v2", terms=["fictional beta"],
                             link="https://example.invalid/fictional/FICT-RECORD-1/v2"),
        )
        self.assertEqual([hit.version for hit in lookup(conn, "fictional alpha")], ["v1"])
        self.assertEqual([hit.version for hit in lookup(conn, "fictional beta")], ["v2"])

    def test_explicit_null_revocation_or_supersession_never_grants_metadata(self):
        for field in ("revoked", "superseded"):
            with self.subTest(field=field):
                record = load_records([fictional_record(**{field: None})])[0]
                self.assertNotEqual(rights_status(record), "granted")
                conn = build_index([record])
                self.addCleanup(conn.close)
                self.assertEqual(lookup(conn, "fictional alpha"), [])

    def test_lookup_and_get_require_exact_organization_and_case(self):
        conn = self.index(fictional_record(case_id="FICT-CASE-A", organization="FICT-ORG-A"))
        for case, organization in (("FICT-CASE-A", "FICT-ORG-B"),
                                   ("FICT-CASE-B", "FICT-ORG-A"),
                                   ("FICT-CASE-A", None)):
            with self.subTest(case=case, organization=organization):
                self.assertEqual(lookup(conn, "fictional alpha", case_id=case,
                                        organization=organization), [])
                self.assertIsNone(evidence_catalog.get(
                    conn, "FICT-RECORD-1", "v1", case_id=case, organization=organization))
        hit = evidence_catalog.get(conn, "FICT-RECORD-1", "v1",
                                   case_id="FICT-CASE-A", organization="FICT-ORG-A")
        self.assertIsNotNone(hit)
        self.assertEqual((hit.case_id, hit.organization), ("FICT-CASE-A", "FICT-ORG-A"))

    def test_scoped_search_terms_do_not_bleed_between_tenants(self):
        conn = self.index(
            fictional_record(case_id="FICT-CASE-A", organization="FICT-ORG-A"),
            fictional_record(case_id="FICT-CASE-A", organization="FICT-ORG-B",
                             terms=["fictional beta"], title="Other fictional organization"),
        )
        self.assertEqual(lookup(conn, "fictional alpha", case_id="FICT-CASE-A",
                                organization="FICT-ORG-B"), [])
        self.assertEqual([hit.title for hit in lookup(
            conn, "fictional beta", case_id="FICT-CASE-A", organization="FICT-ORG-B")],
            ["Other fictional organization"])

    def test_partial_or_malformed_record_scope_is_rejected(self):
        for changes in ({"case_id": "FICT-CASE-A"}, {"organization": "FICT-ORG-A"},
                        {"case_id": "", "organization": "FICT-ORG-A"},
                        {"case_id": 1, "organization": "FICT-ORG-A"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                load_records([fictional_record(**changes)])

    def test_duplicate_exact_record_identity_is_rejected_not_arbitrarily_verified(self):
        with self.assertRaises(ValueError):
            self.index(fictional_record(), fictional_record(title="Conflicting fictional title"))


class PureEvidenceContractTests(unittest.TestCase):
    CONTEXT = {"case_id": "FICT-CASE-A", "organization": "FICT-ORG-A"}

    def function(self, module, name):
        function = getattr(module, name, None)
        self.assertTrue(callable(function), f"Shared {name} behavior is required by the H1 adapter")
        return function

    def record(self, **changes):
        return load_records([fictional_record(**changes)])[0]

    def test_global_metadata_is_available_without_inventing_patient_scope(self):
        metadata_hit = self.function(evidence_catalog, "metadata_hit")
        hit = metadata_hit(self.record(), **self.CONTEXT)
        self.assertIsNotNone(hit)
        self.assertEqual(hit.title, "Independent fictional evidence metadata")
        self.assertEqual((hit.case_id, hit.organization), (None, None))

    def test_metadata_disclosure_gates_display_separately_from_storage(self):
        metadata_hit = self.function(evidence_catalog, "metadata_hit")
        record = self.record(permissions={"metadata": {"store": "allowed", "display": "denied"}})
        self.assertIsNone(metadata_hit(record, **self.CONTEXT).title)
        denied = self.record(permissions={"metadata": {"store": "denied", "display": "allowed"}})
        self.assertIsNone(metadata_hit(denied, **self.CONTEXT))

    def test_false_lifecycle_flags_alone_never_grant_metadata_or_citation(self):
        metadata_hit = self.function(evidence_catalog, "metadata_hit")
        verify_record = self.function(citation_verifier, "verify_record")
        record = self.record(permissions={}, revoked=False, superseded=False)
        self.assertIsNone(metadata_hit(record, **self.CONTEXT))
        self.assertEqual(verify_record(record, "FICT-RECORD-1@v1", **self.CONTEXT).reason, "rights_hold")

    def test_direct_record_malformed_flags_fail_closed(self):
        metadata_hit = self.function(evidence_catalog, "metadata_hit")
        verify_record = self.function(citation_verifier, "verify_record")
        for field in ("revoked", "superseded"):
            for value in (None, 0, 1, "false", [], {}):
                with self.subTest(field=field, value=value):
                    record = replace(self.record(), **{field: value})
                    self.assertIsNone(metadata_hit(record, **self.CONTEXT))
                    self.assertFalse(verify_record(record, "FICT-RECORD-1@v1", **self.CONTEXT).ok)

    def test_scoped_record_is_verified_only_in_exact_case_and_organization(self):
        verify_record = self.function(citation_verifier, "verify_record")
        metadata_hit = self.function(evidence_catalog, "metadata_hit")
        record = self.record(**self.CONTEXT)
        self.assertTrue(verify_record(record, "FICT-RECORD-1@v1", **self.CONTEXT).ok)
        for context, reason in (({"case_id": "FICT-CASE-B", "organization": "FICT-ORG-A"}, "cross_case"),
                                ({"case_id": "FICT-CASE-A", "organization": "FICT-ORG-B"}, "cross_organization")):
            with self.subTest(context=context):
                self.assertIsNone(metadata_hit(record, **context))
                self.assertEqual(verify_record(record, "FICT-RECORD-1@v1", **context).reason, reason)

    def test_citation_verification_preserves_version_and_availability_reasons(self):
        verify_record = self.function(citation_verifier, "verify_record")
        for record, citation, reason in (
            (self.record(), "FICT-RECORD-1@v2", "version_mismatch"),
            (self.record(), "FICT-OTHER@v1", "unknown_id"),
            (self.record(), "FICT-RECORD-1", "no_version"),
            (self.record(revoked=True), "FICT-RECORD-1@v1", "revoked"),
            (self.record(superseded=True), "FICT-RECORD-1@v1", "superseded"),
            (None, "FICT-RECORD-1@v1", "unknown_id"),
        ):
            with self.subTest(citation=citation, reason=reason):
                result = verify_record(record, citation, **self.CONTEXT)
                self.assertFalse(result.ok)
                self.assertEqual(result.reason, reason)

    def test_fingerprint_changes_with_metadata_but_not_rights_history(self):
        fingerprint = self.function(evidence_catalog, "record_fingerprint")
        record = self.record()
        baseline = fingerprint(record)
        self.assertEqual(len(baseline), 64)
        self.assertEqual(baseline, fingerprint(replace(record, revoked=True)))
        self.assertEqual(baseline, fingerprint(replace(record, superseded=True, permissions={})))
        for changes in ({"licence": "different-fictional-licence"}, {"version": "v2"},
                        {"title": "Different exact fictional title"}, {"terms": ("fictional beta",)},
                        {"link": "https://example.invalid/different"},
                        {"case_id": "FICT-CASE-A", "organization": "FICT-ORG-A"}):
            with self.subTest(changes=changes):
                self.assertNotEqual(baseline, fingerprint(replace(record, **changes)))

    def test_non_string_or_malformed_metadata_is_not_disclosed(self):
        metadata_hit = self.function(evidence_catalog, "metadata_hit")
        for changes in ({"title": None}, {"licence": None}, {"terms": "fictional alpha"},
                        {"source_kind": "unregistered"}, {"permissions": {"metadata": {"store": True}}}):
            with self.subTest(changes=changes):
                self.assertIsNone(metadata_hit(replace(self.record(), **changes), **self.CONTEXT))

    def test_doi_version_is_not_swallowed_by_identifier_parser(self):
        self.assertEqual(citation_verifier.parse_citation("10.1234/fictional-record@v2"),
                         ("10.1234/fictional-record", "v2"))


if __name__ == "__main__":
    unittest.main()
