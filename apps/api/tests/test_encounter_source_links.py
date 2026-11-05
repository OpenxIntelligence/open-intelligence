"""Fictional encounter-to-source links; real HTTP, existing source and patient owners."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sqlalchemy import text

from oi_api.app import create_app
from oi_api.config import Settings
from oi_api.encounter_routes import EncounterSourcePage, EncounterSourceReceipt
from http_support import running_server
from test_laboratory_fhir_r4 import encode, example
from test_patients import TOKEN_A, TOKEN_B, credential, request
from test_source_versions import AMENDED, ORIGINAL, SourceVersionFixture


def link_command(source_id, raw, version=1, key="LINK-FIRST"):
    return {"synthetic": True, "request_key": key, "source_id": source_id,
            "expected_version": version, "expected_sha256": hashlib.sha256(raw.encode()).hexdigest()}


class SourceLinkSurfaceTests(unittest.TestCase):
    def test_scoped_routes_require_credentials(self):
        app = create_app(Settings.from_env({}))
        template = "/v1/patients/{patient_id}/encounters/{encounter_id}/cases/{case_id}/source-links"
        for verb in ("get", "post"):
            op = app.openapi()["paths"][template][verb]
            self.assertEqual(op["security"], [{"SyntheticFixture": []}])
        url = template.format(patient_id="PAT-TEST", encounter_id=1, case_id="CASE-TEST")
        with running_server(app) as base:
            for body in (None, link_command("SRC-" + "A"*32, ORIGINAL)):
                status, result, _ = request(base, url, body=body)
                self.assertEqual((status, result), (401, {"detail": "Authentication required"}))


    def test_request_shape_and_scope_fail_before_looking_up_records(self):
        url = "/v1/patients/PAT-ALPHA/encounters/1/cases/CASE-ALPHA/source-links"
        command = link_command("SRC-" + "A"*32, ORIGINAL)
        grants = ["patient_read", "source_read", "encounter.read", "encounter.source.link"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "access.json"

            def access(actions=grants, patients=("PAT-ALPHA",), purpose="operations"):
                item = credential(TOKEN_A, patients=patients, actions=actions) | {"purpose": purpose}
                path.write_text(json.dumps({"version": "oi.synthetic-access/1", "credentials": [item]}))

            access()
            app = create_app(Settings.from_env({"OI_API_ACCESS_FILE": str(path)}))
            with running_server(app) as base:
                for query in ("?limit=0", "?limit=26", "?after_id=-1"):
                    self.assertEqual(request(base, url + query, token=TOKEN_A)[0], 422)
                for invalid in ({"expected_version": True}, {"synthetic": False}, {"expected_sha256": ""},
                                {"source_id": "invalid"}, {"synthetic": 1}, {"unrecognized": "private"}):
                    self.assertEqual(request(base, url, token=TOKEN_A, body=command | invalid)[:2],
                                     (422, {"detail": "Invalid request"}))
                for options in ({"patients": []}, {"purpose": "research"},
                                *({"actions": [g for g in grants if g != removed]}
                                  for removed in ("patient_read", "source_read", "encounter.read"))):
                    access(**options)
                    for body in (None, command):
                        self.assertEqual(request(base, url, token=TOKEN_A, body=body)[0], 404)
                access(actions=grants[:-1])
                self.assertEqual(request(base, url, token=TOKEN_A, body=command)[0], 404)


class EncounterSourceLinkHTTPTests(SourceVersionFixture):
    def setUp(self):
        super().setUp()
        for entry in self.creds:
            entry["actions"].extend(["encounter.schedule", "encounter.read", "encounter.source.link"])
        self.write()

    def encounter(self, base, patient, key="VISIT-ONE"):
        status, receipt, _ = request(base, f"/v1/patients/{patient}/encounters", token=TOKEN_A, body={
            "synthetic": True, "request_key": "SCHEDULE-" + key, "external_key": key,
            "kind": "outpatient", "service_date": "2026-01-10"})
        self.assertEqual(status, 200, receipt)
        return receipt["encounter_id"]

    def links(self, patient, visit, case="CASE-ALPHA"):
        return f"/v1/patients/{patient}/encounters/{visit}/cases/{case}/source-links"

    def counts(self):
        with self.engine.connect() as c:
            return c.execute(text("""SELECT (SELECT count(*) FROM ehr.encounter_source_links),
                (SELECT count(*) FROM identity.identity_domain_events),
                (SELECT count(*) FROM clinical_source.source_versions)""")).one()

    def test_amendment_keeps_exact_link_and_excludes_unlinked_sources_and_visits(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            visit = self.encounter(base, patient)
            url = self.links(patient, visit)
            first = self.ingest(base, patient)[1]["source_id"]
            command = link_command(first, ORIGINAL)
            self.assertEqual(request(base, url, token=TOKEN_A)[1]["links"], [])
            status, receipt, _ = request(base, url, body=command, token=TOKEN_A)
            self.assertEqual((status, receipt["duplicate"]), (201, False))
            link_id = receipt["id"]
            self.assertEqual(request(base, url, token=TOKEN_A)[1]["links"][0]["source_state"], "current")
            second = self.ingest(base, patient, AMENDED)[1]["source_id"]
            previous = self.counts()
            self.assertEqual(request(base, url, token=TOKEN_A, body=command)[:2],
                             (200, {"id": link_id, "duplicate": True}))
            self.assertEqual(self.counts(), previous)
            link = {"id": link_id, "encounter_id": visit, "patient_id": patient, "case_id": "CASE-ALPHA",
                    "source_id": first, "version": 1, "sha256": command["expected_sha256"],
                    "source_state": "superseded"}
            self.assertEqual(request(base, url, token=TOKEN_A)[1]["links"], [link])
            self.assertEqual(request(base, self.url(patient) + "/" + first, token=TOKEN_A)[1]["original_text"], ORIGINAL)
            other_visit = self.encounter(base, patient, "VISIT-TWO")
            other_url = self.links(patient, other_visit)
            self.assertEqual(request(base, other_url, token=TOKEN_A)[1]["links"], [])
            before = self.counts()
            self.assertEqual(request(base, other_url, token=TOKEN_A,
                                     body=command | {"request_key": "HISTORICAL-LINK"})[0], 409)
            self.assertEqual(self.counts(), before)
            status, receipt2, _ = request(base, url, token=TOKEN_A, body=link_command(second, AMENDED, 2, "LINK-SECOND"))
            self.assertEqual(status, 201, receipt2)
        with running_server(create_app(self.settings)) as base:
            status, page, _ = request(base, url + "?limit=1", token=TOKEN_A)
            self.assertEqual(status, 200)
            self.assertEqual({k: page[k] for k in ("patient_id", "encounter_id", "case_id", "links", "next_after_id")},
                             {"patient_id": patient, "encounter_id": visit, "case_id": "CASE-ALPHA",
                              "links": [link], "next_after_id": link_id})
            self.assertRegex(page["access_receipt_id"], r"^ACCESS-[0-9A-F]{32}$")
            with self.engine.connect() as c:
                self.assertEqual(c.execute(text("""SELECT metadata_json->>'case_id'
                    FROM identity.identity_domain_events
                    WHERE patient_id=:p AND event_type='clinical_encounter_sources_read_authorized'
                    AND metadata_json->>'receipt_id'=:receipt"""),
                    {"p": patient, "receipt": page["access_receipt_id"]}).scalar_one(), "CASE-ALPHA")
            page2 = request(base, url + f"?limit=1&after_id={link_id}", token=TOKEN_A)[1]
            self.assertIsNone(page2["next_after_id"])
            self.assertEqual(page2["links"], [link | {"id": receipt2["id"], "source_id": second,
                "version": 2, "sha256": hashlib.sha256(AMENDED.encode()).hexdigest(), "source_state": "current"}])

    def test_refused_intent_wrong_scope_and_withdrawn_binding_leave_no_changes(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            visit = self.encounter(base, patient)
            url = self.links(patient, visit)
            source = self.ingest(base, patient)[1]["source_id"]
            command = link_command(source, ORIGINAL)
            other = self.setup_case(base, case="CASE-BETA", key="CREATE-BETA", source_subject="SUBJECT-BETA")
            self.creds[1]["patient_ids"].append(patient)
            self.write()
            # Use a real active second case, source and encounter. Each component
            # is valid independently; its path/subject combination must match.
            foreign_source = self.ingest(base, other, ORIGINAL.replace("CASE-ALPHA", "CASE-BETA"), case="CASE-BETA")[1]["source_id"]
            foreign_visit = self.encounter(base, other, "VISIT-TWO")
            before = self.counts()
            for path, token, payload, code in (
                (url, TOKEN_A, command | {"expected_sha256": "0"*64}, 409),
                (url, TOKEN_A, command | {"expected_version": 2}, 409),
                (url, TOKEN_A, command | {"source_id": foreign_source}, 404),
                (self.links(patient, foreign_visit), TOKEN_A, command, 404),
                (self.links(patient, visit, "CASE-BETA"), TOKEN_A, command, 404),
                (self.links(patient, foreign_visit), TOKEN_A, None, 404),
                (self.links(patient, visit, "CASE-BETA"), TOKEN_A, None, 404),
                (url, TOKEN_B, command, 404), (url, TOKEN_B, None, 404),
                (url, TOKEN_A, command | {"synthetic": False}, 422),
                (url, TOKEN_A, command | {"expected_version": True}, 422),
            ):
                with self.subTest(path=path, status=code, body=payload):
                    status, result, _ = request(base, path, token=token, body=payload)
                    self.assertEqual(status, code, result)
                    self.assertEqual(set(result), {"detail"})
                    self.assertEqual(self.counts(), before)

            self.assertEqual(request(base, url, token=TOKEN_A, body=command)[0], 201)
            before = self.counts()
            for change in ({"expected_version": 2}, {"request_key": "DIFFERENT-KEY"}):
                self.assertEqual(request(base, url, token=TOKEN_A, body=command | change)[0], 409)
                self.assertEqual(self.counts(), before)
            for grant in ("source_read", "encounter.read", "patient_read", "encounter.source.link"):
                self.creds[0]["actions"].remove(grant)
                self.write()
                before = self.counts()
                self.assertEqual(request(base, url, token=TOKEN_A, body=command)[0], 404)
                if grant != "encounter.source.link":
                    self.assertEqual(request(base, url, token=TOKEN_A)[0], 404)
                self.assertEqual(self.counts(), before)
                if grant == "encounter.source.link":
                    self.assertEqual(request(base, url, token=TOKEN_A)[0], 200)
                self.creds[0]["actions"].append(grant)
                self.write()
            self.assertEqual(request(base, f"/v1/patients/{patient}/case-bindings/CASE-ALPHA/revoke",
                body={"synthetic": True, "reason": "Fictional binding withdrawn."}, token=TOKEN_A)[0], 200)
            before = self.counts()
            for payload in (command, None):
                self.assertEqual(request(base, url, token=TOKEN_A, body=payload)[0], 404)
            self.assertEqual(self.counts(), before)

    def test_authority_loss_during_response_encoding_rolls_back_write_and_read_audit(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            url = self.links(patient, self.encounter(base, patient))
            command = link_command(self.ingest(base, patient)[1]["source_id"], ORIGINAL)
            for model, body in ((EncounterSourceReceipt, command), (EncounterSourcePage, None)):
                with self.subTest(model=model):
                    if body is None:
                        self.assertEqual(request(base, url, token=TOKEN_A, body=command)[0], 201)
                    before = self.counts()
                    original = model.model_dump

                    def revoke(instance, **kw):
                        result = original(instance, **kw)
                        self.creds[0]["actions"].remove("source_read")
                        self.write()
                        return result

                    with patch.object(model, "model_dump", revoke):
                        status, result, _ = request(base, url, token=TOKEN_A, body=body)
                    self.assertEqual(status, 404)
                    self.assertEqual(set(result), {"detail"})
                    self.assertEqual(self.counts(), before)
                    self.creds[0]["actions"].append("source_read")
                    self.write()

    def test_inconsistent_stored_bytes_return_private_503_without_receipt(self):
        # Simulate a damaged restore using only schema-legal inserts. The
        # persisted link and source agree about the digest but the bytes do not.
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            visit = self.encounter(base, patient)
            url = self.links(patient, visit)
            source = "SRC-" + "C"*32
            wrong_hash = "0"*64
            with self.engine.begin() as c:
                c.execute(text("""INSERT INTO clinical_source.source_versions
                    (source_id,case_id,document_id,version,sha256,raw,kind,event_date,
                     issued_at,specimen_id,state) VALUES (:id,'CASE-ALPHA','DOC-ONE',1,
                     :digest,:raw,'pathology','2026-01-10','2026-01-11','SPECIMEN-ONE','current')"""),
                    {"id": source, "digest": wrong_hash, "raw": ORIGINAL.encode()})
                c.execute(text("""INSERT INTO ehr.encounter_source_links
                    (patient_id,encounter_id,case_id,source_id,version,sha256,origin_org,actor,purpose,request_key)
                    VALUES (:pid,:visit,'CASE-ALPHA',:id,1,:digest,'ORG-ALPHA','ACTOR-ALPHA',
                            'operations','LINK-RESTORED')"""),
                    {"pid": patient, "visit": visit, "id": source, "digest": wrong_hash})
            before = self.counts()
            for body in (None, link_command(source, ORIGINAL) | {"expected_sha256": wrong_hash}):
                self.assertEqual(request(base, url, token=TOKEN_A, body=body)[:2],
                                 (503, {"detail": "Patient registry unavailable"}))
                self.assertEqual(self.counts(), before)

    def test_fhir_source_uses_its_canonical_bundle_version(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base, source_subject="FICTIONAL-PATIENT-A")
            url = self.links(patient, self.encounter(base, patient))
            raw = encode(example()).decode()
            status, source, _ = request(base, f"/v1/patients/{patient}/cases/CASE-ALPHA/laboratory/fhir-r4/sources",
                token=TOKEN_A, body={"synthetic": True, "request_key": "LAB-IMPORT-ONE", "bundle_json": raw})
            self.assertEqual(status, 201, source)
            before = self.counts()
            status, receipt, _ = request(base, url, token=TOKEN_A, body=link_command(source["source_id"], raw))
            self.assertEqual(status, 201, receipt)
            row, = request(base, url, token=TOKEN_A)[1]["links"]
            self.assertEqual((row["source_id"], row["version"], row["sha256"]),
                             (source["source_id"], source["version"], source["original_sha256"]))
            self.assertEqual(self.counts()[2], before[2])
