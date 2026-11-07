"""Human transcription checks over the canonical task and source owners' locked originals."""
from datetime import datetime, timezone
import hmac
import uuid

from open_intelligence.patient_registry import PatientRegistryConflict, PatientRegistryDenied, _digest, _key
from .amendment_review_contracts import AmendmentCommand, MAX_REVIEW_ENTRIES, ReviewEntry
from .case_bindings import _case_id
from .question_followthrough import PostgresQuestionFollowthrough
from .source_integrity import SourceIntegrityError
from .sources import PostgresSourceVersions

BASE_GRANTS = ("patient_read", "source_read", "source_original_read", "question_read", "followthrough_read")
TABLE = "investigation.laboratory_amendment_reviews"
FIELDS = ("entry_id", "request_id", "task_id", "question_id", "patient_id", "case_id", "origin_org",
          "actor", "purpose", "action", "reason", "disposition", "original_source_id", "latest_source_id",
          "latest_sha256", "request_key", "intent_sha256", "recorded_at")


def _intent(entry):
    fields = {key: entry[key] for key in ("task_id", "question_id", "patient_id", "case_id", "origin_org",
              "actor", "purpose", "action", "reason", "disposition", "original_source_id", "latest_source_id",
              "latest_sha256", "request_key")}
    if entry["action"] == "respond":
        fields["request_id"] = entry["request_id"]
    return _digest({"operation": "laboratory_amendment_review", **fields})


def _receipt(entry, duplicate):
    return {"entry_id": entry["entry_id"], "request_id": entry["request_id"], "duplicate": duplicate}


