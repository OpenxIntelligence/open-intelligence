"""Populated PostgreSQL upgrades from both published episode and execution schemas."""
import unittest

from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from http_support import running_server
from oi_api.app import create_app
from oi_api.composer_preflight import PostgresSourceComposerPreflight
from oi_api.composer_runs import PostgresComposerRuns
from oi_api.contracts import SCHEMA_REVISION
from oi_api.episode_drafts import DraftCommand, _save
from oi_api.migrate import migrate
from oi_api.source_questions import PostgresSourceQuestions
from oi_api.source_world_model import project_source_world_model
from oi_api.sources import PostgresSourceVersions
from test_document_image_convergence import graph
import test_evidence_convergence_migrations as previous
import test_image_report_convergence_migrations as images
import test_lab_manual_convergence as laboratory
from test_oncology_findings import HEADER, LINES
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import SourceVersionFixture

EPISODES = "0023_episode_drafts"
CORE = "0027_source_purpose"
JOIN = "0028_episode_core_join"
CASE = "CASE-ALPHA"


class EpisodeGraphTests(unittest.TestCase):
    def test_only_the_guarded_join_serves_patient_requests(self):
        script = graph()
        self.assertEqual(script.get_heads(), ["0030_review_history_guard"])
        self.assertEqual(SCHEMA_REVISION, script.get_current_head())
        self.assertEqual(script.get_revision(SCHEMA_REVISION).down_revision, "0029_episode_history_guard")
        self.assertEqual(script.get_revision("0029_episode_history_guard").down_revision, JOIN)
        self.assertEqual(set(script.get_revision(JOIN).down_revision), {EPISODES, CORE})
        self.assertEqual(script.get_revision(EPISODES).down_revision, "0022_lab_citation_source_scope")


