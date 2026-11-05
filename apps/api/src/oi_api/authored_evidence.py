"""Case-owned evidence over the canonical H1 patient/source transaction boundary.

No second chart, global evidence catalog, model context, or clinical review owner.
All supported mutations share the source owner's case lock. Append-only originals,
proposals and reports remain recoverable; current disclosure is rights checked.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timezone
import hashlib
import hmac
import json
import re
import uuid

from open_intelligence.patient_registry import PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError, _key
from open_intelligence.postgres_registry import PostgresPatientRegistry
from open_intelligence.rights import normalize_permissions, permitted, validate_content_item
from open_intelligence.store import InvalidInput, parse_report, parse_synthetic_evidence

from .case_bindings import _case_id
from .composer_preflight import PostgresSourceComposerPreflight
from .authored_evidence_contracts import (AssessEvidence, EvidenceAssessment, EvidenceVersion,
                                 PrepareEvidenceReport, checked_report_snapshot)
from .evidence_report import (canonical_hash, canonical_json, human_content_allowed,
                              packet_hash, quote_offset, render_evidence_report, visible_line)
from .source_question_contracts import QuestionSourceState
from .question_review_returns import _question_id
from .source_questions import PostgresSourceQuestions
from .source_world_model import project_source_world_model
from .sources import PostgresSourceVersions
from .question_passages import QuestionPassages, reference_audit

MAX_EVIDENCE = 100
MAX_ASSESSMENTS = 200
MAX_REPORTS = 100
FLAGS = {"synthetic": True, "human_review_state": "not_performed",
         "clinical_approval": False, "model_executed": False}
VERSION_FIELDS = ("evidence_id", "evidence_key", "version", "sha256", "statement_line", "content_item",
                  "rights_sha256", "permissions", "title", "issued_at", "statement", "created_at")
ASSESSMENT_FIELDS = ("assessment_id", "question_id", "evidence_id", "evidence_sha256", "rights_sha256",
                     "source_snapshot_sha256", "preflight_sha256", "relation", "applicability",
                     "quote", "quote_start", "rationale", "actor_label", "created_at")


def _id(value: str, prefix: str) -> str:
    if type(value) is not str or re.fullmatch(prefix + r"-[0-9A-F]{32}", value) is None:
        raise PatientRegistryError("Invalid evidence reference")
    return value


def _time(value) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise RuntimeError("Stored evidence timestamp integrity failed")
    return value.isoformat()


def _new(prefix: str) -> str:
    return prefix + "-" + uuid.uuid4().hex.upper()


class PostgresQuestionEvidence:
    def __init__(self, registry: PostgresPatientRegistry):
        if not isinstance(registry, PostgresPatientRegistry):
            raise TypeError("Canonical PostgreSQL patient registry required")
        self.registry = registry

    def _run(self, patient_id, case_id, question_id, *, organization, actor, purpose,
             action, operation, recheck_authority, prepare_response, recheck_original_authority=None):
        patient_id = _key(patient_id, "patient_id")
        case_id = _case_id(case_id)
        question_id = _question_id(question_id)
        organization, actor = _key(organization, "organization"), _key(actor, "actor")
        if purpose != "operations":
            raise PatientRegistryDenied("Evidence unavailable")
        needs_original = False
        prepared_context = None
        def require_original():
            nonlocal needs_original
            needs_original = True
            self.registry._allow(actor, patient_id, 'source_original_read', purpose)
        def recheck():
            recheck_authority()
            if needs_original:
                require_original()
                if recheck_original_authority is not None:
                    recheck_original_authority()

        def prepare(index):
            nonlocal prepared_context
            for permission in {"patient_read", "source_read", "question_read", "authored_evidence_read", action}:
                self.registry._allow(actor, patient_id, permission, purpose)
            world = project_source_world_model(index)
            row = self.registry._fetchone(
                "SELECT question_id,patient_id,case_id,question,source_id,source_line,source_sha256,"
                "source_version,source_snapshot_sha256,preflight_sha256,created_at,source_snapshot_contract "
                "FROM investigation.source_questions "
                "WHERE patient_id=%s AND case_id=%s AND origin_org=%s AND question_id=%s "
                "AND source_line IS NOT NULL",
                (patient_id, case_id, organization, question_id))
            if row is None:
                raise PatientRegistryDenied("Evidence question unavailable")
            question = QuestionSourceState(**PostgresSourceQuestions._question_state(row, world)).model_dump(mode="json")
            context = {"patient_id": patient_id, "case_id": case_id, "question_id": question_id,
                       "organization": organization, "actor": actor, "purpose": purpose,
                       "index": index, "world": world, "question": question,
                       "require_original": require_original}
            context['manual_meta'] = QuestionPassages(self.registry).metadata_locked(context)
            context.update(self._read_evidence(context))
            prepared_context = context
            result = operation(context)
            return prepare_response(result) if prepare_response is not None else result

        with self.registry.transaction():
            response = PostgresSourceVersions(self.registry).list_locked(
                patient_id, case_id, organization=organization, actor=actor, purpose=purpose,
                prepare_response=prepare, recheck_authority=recheck)
            if needs_original:
                self.registry.append_event(patient_id, 'investigation.report_manual_context_access_prepared',
                    case_id=case_id, question_id=question_id, actor=actor,
                    receipt_id=prepared_context['index']['access_receipt_id'],
                    **reference_audit(prepared_context))
            recheck()
            return response

    @staticmethod
    def _scope(c):
        return (c["patient_id"], c["case_id"], c["organization"])

    def _read_evidence(self, c):
        rows = self.registry._fetchall(
            "SELECT evidence_id,evidence_key,version,sha256,statement_line,content_item,rights_sha256,"
            "permissions,title,issued_at,statement,created_at,original_bytes,supersedes_id "
            "FROM investigation.case_evidence_versions WHERE patient_id=%s AND case_id=%s AND origin_org=%s "
            "ORDER BY evidence_key,version LIMIT 101", self._scope(c))
        if len(rows) > MAX_EVIDENCE:
            raise PatientRegistryError("Case evidence exceeds bounded history limit")
        versions, families = {}, {}
        try:
            for row in rows:
                e = dict(zip((*VERSION_FIELDS, "original_bytes", "supersedes_id"), row, strict=True))
                raw = bytes(e["original_bytes"])
                parsed = parse_synthetic_evidence(raw)
                if type(e["issued_at"]) is not date:
                    raise ValueError()
                e["issued_at"], e["created_at"] = e["issued_at"].isoformat(), _time(e["created_at"])
                expected = (parsed.evidence_key, parsed.title, parsed.issued_at, parsed.statement, parsed.statement_line,
                            hashlib.sha256(raw).hexdigest(), canonical_hash(e["permissions"]))
                actual = tuple(e[k] for k in ("evidence_key", "title", "issued_at", "statement", "statement_line",
                                              "sha256", "rights_sha256"))
                previous = families.get(e["evidence_key"])
                if (actual != expected or e["evidence_id"] in versions
                        or normalize_permissions(e["permissions"]) != e["permissions"]
                        or not permitted(e["permissions"], "metadata", "store")
                        or not permitted(e["permissions"], e["content_item"], "store")):
                    raise ValueError()
                validate_content_item(e["content_item"])
                if previous is None:
                    if e["version"] != 1 or e["supersedes_id"] is not None or parsed.amends is not None:
                        raise ValueError()
                elif (e["version"] != previous["version"] + 1 or e["supersedes_id"] != previous["evidence_id"]
                      or parsed.amends != (e["evidence_key"], previous["version"])):
                    raise ValueError()
                e["original_bytes"] = raw
                EvidenceVersion(**self._version(e, state="current", visible=human_content_allowed(
                    e["permissions"], e["permissions"], e["content_item"])))
                versions[e["evidence_id"]] = e
                families[e["evidence_key"]] = e
            withdrawals = self.registry._fetchall(
                "SELECT withdrawal_id,evidence_id,reason FROM investigation.case_evidence_withdrawals "
                "WHERE patient_id=%s AND case_id=%s AND origin_org=%s LIMIT 101", self._scope(c))
            if len(withdrawals) > MAX_EVIDENCE:
                raise ValueError()
            withdrawn = set()
            for wid, eid, reason in withdrawals:
                _id(wid, "WITHDRAWAL")
                visible_line(reason, "Withdrawal reason")
                e = versions[eid]
                if families[e["evidence_key"]]["evidence_id"] != eid or e["evidence_key"] in withdrawn:
                    raise ValueError()
                withdrawn.add(e["evidence_key"])
        except Exception:
            raise RuntimeError("Stored evidence integrity check failed") from None
        return {"versions": versions, "families": families, "withdrawn": withdrawn}

    @staticmethod
    def _version(e, *, state, visible):
        result = {k: e[k] for k in VERSION_FIELDS}
        result["state"] = state
        if not visible:
            result["title"] = result["statement"] = None
        return result

    @staticmethod
    def _allowed(c, e, *, export=False):
        current = c["families"][e["evidence_key"]]
        return human_content_allowed(e["permissions"], current["permissions"], e["content_item"],
            withdrawn=e["evidence_key"] in c["withdrawn"], export=export)

    def _versions(self, c):
        return [self._version(e, state=("withdrawn" if e["evidence_key"] in c["withdrawn"] else
                                       "current" if c["families"][e["evidence_key"]]["evidence_id"] == e["evidence_id"] else
                                       "superseded"), visible=self._allowed(c, e))
                for e in c["versions"].values()]

    def _assessments(self, c):
        rows = self.registry._fetchall(
            "SELECT assessment_id,question_id,evidence_id,evidence_sha256,rights_sha256,"
            "source_snapshot_sha256,preflight_sha256,relation,applicability,quote,quote_start,"
            "rationale,actor,created_at,sequence_id FROM investigation.question_evidence_assessments "
            "WHERE patient_id=%s AND case_id=%s AND origin_org=%s AND question_id=%s "
            "ORDER BY sequence_id LIMIT 201", (*self._scope(c), c["question_id"]))
        if len(rows) > MAX_ASSESSMENTS:
            raise PatientRegistryError("Question comparison exceeds bounded history limit")
        stored, latest = {}, {}
        try:
            for row in rows:
                a = dict(zip((*ASSESSMENT_FIELDS, "sequence_id"), row, strict=True))
                a["created_at"] = _time(a["created_at"])
                e = c["versions"][a["evidence_id"]]
                q = c["question"]
                if (a["assessment_id"] in stored or a["question_id"] != c["question_id"]
                        or (a["evidence_sha256"], a["rights_sha256"]) != (e["sha256"], e["rights_sha256"])
                        or (a["source_snapshot_sha256"], a["preflight_sha256"]) !=
                           (q["source_snapshot_sha256"], q["preflight_sha256"])
                        or quote_offset(e["statement"], a["quote"]) != a["quote_start"]):
                    raise ValueError()
                EvidenceAssessment(**self._assessment(a, state="current_unreviewed"))
                stored[a["assessment_id"]] = a
                latest[e["evidence_key"]] = a["assessment_id"]
        except Exception:
            raise RuntimeError("Stored comparison integrity check failed") from None
        result = []
        for a in stored.values():
            e = c["versions"][a["evidence_id"]]
            current = (c["question"]["source_context_state"] == "current_unreviewed_question"
                       and c["families"][e["evidence_key"]]["evidence_id"] == e["evidence_id"]
                       and latest[e["evidence_key"]] == a["assessment_id"])
            state = ("content_withheld" if not self._allowed(c, e) else
                     "current_unreviewed" if current else "reassessment_required")
            result.append(self._assessment(a, state=state))
        return stored, result

    @staticmethod
    def _assessment(a, *, state):
        result = {k: a[k] for k in ASSESSMENT_FIELDS}
        result["state"] = state
        if state == "content_withheld":
            result["quote"] = result["quote_start"] = result["rationale"] = None
        return result

    def _source_at_preparation(self, c, source):
        """Compare the frozen source quote to its actual preserved original.

        The source owner already validated every historical original and its
        lineage under the same lock. Parse that exact preserved bytea again for
        the selected quote; do not accept a self-consistent forged snapshot.
        """
        row = self.registry._fetchone(
            "SELECT raw FROM clinical_source.source_versions WHERE source_id=%s",
            (source["source_id"],))
        if row is None:
            raise ValueError()
        raw = bytes(row[0])
        parsed = parse_report(raw, allow_oncology=True)
        metadata = [s for s in c["index"]["sources"] if s["source_id"] == source["source_id"]]
        findings = [f for f in parsed.findings if f.line == source["line"]]
        if len(metadata) != 1 or len(findings) != 1:
            raise ValueError()
        m, f = metadata[0], findings[0]
        actual = {"source_id": m["source_id"], "document_id": m["document_id"], "version": m["version"],
                  "sha256": m["sha256"], "line": f.line, "finding_key": f.key,
                  "reported_state": f.state, "statement": f.quote, "kind": m["kind"],
                  "event_date": m["event_date"], "issued_at": m["issued_at"], "specimen_id": m["specimen_id"]}
        if f.oncology is not None:
            actual["oncology"] = {"role": f.oncology.role, "episode_id": f.oncology.episode_id}
        if actual != source:
            raise ValueError()

    def _reports(self, c, stored, assessments):
        rows = self.registry._fetchall(
            "SELECT report_id,question_id,prepared_at,body,body_sha256,snapshot,snapshot_sha256,actor "
            "FROM investigation.question_evidence_reports WHERE patient_id=%s AND case_id=%s "
            "AND origin_org=%s AND question_id=%s ORDER BY prepared_at,report_id LIMIT 101",
            (*self._scope(c), c["question_id"]))
        if len(rows) > MAX_REPORTS:
            raise PatientRegistryError("Question report exceeds bounded history limit")
        by_assessment = {a["assessment_id"]: a for a in assessments}
        result = []
        try:
            for rid, qid, prepared_at, body, body_sha, snapshot, snapshot_sha, actor in rows:
                _id(rid, "REPORT")
                origin = self._origin(c, "report", rid)
                checked = checked_report_snapshot(snapshot)
                if (checked != snapshot or canonical_hash(snapshot) != snapshot_sha
                        or hashlib.sha256(body.encode("utf-8")).hexdigest() != body_sha
                        or render_evidence_report(snapshot, renderer=origin["report_renderer"]) != body
                        or datetime.fromisoformat(snapshot["prepared_at"]) != prepared_at
                        or snapshot["actor_label"] != actor or qid != c["question_id"]):
                    raise ValueError()
                q = dict(c["question"])
                q["source_context_state"] = "current_unreviewed_question"
                if snapshot["question"] != q:
                    raise ValueError()
                self._source_at_preparation(c, snapshot["selected_source"])
                allowed, current = True, c["question"]["source_context_state"] == "current_unreviewed_question"
                frozen = snapshot.get('manual_passages')
                if frozen is not None:
                    frozen_current = QuestionPassages(self.registry).verify_frozen_metadata_locked(c, frozen)
                    expected_payload = dict(synthetic=True, request_key=origin['request_key'],
                        expected_packet_sha256=origin['expected_packet_sha256'],
                        expected_manual_context_sha256=frozen['context_sha256'],
                        assessment_ids=sorted(row['assessment']['assessment_id'] for row in snapshot['comparisons']))
                    if self._intent(dict(c, actor=actor), 'report', expected_payload) != origin['intent_sha256']:
                        raise ValueError()
                    current = current and frozen_current
                else:
                    current = current and c['manual_meta']['revision_id'] is None
                for comparison in snapshot["comparisons"]:
                    a = stored[comparison["assessment"]["assessment_id"]]
                    e = c["versions"][a["evidence_id"]]
                    if (comparison["assessment"] != self._assessment(a, state="current_unreviewed")
                            or comparison["evidence"] != self._version(e, state="current", visible=True)):
                        raise ValueError()
                    allowed = allowed and self._allowed(c, e, export=True)
                    current = current and by_assessment[a["assessment_id"]]["state"] == "current_unreviewed"
                state = ("content_withheld" if not allowed else "current_unreviewed" if current
                         else "historical_reassessment_required")
                result.append({"report_id": rid, "question_id": qid, "prepared_at": snapshot["prepared_at"],
                               "body_sha256": body_sha, "snapshot_sha256": snapshot_sha, "state": state,
                               "body": body, "snapshot": snapshot})
        except PatientRegistryDenied:
            raise
        except Exception:
            raise RuntimeError("Stored report integrity check failed") from None
        return result

    def _packet(self, c):
        stored, assessments = self._assessments(c)
        reports = self._reports(c, stored, assessments)
        result = {"contract": "oi.h1-question-evidence/1", "patient_id": c["patient_id"],
                  "case_id": c["case_id"], "question": c["question"],
                  "source_snapshot_sha256": c["world"]["snapshot_fingerprint"],
                  "access_receipt_id": c["index"]["access_receipt_id"],
                  "evidence": self._versions(c), "assessments": assessments,
                  "reports": [{k: v for k, v in r.items() if k not in {"body", "snapshot"}} for r in reports],
                  **FLAGS}
        result["packet_sha256"] = packet_hash(result)
        return result

    def packet(self, patient_id, case_id, question_id, **kwargs):
        return self._run(patient_id, case_id, question_id, action="authored_evidence_read", operation=self._packet, **kwargs)

    @staticmethod
    def _intent(c, operation, payload):
        return canonical_hash({"patient_id": c["patient_id"], "case_id": c["case_id"],
                               "question_id": c["question_id"], "organization": c["organization"],
                               "actor": c["actor"], "purpose": c["purpose"],
                               "operation": operation, "payload": payload})

    def _origin(self, c, operation, object_id):
        row = self.registry._fetchone(
            "SELECT request_key,intent_sha256,expected_packet_sha256,packet_binding,report_renderer,actor,purpose "
            "FROM investigation.evidence_command_origins WHERE patient_id=%s AND case_id=%s AND origin_org=%s "
            "AND question_id=%s AND operation=%s AND object_id=%s",
            (*self._scope(c), c["question_id"], operation, object_id))
        if row is None:
            raise RuntimeError("Stored evidence origin unavailable")
        origin = dict(zip(("request_key", "intent_sha256", "expected_packet_sha256", "packet_binding",
                           "report_renderer", "actor", "purpose"), row, strict=True))
        ledger = self.registry._fetchone(
            "SELECT intent_sha256,result,origin_org,actor,purpose FROM investigation.evidence_commands "
            "WHERE patient_id=%s AND case_id=%s AND operation=%s AND request_key=%s",
            (c["patient_id"], c["case_id"], operation, origin["request_key"]))
        id_field = "assessment_id" if operation == "assess" else "report_id"
        if (ledger is None or ledger[0] != origin["intent_sha256"] or
                ledger[1] != {id_field: object_id, "question_id": c["question_id"]} or
                tuple(ledger[2:]) != (c["organization"], origin["actor"], origin["purpose"]) or
                origin["purpose"] != "operations"):
            raise RuntimeError("Stored evidence origin differs from creating command")
        if operation == "assess":
            valid = (origin["packet_binding"] == "not_applicable" and origin["expected_packet_sha256"] is None
                     and origin["report_renderer"] is None)
        else:
            valid = ((origin["packet_binding"] == "intent_digest_only" and origin["expected_packet_sha256"] is None
                      and origin["report_renderer"] == "oi.h1-evidence-text/1") or
                     (origin["packet_binding"] == "explicit_digest" and type(origin["expected_packet_sha256"]) is str
                      and re.fullmatch(r"[0-9a-f]{64}", origin["expected_packet_sha256"]) is not None
                      and origin["report_renderer"] in {"oi.h1-evidence-text/2", "oi.h1-evidence-text/3"}))
        if not valid:
            raise RuntimeError("Stored evidence origin contract is invalid")
        return origin

    def _verify_recovered_origin(self, c, operation, payload, result):
        field = "assessment_id" if operation == "assess" else "report_id"
        origin = self._origin(c, operation, result[field])
        if (origin["request_key"] != payload["request_key"] or
                not hmac.compare_digest(origin["intent_sha256"], self._intent(c, operation, payload)) or
                origin["actor"] != c["actor"]):
            raise RuntimeError("Recovered object was created by a different command")
        if operation == "report" and origin["packet_binding"] == "explicit_digest" and (
                origin["expected_packet_sha256"] != payload["expected_packet_sha256"]):
            raise RuntimeError("Recovered report inspected a different packet")

    def _recovered_result(self, c, operation, payload, result):
        """A command digest cannot stand in for the actual immutable record."""
        try:
            if operation == "import":
                if set(result) != {"evidence_id", "version"}:
                    raise ValueError()
                e = c["versions"][result["evidence_id"]]
                if (result["version"] != e["version"] or
                        e["original_bytes"] != payload["original_text"].encode("utf-8") or
                        e["content_item"] != payload["content_item"] or
                        e["permissions"] != payload["permissions"]):
                    raise ValueError()
            elif operation == "withdraw":
                if set(result) != {"withdrawal_id", "evidence_id"} or result["evidence_id"] != payload["evidence_id"]:
                    raise ValueError()
                row = self.registry._fetchone(
                    "SELECT evidence_id,reason,actor FROM investigation.case_evidence_withdrawals "
                    "WHERE patient_id=%s AND case_id=%s AND origin_org=%s AND withdrawal_id=%s",
                    (*self._scope(c), result["withdrawal_id"]))
                if row is None or tuple(row) != (payload["evidence_id"], payload["reason"], c["actor"]):
                    raise ValueError()
            elif operation == "assess":
                if set(result) != {"assessment_id", "question_id"} or result["question_id"] != c["question_id"]:
                    raise ValueError()
                self._verify_recovered_origin(c, operation, payload, result)
                stored, _ = self._assessments(c)
                a = stored[result["assessment_id"]]
                for field in ("evidence_id", "evidence_sha256", "rights_sha256", "quote", "relation", "applicability", "rationale"):
                    if a[field] != payload[field]:
                        raise ValueError()
                if (a["actor_label"] != c["actor"] or a["source_snapshot_sha256"] != payload["expected_source_snapshot_sha256"]
                        or a["preflight_sha256"] != payload["expected_preflight_sha256"]):
                    raise ValueError()
            elif operation == "report":
                if set(result) != {"report_id", "question_id"} or result["question_id"] != c["question_id"]:
                    raise ValueError()
                self._verify_recovered_origin(c, operation, payload, result)
                stored, assessments = self._assessments(c)
                reports = self._reports(c, stored, assessments)
                report, = [r for r in reports if r["report_id"] == result["report_id"]]
                if (report["snapshot"]["actor_label"] != c["actor"] or
                        sorted(row["assessment"]["assessment_id"] for row in report["snapshot"]["comparisons"]) !=
                        payload["assessment_ids"]):
                    raise ValueError()
            else:
                raise ValueError()
        except PatientRegistryDenied:
            raise
        except Exception:
            raise RuntimeError("Stored evidence command integrity check failed") from None
        return {**result, "duplicate": True}

    def _command(self, c, operation, payload, apply):
        key = _key(payload["request_key"], "request_key")
        intent = self._intent(c, operation, payload)
        previous = self.registry._fetchone(
            "SELECT intent_sha256,result,origin_org,actor,purpose FROM investigation.evidence_commands "
            "WHERE patient_id=%s AND case_id=%s AND operation=%s AND request_key=%s",
            (c["patient_id"], c["case_id"], operation, key))
        if previous is not None:
            if (not hmac.compare_digest(previous[0], intent) or tuple(previous[2:]) !=
                    (c["organization"], c["actor"], c["purpose"])):
                raise PatientRegistryConflict("Evidence request key reused with changed intent")
            return self._recovered_result(c, operation, payload, previous[1])
        result = apply()
        duplicate = result.pop("duplicate", False)
        self.registry._execute(
            "INSERT INTO investigation.evidence_commands "
            "(patient_id,case_id,origin_org,operation,request_key,intent_sha256,result,actor,purpose) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)",
            (*self._scope(c), operation, key, intent, canonical_json(result), c["actor"], c["purpose"]))
        if operation in {"assess", "report"}:
            is_report = operation == "report"
            self.registry._execute(
                "INSERT INTO investigation.evidence_command_origins "
                "(operation,object_id,patient_id,case_id,origin_org,question_id,request_key,intent_sha256,"
                "expected_packet_sha256,packet_binding,report_renderer,actor,purpose) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (operation, result["report_id" if is_report else "assessment_id"], *self._scope(c),
                 c["question_id"], key, intent, payload["expected_packet_sha256"] if is_report else None,
                 "explicit_digest" if is_report else "not_applicable",
                 c.get('report_renderer', 'oi.h1-evidence-text/2') if is_report else None, c["actor"], c["purpose"]))
        return {**result, "duplicate": duplicate}

    def import_evidence(self, patient_id, case_id, question_id, *, payload, **kwargs):
        try:
            parsed = parse_synthetic_evidence(payload["original_text"].encode("utf-8"))
            item = validate_content_item(payload["content_item"])
            rights = normalize_permissions(payload["permissions"])
        except (ValueError, InvalidInput, UnicodeError) as exc:
            raise PatientRegistryError("Invalid original fictional evidence") from exc
        normalized = {**payload, "permissions": rights}
        digest, rights_sha = hashlib.sha256(parsed.raw).hexdigest(), canonical_hash(rights)

        def operation(c):
            def apply():
                if not all(permitted(rights, target, "store") for target in ("metadata", item)):
                    raise PatientRegistryDenied("Evidence storage permission unavailable")
                for e in c["versions"].values():
                    if e["evidence_key"] == parsed.evidence_key and e["sha256"] == digest:
                        if e["content_item"] != item or e["permissions"] != rights:
                            raise PatientRegistryConflict("Existing original has a different rights declaration")
                        return {"evidence_id": e["evidence_id"], "version": e["version"], "duplicate": True}
                previous = c["families"].get(parsed.evidence_key)
                if (parsed.evidence_key in c["withdrawn"] or
                        (previous is None and parsed.amends is not None) or
                        (previous is not None and parsed.amends != (parsed.evidence_key, previous["version"]))):
                    raise PatientRegistryConflict("Explicit current evidence amendment required")
                if len(c["versions"]) >= MAX_EVIDENCE:
                    raise PatientRegistryError("Case evidence exceeds bounded history limit")
                eid, version = _new("EVIDENCE"), 1 if previous is None else previous["version"] + 1
                self.registry._execute(
                    "INSERT INTO investigation.case_evidence_versions "
                    "(evidence_id,patient_id,case_id,origin_org,evidence_key,version,supersedes_id,original_bytes,"
                    "sha256,title,issued_at,statement,statement_line,content_item,permissions,rights_sha256,actor,purpose) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::date,%s,%s,%s,%s::jsonb,%s,%s,%s)",
                    (eid, *self._scope(c), parsed.evidence_key, version,
                     previous["evidence_id"] if previous else None, parsed.raw, digest, parsed.title, parsed.issued_at,
                     parsed.statement, parsed.statement_line, item, canonical_json(rights), rights_sha, c["actor"], c["purpose"]))
                self.registry.append_event(c["patient_id"], "investigation.evidence.imported", case_id=c["case_id"],
                    evidence_id=eid, version=version, evidence_sha256=digest, rights_sha256=rights_sha, actor=c["actor"])
                return {"evidence_id": eid, "version": version}
            return self._command(c, "import", normalized, apply)
        return self._run(patient_id, case_id, question_id, action="authored_evidence_import", operation=operation, **kwargs)

    def withdraw(self, patient_id, case_id, question_id, evidence_id, *, payload, **kwargs):
        evidence_id = _id(evidence_id, "EVIDENCE")
        visible_line(payload["reason"], "Withdrawal reason")
        def operation(c):
            def apply():
                e = c["versions"].get(evidence_id)
                if e is None:
                    raise PatientRegistryDenied("Evidence unavailable")
                if (c["families"][e["evidence_key"]]["evidence_id"] != evidence_id or
                        e["evidence_key"] in c["withdrawn"]):
                    raise PatientRegistryConflict("Only current evidence can be withdrawn")
                wid = _new("WITHDRAWAL")
                self.registry._execute(
                    "INSERT INTO investigation.case_evidence_withdrawals "
                    "(withdrawal_id,evidence_id,patient_id,case_id,origin_org,reason,actor,purpose) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (wid, evidence_id, *self._scope(c), payload["reason"], c["actor"], c["purpose"]))
                self.registry.append_event(c["patient_id"], "investigation.evidence.withdrawn", case_id=c["case_id"],
                                           evidence_id=evidence_id, withdrawal_id=wid, actor=c["actor"])
                return {"withdrawal_id": wid, "evidence_id": evidence_id}
            return self._command(c, "withdraw", {**payload, "evidence_id": evidence_id}, apply)
        return self._run(patient_id, case_id, question_id, action="authored_evidence_withdraw", operation=operation, **kwargs)

    def original(self, patient_id, case_id, question_id, evidence_id, **kwargs):
        evidence_id = _id(evidence_id, "EVIDENCE")
        def operation(c):
            e = c["versions"].get(evidence_id)
            if e is None or not self._allowed(c, e):
                raise PatientRegistryDenied("Evidence original unavailable")
            return {"contract": "oi.h1-evidence-original/1", "patient_id": c["patient_id"],
                    "case_id": c["case_id"], "evidence_id": evidence_id, "sha256": e["sha256"],
                    "original_text": e["original_bytes"].decode("utf-8"),
                    "access_receipt_id": c["index"]["access_receipt_id"], "synthetic": True}
        return self._run(patient_id, case_id, question_id, action="authored_evidence_original_read", operation=operation, **kwargs)

    def _current_source(self, c, snapshot_sha, preflight_sha):
        q = c["question"]
        if (q["source_context_state"] != "current_unreviewed_question" or
                (q["source_snapshot_sha256"], q["preflight_sha256"]) != (snapshot_sha, preflight_sha)):
            raise PatientRegistryConflict("Question context changed; explicit reassessment required")
        prepared = PostgresSourceComposerPreflight(self.registry).preview_locked(
            c["patient_id"], c["case_id"], organization=c["organization"], actor=c["actor"], purpose=c["purpose"],
            expected_source_snapshot_sha256=snapshot_sha, source_id=q["source_id"], source_line=q["source_line"],
            question=q["question"], source_index=c["index"])
        selected = prepared["selected_source"]
        if (prepared["preflight_sha256"] != preflight_sha
                or prepared["source_snapshot_contract"] != q["source_snapshot_contract"]
                or (selected["source_id"], selected["line"], selected["sha256"], selected["version"]) !=
                   (q["source_id"], q["source_line"], q["source_sha256"], q["source_version"])):
            raise PatientRegistryConflict("Question preflight changed; explicit reassessment required")
        return selected

    def verify_review_assessment_locked(self, item, assessment_id, *, source_index, organization, actor, purpose):
        """Resolve one human assessment inside the review owner's locked source callback.

        The caller owns the final refreshed credential check, audit, and transaction.
        Neither the proof nor the returned rights check discloses the original passage.
        """
        assessment_id = _id(assessment_id, "ASSESSMENT")
        if not self.registry._transaction_active:
            raise PatientRegistryError("Assessment verification requires the active review transaction")
        patient_id = _key(item["patient_id"], "patient_id")
        c = dict(patient_id=patient_id, case_id=_case_id(item["case_id"]), question_id=_question_id(item["question_id"]),
                 organization=_key(organization, "organization"), actor=_key(actor, "actor"), purpose=purpose,
                 question=item, index=source_index)
        if purpose != "operations":
            raise PatientRegistryDenied("Assessment unavailable")

        def authorize():
            if not self.registry._transaction_active:
                raise PatientRegistryError("Assessment verification requires the active review transaction")
            for permission in ("patient_read", "source_read", "question_read", "authored_evidence_read"):
                self.registry._allow(actor, patient_id, permission, purpose)

        authorize()
        self._current_source(c, item["source_snapshot_sha256"], item["preflight_sha256"])

        def current():
            c.update(self._read_evidence(c))
            _, comparisons = self._assessments(c)
            comparison = next((a for a in comparisons if a["assessment_id"] == assessment_id), None)
            if comparison is None or comparison["state"] == "content_withheld":
                raise PatientRegistryDenied("Assessment unavailable")
            if comparison["state"] != "current_unreviewed":
                raise PatientRegistryConflict("Assessment needs reassessment")
            return comparison

        comparison = current()
        evidence = c["versions"][comparison["evidence_id"]]
        # Bind the literal and the human attribution to the original command, so
        # even a different, otherwise valid passage from the same version fails.
        origin = self._origin(c, "assess", assessment_id)
        payload = {k: comparison[k] for k in ("evidence_id", "evidence_sha256", "rights_sha256", "quote",
                                               "relation", "applicability", "rationale")}
        payload.update(synthetic=True, request_key=origin["request_key"],
                       expected_source_snapshot_sha256=comparison["source_snapshot_sha256"],
                       expected_preflight_sha256=comparison["preflight_sha256"])
        author = comparison["actor_label"]
        if (origin["actor"] != author or
                not hmac.compare_digest(origin["intent_sha256"], self._intent(dict(c, actor=author), "assess", payload))):
            raise RuntimeError("Stored assessment differs from its original command")

        def recheck():
            authorize()
            if current() != comparison:
                raise PatientRegistryConflict("Assessment changed during review preparation")

        proof = {"assessment_id": assessment_id, "evidence_id": evidence["evidence_id"],
                 "evidence_version": evidence["version"], "evidence_sha256": evidence["sha256"],
                 "rights_sha256": evidence["rights_sha256"], "statement_line": evidence["statement_line"],
                 "quote_start": comparison["quote_start"], "quote_length": len(comparison["quote"]),
                 "quote_sha256": hashlib.sha256(comparison["quote"].encode("utf-8")).hexdigest()}
        return proof, recheck

    def assess(self, patient_id, case_id, question_id, *, payload, **kwargs):
        normalized = AssessEvidence(**payload).model_dump(mode="json")
        def operation(c):
            def apply():
                self._current_source(c, normalized["expected_source_snapshot_sha256"], normalized["expected_preflight_sha256"])
                e = c["versions"].get(normalized["evidence_id"])
                if e is None:
                    raise PatientRegistryDenied("Evidence unavailable")
                if (c["families"][e["evidence_key"]]["evidence_id"] != e["evidence_id"] or
                    (e["sha256"], e["rights_sha256"]) != (normalized["evidence_sha256"], normalized["rights_sha256"])):
                    raise PatientRegistryConflict("Evidence version changed; explicit reassessment required")
                if not self._allowed(c, e):
                    raise PatientRegistryDenied("Evidence comparison content unavailable")
                offset = quote_offset(e["statement"], normalized["quote"])
                stored, _ = self._assessments(c)
                if len(stored) >= MAX_ASSESSMENTS:
                    raise PatientRegistryError("Question comparison exceeds bounded history limit")
                aid = _new("ASSESSMENT")
                self.registry._execute(
                    "INSERT INTO investigation.question_evidence_assessments "
                    "(assessment_id,patient_id,case_id,origin_org,question_id,evidence_id,evidence_sha256,rights_sha256,"
                    "source_snapshot_sha256,preflight_sha256,relation,applicability,quote,quote_start,rationale,actor,purpose) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (aid, *self._scope(c), c["question_id"], e["evidence_id"], e["sha256"], e["rights_sha256"],
                     c["question"]["source_snapshot_sha256"], c["question"]["preflight_sha256"], normalized["relation"],
                     normalized["applicability"], normalized["quote"], offset, normalized["rationale"], c["actor"], c["purpose"]))
                self.registry.append_event(c["patient_id"], "investigation.evidence.assessed", case_id=c["case_id"],
                                           question_id=c["question_id"], evidence_id=e["evidence_id"],
                                           assessment_id=aid, actor=c["actor"])
                return {"assessment_id": aid, "question_id": c["question_id"]}
            return self._command(c, "assess", normalized, apply)
        return self._run(patient_id, case_id, question_id, action="authored_evidence_assess", operation=operation, **kwargs)

    def create_report(self, patient_id, case_id, question_id, *, payload, **kwargs):
        # Omitted optional fields stay omitted in historical command digests.
        normalized = PrepareEvidenceReport(**payload).model_dump(mode="json", exclude_none=True)
        def operation(c):
            def apply():
                packet = self._packet(c)
                if not hmac.compare_digest(packet["packet_sha256"], normalized["expected_packet_sha256"]):
                    raise PatientRegistryConflict("Inspected evidence context changed")
                manual_meta = c['manual_meta']
                expected_manual = normalized.get('expected_manual_context_sha256')
                manual = None
                if manual_meta['revision_id'] is not None or expected_manual is not None:
                    manual = QuestionPassages(self.registry).context_locked(c)
                    if expected_manual != manual['context_sha256']:
                        raise PatientRegistryConflict('Inspected manual passage context changed')
                    if manual['state'] != 'current_unreviewed':
                        raise PatientRegistryConflict('Manual passages require reassessment before a new report')
                selected = self._current_source(c, c["question"]["source_snapshot_sha256"], c["question"]["preflight_sha256"])
                assessments = {a["assessment_id"]: a for a in packet["assessments"]}
                versions = {e["evidence_id"]: e for e in packet["evidence"]}
                comparisons = []
                for aid in normalized["assessment_ids"]:
                    a = assessments.get(aid)
                    if a is None or a["state"] != "current_unreviewed":
                        raise PatientRegistryConflict("Selected comparison needs reassessment")
                    e = c["versions"][a["evidence_id"]]
                    if not self._allowed(c, e, export=True):
                        raise PatientRegistryDenied("Evidence redistribution unavailable")
                    comparisons.append({"assessment": a, "evidence": versions[e["evidence_id"]]})
                if len(packet["reports"]) >= MAX_REPORTS:
                    raise PatientRegistryError("Question report exceeds bounded history limit")
                snapshot = {"question": c["question"], "selected_source": selected, "comparisons": comparisons,
                            "prepared_at": datetime.now(timezone.utc).isoformat(), "actor_label": c["actor"]}
                if manual is not None and manual['revision_id'] is not None:
                    snapshot['manual_passages'] = manual
                    c['report_renderer'] = 'oi.h1-evidence-text/3'
                body = render_evidence_report(snapshot, renderer=c.get('report_renderer', 'oi.h1-evidence-text/2'))
                rid = _new("REPORT")
                self.registry._execute(
                    "INSERT INTO investigation.question_evidence_reports "
                    "(report_id,patient_id,case_id,origin_org,question_id,prepared_at,body,body_sha256,snapshot,"
                    "snapshot_sha256,actor,purpose) VALUES (%s,%s,%s,%s,%s,%s::timestamptz,%s,%s,%s::jsonb,%s,%s,%s)",
                    (rid, *self._scope(c), c["question_id"], snapshot["prepared_at"], body,
                     hashlib.sha256(body.encode("utf-8")).hexdigest(), canonical_json(snapshot), canonical_hash(snapshot),
                     c["actor"], c["purpose"]))
                self.registry.append_event(c["patient_id"], "investigation.evidence.report_prepared", case_id=c["case_id"],
                                           question_id=c["question_id"], report_id=rid,
                                           snapshot_sha256=canonical_hash(snapshot), actor=c["actor"])
                return {"report_id": rid, "question_id": c["question_id"]}
            return self._command(c, "report", normalized, apply)
        return self._run(patient_id, case_id, question_id, action="evidence_report_export", operation=operation, **kwargs)

    def report(self, patient_id, case_id, question_id, report_id, **kwargs):
        report_id = _id(report_id, "REPORT")
        def operation(c):
            stored, assessments = self._assessments(c)
            reports = self._reports(c, stored, assessments)
            matches = [r for r in reports if r["report_id"] == report_id]
            if len(matches) != 1:
                raise PatientRegistryDenied("Evidence report unavailable")
            result = dict(matches[0])
            if result["state"] == "content_withheld":
                result["body"] = result["snapshot"] = None
            elif result["snapshot"].get("manual_passages") is not None:
                # Only the report actually disclosing frozen manual text needs
                # current original-read authority and exact source re-resolution.
                QuestionPassages(self.registry).verify_frozen_locked(
                    c, result["snapshot"]["manual_passages"])
            return {"contract": "oi.h1-evidence-report/1", "patient_id": c["patient_id"],
                    "case_id": c["case_id"], "access_receipt_id": c["index"]["access_receipt_id"], **result, **FLAGS}
        return self._run(patient_id, case_id, question_id, action="evidence_report_export", operation=operation, **kwargs)
