"""Read-only inspection of the saved laboratory Observation and permitted citation metadata.

The source owner validates the original FHIR bytes and their typed children for every
version in the case before this projection runs. The evidence owner rechecks current
rights after response encoding and receipt insertion. No extracted title, result,
report version, clinician decision or diagnostic interpretation is persisted here.
"""
import hashlib
import hmac

from open_intelligence.patient_registry import PatientRegistryDenied

from .composer_preflight import laboratory_preflight_payload
from .evidence_report import canonical_hash
from .question_evidence import PostgresLaboratoryQuestionEvidence
from .source_integrity import SourceIntegrityError


REPORT_CONTRACT = "oi.laboratory-source-citation-inspection/2"
REPORT_ACTIONS = ("source_read", "question_read", "evidence_read", "review_packet_read")


def inspection_digest(report: dict) -> str:
    """Identify the inspected content across repeated authorized reads.

    Each disclosure receives its own source access receipt. All other report
    fields, including citation order, redactions and source freshness, belong
    to the content being identified.
    """
    content = {key: value for key, value in report.items() if key != "report_sha256"}
    content["citations"] = {key: value for key, value in report["citations"].items()
                            if key != "source_access_receipt_id"}
    return canonical_hash(content)


def membership_digest(citations):
    # Link identifiers and status enums never contain a colon or newline.
    # PostgreSQL verifies this ordered manifest against the report event.
    lines = [link["link_id"] + ":" + link["status"] for link in citations["links"]]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


class LaboratoryCitationReport:
    def __init__(self, registry):
        self.evidence = PostgresLaboratoryQuestionEvidence(registry)
        self.registry = registry

    def read(self, patient_id, case_id, question_id, *, organization, actor, purpose,
             recheck_authority, prepare_response):
        def authority():
            recheck_authority()
            self.registry._allow(actor, patient_id, "review_packet_read", purpose)

        def project(question, citations):
            if not self.registry._transaction_active:
                raise RuntimeError("Report requires the source and evidence owner transaction")
            anchor = citations["question_anchor"]
            # Never select by the reusable Observation reference alone, or substitute a
            # newer version. Match the qualified source subject to the active case too.
            row = self.registry._fetchone(
                "SELECT s.document_id,s.state,f.specimen_reference,f.specimen_type_text,"
                "f.specimen_collected_at,f.report_reference,o.loinc_code,o.effective_at,"
                "o.issued_at,o.status,o.value_text,o.unit_code,o.absent_reason,o.coded_result "
                "FROM clinical_source.source_versions s "
                "JOIN clinical_source.fhir_laboratory_sources f USING (source_id) "
                "JOIN clinical_source.fhir_laboratory_observations o USING (source_id) "
                "JOIN coordination.patient_case_bindings b ON b.case_id=s.case_id "
                "AND b.source_organization=f.source_organization AND b.source_system=f.source_system "
                "AND 'Patient/' || b.source_subject_ref=f.subject_reference "
                "WHERE b.patient_id=%s AND b.case_id=%s AND b.origin_org=%s AND b.purpose=%s "
                "AND b.status='active' AND s.source_id=%s AND s.version=%s AND s.sha256=%s "
                "AND o.observation_reference=%s",
                (patient_id, case_id, organization, purpose, anchor["source_id"],
                 anchor["source_version"], anchor["source_sha256"], anchor["observation_reference"]),
            )
            if row is None:
                raise PatientRegistryDenied("Source-bound inspection unavailable")
            if (row[1] == "superseded"
                    and citations["source_context_state"] != "source_reassessment_required"):
                raise SourceIntegrityError("Inconsistent laboratory source freshness")
            result = {
                "anchor_kind": "fhir_observation", "kind": "laboratory",
                "source_id": anchor["source_id"], "document_id": row[0],
                "version": anchor["source_version"], "sha256": anchor["source_sha256"],
                "resource_reference": anchor["observation_reference"],
                "specimen_reference": row[2], "specimen_type_text": row[3],
                "specimen_collected_at": row[4].isoformat(), "report_reference": row[5],
                "loinc_code": row[6], "effective_at": row[7].isoformat(), "issued_at": row[8].isoformat(),
                "status": row[9], "value_text": row[10], "unit_code": row[11], "absent_reason": row[12],
                **({"coded_result": row[13]} if row[13] is not None else {}),
                "source_reported": True, "review_state": "not_established", "clinical_review": "not_performed",
            }
            # Same serializer used by the original save. This binds literal numeric
            # precision, absence or coding, units, report, specimen, timestamps and wording,
            # even after this source stops appearing in the current World Model.
            original = laboratory_preflight_payload(patient_id, case_id, question["question"],
                                                    anchor["source_snapshot_sha256"], result)
            if not hmac.compare_digest(original["preflight_sha256"], anchor["preflight_sha256"]):
                raise SourceIntegrityError("Saved laboratory preparation no longer matches its original")
            report = {"contract": REPORT_CONTRACT, "question": question["question"],
                      "reported_result": result, "citations": citations,
                      "clinical_review": "not_performed", "claim_appraisal": "not_performed"}
            report["report_sha256"] = inspection_digest(report)
            self.registry.append_event(
                patient_id, "investigation.laboratory_citation_report.read_authorized",
                report_sha256=report["report_sha256"],
                source_context_state=citations["source_context_state"], membership_sha256=membership_digest(citations),
                case_id=case_id, question_id=question_id, actor=actor,
                source_access_receipt_id=citations["source_access_receipt_id"],
                source_id=anchor["source_id"], observation_reference=anchor["observation_reference"],
            )
            return report

        return self.evidence.links(
            patient_id, case_id, question_id, organization=organization, actor=actor, purpose=purpose,
            project_links=project, recheck_authority=authority, prepare_response=prepare_response,
        )