class LaboratoryAmendmentReviews:
    def __init__(self, registry):
        self.registry = registry
        self.followthrough = PostgresQuestionFollowthrough(registry)

    def _lineages(self, scope, index):
        # SourceVersions has checked the typed fields against every original,
        # each supersedes edge, contiguous version, and unique current head.
        # Also require each FHIR predecessor to match the active binding's
        # source system, source organization and original subject.
        rows = self.registry._fetchall(
            "SELECT f.source_id FROM clinical_source.fhir_laboratory_sources f "
            "JOIN clinical_source.source_versions s USING (source_id) "
            "JOIN coordination.patient_case_bindings b ON b.case_id=s.case_id "
            "AND b.source_organization=f.source_organization AND b.source_system=f.source_system "
            "AND 'Patient/' || b.source_subject_ref=f.subject_reference "
            "WHERE (b.patient_id,b.case_id,b.origin_org)=(%s,%s,%s) AND b.status='active' "
            "AND b.purpose='operations'", scope)
        qualified = {r[0] for r in rows}
        lineage, heads = {}, {}
        for source in sorted(index["sources"], key=lambda s: s["version"]):
            if source["state"] == "current":
                heads[source["document_id"]] = source
            if source["source_id"] in qualified and (
                    source["version"] == 1 or source["supersedes_id"] in lineage):
                lineage[source["source_id"]] = source
        return lineage, heads

    def _history(self, scope, tasks, lineage):
        # Include children by their task as well as declared scope. A damaged
        # final response must not make its request appear unanswered.
        rows = self.registry._fetchall(
            "SELECT " + ",".join(FIELDS) + " FROM " + TABLE +
            " WHERE (patient_id,case_id,origin_org)=(%s,%s,%s) OR task_id=ANY(%s) "
            "ORDER BY recorded_at,action,entry_id LIMIT 751", (*scope, list(tasks)))
        if len(rows) > MAX_REVIEW_ENTRIES:
            raise SourceIntegrityError("Amendment history exceeds its case limit")
        entries = [dict(zip(FIELDS, row, strict=True)) for row in rows]
        requests, answers, pairs = {}, set(), set()
        for entry in entries:
            task = tasks.get(entry["task_id"])
            original, latest = (lineage.get(entry[k]) for k in ("original_source_id", "latest_source_id"))
            if (task is None or tuple(entry[k] for k in ("patient_id", "case_id", "origin_org")) != scope
                    or entry["purpose"] != "operations" or task["question_id"] != entry["question_id"]
                    or original is None or latest is None or original["source_id"] != task["source_id"]
                    or original["document_id"] != latest["document_id"] or latest["version"] <= original["version"]
                    or latest["sha256"] != entry["latest_sha256"]
                    or not hmac.compare_digest(entry["intent_sha256"], _intent(entry))):
                raise SourceIntegrityError("Invalid amendment review origin")
            if entry["action"] == "request":
                pair = (task["task_id"], latest["source_id"])
                if (entry["request_id"] != entry["entry_id"] or entry["disposition"] is not None
                        or pair in pairs):
                    raise SourceIntegrityError("Invalid amendment request history")
                pairs.add(pair)
                requests[entry["request_id"]] = entry
        for entry in entries:
            if entry["action"] == "request":
                continue
            request = requests.get(entry["request_id"])
            if (entry["action"] != "respond" or request is None or request["actor"] == entry["actor"]
                    or entry["entry_id"] == entry["request_id"] or entry["request_id"] in answers
                    or entry["disposition"] not in ("transcription_checked", "needs_clarification")
                    or any(entry[k] != request[k] for k in ("task_id", "original_source_id", "latest_source_id"))):
                raise SourceIntegrityError("Invalid amendment response history")
            answers.add(entry["request_id"])
        return entries, requests, answers

    def _comparison(self, task, original, latest):
        reference = task["observation_reference"]
        # Both qualified source IDs came from the validated version chain.
        # Match only this immutable Observation identity, in each exact version.
        rows = self.registry._fetchall(
            "SELECT o.source_id,o.loinc_code,o.status,o.value_text,o.unit_code,o.absent_reason,"
            "f.specimen_reference,o.effective_at,o.issued_at "
            "FROM clinical_source.fhir_laboratory_observations o "
            "JOIN clinical_source.fhir_laboratory_sources f USING (source_id) "
            "WHERE o.source_id=ANY(%s) AND o.observation_reference=%s",
            ([original["source_id"], latest["source_id"]], reference))
        observations = {r[0]: dict(loinc_code=r[1], status=r[2], value_text=r[3], unit_code=r[4],
                                   absent_reason=r[5], specimen_reference=r[6], effective_at=r[7].isoformat(),
                                   issued_at=r[8].isoformat()) for r in rows}
        if original["source_id"] not in observations:
            raise SourceIntegrityError("Original task Observation unavailable")
        return tuple({k: s[k] for k in ("source_id", "version", "sha256", "document_id")}
                     | {"observation": observations.get(s["source_id"])} for s in (original, latest))

    def _record(self, scope, task, latest, actor, command, entries, requests, answers):
        entry_id = "VERIFY-" + uuid.uuid4().hex.upper()
        responding = command.action == "respond"
        entry = dict(zip(("patient_id", "case_id", "origin_org"), scope, strict=True))
        entry.update(task_id=task["task_id"], question_id=task["question_id"], actor=actor, purpose="operations",
                     entry_id=entry_id, request_id=command.request_id if responding else entry_id,
                     action=command.action, reason=command.reason, disposition=command.disposition if responding else None,
                     original_source_id=task["source_id"], latest_source_id=command.expected_latest_source_id,
                     latest_sha256=command.expected_latest_sha256, request_key=command.request_key)
        entry["intent_sha256"] = _intent(entry)

        def prior():
            row = self.registry._fetchone(
                "SELECT entry_id,request_id,case_id,origin_org,actor,intent_sha256 FROM " + TABLE +
                " WHERE patient_id=%s AND request_key=%s", (scope[0], command.request_key))
            if row is None:
                return None
            if row[2:5] != (scope[1], scope[2], actor):
                raise PatientRegistryDenied("Amendment verification unavailable")
            if not hmac.compare_digest(row[5], entry["intent_sha256"]):
                raise PatientRegistryConflict("Amendment verification intent changed")
            return {"entry_id": row[0], "request_id": row[1], "duplicate": True}

        replay = prior()
        if replay is not None:
            return replay
        if responding:
            request = requests.get(command.request_id)
            if request is None or request["task_id"] != task["task_id"] or request["actor"] == actor:
                raise PatientRegistryDenied("Amendment verification unavailable")
            if (command.request_id in answers or request["latest_source_id"] != entry["latest_source_id"]
                    or request["latest_sha256"] != entry["latest_sha256"]):
                raise PatientRegistryConflict("Requested basis is unavailable")
        elif any(r["task_id"] == task["task_id"] and r["latest_source_id"] == entry["latest_source_id"]
                 for r in requests.values()):
            raise PatientRegistryConflict("Verification already requested")
        if (latest["source_id"] != entry["latest_source_id"] or latest["sha256"] != entry["latest_sha256"]
                or len(entries) >= MAX_REVIEW_ENTRIES):
            raise PatientRegistryConflict("Amendment verification basis or capacity changed")
        inserted = self.registry._fetchone(
            "INSERT INTO " + TABLE + " (" + ",".join(entry) + ") VALUES (" + ",".join(["%s"] * len(entry)) +
            ") ON CONFLICT (patient_id,request_key) DO NOTHING RETURNING entry_id", tuple(entry.values()))
        if inserted is None:
            # Different cases serialize on separate binding locks but share the patient key namespace.
            replay = prior()
            if replay is None:
                raise SourceIntegrityError("Missing amendment command receipt")
            return replay
        event = "responded" if responding else "requested"
        self.registry.append_event(
            scope[0], "investigation.laboratory_amendment." + event, case_id=scope[1], actor=actor,
            task_id=task["task_id"], question_id=task["question_id"], entry_id=entry_id,
            request_id=entry["request_id"], original_source_id=task["source_id"], latest_source_id=latest["source_id"])
        return _receipt(entry, False)

    def run(self, patient_id, case_id, *, organization, actor, purpose, task_id=None,
            command: AmendmentCommand | None = None, recheck_authority, prepare_response):
        scope = (_key(patient_id, "patient_id"), _case_id(case_id), _key(organization, "organization"))
        actor = _key(actor, "actor")
        if purpose != "operations" or (command is not None and task_id is None):
            raise PatientRegistryDenied("Amendment verification unavailable")
        actions = BASE_GRANTS
        if task_id is None:
            actions += ("review_queue_read",)
        elif command is not None:
            actions += (("followthrough_create",) if command.action == "request" else ("review_queue_read", "review_return"))

        def authority():
            recheck_authority(actions)
            for grant in actions:
                self.registry._allow(actor, patient_id, grant, purpose)

        def prepare(index):
            current_day = datetime.now(timezone.utc).date().isoformat()
            all_tasks, _, _ = self.followthrough._read_locked(*scope, index, current_day)
            tasks = {t["task_id"]: t for t in all_tasks if "observation_reference" in t}
            if task_id is not None and task_id not in tasks:
                raise PatientRegistryDenied("Amendment verification unavailable")
            lineage, heads = self._lineages(scope, index)
            entries, requests, answers = self._history(scope, tasks, lineage)
            common = dict(patient_id=patient_id, case_id=case_id, clinical_approval=False)
            if task_id is None:
                pending = [{k: r[k] for k in ("request_id", "task_id", "question_id", "latest_source_id")}
                           for rid, r in requests.items() if rid not in answers]
                self.registry.append_event(patient_id, "investigation.laboratory_amendment.inbox_read",
                                           case_id=case_id, actor=actor, source_access_receipt_id=index["access_receipt_id"])
                return prepare_response(dict(common, contract="oi.laboratory-amendment-inbox/1", requests=pending))
            task = tasks[task_id]
            original = lineage.get(task["source_id"])
            if original is None or heads[original["document_id"]]["source_id"] not in lineage:
                raise PatientRegistryDenied("Laboratory source subject or lineage unavailable")
            latest = heads[original["document_id"]]
            if latest["version"] <= original["version"]:
                raise PatientRegistryConflict("No newer report version")
            original, latest = self._comparison(task, original, latest)
            if command is not None:
                return prepare_response(self._record(scope, task, latest, actor, command, entries, requests, answers))
            history = [{k: r[k] for k in ReviewEntry.model_fields} | {"recorded_at": r["recorded_at"].isoformat()}
                       for r in entries if r["task_id"] == task_id]
            self.registry.append_event(patient_id, "investigation.laboratory_amendment.comparison_read",
                                       case_id=case_id, task_id=task_id, actor=actor, original_source_id=original["source_id"],
                                       latest_source_id=latest["source_id"], source_access_receipt_id=index["access_receipt_id"])
            return prepare_response(dict(common, contract="oi.laboratory-amendment-review/1",
                                         task_id=task_id, question_id=task["question_id"],
                                         observation_reference=task["observation_reference"],
                                         original=original, latest=latest, entries=history))

        with self.registry.transaction():
            authority()
            return PostgresSourceVersions(self.registry).list_locked(
                patient_id, case_id, organization=organization, actor=actor, purpose=purpose,
                recheck_authority=authority, prepare_response=prepare)
