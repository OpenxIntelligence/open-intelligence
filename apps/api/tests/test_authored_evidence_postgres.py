"""Independent actual PG16/HTTP acceptance for case-owned fictional evidence.

All originals, questions, claims and identities are independently authored test
material. The tests enter through the existing canonical patient/source/question
API; no reference SQLite store or integer identity alias is used. The shared
fixture is inherited without re-running any upstream test methods.
"""
import copy
import hashlib
import json
import unittest

from sqlalchemy import text

from http_support import running_server
from oi_api.app import create_app
from oi_api.config import Settings
from test_canonical_review_flow import create_question
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import AMENDED, DIFFERENT, ORIGINAL, SourceVersionFixture


PREFIX = "/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}"
PACKET_CONTRACT = "oi.h1-question-evidence/1"
REPORT_CONTRACT = "oi.h1-evidence-report/1"
PRIVATE_FAILURE = "PRIVATE-FICTIONAL-EVIDENCE-FAILURE"
SUPPORT_STATEMENT = (
    "🧪 Fictional bench comparison: the invented Aster marker appeared in three "
    "authored samples; this is not an observation about a person."
)
CONTRADICT_STATEMENT = (
    "A separate fictional bench comparison found no invented Aster marker in "
    "three authored samples; the two examples do not establish clinical benefit."
)
AMENDED_STATEMENT = (
    "The corrected fictional bench comparison leaves the invented Aster marker "
    "indeterminate because its authored controls were incomplete."
)
SUPPORT_QUOTE = "the invented Aster marker appeared in three authored samples"
CONTRADICT_QUOTE = "found no invented Aster marker in three authored samples"
RATIONALE = "Human-authored fictional comparison only; independent scientific review remains pending."
WITHDRAW_REASON = "The authored evidence declaration is withdrawn pending independent verification."
ITEMS = ("metadata", "abstract", "full_text", "figures", "terminology", "api_output")
USES = ("store", "display", "redistribute", "ml_use")
ACTIONS = (
    "authored_evidence_read", "authored_evidence_import", "authored_evidence_assess", "authored_evidence_withdraw",
    "authored_evidence_original_read", "evidence_report_export",
)


