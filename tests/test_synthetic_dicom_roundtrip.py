"""Actual binary DICOM Part10 and loopback HTTP, fictional source-bound only."""
import tempfile
from pathlib import Path
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.store import CaseStore
from open_intelligence.synthetic_dicom_roundtrip import (
    synthetic_dicom_bytes, _unpack, local_roundtrip, SyntheticObjectServer,
)

FIXTURE = Path(__file__).resolve().parents[1]/"examples"/"synthetic"/"alpha-imaging.txt"


class DicomRoundTripTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name)/"fictional.sqlite")
        self.store = CaseStore(self.path)
        self.store.add_case("CASE-ALPHA","Fictional Alpha")
        self.store.add_case("CASE-BETA","Fictional Beta")
        self.source_id = self.store.import_report("CASE-ALPHA",FIXTURE.read_bytes())["source_id"]
        self.fixture = synthetic_dicom_bytes()

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def server(self,case="CASE-ALPHA"):
        result = SyntheticObjectServer(self.store,case,self.source_id)
        self.addCleanup(result.close)
        return result.start()

    def test_real_binary_http_roundtrip_and_original_byte_digest(self):
        self.assertEqual(self.fixture[128:132],b"DICM")
        parsed = _unpack(self.fixture)
        self.assertEqual(parsed["study"],"1.2.3")
        self.assertEqual(parsed["date"],"20260517")
        receipt = local_roundtrip(self.server(),self.fixture)
        self.assertTrue(receipt["actual_http_roundtrip"])
        self.assertEqual(receipt["original_sha256"],receipt["retrieved_sha256"])
        self.assertEqual(receipt["store_receipt"]["sha256"],receipt["retrieved_sha256"])
        self.assertEqual(receipt["qido_metadata"][0]["oi_test_source_version_id"],self.source_id)
        self.assertFalse(receipt["full_dicomweb_conformance"])
        self.assertFalse(receipt["clinical_validation"])

    def test_wrong_case_refuses_storage(self):
        base=self.server(case="CASE-BETA")
        req=Request(base+"/studies",data=self.fixture,method="POST",
                    headers={"Content-Type":"application/dicom"})
        with self.assertRaises(HTTPError) as caught:
            urlopen(req,timeout=5)
        self.assertEqual(caught.exception.code,422)

    def test_incomplete_dicom_and_unmatched_study_date_refused(self):
        base=self.server()
        for payload in (self.fixture[:142],
                        synthetic_dicom_bytes(study_uid="1.2.3.4")[:-3]):
            with self.subTest(payload=len(payload)),self.assertRaises(HTTPError):
                urlopen(Request(base+"/studies",data=payload,method="POST",
                                headers={"Content-Type":"application/dicom"}),timeout=5)

    def test_amended_report_blocks_retrieval_of_prior_object(self):
        base=self.server()
        local_roundtrip(base,self.fixture)
        amended = (
            "OI-SYNTHETIC-REPORT/1\nPatient: CASE-ALPHA\n"
            "Document: IMG-ALPHA\nType: imaging\n"
            "Event-Date: 2026-05-17\nIssued-At: 2026-05-19\n"
            "Amends: IMG-ALPHA@1\n"
            "Finding: review|reported|Fictional corrected imaging report.\n"
        ).encode()
        self.store.import_report("CASE-ALPHA",amended)
        with self.assertRaises(HTTPError) as error:
            urlopen(base+"/studies",timeout=5)
        self.assertEqual(error.exception.code,409)

    def test_source_record_is_not_modified_by_http_transfer(self):
        before=self.store.state("CASE-ALPHA")
        local_roundtrip(self.server(),self.fixture)
        self.assertEqual(before,self.store.state("CASE-ALPHA"))


if __name__=="__main__":
    unittest.main()
