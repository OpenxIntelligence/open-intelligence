"""Actual PG16/HTTP authority through final image response preparation.

Only independently authored source/image fixtures and synthetic credentials are
used. Routes are registered before constructor patches; source ownership,
transactions, final authorization and the event journal remain real.
"""

import copy
import json
from unittest.mock import patch

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from oi_api import patients as patient_routes
from oi_api.app import create_app
from http_support import running_server
from test_image_custody import AMENDED, REPORT, image_bytes, image_request
from test_patients import TOKEN_A
from test_source_versions import SourceVersionFixture


class ImageProjectionAuthorityTests(SourceVersionFixture):
    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend((
            "image_import", "image_read", "image_original_read",
        ))
        self.write()

    def prepare_images(self, base):
        """Keep one current link, one pending relink and one possible new object."""
        patient = self.setup_case(base)
        status, source, _ = self.ingest(base, patient, REPORT)
        self.assertEqual(status, 201, source)
        old_path = self.url(patient) + "/" + source["source_id"] + "/images"
        first, second = image_bytes(), image_bytes(sop_uid="2.25.104")
        status, first_receipt, _ = image_request(base, old_path, raw=first)
        self.assertEqual(status, 201, first_receipt)
        status, second_receipt, _ = image_request(base, old_path, raw=second)
        self.assertEqual(status, 201, second_receipt)
        status, amended, _ = self.ingest(base, patient, AMENDED)
        self.assertEqual(status, 201, amended)
        path = self.url(patient) + "/" + amended["source_id"] + "/images"
        status, linked, _ = image_request(base, path, raw=first)
        self.assertEqual((status, linked["result"], linked["image_id"]),
                         (201, "linked", first_receipt["image_id"]))
        original_path = path + "/" + first_receipt["image_id"]
        operations = (
            ("new_object", "SourceImageReceipt", "image_import", path,
             image_bytes(sop_uid="2.25.105")),
            ("identical_retry", "SourceImageReceipt", "image_import", path, first),
            ("explicit_relink", "SourceImageReceipt", "image_import", path, second),
            ("index", "SourceImageIndex", "image_read", path, None),
            ("original", "Response", "image_original_read", original_path, None),
        )
        return patient, operations

    def custody_state(self):
        with self.engine.connect() as connection:
            objects = connection.execute(text(
                "SELECT count(*) FROM clinical_source.dicom_objects"
            )).scalar_one()
            links = connection.execute(text(
                "SELECT count(*) FROM clinical_source.source_image_links"
            )).scalar_one()
            rows = connection.execute(text(
                "SELECT event_type,metadata_json FROM identity.identity_domain_events "
                "WHERE event_type LIKE 'image.%' ORDER BY id"
            )).all()
        return {"objects": objects, "links": links,
                "events": [(row[0], dict(row[1])) for row in rows]}

    def assert_withheld(self, response, status, before):
        actual, body, headers = response
        self.assertEqual(actual, status, body)
        self.assertIsInstance(body, dict)
        self.assertEqual(set(body), {"detail"})
        if status == 503:
            self.assertEqual(body, {"detail": "Patient registry unavailable"})
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIsNone(headers.get("X-OI-Access-Receipt"))
        serialized = json.dumps(body, ensure_ascii=False)
        for private in (TOKEN_A, "SUBJECT-ALPHA", "SYS-SYNTH", "2.25.103",
                        "PRIVATE-IMAGE-PREPARATION", REPORT):
            self.assertNotIn(private, serialized)
        self.assertEqual(self.custody_state(), before)

    def test_grant_withdrawn_after_real_preparation_withholds_response_and_effects(self):
        # App creation must precede patching: FastAPI retains the real response
        # models, while the route's final DTO/Response construction is observed.
        app = create_app(self.settings)
        with running_server(app) as base:
            _, operations = self.prepare_images(base)
            initial = copy.deepcopy(self.creds)
            for name, symbol, action, path, raw in operations:
                with self.subTest(operation=name):
                    self.creds = copy.deepcopy(initial)
                    self.write()
                    before = self.custody_state()
                    constructor = getattr(patient_routes, symbol)

                    def prepare_then_withdraw(*args, **kwargs):
                        prepared = constructor(*args, **kwargs)
                        self.creds[0]["actions"] = [
                            value for value in self.creds[0]["actions"] if value != action
                        ]
                        self.write()
                        return prepared

                    with patch.object(patient_routes, symbol,
                                      side_effect=prepare_then_withdraw) as prepared:
                        response = image_request(base, path, raw=raw)
                    prepared.assert_called_once()
                    self.assert_withheld(response, 404, before)

    def test_preparation_failure_rolls_back_custody_links_and_read_receipts(self):
        app = create_app(self.settings)
        with running_server(app) as base:
            _, operations = self.prepare_images(base)
            for name, symbol, _, path, raw in operations:
                with self.subTest(operation=name):
                    before = self.custody_state()
                    constructor = getattr(patient_routes, symbol)

                    def fail_after_preparation(*args, **kwargs):
                        constructor(*args, **kwargs)
                        raise RuntimeError("PRIVATE-IMAGE-PREPARATION")

                    with patch.object(patient_routes, symbol,
                                      side_effect=fail_after_preparation) as prepared:
                        response = image_request(base, path, raw=raw)
                    prepared.assert_called_once()
                    self.assert_withheld(response, 503, before)

    def test_patient_and_case_locks_cover_preparation_until_matching_receipt_commits(self):
        app = create_app(self.settings)
        with running_server(app) as base:
            patient, operations = self.prepare_images(base)
            targets = (
                ("patient", "SELECT patient_id FROM identity.identity_patients "
                            "WHERE patient_id=:patient FOR UPDATE NOWAIT",
                 {"patient": patient}),
                ("binding", "SELECT case_id FROM coordination.patient_case_bindings "
                            "WHERE case_id=:case FOR UPDATE NOWAIT",
                 {"case": "CASE-ALPHA"}),
            )

            def attempt_lock(sql, parameters):
                # A separate actual PG session proves the lock without sleeps.
                with self.engine.connect() as connection:
                    try:
                        connection.execute(text(sql), parameters).scalar_one()
                    except DBAPIError as error:
                        details = error.orig.args[0] if error.orig.args else None
                        return details.get("C") if isinstance(details, dict) else None
                return "acquired"

            for name, symbol, _, path, raw in operations[-2:]:
                with self.subTest(operation=name):
                    before = self.custody_state()
                    constructor = getattr(patient_routes, symbol)
                    observed = {}

                    def observe_preparation(*args, **kwargs):
                        prepared = constructor(*args, **kwargs)
                        observed["state"] = self.custody_state()
                        observed["locks"] = [
                            (label, attempt_lock(sql, parameters))
                            for label, sql, parameters in targets
                        ]
                        observed["receipt"] = (
                            prepared.access_receipt_id if name == "index"
                            else prepared.headers["X-OI-Access-Receipt"]
                        )
                        return prepared

                    with patch.object(patient_routes, symbol,
                                      side_effect=observe_preparation) as prepared:
                        status, body, headers = image_request(base, path, raw=raw)
                    prepared.assert_called_once()
                    self.assertEqual(status, 200, body)
                    self.assertEqual(observed["state"], before)
                    self.assertEqual(observed["locks"],
                                     [("patient", "55P03"), ("binding", "55P03")])
                    receipt = (body["access_receipt_id"] if name == "index"
                               else headers["X-OI-Access-Receipt"])
                    self.assertEqual(observed["receipt"], receipt)
                    after = self.custody_state()
                    self.assertEqual((after["objects"], after["links"]),
                                     (before["objects"], before["links"]))
                    self.assertEqual(after["events"][:-1], before["events"])
                    self.assertEqual(after["events"][-1][0],
                                     "image.read_authorized" if name == "index"
                                     else "image.original_read_authorized")
                    self.assertEqual(after["events"][-1][1]["receipt_id"], receipt)
                    for label, sql, parameters in targets:
                        with self.subTest(released_lock=label):
                            self.assertEqual(attempt_lock(sql, parameters), "acquired")