def digest(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def permissions(item="full_text", *, display="allowed", export="allowed"):
    result = {name: {use: "unknown" for use in USES} for name in ITEMS}
    for name in ("metadata", item):
        result[name].update(store="allowed", display=display, redistribute=export)
    return result


def evidence_text(key="FICTION-SUPPORT", statement=SUPPORT_STATEMENT, *, amends=None):
    amendment = "" if amends is None else f"Amends: {key}@{amends}\n"
    return (
        f"OI-SYNTHETIC-EVIDENCE/1\nEvidence: {key}\n"
        f"Title: Independently authored {key} example\nIssued-At: 2026-10-30\n"
        "Rights: original-synthetic\n" + amendment + f"Statement: {statement}\n"
    )


class QuestionEvidenceRouteContractTests(unittest.TestCase):
    def test_seven_evidence_routes_reuse_the_current_authenticated_patient_api(self):
        schema = create_app(Settings.from_env({})).openapi()
        routes = (
            ("/evidence", "get"), ("/evidence", "post"),
            ("/evidence/{evidence_id}/withdraw", "post"),
            ("/evidence/{evidence_id}/original", "get"),
            ("/evidence-assessments", "post"),
            ("/evidence-reports", "post"),
            ("/evidence-reports/{report_id}", "get"),
        )
        for suffix, method in routes:
            with self.subTest(route=suffix, method=method):
                self.assertIn(PREFIX + suffix, list(schema["paths"]))
                self.assertEqual(schema["paths"][PREFIX + suffix][method]["security"],
                                 [{"SyntheticFixture": []}])


class EvidenceFixture(SourceVersionFixture):
    """Only helpers; tests below do not duplicate existing source acceptance."""

    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend((
            "composer_context_read", "question_create", "question_read", *ACTIONS,
        ))
        self.write()

    @staticmethod
    def prefix(patient, question, case="CASE-ALPHA"):
        return f"/v1/patients/{patient}/cases/{case}/questions/{question}"

    def start(self, base, *, raw=ORIGINAL, line=8):
        patient = self.setup_case(base)
        status, source, _ = self.ingest(base, patient, raw)
        self.assertEqual(status, 201, source)
        question, _ = create_question(self, base, patient, source["source_id"], line=line)
        return patient, question, source["source_id"]

    def packet(self, base, patient, question, *, case="CASE-ALPHA"):
        code, value, _ = request(base, self.prefix(patient, question, case) + "/evidence",
                                 token=TOKEN_A)
        self.assertEqual(code, 200, value)
        self.assertEqual(value["contract"], PACKET_CONTRACT)
        self.assertEqual((value["patient_id"], value["case_id"],
                          value["question"]["question_id"]), (patient, case, question))
        self.assertEqual(value["packet_sha256"], digest({
            key: item for key, item in value.items()
            if key not in {"access_receipt_id", "packet_sha256", "reports"}
        }))
        return value

    def imported(self, base, patient, question, *, key="IMPORT-SUPPORT", raw=None,
                 item="full_text", rights=None, case="CASE-ALPHA", token=TOKEN_A):
        return request(base, self.prefix(patient, question, case) + "/evidence",
                       token=token, body={
                           "synthetic": True, "request_key": key,
                           "original_text": evidence_text() if raw is None else raw,
                           "content_item": item,
                           "permissions": permissions(item) if rights is None else rights,
                       })

    def assessment_body(self, packet, evidence_id, *, key="ASSESS-SUPPORT",
                        quote=SUPPORT_QUOTE, relation="supports", applicability="limited"):
        version, = [row for row in packet["evidence"] if row["evidence_id"] == evidence_id]
        return {
            "synthetic": True, "request_key": key, "evidence_id": evidence_id,
            "evidence_sha256": version["sha256"], "rights_sha256": version["rights_sha256"],
            "expected_source_snapshot_sha256": packet["question"]["source_snapshot_sha256"],
            "expected_preflight_sha256": packet["question"]["preflight_sha256"],
            "quote": quote, "relation": relation, "applicability": applicability,
            "rationale": RATIONALE,
        }

    def assessed(self, base, patient, question, body):
        return request(base, self.prefix(patient, question) + "/evidence-assessments",
                       token=TOKEN_A, body=body)

    def report_body(self, packet, ids, *, key="REPORT-SUPPORT"):
        return {"synthetic": True, "request_key": key,
                "expected_packet_sha256": packet["packet_sha256"],
                "assessment_ids": ids}

    def reported(self, base, patient, question, body):
        return request(base, self.prefix(patient, question) + "/evidence-reports",
                       token=TOKEN_A, body=body)

    def read_report(self, base, patient, question, report_id):
        return request(base, self.prefix(patient, question) + "/evidence-reports/" + report_id,
                       token=TOKEN_A)

    def withdrawn(self, base, patient, question, evidence_id, *, key="WITHDRAW-SUPPORT"):
        return request(base, self.prefix(patient, question) + "/evidence/" + evidence_id + "/withdraw",
                       token=TOKEN_A, body={"synthetic": True, "request_key": key,
                                           "reason": WITHDRAW_REASON})

    def support_report(self, base, *, raw=ORIGINAL, line=8):
        patient, question, source = self.start(base, raw=raw, line=line)
        status, imported, _ = self.imported(base, patient, question)
        self.assertEqual(status, 201, imported)
        evidence_id = imported["evidence_id"]
        packet = self.packet(base, patient, question)
        assessment_body = self.assessment_body(packet, evidence_id)
        status, assessment, _ = self.assessed(base, patient, question, assessment_body)
        self.assertEqual(status, 201, assessment)
        packet = self.packet(base, patient, question)
        report_body = self.report_body(packet, [assessment["assessment_id"]])
        status, report, _ = self.reported(base, patient, question, report_body)
        self.assertEqual(status, 201, report)
        status, prepared, _ = self.read_report(base, patient, question, report["report_id"])
        self.assertEqual(status, 200, prepared)
        return {
            "patient": patient, "question": question, "source": source,
            "evidence_id": evidence_id, "assessment": assessment,
            "assessment_body": assessment_body, "report_body": report_body,
            "report_id": report["report_id"], "prepared": prepared,
        }

    def persisted_state(self):
        """Compare real durable rows, including commands and successful receipts."""
        queries = {
            "sources": "SELECT * FROM clinical_source.source_versions ORDER BY source_id",
            "assertions": "SELECT * FROM clinical_source.assertions ORDER BY assertion_id",
            "questions": "SELECT * FROM investigation.source_questions ORDER BY question_id",
            "versions": "SELECT * FROM investigation.case_evidence_versions ORDER BY evidence_id",
            "withdrawals": "SELECT * FROM investigation.case_evidence_withdrawals ORDER BY withdrawal_id",
            "assessments": "SELECT * FROM investigation.question_evidence_assessments ORDER BY assessment_id",
            "reports": "SELECT * FROM investigation.question_evidence_reports ORDER BY report_id",
            "commands": "SELECT * FROM investigation.evidence_commands ORDER BY operation,request_key",
            "origins": "SELECT * FROM investigation.evidence_command_origins ORDER BY operation,object_id",
            "events": "SELECT * FROM identity.identity_domain_events ORDER BY id",
        }
        with self.engine.connect() as db:
            return {key: [dict(row) for row in db.execute(text(sql)).mappings()]
                    for key, sql in queries.items()}

    def assert_denied(self, response, expected=404):
        self.assertEqual(response[0], expected, response[1])
        self.assertEqual(set(response[1]), {"detail"})
        self.assertEqual(response[2]["Cache-Control"], "no-store")
        encoded = json.dumps(response[1], ensure_ascii=False)
        for content in (SUPPORT_STATEMENT, SUPPORT_QUOTE, CONTRADICT_STATEMENT,
                        RATIONALE, PRIVATE_FAILURE, TOKEN_A):
            self.assertNotIn(content, encoded)


class QuestionEvidenceLifecycleTests(EvidenceFixture):
    def test_support_and_contradiction_preserve_originals_proposals_and_report_after_restart(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, source = self.start(base)
            initial = self.packet(base, patient, question)
            self.assertEqual((initial["evidence"], initial["assessments"], initial["reports"]),
                             ([], [], []))
            self.assertEqual(initial["human_review_state"], "not_performed")
            self.assertIs(initial["clinical_approval"], False)
            self.assertIs(initial["model_executed"], False)
            raw_support = evidence_text()
            raw_contradiction = evidence_text("FICTION-CONTRADICT", CONTRADICT_STATEMENT)
            code, supporting, _ = self.imported(base, patient, question, raw=raw_support)
            self.assertEqual(code, 201, supporting)
            code, contrary, _ = self.imported(
                base, patient, question, key="IMPORT-CONTRADICTION",
                raw=raw_contradiction, item="abstract",
            )
            self.assertEqual(code, 201, contrary)
            self.assertRegex(supporting["evidence_id"], r"^EVIDENCE-[0-9A-F]{32}$")
            packet = self.packet(base, patient, question)
            self.assertEqual(len(packet["evidence"]), 2)
            for original, receipt, item in (
                (raw_support, supporting, "full_text"),
                (raw_contradiction, contrary, "abstract"),
            ):
                row, = [row for row in packet["evidence"]
                        if row["evidence_id"] == receipt["evidence_id"]]
                self.assertEqual(row["sha256"], hashlib.sha256(original.encode()).hexdigest())
                self.assertEqual((row["statement_line"], row["version"], row["state"]),
                                 (6, 1, "current"))
                self.assertEqual(row["permissions"][item]["ml_use"], "unknown")
                self.assertEqual(row["rights_sha256"], digest(row["permissions"]))
                code, actual, _ = request(
                    base, self.prefix(patient, question) + "/evidence/" +
                    receipt["evidence_id"] + "/original", token=TOKEN_A,
                )
                self.assertEqual(code, 200, actual)
                self.assertEqual(actual["original_text"].encode(), original.encode())
                self.assertEqual(actual["sha256"], row["sha256"])
            ids = []
            for version, quote, relation, key in (
                (supporting, SUPPORT_QUOTE, "supports", "ASSESS-SUPPORT"),
                (contrary, CONTRADICT_QUOTE, "contradicts", "ASSESS-CONTRADICTION"),
            ):
                intent = self.assessment_body(packet, version["evidence_id"],
                                              quote=quote, relation=relation, key=key)
                code, assessment, _ = self.assessed(base, patient, question, intent)
                self.assertEqual(code, 201, assessment)
                self.assertRegex(assessment["assessment_id"], r"^ASSESSMENT-[0-9A-F]{32}$")
                ids.append(assessment["assessment_id"])
            packet = self.packet(base, patient, question)
            support, = [row for row in packet["assessments"] if row["relation"] == "supports"]
            self.assertEqual(support["quote_start"], SUPPORT_STATEMENT.index(SUPPORT_QUOTE))
            self.assertEqual(support["state"], "current_unreviewed")
            self.assertEqual(support["rationale"], RATIONALE)
            self.assertEqual(support["source_snapshot_sha256"], initial["question"]["source_snapshot_sha256"])
            intent = self.report_body(packet, ids, key="REPORT-TWO-RELATIONS")
            code, receipt, _ = self.reported(base, patient, question, intent)
            self.assertEqual(code, 201, receipt)
            code, report, _ = self.read_report(base, patient, question, receipt["report_id"])
            self.assertEqual(code, 200, report)
            self.assertEqual(report["contract"], REPORT_CONTRACT)
            self.assertEqual(report["state"], "current_unreviewed")
            self.assertEqual(report["body_sha256"], hashlib.sha256(report["body"].encode()).hexdigest())
            self.assertEqual(report["snapshot_sha256"], digest(report["snapshot"]))
            snapshot = report["snapshot"]
            self.assertEqual(snapshot["question"]["question_id"], question)
            self.assertEqual(snapshot["selected_source"]["source_id"], source)
            self.assertEqual({row["assessment"]["assessment_id"] for row in snapshot["comparisons"]}, set(ids))
            self.assertEqual({row["assessment"]["relation"] for row in snapshot["comparisons"]},
                             {"supports", "contradicts"})
            for value in (source, question, SUPPORT_QUOTE, CONTRADICT_QUOTE, RATIONALE):
                self.assertIn(value, report["body"])
            self.assertIs(report["clinical_approval"], False)
            self.assertIs(report["model_executed"], False)
            self.assertEqual(report["human_review_state"], "not_performed")
            # A new access receipt and report summary do not change inspected context.
            again = self.packet(base, patient, question)
            self.assertEqual(again["packet_sha256"], packet["packet_sha256"])
            self.assertNotEqual(again["access_receipt_id"], packet["access_receipt_id"])
        with running_server(create_app(self.settings)) as restarted:
            code, saved, _ = self.read_report(restarted, patient, question, receipt["report_id"])
            self.assertEqual(code, 200, saved)
            for field in ("report_id", "prepared_at", "body", "body_sha256", "snapshot", "snapshot_sha256"):
                self.assertEqual(saved[field], report[field], field)
            self.assertEqual(len(self.packet(restarted, patient, question)["assessments"]), 2)

    def test_evidence_amendment_requires_explicit_reassessment_and_preserves_exact_retry(self):
        with running_server(create_app(self.settings)) as base:
            state = self.support_report(base)
            p, q = state["patient"], state["question"]
            code, amended, _ = self.imported(
                base, p, q, key="IMPORT-AMENDMENT",
                raw=evidence_text(statement=AMENDED_STATEMENT, amends=1),
            )
            self.assertEqual((code, amended["version"]), (201, 2), amended)
            packet = self.packet(base, p, q)
            self.assertEqual([row["state"] for row in packet["evidence"]], ["superseded", "current"])
            self.assertEqual(packet["assessments"][0]["state"], "reassessment_required")
            prior = self.read_report(base, p, q, state["report_id"])[1]
            self.assertEqual(prior["state"], "historical_reassessment_required")
            self.assertEqual(prior["body"], state["prepared"]["body"])
            self.assertEqual(prior["snapshot"], state["prepared"]["snapshot"])
            for command, body, identity in (
                (self.assessed, state["assessment_body"], "assessment_id"),
                (self.reported, state["report_body"], "report_id"),
            ):
                code, recovered, _ = command(base, p, q, body)
                self.assertEqual((code, recovered["duplicate"]), (200, True), recovered)
                expected = state["assessment"]["assessment_id"] if identity == "assessment_id" else state["report_id"]
                self.assertEqual(recovered[identity], expected)
                self.assertEqual(command(base, p, q, {**body, "request_key": "NEW-STALE-KEY"})[0], 409)
            intent = self.assessment_body(
                packet, amended["evidence_id"], key="REASSESS-AMENDED",
                quote="leaves the invented Aster marker indeterminate", relation="context",
            )
            code, new_assessment, _ = self.assessed(base, p, q, intent)
            self.assertEqual(code, 201, new_assessment)
            packet = self.packet(base, p, q)
            self.assertEqual([row["state"] for row in packet["assessments"]],
                             ["reassessment_required", "current_unreviewed"])
            report_intent = self.report_body(packet, [new_assessment["assessment_id"]], key="REPORT-AMENDED")
            code, new_report, _ = self.reported(base, p, q, report_intent)
            self.assertEqual(code, 201, new_report)
            self.assertNotEqual(new_report["report_id"], state["report_id"])
            self.assertIn("leaves the invented Aster marker indeterminate",
                          self.read_report(base, p, q, new_report["report_id"])[1]["body"])

    def test_amended_episode_is_not_substituted_in_saved_brief_or_preserved_report(self):
        from test_oncology_findings import HEADER, LINES

        self.creds[0]["actions"].append("source_brief_export")
        self.write()
        with running_server(create_app(self.settings)) as base:
            state = self.support_report(base, raw=HEADER + LINES, line=10)
            p, q, original = state["patient"], state["question"], state["prepared"]
            source = original["snapshot"]["selected_source"]
            self.assertEqual(source["oncology"], {"role": "metastasis", "episode_id": None})
            self.assertEqual((source["source_id"], source["version"], source["line"]), (state["source"], 1, 10))
            saved = original["snapshot"]["question"]
            intent = dict(synthetic=True, source_snapshot_contract=saved["source_snapshot_contract"],
                          expected_source_snapshot_sha256=saved["source_snapshot_sha256"],
                          expected_preflight_sha256=saved["preflight_sha256"])
            path = self.prefix(p, q) + "/brief"
            status, brief, _ = request(base, path, token=TOKEN_A, body=intent)
            self.assertEqual(status, 200, brief)
            self.assertEqual(brief["selected_source"], source)
            self.assertIn("Source oncology role: metastasis. episode: unassigned", original["body"])
            amended = HEADER + "Amends: DOC-ALPHA@1\n" + LINES.replace("metastasis|?", "metastasis|EP-B")
            self.assertEqual(self.ingest(base, p, amended)[0], 201)
            self.assertEqual(request(base, path, token=TOKEN_A, body=intent)[0], 409)
            status, historical, _ = self.read_report(base, p, q, state["report_id"])
            self.assertEqual(status, 200, historical)
            self.assertEqual(historical["state"], "historical_reassessment_required")
            for key in ("body", "snapshot", "body_sha256", "snapshot_sha256"):
                self.assertEqual(historical[key], original[key])

    def test_source_amendment_keeps_old_report_historical_and_new_question_can_reuse_case_evidence(self):
        with running_server(create_app(self.settings)) as base:
            state = self.support_report(base)
            p, q = state["patient"], state["question"]
            code, amended, _ = self.ingest(base, p, AMENDED)
            self.assertEqual(code, 201, amended)
            packet = self.packet(base, p, q)
            self.assertEqual(packet["question"]["source_context_state"], "source_reassessment_required")
            self.assertEqual(packet["assessments"][0]["state"], "reassessment_required")
            self.assertEqual(self.assessed(base, p, q, {
                **state["assessment_body"], "request_key": "NEW-AFTER-SOURCE-AMENDMENT",
            })[0], 409)
            old = self.read_report(base, p, q, state["report_id"])[1]
            self.assertEqual(old["state"], "historical_reassessment_required")
            self.assertEqual(old["body_sha256"], state["prepared"]["body_sha256"])
            new_q, _ = create_question(self, base, p, amended["source_id"], line=9,
                                       request_key="QUESTION-SOURCE-AMENDED")
            current = self.packet(base, p, new_q)
            self.assertEqual(current["evidence"][0]["evidence_id"], state["evidence_id"])
            self.assertEqual(current["assessments"], [])
            intent = self.assessment_body(current, state["evidence_id"], key="ASSESS-NEW-QUESTION")
            self.assertEqual(self.assessed(base, p, new_q, intent)[0], 201)
            self.assertEqual(self.packet(base, p, q)["assessments"][0]["assessment_id"],
                             state["assessment"]["assessment_id"])

    def test_withdrawal_withholds_prior_quotations_and_reports_without_erasing_history(self):
        with running_server(create_app(self.settings)) as base:
            state = self.support_report(base)
            p, q, eid = state["patient"], state["question"], state["evidence_id"]
            code, receipt, _ = self.withdrawn(base, p, q, eid)
            self.assertEqual((code, receipt["duplicate"]), (201, False), receipt)
            self.assertRegex(receipt["withdrawal_id"], r"^WITHDRAWAL-[0-9A-F]{32}$")
            self.assertEqual(self.withdrawn(base, p, q, eid)[:2],
                             (200, {**receipt, "duplicate": True}))
            packet = self.packet(base, p, q)
            row = packet["evidence"][0]
            self.assertEqual(row["state"], "withdrawn")
            self.assertIsNone(row["statement"])
            self.assertIsNone(row["title"])
            assessment = packet["assessments"][0]
            self.assertEqual(assessment["state"], "content_withheld")
            for field in ("quote", "quote_start", "rationale"):
                self.assertIsNone(assessment[field])
            code, report, _ = self.read_report(base, p, q, state["report_id"])
            self.assertEqual(code, 200, report)
            self.assertEqual(report["state"], "content_withheld")
            self.assertIsNone(report["body"])
            self.assertIsNone(report["snapshot"])
            self.assertEqual(report["body_sha256"], state["prepared"]["body_sha256"])
            self.assertNotIn(SUPPORT_QUOTE, json.dumps(packet))
            self.assert_denied(request(base, self.prefix(p, q) + "/evidence/" + eid + "/original", token=TOKEN_A))
            # Receipt recovery remains exact, not permission to disclose content.
            self.assertEqual(self.assessed(base, p, q, state["assessment_body"])[0], 200)
            self.assertEqual(self.reported(base, p, q, state["report_body"])[0], 200)
            self.assertEqual(self.imported(base, p, q, key="WITHDRAWN-REVIVE",
                                          raw=evidence_text(statement=AMENDED_STATEMENT, amends=1))[0], 409)
            with self.engine.connect() as db:
                self.assertEqual(db.execute(text(
                    "SELECT count(*) FROM investigation.case_evidence_versions"
                )).scalar_one(), 1)
                self.assertEqual(db.execute(text(
                    "SELECT count(*) FROM investigation.question_evidence_reports"
                )).scalar_one(), 1)

    def test_identical_content_recovery_and_changed_request_intents_do_not_duplicate_effects(self):
        with running_server(create_app(self.settings)) as base:
            p, q, _ = self.start(base)
            code, first, _ = self.imported(base, p, q)
            self.assertEqual(code, 201, first)
            self.assertEqual(self.imported(base, p, q)[:2], (200, {**first, "duplicate": True}))
            another = self.imported(base, p, q, key="IMPORT-OTHER-KEY")
            self.assertEqual(another[:2], (200, {**first, "duplicate": True}))
            for key in ("IMPORT-SUPPORT", "IMPORT-OTHER-KEY"):
                self.assertEqual(self.imported(base, p, q, key=key, rights=permissions(export="denied"))[0], 409)
            self.assertEqual(self.imported(base, p, q, key="CONFLICTING-RIGHTS", rights=permissions(export="denied"))[0], 409)
            self.assertEqual(self.imported(base, p, q, key="UNDECLARED-AMENDMENT",
                                          raw=evidence_text(statement=AMENDED_STATEMENT))[0], 409)
            self.assertEqual(self.imported(base, p, q, key="WRONG-AMENDMENT",
                                          raw=evidence_text(statement=AMENDED_STATEMENT, amends=7))[0], 409)
            packet = self.packet(base, p, q)
            intent = self.assessment_body(packet, first["evidence_id"])
            code, assessed, _ = self.assessed(base, p, q, intent)
            self.assertEqual(code, 201, assessed)
            self.assertEqual(self.assessed(base, p, q, intent)[:2], (200, {**assessed, "duplicate": True}))
            self.assertEqual(self.assessed(base, p, q, {**intent, "rationale": RATIONALE + " Changed."})[0], 409)
            self.creds[0]["actor"] = "ACTOR-CHANGED"
            self.write()
            self.assertEqual(self.assessed(base, p, q, intent)[0], 409)
            with self.engine.connect() as db:
                counts = [db.execute(text("SELECT count(*) FROM investigation." + name)).scalar_one()
                          for name in ("case_evidence_versions", "question_evidence_assessments")]
            self.assertEqual(counts, [1, 1])

    def test_latest_explicit_assessment_replaces_current_proposal_without_rewriting_prior_report(self):
        with running_server(create_app(self.settings)) as base:
            state = self.support_report(base)
            p, q = state["patient"], state["question"]
            packet = self.packet(base, p, q)
            revised = self.assessment_body(packet, state["evidence_id"], key="REVISED-APPRAISAL",
                                          relation="unknown", applicability="unknown")
            code, saved, _ = self.assessed(base, p, q, revised)
            self.assertEqual(code, 201, saved)
            packet = self.packet(base, p, q)
            self.assertEqual([row["state"] for row in packet["assessments"]],
                             ["reassessment_required", "current_unreviewed"])
            prior = self.read_report(base, p, q, state["report_id"])[1]
            self.assertEqual(prior["state"], "historical_reassessment_required")
            self.assertEqual(prior["snapshot"], state["prepared"]["snapshot"])
            intent = self.report_body(packet, [state["assessment"]["assessment_id"]], key="REUSE-OLD-ASSESSMENT")
            self.assertEqual(self.reported(base, p, q, intent)[0], 409)


class QuestionEvidenceRightsAndScopeTests(EvidenceFixture):
    def test_exact_declared_content_item_and_metadata_gate_storage_independently(self):
        with running_server(create_app(self.settings)) as base:
            p, q, _ = self.start(base)
            for label, item, rights in (
                ("no-item-store", "abstract", permissions("api_output")),
                ("no-metadata-store", "full_text", {"full_text": {"store": "allowed"}}),
                ("unknown", "full_text", {}),
                ("denied", "full_text", {"metadata": {"store": "allowed"},
                                           "full_text": {"store": "denied"}}),
            ):
                with self.subTest(reason=label):
                    before = self.persisted_state()
                    self.assert_denied(self.imported(base, p, q, key=label,
                                                     item=item, rights=rights))
                    self.assertEqual(self.persisted_state(), before)
            for item in ("full_text", "abstract", "api_output"):
                code, saved, _ = self.imported(base, p, q, key="IMPORT-" + item,
                    raw=evidence_text("FICTION-" + item.replace("_", "-").upper()), item=item)
                self.assertEqual(code, 201, saved)
            packet = self.packet(base, p, q)
            self.assertEqual({row["content_item"] for row in packet["evidence"]},
                             {"full_text", "abstract", "api_output"})
            for row in packet["evidence"]:
                self.assertEqual(row["statement"], SUPPORT_STATEMENT)
                self.assertEqual(row["permissions"][row["content_item"]]["ml_use"], "unknown")
                for other in {"full_text", "abstract", "api_output"} - {row["content_item"]}:
                    self.assertEqual(row["permissions"][other]["display"], "unknown")

    def test_store_only_evidence_is_not_displayed_or_assessed_and_read_does_not_grant_export(self):
        with running_server(create_app(self.settings)) as base:
            p, q, _ = self.start(base)
            code, stored, _ = self.imported(base, p, q, rights=permissions(display="denied"))
            self.assertEqual(code, 201, stored)
            packet = self.packet(base, p, q)
            self.assertIsNone(packet["evidence"][0]["statement"])
            self.assertIsNone(packet["evidence"][0]["title"])
            self.assert_denied(self.assessed(base, p, q, self.assessment_body(packet, stored["evidence_id"])))
            self.assert_denied(request(base, self.prefix(p, q) + "/evidence/" +
                                       stored["evidence_id"] + "/original", token=TOKEN_A))
            code, visible, _ = self.imported(base, p, q, key="DISPLAY-ONLY-IMPORT",
                raw=evidence_text("FICTION-DISPLAY-ONLY"), rights=permissions(export="denied"))
            self.assertEqual(code, 201, visible)
            packet = self.packet(base, p, q)
            intent = self.assessment_body(packet, visible["evidence_id"], key="DISPLAY-ONLY-ASSESS")
            code, assessment, _ = self.assessed(base, p, q, intent)
            self.assertEqual(code, 201, assessment)
            packet = self.packet(base, p, q)
            self.assertEqual(packet["assessments"][0]["quote"], SUPPORT_QUOTE)
            before = self.persisted_state()
            self.assert_denied(self.reported(base, p, q,
                self.report_body(packet, [assessment["assessment_id"]])))
            self.assertEqual(self.persisted_state(), before)

    def test_metadata_redistribution_is_required_even_when_content_item_allows_export(self):
        with running_server(create_app(self.settings)) as base:
            p, q, _ = self.start(base)
            rights = permissions("api_output")
            rights["metadata"]["redistribute"] = "unknown"
            code, saved, _ = self.imported(base, p, q, item="api_output", rights=rights)
            self.assertEqual(code, 201, saved)
            packet = self.packet(base, p, q)
            code, assessed, _ = self.assessed(base, p, q, self.assessment_body(packet, saved["evidence_id"]))
            self.assertEqual(code, 201, assessed)
            packet = self.packet(base, p, q)
            self.assert_denied(self.reported(base, p, q,
                self.report_body(packet, [assessed["assessment_id"]])))

    def test_later_abstract_permission_cannot_authorize_an_old_full_text_report(self):
        with running_server(create_app(self.settings)) as base:
            state = self.support_report(base)
            p, q = state["patient"], state["question"]
            code, amended, _ = self.imported(base, p, q, key="ABSTRACT-DECLARATION",
                raw=evidence_text(statement=AMENDED_STATEMENT, amends=1), item="abstract")
            self.assertEqual(code, 201, amended)
            packet = self.packet(base, p, q)
            previous = next(row for row in packet["evidence"] if row["evidence_id"] == state["evidence_id"])
            current = next(row for row in packet["evidence"] if row["evidence_id"] == amended["evidence_id"])
            self.assertIsNone(previous["statement"])
            self.assertEqual(current["statement"], AMENDED_STATEMENT)
            self.assertEqual(packet["assessments"][0]["state"], "content_withheld")
            report = self.read_report(base, p, q, state["report_id"])[1]
            self.assertEqual(report["state"], "content_withheld")
            self.assertIsNone(report["body"])
            self.assertIsNone(report["snapshot"])
            self.assertEqual(report["snapshot_sha256"], state["prepared"]["snapshot_sha256"])

    def test_current_redistribution_withdrawal_withholds_old_report_but_preserves_reader(self):
        with running_server(create_app(self.settings)) as base:
            state = self.support_report(base)
            p, q = state["patient"], state["question"]
            self.assertEqual(self.imported(base, p, q, key="EXPORT-NOW-DENIED",
                raw=evidence_text(statement=AMENDED_STATEMENT, amends=1),
                rights=permissions(export="denied"))[0], 201)
            packet = self.packet(base, p, q)
            old = next(row for row in packet["evidence"] if row["evidence_id"] == state["evidence_id"])
            self.assertEqual(old["statement"], SUPPORT_STATEMENT)
            self.assertEqual(packet["assessments"][0]["quote"], SUPPORT_QUOTE)
            self.assertEqual(packet["assessments"][0]["state"], "reassessment_required")
            report = self.read_report(base, p, q, state["report_id"])[1]
            self.assertEqual(report["state"], "content_withheld")
            self.assertIsNone(report["body"])

    def test_independent_action_and_patient_organization_purpose_grants_are_required(self):
        with running_server(create_app(self.settings)) as base:
            state = self.support_report(base)
            p, q, eid = state["patient"], state["question"], state["evidence_id"]
            prefix = self.prefix(p, q)
            packet = self.packet(base, p, q)
            operations = (
                ("authored_evidence_read", prefix + "/evidence", None),
                ("authored_evidence_import", prefix + "/evidence", {
                    "synthetic": True, "request_key": "IMPORT-SUPPORT", "original_text": evidence_text(),
                    "content_item": "full_text", "permissions": permissions(),
                }),
                ("authored_evidence_assess", prefix + "/evidence-assessments", state["assessment_body"]),
                ("authored_evidence_withdraw", prefix + "/evidence/" + eid + "/withdraw", {
                    "synthetic": True, "request_key": "WITHDRAW-NO-GRANT", "reason": WITHDRAW_REASON,
                }),
                ("authored_evidence_original_read", prefix + "/evidence/" + eid + "/original", None),
                ("evidence_report_export", prefix + "/evidence-reports", state["report_body"]),
                ("evidence_report_export", prefix + "/evidence-reports/" + state["report_id"], None),
            )
            initial = copy.deepcopy(self.creds)
            for action, path, body in operations:
                for missing in {action, "patient_read", "source_read", "question_read", "authored_evidence_read"}:
                    with self.subTest(route=path.rsplit("/", 1)[-1], missing=missing):
                        before = self.persisted_state()
                        self.creds = copy.deepcopy(initial)
                        self.creds[0]["actions"].remove(missing)
                        self.write()
                        self.assert_denied(request(base, path, token=TOKEN_A, body=body))
                        self.assertEqual(self.persisted_state(), before)
            self.creds = copy.deepcopy(initial)
            self.write()
            for field, value in (("patient_ids", []), ("organization", "ORG-OTHER"),
                                 ("purpose", "research")):
                with self.subTest(field=field):
                    before = self.persisted_state()
                    self.creds = copy.deepcopy(initial)
                    self.creds[0][field] = value
                    self.write()
                    self.assert_denied(request(base, prefix + "/evidence", token=TOKEN_A))
                    self.assertEqual(self.persisted_state(), before)
            self.creds = copy.deepcopy(initial)
            self.creds[1]["actions"] = self.creds[0]["actions"][:]
            self.creds[1]["patient_ids"] = [p]
            self.write()
            self.assert_denied(request(base, prefix + "/evidence", token=TOKEN_B))
            self.assert_denied(request(base, prefix + "/evidence"), 401)

    def test_case_and_question_boundary_prevents_reusing_another_cases_evidence(self):
        with running_server(create_app(self.settings)) as base:
            state = self.support_report(base)
            p, q, eid = state["patient"], state["question"], state["evidence_id"]
            second = self.setup_case(base, case="CASE-BETA", key="CREATE-SECOND",
                                     source_subject="SUBJECT-BETA")
            code, source, _ = self.ingest(base, second, DIFFERENT, case="CASE-BETA")
            self.assertEqual(code, 201, source)
            prefix = f"/v1/patients/{second}/cases/CASE-BETA"
            code, world, _ = request(base, prefix + "/world-model", token=TOKEN_A)
            self.assertEqual(code, 200, world)
            question_text = "Which independently fictional imaging source needs verification?"
            body = {"synthetic": True, "source_id": source["source_id"], "source_line": 7,
                    "question": question_text, "expected_source_snapshot_sha256": world["snapshot_fingerprint"]}
            code, prepared, _ = request(base, prefix + "/composer/source-preflight", token=TOKEN_A, body=body)
            self.assertEqual(code, 200, prepared)
            code, saved, _ = request(base, prefix + "/questions", token=TOKEN_A, body={
                **body, "request_key": "QUESTION-SECOND-CASE", "expected_preflight_sha256": prepared["preflight_sha256"],
            })
            self.assertEqual(code, 201, saved)
            second_q = saved["question_id"]
            other = self.packet(base, second, second_q, case="CASE-BETA")
            self.assertEqual(other["evidence"], [])
            for path in (
                self.prefix(second, q, "CASE-BETA") + "/evidence",
                self.prefix(p, q, "CASE-BETA") + "/evidence",
                self.prefix(second, second_q, "CASE-BETA") + "/evidence/" + eid + "/original",
                self.prefix(second, second_q, "CASE-BETA") + "/evidence-reports/" + state["report_id"],
            ):
                with self.subTest(path=path):
                    self.assert_denied(request(base, path, token=TOKEN_A))
            self.assert_denied(request(base, self.prefix(second, second_q, "CASE-BETA") +
                "/evidence/" + eid + "/withdraw", token=TOKEN_A,
                body={"synthetic": True, "request_key": "WRONG-CASE-WITHDRAW", "reason": WITHDRAW_REASON}))
            code, second_evidence, _ = self.imported(base, second, second_q, case="CASE-BETA")
            self.assertEqual(code, 201, second_evidence)
            self.assertNotEqual(second_evidence["evidence_id"], eid)
            self.assertEqual(self.packet(base, p, q)["evidence"][0]["state"], "current")

    def test_forged_anchors_ambiguous_quotes_and_stale_packet_cannot_create_current_proposals(self):
        with running_server(create_app(self.settings)) as base:
            p, q, _ = self.start(base)
            code, evidence, _ = self.imported(base, p, q)
            self.assertEqual(code, 201, evidence)
            packet = self.packet(base, p, q)
            original = self.assessment_body(packet, evidence["evidence_id"])
            cases = (
                ({"evidence_sha256": "0" * 64}, 409),
                ({"rights_sha256": "0" * 64}, 409),
                ({"expected_source_snapshot_sha256": "0" * 64}, 409),
                ({"expected_preflight_sha256": "0" * 64}, 409),
                ({"quote": "This quotation was never in the authored evidence."}, 422),
                ({"quote": ""}, 422),
                ({"quote": "x" * 401}, 422),
                ({"relation": "supports", "applicability": "not_applicable"}, 422),
                ({"rationale": "Invisible\u202edirection is prohibited."}, 422),
                ({"source_line": 8}, 422),
                ({"synthetic": False}, 422),
            )
            for override, status in cases:
                with self.subTest(override=override):
                    before = self.persisted_state()
                    self.assert_denied(self.assessed(base, p, q, {**original, **override}), status)
                    self.assertEqual(self.persisted_state(), before)
            code, saved, _ = self.assessed(base, p, q, original)
            self.assertEqual(code, 201, saved)
            stale_report = self.report_body(packet, [saved["assessment_id"]])
            self.assertEqual(self.reported(base, p, q, stale_report)[0], 409)
            packet = self.packet(base, p, q)
            self.assertEqual(self.reported(base, p, q, self.report_body(packet, []))[0], 422)
            self.assertEqual(self.reported(base, p, q,
                self.report_body(packet, [saved["assessment_id"], saved["assessment_id"]]))[0], 422)
            code, repeated, _ = self.imported(base, p, q, key="AMBIGUOUS-IMPORT",
                raw=evidence_text("FICTION-REPEATED", "Echo phrase appears. Echo phrase appears again in this fictional text."))
            self.assertEqual(code, 201, repeated)
            packet = self.packet(base, p, q)
            ambiguous = self.assessment_body(packet, repeated["evidence_id"], key="AMBIGUOUS-QUOTE", quote="Echo phrase")
            self.assertEqual(self.assessed(base, p, q, ambiguous)[0], 422)
            code, overlapping, _ = self.imported(base, p, q, key="OVERLAPPING-IMPORT",
                raw=evidence_text("FICTION-OVERLAPPING", "Fictional aaa marker text has two overlapping matching passages."))
            self.assertEqual(code, 201, overlapping)
            packet = self.packet(base, p, q)
            ambiguous = self.assessment_body(packet, overlapping["evidence_id"], key="OVERLAPPING-QUOTE", quote="aa")
            self.assertEqual(self.assessed(base, p, q, ambiguous)[0], 422)

    def test_malformed_import_contract_does_not_store_arbitrary_or_misclassified_text(self):
        with running_server(create_app(self.settings)) as base:
            p, q, _ = self.start(base)
            good = {"synthetic": True, "request_key": "BAD-IMPORT",
                    "original_text": evidence_text(), "content_item": "full_text",
                    "permissions": permissions()}
            for changes in (
                {"synthetic": False}, {"original_text": "Unframed arbitrary content"},
                {"original_text": evidence_text().replace("original-synthetic", "public-domain")},
                {"original_text": evidence_text().replace("\n", "\r\n")},
                {"content_item": "metadata"}, {"content_item": "Full Text"},
                {"permissions": {"invented_item": {"store": "allowed"}}},
                {"permissions": {"full_text": {"invented_use": "allowed"}}},
                {"permissions": {"full_text": {"store": True}}},
                {"unexpected": "must not be ignored"},
            ):
                with self.subTest(changes=changes):
                    before = self.persisted_state()
                    response = request(base, self.prefix(p, q) + "/evidence", token=TOKEN_A,
                                       body={**good, **changes})
                    self.assert_denied(response, 422)
                    self.assertEqual(self.persisted_state(), before)
