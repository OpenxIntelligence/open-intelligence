"""Actual PG16/HTTP provenance checks for the existing source projections.

All content is independently fictional. Deliberately inconsistent fixtures use
schema-legal INSERTs into the disposable database; immutable guards stay active.
The source index and its World Model consumer must reject inconsistent stored
provenance before issuing an access receipt or disclosing a projection.
"""

import hashlib

from sqlalchemy import text

from oi_api.app import create_app

from http_support import running_server
from test_patients import TOKEN_A, request
from test_source_versions import AMENDED, ORIGINAL, SourceVersionFixture


ORIGINAL_FINDING = (
    "marker", "not-reported", "Fictional café <script>literal</script>.", 8,
)
AMENDED_FINDING = (
    "marker", "negative", "Amended fictional marker is reported negative.", 9,
)


class SourceIndexIntegrityTests(SourceVersionFixture):
    def projection_paths(self, patient):
        index = self.url(patient)
        return index, index.removesuffix("/sources") + "/world-model"

    def insert_stored_source(self, *, original=ORIGINAL, source_id="SRC-" + "A" * 32,
                             version=1, state="current", issued_at="2026-01-11",
                             supersedes_id=None, digest=None, assertions=(ORIGINAL_FINDING,)):
        """Seed one source and its claimed finding rows without changing guards."""
        raw = original.encode("utf-8")
        with self.engine.begin() as connection:
            connection.execute(text("""INSERT INTO clinical_source.source_versions
                (source_id,case_id,document_id,version,sha256,raw,kind,event_date,
                 issued_at,specimen_id,state,supersedes_id)
                VALUES (:id,'CASE-ALPHA','DOC-ONE',:version,:digest,:raw,'pathology',
                 '2026-01-10',CAST(:issued_at AS date),'SPECIMEN-ONE',:state,:supersedes_id)"""), {
                "id": source_id, "version": version, "raw": raw,
                "digest": hashlib.sha256(raw).hexdigest() if digest is None else digest,
                "issued_at": issued_at, "state": state, "supersedes_id": supersedes_id,
            })
            for key, certainty, quote, line in assertions:
                connection.execute(text("""INSERT INTO clinical_source.assertions
                    (source_id,finding_key,certainty,quote,source_line)
                    VALUES (:source,:key,:certainty,:quote,:line)"""), {
                    "source": source_id, "key": key, "certainty": certainty,
                    "quote": quote, "line": line,
                })
        return source_id

    def assert_projections_unavailable(self, base, patient):
        # Compare the entire existing journal, not just a response field: a
        # failed projection must not commit an otherwise hidden read receipt.
        journal = text("SELECT id,event_type,metadata_json FROM identity.identity_domain_events ORDER BY id")
        with self.engine.connect() as connection:
            before = connection.execute(journal).all()
        for path in self.projection_paths(patient):
            with self.subTest(path=path):
                status, value, headers = request(base, path, token=TOKEN_A)
                self.assertEqual((status, value), (503, {"detail": "Patient registry unavailable"}))
                self.assertEqual(headers["Cache-Control"], "no-store")
                with self.engine.connect() as connection:
                    self.assertEqual(connection.execute(journal).all(), before,
                                     "Corrupt projection created an access receipt")

    def assert_bad_assertions_denied(self, assertions):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.insert_stored_source(assertions=assertions)
            self.assert_projections_unavailable(base, patient)

    def test_valid_unicode_findings_and_amendment_history_remain_readable(self):
        amended_quote = "Amended fictional café marker — reported negative."
        amended = AMENDED.replace(AMENDED_FINDING[2], amended_quote)
        receipts = []
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            status, first, _ = self.ingest(base, patient)
            self.assertEqual(status, 201)
            original_id = first["source_id"]
            for path, findings_key in zip(self.projection_paths(patient),
                                           ("source_reported_assertions", "observations")):
                status, value, _ = request(base, path, token=TOKEN_A)
                self.assertEqual(status, 200)
                finding, = value[findings_key]
                self.assertEqual((finding["source_id"], finding["finding_key"],
                                  finding["reported_state"], finding["source_statement"],
                                  finding["source_line"]), (original_id, *ORIGINAL_FINDING))
                receipts.append(value["access_receipt_id"])

            status, second, _ = self.ingest(base, patient, amended)
            self.assertEqual((status, second["version"]), (201, 2))
            amended_id = second["source_id"]
            for path, findings_key in zip(self.projection_paths(patient),
                                           ("source_reported_assertions", "observations")):
                status, value, _ = request(base, path, token=TOKEN_A)
                self.assertEqual(status, 200)
                finding, = value[findings_key]
                self.assertEqual((finding["source_id"], finding["finding_key"],
                                  finding["reported_state"], finding["source_statement"],
                                  finding["source_line"]),
                                 (amended_id, "marker", "negative", amended_quote, 9))
                sources = value.get("sources")
                if sources is None:
                    sources = value["history"] + value["current_sources"]
                self.assertEqual([(source["source_id"], source["state"], source["supersedes_id"])
                                  for source in sources],
                                 [(original_id, "superseded", None),
                                  (amended_id, "current", original_id)])
                self.assertEqual([source["sha256"] for source in sources],
                                 [hashlib.sha256(raw.encode("utf-8")).hexdigest()
                                  for raw in (ORIGINAL, amended)])
                receipts.append(value["access_receipt_id"])
            status, historical, _ = request(base, self.url(patient) + "/" + original_id,
                                            token=TOKEN_A)
            self.assertEqual(status, 200)
            self.assertEqual(historical["original_text"].encode("utf-8"), ORIGINAL.encode("utf-8"))
            self.assertEqual(historical["state"], "superseded")
        self.assertEqual(len(set(receipts)), 4)
        with self.engine.connect() as connection:
            recorded = connection.execute(text(
                "SELECT metadata_json->>'receipt_id' FROM identity.identity_domain_events "
                "WHERE event_type='source.read_authorized' ORDER BY id"
            )).scalars().all()
        self.assertEqual(recorded, receipts)

    def test_different_stored_quote_cannot_replace_the_original_statement(self):
        self.assert_bad_assertions_denied((
            ("marker", "not-reported", "Injected independently fictional quote.", 8),
        ))

    def test_different_stored_key_cannot_relabel_the_original_finding(self):
        self.assert_bad_assertions_denied((
            ("other_marker", "not-reported", ORIGINAL_FINDING[2], 8),
        ))

    def test_different_stored_state_cannot_turn_not_reported_into_negative(self):
        self.assert_bad_assertions_denied((
            ("marker", "negative", ORIGINAL_FINDING[2], 8),
        ))

    def test_stored_line_must_point_to_the_exact_original_finding_line(self):
        self.assert_bad_assertions_denied((
            ("marker", "not-reported", ORIGINAL_FINDING[2], 7),
        ))

    def test_missing_assertion_cannot_hide_an_original_finding(self):
        self.assert_bad_assertions_denied(())

    def test_extra_assertion_cannot_add_a_finding_absent_from_the_original(self):
        self.assert_bad_assertions_denied((
            ORIGINAL_FINDING,
            ("invented", "reported", "Additional independently fictional finding.", 9),
        ))

    def test_matching_hash_does_not_authorize_a_wrong_case_original(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            wrong_case = ORIGINAL.replace("Patient: CASE-ALPHA", "Patient: CASE-BETA")
            self.insert_stored_source(original=wrong_case)
            self.assert_projections_unavailable(base, patient)

    def test_current_original_with_bad_hash_is_unavailable(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.insert_stored_source(digest="0" * 64)
            self.assert_projections_unavailable(base, patient)

    def test_historical_hash_corruption_is_not_hidden_by_a_valid_current_amendment(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            previous = self.insert_stored_source(state="superseded", digest="0" * 64)
            self.insert_stored_source(original=AMENDED, source_id="SRC-" + "B" * 32,
                                      version=2, issued_at="2026-01-12", supersedes_id=previous,
                                      assertions=(AMENDED_FINDING,))
            self.assert_projections_unavailable(base, patient)

    def test_amendment_must_link_to_its_immediate_previous_version(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            previous = self.insert_stored_source(state="superseded")
            third = AMENDED.replace("DOC-ONE@1", "DOC-ONE@2").replace("2026-01-12", "2026-01-13")
            self.insert_stored_source(original=third, source_id="SRC-" + "C" * 32,
                                      version=3, issued_at="2026-01-13", supersedes_id=previous,
                                      assertions=(AMENDED_FINDING,))
            self.assert_projections_unavailable(base, patient)

    def test_all_superseded_history_cannot_masquerade_as_an_empty_current_case(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.insert_stored_source(state="superseded")
            self.assert_projections_unavailable(base, patient)
