"""Immutable inspection membership under the existing authorized report transaction."""
from datetime import datetime, timezone
import hmac
import json
import re
import uuid

from open_intelligence.patient_registry import PatientRegistryConflict, PatientRegistryDenied, _key

from .evidence_report import canonical_hash
from .laboratory_citation_report import LaboratoryCitationReport, inspection_digest
from .source_integrity import SourceIntegrityError

CAPTURE = "laboratory_snapshot_create"
FIELDS = ("snapshot_id", "patient_id", "case_id", "question_id", "origin_org", "actor", "purpose",
          "request_key", "capture_access_receipt_id", "captured_at", "captured_report_sha256", "manifest", "manifest_sha256")
LINK_FIELDS = ("link_id", "citation", "metadata_sha256", "status")
STATES = {"current_unreviewed_question", "source_reassessment_required"}
LINK_STATES = {"available", "rights_restricted", "superseded", "unavailable"}


def _manifest(report, decisions):
    citations = report["citations"]
    return {"anchor": citations["question_anchor"], "source_context_state": citations["source_context_state"],
            "links": [{**{k: link[k] for k in LINK_FIELDS}, "rights_decision_id": decisions[link["link_id"]]}
                      for link in citations["links"]]}


def _stamp(row):
    return row["captured_at"].astimezone(timezone.utc).isoformat(timespec="microseconds")


def _checksum(row):
    return canonical_hash({**{k: row[k] for k in FIELDS if k != "manifest_sha256"}, "captured_at": _stamp(row)})


def _summary(row):
    return {"snapshot_id": row["snapshot_id"], "captured_report_sha256": row["captured_report_sha256"],
            "captured_at": _stamp(row), "citation_count": len(row["manifest"]["links"]),
            "captured_source_context_state": row["manifest"]["source_context_state"]}


def _checked(row, report):
    stored = dict(zip(FIELDS, row))
    manifest = stored["manifest"]
    if (not hmac.compare_digest(stored["manifest_sha256"], _checksum(stored))
            or type(manifest) is not dict or set(manifest) != {"anchor", "source_context_state", "links"}
            or manifest["anchor"] != report["citations"]["question_anchor"]
            or manifest["source_context_state"] not in STATES or type(manifest["links"]) is not list
            or len(manifest["links"]) > 100):
        raise SourceIntegrityError("Stored laboratory snapshot is inconsistent")
    current = {r["link_id"]: r for r in report["citations"]["links"]}
    selected = []
    seen = set()
    for link in manifest["links"]:
        if (type(link) is not dict or set(link) != {*LINK_FIELDS, "rights_decision_id"}
                or not re.fullmatch(r"EVIDENCE-RIGHTS-[0-9A-F]{32}", link["rights_decision_id"])
                or link["status"] not in LINK_STATES or link["link_id"] in seen):
            raise SourceIntegrityError("Stored laboratory snapshot citation is inconsistent")
        now = current.get(link["link_id"])
        if now is None or (now["citation"], now["metadata_sha256"]) != (link["citation"], link["metadata_sha256"]):
            raise SourceIntegrityError("Stored laboratory snapshot citation no longer resolves")
        seen.add(link["link_id"])
        # A later grant must never fill in metadata absent from this snapshot.
        if now["status"] == "available" and link["status"] != "available":
            now = {**now, "status": link["status"], "record": None}
        selected.append(now)
    reopened = {**report, "citations": {**report["citations"], "links": selected}}
    reopened["report_sha256"] = inspection_digest(reopened)
    if (manifest["source_context_state"] == report["citations"]["source_context_state"]
            and all(c["status"] == now["status"] for c, now in zip(manifest["links"], selected))
            and not hmac.compare_digest(reopened["report_sha256"], stored["captured_report_sha256"])):
        raise SourceIntegrityError("Reopened laboratory snapshot does not reproduce captured content")
    return stored, reopened


