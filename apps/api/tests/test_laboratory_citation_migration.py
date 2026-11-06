"""Populated PostgreSQL upgrades and direct-database typed citation invariants."""
import json
import uuid

from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from oi_api.contracts import SCHEMA_REVISION
from oi_api.evidence_catalog import append_rights_decision, fictional_records, seed_fictional_records
from oi_api.migrate import migrate
from oi_api.question_evidence import PostgresLaboratoryQuestionEvidence
import test_evidence_convergence_migrations as evidence
import test_lab_manual_convergence as joined
import test_laboratory_question_migration as previous
from test_source_versions import SourceVersionFixture

PREVIOUS = previous.QUESTION_REVISION


class LaboratoryCitationMigrationTests(SourceVersionFixture):
    services = evidence.EvidenceConvergenceMigrationTests.services
    start_at = evidence.EvidenceConvergenceMigrationTests.start_at
    snapshot = evidence.EvidenceConvergenceMigrationTests.snapshot
    seed_lab = joined.LabManualPopulatedMigrationTests.seed_lab

    def test_populated_0018_upgrades_and_exact_anchor_rights_are_required(self):
        patient, _, question, saved = previous.LaboratoryQuestionMigrationTests.seed(self)
        with self.services() as registry:
            seed_fictional_records(registry, fictional_records(), recorded_by="FICTIONAL-AUTHOR")
        before = self.snapshot()
        migrate(self.admin, "upgrade", SCHEMA_REVISION)
        self.assertEqual(self.snapshot(before[0]), before)
        self.assertEqual(self.snapshot()[0]["investigation.laboratory_citation_anchors"], [])
        migrate(self.admin, "downgrade", PREVIOUS)
        self.assertEqual(self.snapshot(), before)
        migrate(self.admin, "upgrade", SCHEMA_REVISION)

        qid = saved["question_id"]
        scope = (patient, "CASE-ALPHA", qid)
        with self.services() as registry:
            owner = PostgresLaboratoryQuestionEvidence(registry)
            hit, = owner.search(*scope, query="continuity", **evidence.OPTIONS)["records"]
            command = dict(citation=hit["citation"], expected_metadata_sha256=hit["metadata_sha256"],
                           source_snapshot_contract="oi.pg-source-world-model/1",
                           expected_source_snapshot_sha256=question["expected_source_snapshot_sha256"],
                           expected_preflight_sha256=question["expected_preflight_sha256"],
                           request_key="LAB-CITATION-VALID")
            receipt = owner.create_link(*scope, **command, **evidence.OPTIONS)
        old = receipt["link_id"]
        with self.engine.connect() as conn:
            original = conn.execute(text("SELECT rights_decision_id FROM investigation.laboratory_citation_anchors "
                                         "WHERE link_id=:link"), {"link": old}).scalar_one()
            wrong = conn.execute(text("SELECT decision_id FROM investigation.evidence_rights_decisions "
                                      "WHERE record_id='FICT-TRIAL-PREPARATION'")).scalar_one()

        def insert_copy(conn, *, anchor=True, rights=original, replace_ref=False):
            link = "EVIDENCE-LINK-" + uuid.uuid4().hex.upper()
            if anchor:
                override = {"link_id": link, "rights_decision_id": rights}
                if replace_ref:
                    override["observation_reference"] = "Observation/FICTIONAL-NO-SUCH-OBS"
                conn.execute(text("""
                    INSERT INTO investigation.laboratory_citation_anchors
                    SELECT (jsonb_populate_record(NULL::investigation.laboratory_citation_anchors,
                        to_jsonb(a) || CAST(:replacements AS jsonb))).*
                    FROM investigation.laboratory_citation_anchors a WHERE link_id=:old
                """), {"old": old, "replacements": json.dumps(override)})
            conn.execute(text("""
                INSERT INTO investigation.question_evidence_links
                SELECT (jsonb_populate_record(NULL::investigation.question_evidence_links,
                    to_jsonb(l) || CAST(:replacements AS jsonb))).*
                FROM investigation.question_evidence_links l WHERE link_id=:old
            """), {"old": old, "replacements": json.dumps({"link_id": link, "request_key": link})})

        for label, options, error in (
                ("no typed provenance", {"anchor": False}, "OI-LAB-CITATION-ANCHOR-REQUIRED"),
                ("unrelated rights", {"rights": wrong}, "OI-LAB-CITATION-RIGHTS"),
                ("wrong observation", {"replace_ref": True}, "foreign key constraint")):
            with self.subTest(label=label), self.assertRaisesRegex(DBAPIError, error):
                with self.engine.begin() as conn:
                    insert_copy(conn, **options)
        with self.services() as registry:
            append_rights_decision(registry, "FICT-RECORD-CONTINUITY", "1",
                permissions={"metadata": {"store": "allowed", "display": "denied"}},
                revoked=False, superseded=False, recorded_by="FICTIONAL-AUTHOR",
                reason="Withdraw fictional display permission")
        with self.assertRaisesRegex(DBAPIError, "OI-LAB-CITATION-RIGHTS"):
            with self.engine.begin() as conn:
                insert_copy(conn)
        with self.engine.connect() as conn:
            decision = conn.execute(text("SELECT decision_id FROM investigation.evidence_rights_decisions "
                                         "WHERE record_id='FICT-RECORD-CONTINUITY' ORDER BY revision DESC LIMIT 1")).scalar_one()
        with self.assertRaisesRegex(DBAPIError, "OI-LAB-CITATION-RIGHTS"):
            with self.engine.begin() as conn:
                insert_copy(conn, rights=decision)
        # PostgreSQL checks all referencing tables before it
        # runs a parent's BEFORE TRUNCATE trigger. Exercise both boundaries.
        with self.assertRaisesRegex(DBAPIError, "cannot truncate a table referenced"):
            with self.engine.begin() as conn:
                conn.execute(text("TRUNCATE investigation.laboratory_question_anchors"))
        for command in ("TRUNCATE investigation.laboratory_question_anchors, investigation.laboratory_citation_anchors, "
                        "investigation.laboratory_inspection_snapshots",
                        "UPDATE investigation.laboratory_citation_anchors SET rights_decision_id=rights_decision_id",
                        "DELETE FROM investigation.laboratory_citation_anchors",
                        "TRUNCATE investigation.laboratory_citation_anchors"):
            with self.subTest(command=command), self.assertRaisesRegex(DBAPIError, "HISTORY-IMMUTABLE"):
                with self.engine.begin() as conn:
                    conn.execute(text(command))
        preserved = self.snapshot()
        with self.assertRaisesRegex(CommandError, "Stored laboratory citation history"):
            migrate(self.admin, "downgrade", PREVIOUS)
        self.assertEqual(self.snapshot(), preserved)
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one(),
                             SCHEMA_REVISION)
