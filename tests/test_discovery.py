import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler, seed
from open_intelligence.discovery import DiscoveryInputError, parse_discovery
from open_intelligence.store import CaseStore, InvalidInput

ROOT = Path(__file__).resolve().parents[1]
TRIAL = (ROOT / "examples" / "synthetic" / "discovery-trial-001.txt").read_bytes()
LITERATURE = (ROOT / "examples" / "synthetic" / "discovery-literature-001.txt").read_bytes()


def variant(raw, old, new):
    text = raw.decode()
    assert old in text, old
    return text.replace(old, new, 1).encode()


class ParseTests(unittest.TestCase):
    def test_valid_trial_and_literature(self):
        trial = parse_discovery(TRIAL)
        self.assertEqual((trial.kind, trial.registry_id, trial.doi), ("trial", "FICT-NCT-000001", None))
        lit = parse_discovery(LITERATURE)
        self.assertEqual((lit.kind, lit.registry_id, lit.doi), ("literature", None, "10.5555/oi-synthetic-002"))

    def test_unknown_field_and_abstract_rejected(self):
        for line in ("Abstract: This is copyrighted text.", "Sponsor: Someone"):
            with self.subTest(line=line):
                raw = TRIAL.decode().replace(
                    "Summary: Fictional registry listing",
                    "Summary: Fictional registry listing\n" + line).encode()
                with self.assertRaises(DiscoveryInputError):
                    parse_discovery(raw)

    def test_wrong_rights_and_kinds_rejected(self):
        with self.assertRaises(DiscoveryInputError):
            parse_discovery(variant(TRIAL, "Rights: original-synthetic", "Rights: harvested"))
        with self.assertRaises(DiscoveryInputError):
            parse_discovery(variant(TRIAL, "Status: not-verified", "Status: recruiting"))
        with self.assertRaises(DiscoveryInputError):
            parse_discovery(variant(TRIAL, "Kind: trial", "Kind: guideline"))
        with self.assertRaises(DiscoveryInputError):
            parse_discovery(variant(LITERATURE, "DOI: 10.5555/oi-synthetic-002", "DOI: not-a-doi"))
        with self.assertRaises(DiscoveryInputError):
            parse_discovery(variant(LITERATURE, "Issued-At: 2026-02-20",
                                    "Issued-At: 2026-02-20\nRegistry-Id: FICT-NCT-000009"))

    def test_banned_language_rejected(self):
        for word in ("eligible", "effective", "recommended", "proven"):
            raw = variant(TRIAL, "study design", f"study design that looks {word}")
            with self.subTest(word=word):
                with self.assertRaises(DiscoveryInputError):
                    parse_discovery(raw)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(str(Path(self.tmp.name) / "d.sqlite"))
        self.store.add_case("CASE-ALPHA", "Fictional case Alpha")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_import_list_projection(self):
        out = self.store.import_discovery(TRIAL)
        self.assertEqual(out["result"], "imported")
        dup = self.store.import_discovery(TRIAL)
        self.assertEqual(dup["result"], "duplicate")
        with self.assertRaises(InvalidInput):
            self.store.import_discovery(variant(TRIAL, "FICT-TRIAL-001", "FICT-TRIAL-001")
                                        .replace(b"demonstration only", b"demonstration only!"))
        items = self.store.list_discovery()
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertTrue(item["fictional"])
        self.assertIn("No eligibility", item["disclaimer"])
        self.assertNotIn("abstract", item)
        self.assertEqual(item["status"], "not-verified")

    def test_link_rules(self):
        discovery_id = self.store.import_discovery(TRIAL)["discovery_id"]
        qid = self.store.add_question("CASE-ALPHA", "What fictional sources relate to this question?")
        link = self.store.link_discovery("CASE-ALPHA", qid, discovery_id, "unknown",
                                         "No applicability judgement made yet for this listing.")
        self.assertGreater(link, 0)
        with self.assertRaises(InvalidInput):
            self.store.link_discovery("CASE-ALPHA", qid, discovery_id, "unknown",
                                      "No applicability judgement made yet for this listing.")
        with self.assertRaises(InvalidInput):
            self.store.link_discovery("CASE-ALPHA", qid, 9999, "unknown",
                                      "Linking an item that does not exist here.")
        with self.assertRaises(InvalidInput):
            self.store.link_discovery("CASE-ALPHA", qid, discovery_id, "maybe",
                                      "Applicability outside the allowed set here.")
        with self.assertRaises(InvalidInput):
            self.store.link_discovery("CASE-ALPHA", qid, discovery_id, "unknown",
                                      "Patient looks eligible for this study.")
        self.store.add_case("CASE-BETA", "Fictional case Beta")
        with self.assertRaises(InvalidInput):
            self.store.link_discovery("CASE-BETA", qid, discovery_id, "unknown",
                                      "Question belongs to another case entirely.")
        links = self.store.case_discovery_links("CASE-ALPHA")
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["applicability"], "unknown")
        self.assertTrue(links[0]["item"]["fictional"])


class DiscoveryApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "api.sqlite")
        seed(cls.path)
        bound = type("DiscoveryTestHandler", (Handler,), {"db_path": cls.path})
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), bound)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def call(self, path, data=None):
        headers = {}
        if data is not None:
            headers["Content-Type"] = "application/json"
            headers["Origin"] = f"http://127.0.0.1:{self.port}"
        request = Request(f"http://127.0.0.1:{self.port}{path}",
                          data=None if data is None else json.dumps(data).encode(),
                          headers=headers)
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_http_flow(self):
        status, imported = self.call("/api/discovery/imports", {"text": TRIAL.decode()})
        self.assertEqual(status, 200)
        self.assertEqual(imported["result"], "imported")
        status, banned = self.call("/api/discovery/imports", {
            "text": variant(TRIAL, "study design", "study design proven effective").decode()})
        self.assertEqual(status, 422)
        status, items = self.call("/api/discovery")
        self.assertEqual(status, 200)
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0]["fictional"])
        status, q = self.call("/api/cases/CASE-ALPHA/questions",
                              {"question": "Which fictional listings relate here?"})
        self.assertEqual(status, 201)
        status, link = self.call("/api/cases/CASE-ALPHA/discovery-links", {
            "question_id": q["question_id"], "discovery_id": items[0]["id"],
            "applicability": "unknown",
            "rationale": "No applicability judgement made yet for this listing."})
        self.assertEqual(status, 201)
        status, links = self.call("/api/cases/CASE-ALPHA/discovery")
        self.assertEqual(status, 200)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["item"]["discovery_key"], "FICT-TRIAL-001")


if __name__ == "__main__":
    unittest.main()
