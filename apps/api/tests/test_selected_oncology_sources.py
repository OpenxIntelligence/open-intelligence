"""Exact structured-line attribution in fictional questions, briefs and frozen evidence."""
from copy import deepcopy
import hashlib
import unittest
from unittest.mock import Mock

from open_intelligence.patient_registry import PatientRegistryError
from open_intelligence.postgres_registry import PostgresPatientRegistry
from oi_api.authored_evidence import PostgresQuestionEvidence
from oi_api.authored_evidence_contracts import checked_report_snapshot
from oi_api.composer_preflight import PostgresSourceComposerPreflight
from oi_api.evidence_report import canonical_hash, render_evidence_report
from oi_api.patients import PreparedSourceComposer
from oi_api.source_brief import render_source_brief
from oi_api.source_world_model import project_source_world_model
from test_authored_evidence_contracts import snapshot
from test_oncology_findings import HEADER, LINES
from test_question_source_brief import (PATIENT, PREPARED_AT, QUESTION, SOURCE,
                                        fictional_brief_inputs, fictional_source_index)


class SelectedOncologySourcesTests(unittest.TestCase):
    def prepare(self, index):
        registry = object.__new__(PostgresPatientRegistry)
        registry._transaction_active = True
        world = project_source_world_model(index)
        return world, PostgresSourceComposerPreflight(registry).preview_locked(
            PATIENT, "CASE-ALPHA", organization="ORG-FIXTURE", actor="ACTOR-FIXTURE", purpose="operations",
            expected_source_snapshot_sha256=world["snapshot_fingerprint"], source_id=SOURCE,
            source_line=2, question=QUESTION, source_index=index)

    def test_untyped_line_keeps_preflight_brief_and_stored_report_digests(self):
        # Golden content from 6a470c1, before selected anchors gained an optional key.
        _, packet = self.prepare(fictional_source_index())
        self.assertNotIn("oncology", PreparedSourceComposer(**packet).model_dump()["selected_source"])
        self.assertEqual(packet["preflight_sha256"], "4dfa69a46fe85009eb99ef4fde9dd9f8d7602e8ad112287da79452819f5951aa")
        brief = render_source_brief(*fictional_brief_inputs(), prepared_at=PREPARED_AT)
        self.assertEqual(brief["body_sha256"], "c7492cc50847574e3a1fac33f0307ef7dadff17c9d6feef95e3663520512eeba")
        self.assertEqual(canonical_hash(checked_report_snapshot(snapshot())),
                         "b1a36b785d920e46436d79b49f7789f79e2f9b01e0bcb4340cc7be73d1257d78")
        self.assertEqual(hashlib.sha256(render_evidence_report(snapshot()).encode()).hexdigest(),
                         "cd8eb613b47606f50824a04e46b406a6568dbe186c38b2f3ab2412fef0a0faa9")

    def test_preflight_and_brief_bind_missing_and_assigned_episodes_to_the_selected_line(self):
        for role, episode in (("primary", "EP-A"), ("metastasis", None)):
            with self.subTest(role=role, episode=episode):
                index = fictional_source_index()
                context = {"role": role, "episode_id": episode}
                index["source_reported_assertions"][0]["oncology"] = context
                world, packet = self.prepare(index)
                selected = PreparedSourceComposer(**packet).model_dump()["selected_source"]
                self.assertEqual(selected["oncology"], context)
                _, question, untyped = fictional_brief_inputs()
                question.update(source_snapshot_sha256=world["snapshot_fingerprint"],
                                preflight_sha256=packet["preflight_sha256"])
                stable = {k: v for k, v in packet.items() if k not in {"preflight_sha256", "access_receipt_id"}}
                self.assertEqual(packet["preflight_sha256"], canonical_hash(stable))
                self.assertNotEqual(packet["preflight_sha256"], canonical_hash(dict(stable, selected_source=untyped)))
                brief = render_source_brief(world, question, selected, prepared_at=PREPARED_AT)
                block = brief["body"].split("SELECTED ORIGINAL SOURCE ANCHOR\n")[1].split("CURRENT SOURCE-REPORTED")[0]
                self.assertIn(f'Source oncology role: {role}. episode: {episode or "unassigned"}', block)
                report = snapshot()
                report["selected_source"]["oncology"] = context
                self.assertEqual(checked_report_snapshot(report)["selected_source"]["oncology"], context)
                self.assertIn(f'Source oncology role: {role}. episode: {episode or "unassigned"}',
                              render_evidence_report(report))
                for forged in (untyped, {**untyped, "oncology": dict(context, episode_id="EP-DIFFERENT")},
                               {**untyped, "oncology": dict(context, role="primary" if role == "metastasis" else "metastasis")}):
                    with self.assertRaises(PatientRegistryError):
                        render_source_brief(world, question, forged, prepared_at=PREPARED_AT)

    def test_brief_disagreements_identify_each_source_reported_episode(self):
        index = fictional_source_index("reported")
        source, finding = index["sources"].pop(), index["source_reported_assertions"].pop()
        for letter, episode, state in (("B", "EP-A", "reported"), ("C", "EP-A", "negative"),
                                       ("D", "EP-B", "reported"), ("E", "EP-B", "negative")):
            sid = "SRC-" + letter * 32
            index["sources"].append(dict(source, document_id="DOC-" + letter, source_id=sid))
            index["source_reported_assertions"].append(dict(finding, source_id=sid, reported_state=state,
                                                            oncology={"role": "primary", "episode_id": episode}))
        world, packet = self.prepare(index)
        _, question, _ = fictional_brief_inputs("reported")
        question.update(source_snapshot_sha256=world["snapshot_fingerprint"], preflight_sha256=packet["preflight_sha256"])
        brief = render_source_brief(world, question, packet["selected_source"], prepared_at=PREPARED_AT)
        block = brief["body"].split("SOURCE-LABEL DISAGREEMENTS\n")[1].split("HISTORICAL SOURCE VERSIONS")[0]
        self.assertEqual(len(world["conflicts"]), 2)
        ordered = block.split("Source oncology role: primary. episode: ")
        self.assertEqual(len(ordered), 3)
        for group, episode, letters in zip(ordered[1:], ("EP-A", "EP-B"), ("BC", "DE"), strict=True):
            self.assertTrue(group.startswith(episode + "\n"))
            for letter in letters:
                self.assertIn("SRC-" + letter * 32 + " line 2", group)

    def test_historical_report_is_checked_against_the_typed_original_not_the_latest_attribution(self):
        raw = (HEADER + LINES).encode()
        sha = hashlib.sha256(raw).hexdigest()
        selected = dict(source_id=SOURCE, document_id="DOC-ALPHA", version=1, sha256=sha,
                        line=10, finding_key="nodule", reported_state="indeterminate",
                        statement="Fictional nodule; origin unclear.", kind="pathology",
                        event_date="2026-05-03", issued_at="2026-05-05", specimen_id="BIOPSY-ALPHA",
                        oncology={"role": "metastasis", "episode_id": None})
        registry = object.__new__(PostgresPatientRegistry)
        registry._fetchone = Mock(return_value=(raw,))
        owner = PostgresQuestionEvidence(registry)
        metadata = {k: selected[k] for k in ("source_id", "document_id", "version", "sha256", "kind", "event_date", "issued_at", "specimen_id")}
        c = {"index": {"sources": [dict(metadata, state="superseded")]}}
        owner._source_at_preparation(c, selected)
        for replacement in (None, {"role": "metastasis", "episode_id": "EP-B"},
                            {"role": "primary", "episode_id": None}):
            forged = deepcopy(selected)
            if replacement is None:
                del forged["oncology"]
            else:
                forged["oncology"] = replacement
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                owner._source_at_preparation(c, forged)
