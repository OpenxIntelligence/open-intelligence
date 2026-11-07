"""Receipt-time history uses the canonical source owner and current authority."""
from datetime import datetime, timezone
import hashlib
import json
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from sqlalchemy import text
from oi_api.app import create_app
from oi_api.patients import SourceHistory
from oi_api.sources import PostgresSourceVersions
from oi_api.source_integrity import SourceIntegrityError
from open_intelligence.patient_registry import PatientRegistryError
from open_intelligence.postgres_registry import PostgresPatientRegistry
from http_support import running_server
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import SourceVersionFixture, ORIGINAL, AMENDED


class ReceiptCutoffTests(unittest.TestCase):
    def test_explicit_timezone_and_microsecond_boundary(self):
        parse = PostgresSourceVersions.receipt_cutoff
        first = "2026-01-10T10:00:00.000001Z"
        self.assertEqual(parse(first), parse("2026-01-10T11:00:00.000001+01:00"))
        index = {"patient_id": "PAT-FICTIONAL", "case_id": "CASE-ALPHA", "sources": [
            {"document_id": "DOC-ONE", "version": 2, "received_at": "2026-01-10T10:00:00.000002Z", "state": "current"},
            {"document_id": "DOC-ONE", "version": 1, "received_at": first, "state": "superseded"}]}
        result = PostgresSourceVersions._history(index, parse(first))
        self.assertEqual(result["sources"], [{"document_id": "DOC-ONE", "version": 1, "received_at": first}])
        for value in ("2026-01-10", "2026-01-10T10:00:00", "2026-01-10T10:00:00.0000001Z",
                      "2026-02-30T10:00:00Z", "2026-01-10T10:00:00+00:60", "9999-01-01T00:00:00Z", "0"):
            with self.subTest(value=value), self.assertRaises(PatientRegistryError):
                parse(value)
        index["sources"][0]["received_at"] = "2026-01-09T00:00:00Z"
        with self.assertRaises(SourceIntegrityError):
            PostgresSourceVersions._history(index, parse(first))


class SourceHistoryHTTPTests(SourceVersionFixture):
    def history_url(self, patient, cutoff, case="CASE-ALPHA"):
        return self.url(patient, case).removesuffix("/sources") + "/source-history?" + urlencode({"received_through": cutoff})

    def events(self):
        with self.engine.connect() as c:
            return c.execute(text("SELECT metadata_json FROM identity.identity_domain_events "
                                  "WHERE event_type='source.read_authorized' ORDER BY id")).scalars().all()

    def test_late_old_report_amendment_exact_original_and_api_restart(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            first = self.ingest(base, patient)[1]
            index = request(base, self.url(patient), token=TOKEN_A)[1]
            cutoff = index["sources"][0]["received_at"]
            self.assertEqual(self.ingest(base, patient, AMENDED)[0], 201)
            late = ORIGINAL.replace("DOC-ONE", "DOC-LATE").replace("2026-01-10", "2025-01-10").replace("2026-01-11", "2025-01-11")
            self.assertEqual(self.ingest(base, patient, late)[0], 201)
            path = self.history_url(patient, cutoff)
            status, result, headers = request(base, path, token=TOKEN_A)
            self.assertEqual(status, 200)
            self.assertEqual(headers.get("Cache-Control"), "no-store")
            self.assertEqual(result["sources"], [{k:v for k,v in index["sources"][0].items() if k != "state"}])
            self.assertNotIn("source_reported_assertions", result)
            self.assertNotIn("superseded", json.dumps(result))
            self.assertEqual(request(base, self.history_url(patient, "2025-01-01T00:00:00Z"), token=TOKEN_A)[1]["sources"], [])
            newest = request(base, self.url(patient), token=TOKEN_A)[1]
            latest_cutoff = max(datetime.fromisoformat(s["received_at"].replace("Z", "+00:00")) for s in newest["sources"])
            latest = request(base, self.history_url(patient, latest_cutoff.isoformat()), token=TOKEN_A)[1]
            self.assertEqual({s["document_id"]:s["version"] for s in latest["sources"]}, {"DOC-LATE":1,"DOC-ONE":2})
            original_path = self.url(patient) + "/" + first["source_id"]
            self.assertEqual(request(base, original_path, token=TOKEN_A)[1]["original_text"], ORIGINAL)
            event = next(e for e in self.events() if e["receipt_id"] == result["access_receipt_id"])
            content = {k:v for k,v in result.items() if k != "access_receipt_id"}
            digest = hashlib.sha256(json.dumps(content,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
            self.assertEqual((event["snapshot_sha256"],event["source_count"],event["assertion_count"],event["received_through"]), (digest,1,0,cutoff))
            self.creds[0]["actions"].remove("source_original_read"); self.write()
            self.assertEqual(request(base, original_path, token=TOKEN_A)[0], 404)
            self.assertEqual(request(base, path, token=TOKEN_A)[0], 200)
        with running_server(create_app(self.settings)) as base:
            recovered = request(base, path, token=TOKEN_A)[1]
            self.assertEqual({k:v for k,v in recovered.items() if k != "access_receipt_id"}, content)
            self.assertNotEqual(recovered["access_receipt_id"],result["access_receipt_id"])

    def test_denial_and_ambiguous_cutoffs_produce_no_history_receipt(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.ingest(base, patient)
            cutoff = datetime.now(timezone.utc).isoformat()
            path = self.history_url(patient, cutoff)
            for bad in ("2026-01-10", "2026-01-10T00:00:00", "2026-01-10T00:00:00.0000001Z"):
                self.assertEqual(request(base,self.history_url(patient,bad),token=TOKEN_A)[0],422)
            self.assertEqual(request(base,path,token=TOKEN_B)[0],404)
            self.assertEqual(request(base,self.history_url(patient,cutoff,"CASE-WRONG"),token=TOKEN_A)[0],404)
            self.creds[0]["actions"].remove("source_read"); self.write()
            with patch.object(PostgresSourceVersions,"_sources",side_effect=AssertionError("must not read")):
                self.assertEqual(request(base,path,token=TOKEN_A)[0],404)
            self.assertEqual(self.events(),[])

    def test_final_authority_and_failed_audit_withhold_prepared_history(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.ingest(base, patient)
            path = self.history_url(patient,datetime.now(timezone.utc).isoformat())
            initial = json.loads(json.dumps(self.creds))
            dump = SourceHistory.model_dump
            def withdraw(model, *args, **kwargs):
                result = dump(model,*args,**kwargs)
                self.creds[0]["patient_ids"] = []; self.write()
                return result
            with patch.object(SourceHistory,"model_dump",withdraw):
                status,body,_ = request(base,path,token=TOKEN_A)
                self.assertEqual(status,404); self.assertNotIn("sources",body)
            self.creds = json.loads(json.dumps(initial)); self.write()
            append = PostgresPatientRegistry.append_event
            def revoke_after_append(registry,*args,**kwargs):
                result = append(registry,*args,**kwargs)
                self.creds.clear(); self.write()
                return result
            with patch.object(PostgresPatientRegistry,"append_event",revoke_after_append):
                status,body,_ = request(base,path,token=TOKEN_A)
                self.assertEqual(status,401); self.assertNotIn("sources",body)
            self.creds = initial; self.write()
            with patch.object(PostgresPatientRegistry,"append_event",side_effect=OSError("PRIVATE AUDIT FAILURE")):
                status,body,_ = request(base,path,token=TOKEN_A)
                self.assertEqual(status,503); self.assertNotIn("PRIVATE",json.dumps(body))
            self.assertEqual(self.events(),[])
