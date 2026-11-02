"""Real local multipart transfer against the original fictional DICOM object."""
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.store import CaseStore, InvalidInput
from open_intelligence.synthetic_dicom_roundtrip import SyntheticObjectServer, synthetic_dicom_bytes
from open_intelligence.synthetic_dicom_multipart import encode_dicom_part, decode_dicom_part

FIXTURE=Path(__file__).resolve().parents[1]/"examples/synthetic/alpha-imaging.txt"


class MultipartDicomTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=CaseStore(str(Path(self.tmp.name)/"synthetic.sqlite"))
        self.store.add_case("CASE-ALPHA","Fictional Alpha")
        self.store.add_case("CASE-BETA","Fictional Beta")
        self.source=self.store.import_report("CASE-ALPHA",FIXTURE.read_bytes())["source_id"]
        self.server=SyntheticObjectServer(self.store,"CASE-ALPHA",self.source)
        self.base=self.server.start()
        self.dicom=synthetic_dicom_bytes()

    def tearDown(self):
        self.server.close()
        self.store.close()
        self.tmp.cleanup()

    def test_multipart_post_qido_get_and_wado_roundtrip(self):
        mime,payload=encode_dicom_part(self.dicom)
        self.assertEqual(decode_dicom_part(mime,payload),self.dicom)
        request=Request(self.base+"/studies",data=payload,method="POST",
                        headers={"Content-Type":mime})
        with urlopen(request,timeout=5) as response:
            receipt=json.loads(response.read())
        self.assertEqual(receipt["status"],"stored_fictional_test_object")
        with urlopen(self.base+"/studies",timeout=5) as response:
            metadata=json.loads(response.read())
        self.assertEqual(metadata[0]["oi_test_source_version_id"],self.source)
        request=Request(self.base+"/studies/1.2.3/series/1.2.3.1/instances/1.2.3.1.1",
                        headers={"Accept":'multipart/related; type="application/dicom"'})
        with urlopen(request,timeout=5) as response:
            returned=decode_dicom_part(response.headers["Content-Type"],response.read())
        self.assertEqual(returned,self.dicom)

    def test_wrong_case_and_source_amendment_denied(self):
        mime,payload=encode_dicom_part(self.dicom)
        other=SyntheticObjectServer(self.store,"CASE-BETA",self.source)
        base=other.start()
        try:
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(base+"/studies",data=payload,method="POST",
                                headers={"Content-Type":mime}),timeout=5)
            self.assertEqual(error.exception.code,422)
        finally:
            other.close()
        with urlopen(Request(self.base+"/studies",data=payload,method="POST",
                             headers={"Content-Type":mime}),timeout=5):
            pass
        amended=(
            "OI-SYNTHETIC-REPORT/1\nPatient: CASE-ALPHA\nDocument: IMG-ALPHA\n"
            "Type: imaging\nEvent-Date: 2026-05-17\nIssued-At: 2026-05-19\n"
            "Amends: IMG-ALPHA@1\nFinding: lesion|reported|Fictional corrected report.\n"
        ).encode()
        self.store.import_report("CASE-ALPHA",amended)
        with self.assertRaises(HTTPError) as error:
            urlopen(self.base+"/studies",timeout=5)
        self.assertEqual(error.exception.code,409)

    def test_bad_boundary_and_second_part_fail_closed(self):
        mime,payload=encode_dicom_part(self.dicom)
        for bad_mime,bad_body in (
            (mime.replace("oi-synthetic-dicom-test-1","badboundary"),payload),
            (mime,payload[:-2]+b"JUNK"),
            (mime,payload+b"more"),
        ):
            with self.subTest(mime=bad_mime),self.assertRaises(HTTPError):
                urlopen(Request(self.base+"/studies",data=bad_body,method="POST",
                                headers={"Content-Type":bad_mime}),timeout=5)
        with self.assertRaises(InvalidInput):
            encode_dicom_part(self.dicom,boundary="x")

    def test_legacy_single_part_does_not_regress(self):
        with urlopen(Request(self.base+"/studies",data=self.dicom,method="POST",
                             headers={"Content-Type":"application/dicom"}),timeout=5):
            pass
        with urlopen(self.base+"/studies/1.2.3/series/1.2.3.1/instances/1.2.3.1.1",timeout=5) as r:
            self.assertEqual(r.read(),self.dicom)


if __name__=="__main__":
    unittest.main()
