"""Semantic contract regressions, compatible with repository unittest discovery."""
import unittest

from open_intelligence.semantic_contract import (
    Concept, Relationship, SemanticContractError, SemanticReference, SemanticRegistry,
)


def registry():
    return SemanticRegistry(
        (Concept("oi:observation", 1, "Source-bound observation"),
         Concept("oi:calculation", 1, "Versioned derived computation")),
        (Relationship("oi:input-to", 1, "oi:observation", "oi:calculation"),),
    )


def reference(concept="oi:observation", **overrides):
    fields = dict(owner="source", record_id="record-1", concept_id=concept,
                  concept_version=1, source_version_id="version-1",
                  knowledge_kind="reported", evidence_status="pending")
    fields.update(overrides)
    return SemanticReference(**fields)


class SemanticContractTests(unittest.TestCase):
    def assert_rejected(self, reason, callback):
        with self.assertRaises(SemanticContractError) as error:
            callback()
        self.assertEqual(error.exception.code, reason)

    def test_valid_source_to_calculation(self):
        registry().validate_edge(
            "oi:input-to", 1, reference(),
            reference("oi:calculation", owner="calculation", knowledge_kind="calculated"),
        )

    def test_invalid_reference_fails_closed(self):
        for field, value, reason in (
            ("concept_version", 2, "unknown_concept_version"),
            ("source_version_id", "", "missing_provenance"),
            ("knowledge_kind", "reviewed", "invalid_knowledge_kind"),
            ("evidence_status", "normal", "invalid_evidence_status"),
        ):
            with self.subTest(field=field, value=value):
                self.assert_rejected(reason, lambda: registry().validate_reference(reference(**{field: value})))

    def test_invalid_relationship_direction(self):
        self.assert_rejected("relationship_domain_range_mismatch",
                             lambda: registry().validate_edge("oi:input-to", 1,
                                                              reference("oi:calculation"), reference()))

    def test_unknown_relationship_version(self):
        self.assert_rejected("unknown_relationship_version",
                             lambda: registry().validate_edge("oi:input-to", 2, reference(),
                                                              reference("oi:calculation")))

    def test_duplicate_concept_rejected(self):
        c = Concept("oi:observation", 1, "Source-bound observation")
        self.assert_rejected("duplicate_concept", lambda: SemanticRegistry((c, c), ()))

    def test_invalid_concept_versions(self):
        for bad in (0, -1, True, 1.0, "1"):
            with self.subTest(version=bad):
                self.assert_rejected("invalid_concept",
                                     lambda: SemanticRegistry((Concept("oi:observation", bad, "Observation"),), ()))

    def test_malformed_semantic_identifiers(self):
        for bad in ("", ":observation", "oi:", " oi:observation", "oi:observation "):
            with self.subTest(identifier=bad):
                self.assert_rejected("invalid_semantic_id",
                                     lambda: SemanticRegistry((Concept(bad, 1, "Observation"),), ()))

    def test_whitespace_only_provenance(self):
        for field in ("owner", "record_id", "source_version_id"):
            with self.subTest(field=field):
                self.assert_rejected("missing_provenance",
                                     lambda: registry().validate_reference(reference(**{field: "  "})))

    def test_invalid_relationship_version(self):
        self.assert_rejected("invalid_relationship", lambda: SemanticRegistry(
            (Concept("oi:observation", 1, "Observation"),),
            (Relationship("oi:self", True, "oi:observation", "oi:observation"),),
        ))


if __name__ == "__main__":
    unittest.main()