class LaboratoryInspectionSnapshots:
    def __init__(self, registry):
        self.registry = registry
        self.reports = LaboratoryCitationReport(registry)

    def capture(self, patient_id, case_id, question_id, *, organization, actor, purpose,
                request_key, expected_report_sha256, recheck_authority, prepare_response):
        key = _key(request_key, "request_key")
        if type(expected_report_sha256) is not str or not re.fullmatch(r"[a-f0-9]{64}", expected_report_sha256):
            raise PatientRegistryConflict("Exact inspection digest required")

        def authority():
            recheck_authority()
            self.registry._allow(actor, patient_id, CAPTURE, purpose)

        def persist(report):
            prior = self.registry._fetchone(
                "SELECT " + ",".join(FIELDS) + " FROM investigation.laboratory_inspection_snapshots "
                "WHERE patient_id=%s AND request_key=%s FOR UPDATE", (patient_id, key))
            if prior:
                old = dict(zip(FIELDS, prior))
                if ((old["case_id"], old["question_id"], old["origin_org"], old["actor"], old["purpose"],
                     old["captured_report_sha256"]) != (case_id, question_id, organization, actor, purpose, expected_report_sha256)):
                    raise PatientRegistryConflict("Snapshot request key reused with changed intent")
                _checked(prior, report)
                return prepare_response({"snapshot_id": old["snapshot_id"], "captured_report_sha256": expected_report_sha256,
                                         "duplicate": True})
            if not hmac.compare_digest(report["report_sha256"], expected_report_sha256):
                raise PatientRegistryConflict("Inspection changed; inspect the current report before capture")
            count, = self.registry._fetchone(
                "SELECT count(*) FROM investigation.laboratory_inspection_snapshots WHERE question_id=%s", (question_id,))
            if count >= 100:
                raise PatientRegistryConflict("Inspection snapshot limit reached")
            decisions = dict(self.registry._fetchall(
                "SELECT l.link_id,d.decision_id FROM investigation.question_evidence_links l "
                "JOIN LATERAL (SELECT decision_id FROM investigation.evidence_rights_decisions "
                "WHERE record_id=l.record_id AND version=l.version ORDER BY revision DESC LIMIT 1) d ON true "
                "WHERE l.patient_id=%s AND l.case_id=%s AND l.question_id=%s AND l.origin_org=%s AND l.purpose=%s",
                (patient_id, case_id, question_id, organization, purpose)))
            identifier = "LAB-SNAPSHOT-" + uuid.uuid4().hex.upper()
            row = {"snapshot_id": identifier, "patient_id": patient_id, "case_id": case_id, "question_id": question_id,
                   "origin_org": organization, "actor": actor, "purpose": purpose, "request_key": key,
                   "capture_access_receipt_id": report["citations"]["source_access_receipt_id"],
                   "captured_at": datetime.now(timezone.utc), "captured_report_sha256": expected_report_sha256,
                   "manifest": _manifest(report, decisions)}
            row["manifest_sha256"] = _checksum(row)
            values = [row[k] if k != "manifest" else json.dumps(row[k]) for k in FIELDS]
            created = self.registry._fetchone(
                "INSERT INTO investigation.laboratory_inspection_snapshots (" + ",".join(FIELDS) + ") "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s) "
                "ON CONFLICT (patient_id,request_key) DO NOTHING RETURNING snapshot_id", tuple(values))
            if created is None:
                # Single-case writers serialize under the source owner's case lock.
                raise PatientRegistryConflict("Snapshot request key reused with changed intent")
            self.registry.append_event(patient_id, "investigation.laboratory_snapshot.captured",
                snapshot_id=identifier, case_id=case_id, question_id=question_id, actor=actor,
                captured_report_sha256=expected_report_sha256, manifest_sha256=row["manifest_sha256"],
                source_access_receipt_id=report["citations"]["source_access_receipt_id"])
            return prepare_response({"snapshot_id": identifier, "captured_report_sha256": expected_report_sha256,
                                     "duplicate": False})

        return self.reports.read(patient_id, case_id, question_id, organization=organization, actor=actor, purpose=purpose,
                                 recheck_authority=authority, prepare_response=persist)

    def read(self, patient_id, case_id, question_id, *, organization, actor, purpose,
             snapshot_id=None, recheck_authority, prepare_response):
        if snapshot_id is not None and (type(snapshot_id) is not str or
                                        not re.fullmatch(r"LAB-SNAPSHOT-[0-9A-F]{32}", snapshot_id)):
            raise PatientRegistryDenied("Laboratory snapshot unavailable")

        def project(report):
            where = "WHERE patient_id=%s AND case_id=%s AND question_id=%s AND origin_org=%s AND purpose=%s"
            scope = (patient_id, case_id, question_id, organization, purpose)
            table = " FROM investigation.laboratory_inspection_snapshots "
            select = "SELECT " + ",".join(FIELDS) + table + where
            if snapshot_id is not None:
                record = self.registry._fetchone(select + " AND snapshot_id=%s", (*scope, snapshot_id))
                if record is None:
                    raise PatientRegistryDenied("Laboratory snapshot unavailable")
                row, inspection = _checked(record, report)
                self.registry.append_event(patient_id, "investigation.laboratory_snapshot.reopened",
                    snapshot_id=snapshot_id, case_id=case_id, question_id=question_id, actor=actor,
                    captured_report_sha256=row["captured_report_sha256"], report_sha256=inspection["report_sha256"],
                    source_context_state=inspection["citations"]["source_context_state"],
                    source_access_receipt_id=inspection["citations"]["source_access_receipt_id"])
                return prepare_response({"snapshot": _summary(row), "inspection": inspection})
            rows = self.registry._fetchall(select + " ORDER BY captured_at,snapshot_id LIMIT 101", scope)
            if len(rows) > 100:
                raise SourceIntegrityError("Laboratory snapshot history exceeds bound")
            summaries = [_summary(_checked(row, report)[0]) for row in rows]
            return prepare_response({"patient_id": patient_id, "case_id": case_id, "question_id": question_id,
                                     "source_access_receipt_id": report["citations"]["source_access_receipt_id"],
                                     "snapshots": summaries})

        return self.reports.read(patient_id, case_id, question_id, organization=organization, actor=actor, purpose=purpose,
                                 recheck_authority=recheck_authority, prepare_response=project)