class EpisodeUpgradeTests(SourceVersionFixture):
    services = previous.PublishedEvidenceFixture.services
    start_with_source = previous.PublishedEvidenceFixture.start_with_source
    snapshot = previous.EvidenceConvergenceMigrationTests.snapshot
    heads = images.ImageReportConvergenceMigrationTests.heads
    readiness = images.ImageReportConvergenceMigrationTests.readiness
    assert_existing_history_preserved = laboratory.LabManualPopulatedMigrationTests.assert_existing_history_preserved

    def seed_origin(self, revision):
        patient, _, _ = self.start_with_source(revision)
        with self.services() as registry:
            sources = PostgresSourceVersions(registry)
            receipt = sources.import_original(patient, CASE, (HEADER + LINES).encode(), **previous.OPTIONS)
            world = project_source_world_model(sources.list(patient, CASE, **previous.OPTIONS))
            origin = next(o for o in world["observations"] if o["source_id"] == receipt["source_id"]
                          and o["finding_key"] == "breast")
            draft = DraftCommand(synthetic=True, source_id=origin["source_id"], source_line=origin["source_line"],
                                 source_version=origin["document_version"], source_sha256=origin["source_sha256"],
                                 snapshot_sha256=world["snapshot_fingerprint"])
        return patient, draft

    def save_on_old_owner(self, registry, patient, draft):
        return PostgresSourceVersions(registry).list(
            patient, CASE, **previous.COMMON, recheck_authority=lambda: None,
            prepare_response=lambda index: _save(registry, project_source_world_model(index), draft,
                                                  previous.COMMON["actor"])).model_dump()

    def check_parent(self, revision):
        patient, draft = self.seed_origin(revision)
        anchor = dict(source_id=draft.source_id, source_line=draft.source_line,
                      question="Which details of this fictional source require review?",
                      expected_source_snapshot_sha256=draft.snapshot_sha256)
        with self.services() as registry:
            prepared = PostgresSourceComposerPreflight(registry).preview(patient, CASE, **previous.OPTIONS, **anchor)
            question = PostgresSourceQuestions(registry).create(patient, CASE, **previous.OPTIONS, **anchor,
                request_key="EPISODE-JOIN-QUESTION", expected_preflight_sha256=prepared["preflight_sha256"])["question_id"]
            intent = dict(request_key="EPISODE-JOIN-RUN", source_snapshot_contract=prepared["source_snapshot_contract"],
                          expected_source_snapshot_sha256=draft.snapshot_sha256,
                          expected_preflight_sha256=prepared["preflight_sha256"])
            if revision == EPISODES:
                original = self.save_on_old_owner(registry, patient, draft)["episode_id"]
            else:
                original = PostgresComposerRuns(registry).enqueue(
                    patient, CASE, question, **previous.OPTIONS, **intent)["run"]["run_id"]

        before = self.snapshot()
        migrate(self.admin, "upgrade", JOIN)
        self.assertEqual(self.heads(), {JOIN})
        self.readiness(False)
        self.assert_existing_history_preserved(before)
        joined = self.snapshot()
        migrate(self.admin, "upgrade", "head")
        migrate(self.admin, "upgrade", "head")
        self.assertEqual(self.heads(), {SCHEMA_REVISION})
        self.readiness(True)
        self.assertEqual(self.snapshot(), joined)
        with self.engine.connect() as db:
            events = db.execute(text("SELECT id,metadata_json->>'source_id' FROM identity.identity_domain_events "
                                     "WHERE patient_id=:p AND event_type='source.original.imported' ORDER BY id"),
                                {"p": patient}).all()
            delivered = db.execute(text("SELECT event_id,source_id FROM coordination.source_event_outbox "
                                        "WHERE patient_id=:p AND case_id=:c ORDER BY event_id"),
                                   {"p": patient, "c": CASE}).all()
        self.assertEqual(len(events), 2)
        self.assertEqual(delivered, events)

        self.creds[0]["actions"].extend(("episode_draft_read", "episode_draft_create",
                                          "source_brief_export", "question_read"))
        self.write()
        prefix = f"/v1/patients/{patient}/cases/{CASE}"
        drafts_url, runs_url = prefix + "/episode-drafts", prefix + f"/questions/{question}/runs"
        with running_server(create_app(self.settings)) as base:
            def send(url, body=None, token=TOKEN_A):
                return request(base, url, token=token, body=body)[:2]

            status, episode = send(drafts_url, draft.model_dump())
            self.assertEqual(status, 200 if revision == EPISODES else 201, episode)
            status, queued = send(runs_url, {"synthetic": True, **intent})
            self.assertEqual(status, 200 if revision == CORE else 201, queued)
            run = queued["run"]["run_id"]
            self.assertEqual(original, episode["episode_id"] if revision == EPISODES else run)
            self.assertEqual(send(drafts_url, draft.model_dump()), (200, episode | {"duplicate": True}))
            self.assertEqual(send(runs_url, {"synthetic": True, **intent}), (200, queued | {"duplicate": True}))
            row, = send(drafts_url)[1]["drafts"]
            self.assertEqual((row["episode_id"], row["source_id"], row["basis_sha256"], row["review_state"]),
                             (episode["episode_id"], draft.source_id, draft.snapshot_sha256, "unreviewed_draft"))
            self.assertEqual(send(drafts_url, token=TOKEN_B)[0], 404)
            self.assertEqual(send(runs_url + "/" + run, token=TOKEN_B)[0], 404)
            self.creds[0]["actions"].remove("episode_draft_create")
            self.write()
            self.assertEqual(send(drafts_url, draft.model_dump())[0], 404)
            self.assertEqual(send(runs_url + "/" + run)[0], 200)
            self.creds[0]["actions"].remove("source_brief_export")
            self.write()
            self.assertEqual(send(runs_url, {"synthetic": True, **intent})[0], 404)
            self.assertEqual(send(drafts_url)[0], 200)

        old = self.snapshot()
        with self.assertRaisesRegex(DBAPIError, "OI-IDENTITY-HISTORY-IMMUTABLE"), self.engine.begin() as db:
            db.execute(text("TRUNCATE clinical_source.episode_drafts"))
        self.assertEqual(self.snapshot(), old)
        with self.assertRaisesRegex(CommandError, "Populated episode drafts"):
            migrate(self.admin, "downgrade", JOIN)
        self.assertEqual(self.heads(), {SCHEMA_REVISION})
        self.assertEqual(self.snapshot(), old)

    def test_episode_parent_keeps_draft_origin_then_accepts_and_recovers_a_run(self):
        self.check_parent(EPISODES)

    def test_integrated_parent_keeps_run_then_accepts_and_recovers_a_draft(self):
        self.check_parent(CORE)

    def test_orphaned_creation_event_prevents_certification_without_repairing_history(self):
        patient, draft = self.seed_origin(EPISODES)
        with self.services() as registry:
            self.save_on_old_owner(registry, patient, draft)
        migrate(self.admin, "upgrade", JOIN)
        with self.engine.begin() as db:
            db.execute(text("TRUNCATE clinical_source.episode_drafts"))
            self.assertEqual(db.execute(text("SELECT count(*) FROM identity.identity_domain_events "
                                             "WHERE event_type='episode.draft_created'")).scalar_one(), 1)
        before = self.snapshot()
        with self.assertRaisesRegex(CommandError, "Orphaned episode creation event"):
            migrate(self.admin, "upgrade", "head")
        self.assertEqual(self.heads(), {JOIN})
        self.assertEqual(self.snapshot(), before)
        self.readiness(False)
