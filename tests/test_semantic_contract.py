"""Reuse #606 contract cases with strict version/provenance regressions."""
import unittest
from open_intelligence.semantic_contract import Concept, Relationship, SemanticContractError, SemanticReference, SemanticRegistry


def registry():
    return SemanticRegistry((Concept('oi:observation', 1, 'Source-bound observation'),
                             Concept('oi:calculation', 1, 'Versioned derived computation')),
                            (Relationship('oi:input-to', 1, 'oi:observation', 'oi:calculation'),))


def reference(concept='oi:observation', **overrides):
    fields = dict(owner='source', record_id='record-1', concept_id=concept, concept_version=1,
                  source_version_id='version-1', knowledge_kind='reported', evidence_status='pending')
    fields.update(overrides)
    return SemanticReference(**fields)


class SemanticContractTests(unittest.TestCase):
    def test_valid_source_to_calculation(self):
        registry().validate_edge('oi:input-to', 1, reference(), reference('oi:calculation', knowledge_kind='calculated'))

    def test_invalid_references_fail_closed(self):
        for field, value, reason in [('concept_version', 2, 'unknown_concept_version'),
            ('concept_version', True, 'unknown_concept_version'), ('concept_version', 1.0, 'unknown_concept_version'),
            ('owner', ' ', 'missing_provenance'), ('source_version_id', '', 'missing_provenance'),
            ('knowledge_kind', 'reviewed', 'invalid_knowledge_kind'), ('evidence_status', 'normal', 'invalid_evidence_status')]:
            with self.subTest(field=field, value=value), self.assertRaises(SemanticContractError) as error:
                registry().validate_reference(reference(**{field:value}))
            self.assertEqual(error.exception.code, reason)

    def test_reversed_relation_fails(self):
        with self.assertRaises(SemanticContractError):
            registry().validate_edge('oi:input-to', 1, reference('oi:calculation'), reference())

    def test_unknown_and_coerced_versions_fail(self):
        for version in (2, True, 1.0):
            with self.subTest(version=version), self.assertRaises(SemanticContractError):
                registry().validate_edge('oi:input-to', version, reference(), reference('oi:calculation'))

    def test_duplicate_and_invalid_concepts_fail(self):
        c = Concept('oi:observation', 1, 'Source-bound observation')
        for concepts in ((c,c), (Concept('oi:observation', True, 'Invalid version'),)):
            with self.assertRaises(SemanticContractError):
                SemanticRegistry(concepts, ())
