"""Independently fictional patient episodes and their immutable originating assertions."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from alembic.util import CommandError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from oi_api.app import create_app
from oi_api.migrate import migrate
from oi_api.episode_drafts import DraftCommand, eligible_primary
from oi_api.sources import PostgresSourceVersions
from http_support import running_server
from test_oncology_findings import HEADER, LINES
from test_patients import request, TOKEN_A, TOKEN_B
from test_source_versions import SourceVersionFixture


class EligibilityTests(unittest.TestCase):
    def test_only_an_explicit_reported_primary_can_start_a_draft(self):
        for role, label, state, expected in [
            ("primary", "EP-A", "reported", True), ("primary", None, "reported", False),
            ("primary", "EP-A", "negative", False), ("primary", "EP-B", "pending", False),
            ("metastasis", "EP-A", "reported", False), ("metastasis", None, "indeterminate", False),
        ]:
            with self.subTest(role=role, state=state, label=label):
                self.assertEqual(eligible_primary(role, label, state), expected)

    def test_historical_original_authority_is_required_before_historical_text_is_parsed(self):
        from oi_api.episode_drafts import _history
        from unittest.mock import Mock
        from open_intelligence.patient_registry import PatientRegistryDenied
        reg = Mock()
        reg._fetchall.return_value = [("EPISODE-X",8,"a"*64,"ACTOR",None,"SRC-OLD",b"unreadable")]
        history = {"case_id":"CASE-ALPHA","history":[{"source_id":"SRC-OLD"}],"current_sources":[]}
        guard = Mock(side_effect=PatientRegistryDenied("Historical original unavailable"))
        with self.assertRaises(PatientRegistryDenied):
            _history(reg, history, guard)
        guard.assert_called_once_with()

    def test_command_refuses_fake_clinical_authority_and_coerced_anchors(self):
        command = dict(synthetic=True, source_id="SRC-" + "A"*32, source_line=8,
                       source_version=1, source_sha256="a"*64, snapshot_sha256="b"*64)
        for mutation in [dict(source_line=True), dict(source_version="1"), dict(synthetic=1),
                         dict(synthetic=False), dict(clinical_approval=True), dict(episode_label="EP-A")]:
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                DraftCommand(**(command | mutation))


class EpisodeHTTPTests(SourceVersionFixture):
    def test_two_independent_drafts_reopen_and_preserve_the_original_after_amendment(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            case = self.url(patient).removesuffix("/sources")
            url = case + "/episode-drafts"
            status, original, _ = self.ingest(base, patient, HEADER + LINES)
            self.assertEqual(status, 201)
            world = request(base, case + "/world-model", token=TOKEN_A)[1]
            cmd = dict(synthetic=True, source_id=original["source_id"], source_line=8,
                       source_version=1, source_sha256=world["current_sources"][0]["sha256"],
                       snapshot_sha256=world["snapshot_fingerprint"])
            self.assertEqual(request(base, url, token=TOKEN_A, body=cmd)[0], 404)
            self.creds[0]["actions"] += ["episode_draft_create", "episode_draft_read"]
            self.write()
            post = lambda payload: request(base, url, token=TOKEN_A, body=payload)
            self.assertEqual(post(cmd | {"source_line": 10})[0], 409)
            self.assertEqual(post(cmd | {"snapshot_sha256": "0"*64})[0], 409)
            first, second = post(cmd), post(cmd | {"source_line": 9})
            self.assertEqual((first[0], second[0]), (201, 201))
            self.assertNotEqual(first[1]["episode_id"], second[1]["episode_id"])
            first_id = first[1]["episode_id"]
            self.assertEqual(post(cmd)[1], dict(first[1], duplicate=True))
            before = request(base, url, token=TOKEN_A)[1]["drafts"]
            self.assertCountEqual([d["source_label"] for d in before], ["EP-A","EP-B"])
            self.assertTrue(all(d["basis_state"] == "current" for d in before))
            amended = HEADER + "Amends: DOC-ALPHA@1\n" + LINES.replace("EP-A", "EP-C")
            self.assertEqual(self.ingest(base, patient, amended)[0], 201)
            self.assertEqual(post(cmd)[1]["episode_id"], first_id)
            self.assertEqual(post(cmd | {"snapshot_sha256": "0"*64})[0], 409)
            updated = request(base, case + "/world-model", token=TOKEN_A)[1]
            current = updated["observations"][0]
            self.assertEqual(post(cmd | dict(source_id=current["source_id"], source_line=current["source_line"],
                                      source_version=2, source_sha256=current["source_sha256"],
                                      snapshot_sha256=updated["snapshot_fingerprint"]))[0], 409)
            self.assertEqual(request(base, url, token=TOKEN_B)[0], 404)
        with running_server(create_app(self.settings)) as restarted:
            status, history, _ = request(restarted, url, token=TOKEN_A)
            self.assertEqual(status, 200)
            row = next(d for d in history["drafts"] if d["episode_id"] == first_id)
            self.assertEqual((row["source_label"],row["source_line"],row["source_version"],row["source_sha256"]),
                             ("EP-A",8,1,cmd["source_sha256"]))
            self.assertEqual(row["statement"], "Fictional breast primary.")
            self.assertTrue(all(d["basis_state"] == "reassessment_required" for d in history["drafts"]))
            self.assertEqual(row["source_state"], "superseded")
            # A historical literal is a protected read of the old original.
            self.creds[0]["actions"].remove("source_original_read")
            self.write()
            denied, body, _ = request(restarted, url, token=TOKEN_A)
            self.assertEqual(denied, 404)
            self.assertNotIn("Fictional breast primary.", str(body))
            self.creds[0]["actions"].append("source_original_read")
            self.creds[0]["actions"].remove("source_read")
            self.write()
            self.assertEqual(request(restarted, url, token=TOKEN_A)[0], 404)
        with self.assertRaisesRegex(CommandError, "Populated episode drafts"):
            migrate(self.admin, "downgrade", "0022_lab_citation_source_scope")
        with self.engine.connect() as db:
            self.assertEqual(db.execute(text("SELECT count(*) FROM clinical_source.episode_drafts")).scalar_one(), 2)

    def test_concurrent_commands_and_other_patient_cannot_rebind_or_duplicate_origin(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            other = self.setup_case(base, case="CASE-OTHER", key="CREATE-OTHER", source_subject="SUBJECT-OTHER")
            self.creds[0]["actions"] += ["episode_draft_read", "episode_draft_create"]
            self.write()
            self.assertEqual(self.ingest(base, patient, HEADER + LINES)[0], 201)
            scope = self.url(patient).removesuffix("/sources")
            world = request(base, scope + "/world-model", token=TOKEN_A)[1]
            origin = world["observations"][0]
            command = dict(synthetic=True, source_id=origin["source_id"], source_line=8, source_version=1,
                           source_sha256=origin["source_sha256"], snapshot_sha256=world["snapshot_fingerprint"])
            url = scope + "/episode-drafts"
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: request(base, url, token=TOKEN_A, body=command), range(2)))
            self.assertCountEqual([r[0] for r in results], [200,201])
            self.assertEqual(results[0][1]["episode_id"], results[1][1]["episode_id"])
            self.assertEqual(request(base, url.replace(patient,other), token=TOKEN_A)[0],404)
            other_url = url.replace(patient,other).replace("CASE-ALPHA","CASE-OTHER")
            other_world = request(base, other_url.replace("/episode-drafts","/world-model"), token=TOKEN_A)[1]
            self.assertEqual(request(base, other_url, token=TOKEN_A, body=command | {
                "snapshot_sha256":other_world["snapshot_fingerprint"]})[0],409)
            self.assertEqual(request(base, other_url, token=TOKEN_A)[1]["drafts"],[])
        with self.engine.connect() as db:
            self.assertEqual(db.execute(text("SELECT count(*) FROM identity.identity_domain_events "
                                             "WHERE event_type='episode.draft_created'")).scalar_one(),1)
        with self.assertRaisesRegex(DBAPIError, "OI-EPISODE-CREATION-ORIGIN"):
            with self.engine.begin() as db:
                db.execute(text("INSERT INTO clinical_source.episode_drafts "
                    "SELECT 'EPISODE-' || repeat('F',32),source_id,9,basis_sha256,created_by,"
                    "creation_event_id,created_at FROM clinical_source.episode_drafts"))
        with self.assertRaisesRegex(DBAPIError, "IMMUTABLE"):
            with self.engine.begin() as db:
                db.execute(text("UPDATE clinical_source.episode_drafts SET source_line=9"))

    def test_revocation_after_response_preparation_rolls_back_the_draft_and_events(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            case = self.url(patient).removesuffix("/sources")
            self.ingest(base, patient, HEADER + LINES)
            world = request(base, case + "/world-model", token=TOKEN_A)[1]
            obs = world["observations"][0]
            self.creds[0]["actions"] += ["episode_draft_read", "episode_draft_create"]
            self.write()
            receipt = PostgresSourceVersions._read_receipt
            def revoke(owner, *args, **kw):
                self.creds[0]["actions"].remove("episode_draft_create")
                self.write()
                return receipt(owner, *args, **kw)
            with self.engine.connect() as conn:
                prior = conn.execute(text("SELECT count(*) FROM identity.identity_domain_events")).scalar_one()
            with patch.object(PostgresSourceVersions, "_read_receipt", revoke):
                status, _, _ = request(base, case+"/episode-drafts", token=TOKEN_A,
                    body=dict(synthetic=True, source_id=obs["source_id"], source_line=8,
                              source_version=1, source_sha256=obs["source_sha256"],
                              snapshot_sha256=world["snapshot_fingerprint"]))
            self.assertEqual(status,404)
            with self.engine.connect() as conn:
                self.assertEqual(conn.execute(text("SELECT count(*) FROM clinical_source.episode_drafts")).scalar_one(),0)
                self.assertEqual(conn.execute(text("SELECT count(*) FROM identity.identity_domain_events")).scalar_one(),prior)
