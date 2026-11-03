"""Unit contracts: independently authored synthetic source versions only."""
import hashlib
import sqlite3
import unittest
from dataclasses import dataclass
from open_intelligence.bound_source import (
    read_bound_source, SourceAccessDenied, SourceIntegrityFailure,
)

@dataclass
class Principal:
    actor: str = "ACT-ONE"
    organization: str = "ORG-ONE"
    purpose: str = "operations"

class TestBoundSource(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.execute("""CREATE TABLE source_versions(
          id INTEGER PRIMARY KEY,case_id TEXT,document_id TEXT,version INTEGER,
          state TEXT,sha256 TEXT,raw BLOB,kind TEXT,event_date TEXT,
          issued_at TEXT,received_at TEXT,specimen_id TEXT,supersedes_id INTEGER)""")
        for ident, state, text, parent in (
            (1,"superseded",b"OI-SYNTHETIC-REPORT/1\nPatient: CASE-A\nFinding: assay|pending|Awaiting result\n",None),
            (2,"current",b"OI-SYNTHETIC-REPORT/1\nPatient: CASE-A\nFinding: assay|negative|Not detected\n",1),
        ):
            self.db.execute(
                "INSERT INTO source_versions VALUES (?, 'CASE-A','DOC-A',?, ?, ?, ?, "
                "'laboratory','2026-01-01','2026-01-02','2026-01-03',NULL,?)",
                (ident,ident,state,hashlib.sha256(text).hexdigest(),text,parent),
            )
        self.db.commit()
        self.store = type("Store", (), {"db":self.db})()
        self.binding = dict(patient_id="PAT-ONE",case_id="CASE-A",
                            source_store_id="STORE-ONE",organization="ORG-ONE",status="active")
        self.principal = Principal()
        self.allowed = True

    def read(self, source_version_id=1, **overrides):
        options=dict(patient_id="PAT-ONE",case_id="CASE-A",
                     source_store_id="STORE-ONE",source_version_id=source_version_id,
                     principal=self.principal,store=self.store,
                     resolve_binding=lambda *a:self.binding,
                     authorize=lambda *a:self.allowed)
        options.update(overrides)
        return read_bound_source(**options)

    def test_original_history_remains_visible(self):
        old, new = self.read(1), self.read(2)
        self.assertEqual((old.version,old.state),(1,"superseded"))
        self.assertEqual((new.version,new.state,new.supersedes_id),(2,"current",1))
        self.assertNotEqual(old.raw,new.raw)

    def test_wrong_patient_case_store_organization_denied(self):
        for options in (dict(patient_id="PAT-TWO"),dict(case_id="CASE-B"),
                        dict(source_store_id="STORE-TWO"),
                        dict(principal=Principal(organization="ORG-TWO"))):
            with self.subTest(options=options), self.assertRaises(SourceAccessDenied):
                self.read(**options)

    def test_separate_source_permission_required(self):
        self.allowed=False
        with self.assertRaises(SourceAccessDenied): self.read()

    def test_revocation_and_research_are_denied(self):
        self.binding["status"]="revoked"
        with self.assertRaises(SourceAccessDenied): self.read()
        self.binding["status"]="active"
        self.principal.purpose="research"
        with self.assertRaises(SourceAccessDenied): self.read()

    def test_bad_source_identifiers_denied(self):
        for version in (0,-1,True,999):
            with self.subTest(version=version), self.assertRaises(SourceAccessDenied):
                self.read(version)

    def test_tampered_original_rejected(self):
        self.db.execute("UPDATE source_versions SET raw=? WHERE id=1",(b"altered",))
        self.db.commit()
        with self.assertRaises(SourceIntegrityFailure): self.read()

    def test_revoked_between_two_checks(self):
        attempts=[0]
        def resolve(*a):
            attempts[0]+=1
            if attempts[0]==2: self.binding["status"]="revoked"
            return self.binding
        with self.assertRaises(SourceAccessDenied):
            self.read(resolve_binding=resolve)
        self.assertEqual(attempts[0],2)

    def test_authorization_failure_is_closed(self):
        def failure(*a): raise RuntimeError("secret-provider-details")
        with self.assertRaises(SourceAccessDenied):
            self.read(authorize=failure)

    def tearDown(self): self.db.close()

if __name__=="__main__": unittest.main()
