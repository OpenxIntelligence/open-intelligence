"""First contract regressions: no clinical inference or permission elevation."""
import pytest

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


def test_valid_source_to_calculation():
    r = registry()
    r.validate_edge("oi:input-to", 1, reference(),
                    reference("oi:calculation", owner="calculation", knowledge_kind="calculated"))


@pytest.mark.parametrize("field,value,reason", [
    ("concept_version", 2, "unknown_concept_version"),
    ("source_version_id", "", "missing_provenance"),
    ("knowledge_kind", "reviewed", "invalid_knowledge_kind"),
    ("evidence_status", "normal", "invalid_evidence_status"),
])
def test_invalid_reference_fails_closed(field, value, reason):
    with pytest.raises(SemanticContractError) as error:
        registry().validate_reference(reference(**{field: value}))
    assert error.value.code == reason


def test_invalid_relationship_direction():
    with pytest.raises(SemanticContractError) as error:
        registry().validate_edge("oi:input-to", 1,
                                 reference("oi:calculation"),
                                 reference("oi:observation"))
    assert error.value.code == "relationship_domain_range_mismatch"


def test_unknown_relationship_version():
    with pytest.raises(SemanticContractError) as error:
        registry().validate_edge("oi:input-to", 2, reference(), reference("oi:calculation"))
    assert error.value.code == "unknown_relationship_version"


def test_duplicate_concept_rejected():
    c = Concept("oi:observation", 1, "Source-bound observation")
    with pytest.raises(SemanticContractError) as error:
        SemanticRegistry((c, c), ())
    assert error.value.code == "duplicate_concept"


@pytest.mark.parametrize("bad_version", [0, -1, True, 1.0, "1"])
def test_reject_invalid_concept_versions(bad_version):
    with pytest.raises(SemanticContractError) as error:
        SemanticRegistry((Concept("oi:observation", bad_version, "Observation"),), ())
    assert error.value.code == "invalid_concept"


@pytest.mark.parametrize("bad_id", ["", ":observation", "oi:", " oi:observation", "oi:observation "])
def test_reject_malformed_semantic_identifiers(bad_id):
    with pytest.raises(SemanticContractError) as error:
        SemanticRegistry((Concept(bad_id, 1, "Observation"),), ())
    assert error.value.code == "invalid_semantic_id"


@pytest.mark.parametrize("field", ["owner", "record_id", "source_version_id"])
def test_reject_whitespace_only_provenance(field):
    with pytest.raises(SemanticContractError) as error:
        registry().validate_reference(reference(**{field: "  "}))
    assert error.value.code == "missing_provenance"


def test_reject_invalid_relationship_version():
    with pytest.raises(SemanticContractError) as error:
        SemanticRegistry(
            (Concept("oi:observation", 1, "Observation"),),
            (Relationship("oi:self", True, "oi:observation", "oi:observation"),),
        )
    assert error.value.code == "invalid_relationship"
