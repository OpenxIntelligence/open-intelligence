"""Capability identity/discovery must not guess versions or imply authority."""
from dataclasses import FrozenInstanceError, replace
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]


class CapabilityCliTests(unittest.TestCase):
    def command(self, *args):
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src") + os.pathsep + str(ROOT / "apps/api/src"),
               "OI_API_WORKER_TOKEN_FILE": "/no-such-private-worker-token",
               "OI_API_DATABASE_URL": "not-a-database-private-sentinel"}
        return subprocess.run([sys.executable, "-m", "oi_api.worker", *args], env=env,
                              cwd=ROOT, capture_output=True, text=True, timeout=15)

    def test_catalog_inspection_needs_no_patient_database_or_credential(self):
        result = self.command("--capabilities")
        self.assertEqual(result.returncode, 0, result.stderr)
        body = json.loads(result.stdout)
        self.assertEqual(body["contract"], "oi.execution-capability-catalog/1")
        self.assertEqual(body["runtime_readiness"], "not_checked")
        self.assertEqual([c["kind"] for c in body["capabilities"]], ["source-question-brief/1"])
        self.assertFalse(body["authorizes_execution"])
        self.assertNotIn("private", result.stdout + result.stderr)

    def test_discovery_and_execution_arguments_cannot_be_combined(self):
        for args in (("--capabilities", "--once"), ("--capabilities", "--patient", "PATIENT-ONE"),
                     ("--capabilities", "--case", "CASE-ONE"),
                     ("--capabilities", "--lease-seconds", "20")):
            with self.subTest(args=args):
                self.assertEqual(self.command(*args).returncode, 2)

    def test_execution_still_requires_patient_and_case(self):
        for args in (("--once",), ("--once", "--patient", "PATIENT-ONE"),
                     ("--once", "--case", "CASE-ONE")):
            with self.subTest(args=args):
                self.assertEqual(self.command(*args).returncode, 2)


class CapabilityCatalogTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module("oi_api.execution_capabilities")
        self.builtins = importlib.import_module("oi_api.composer_capabilities")
        self.descriptor = self.builtins.SOURCE_BRIEF_CAPABILITY

    def test_exact_version_resolution_never_falls_back(self):
        catalog = self.builtins.COMPOSER_CAPABILITIES
        self.assertEqual(catalog.require("source-question-brief/1").kind, "source-question-brief/1")
        for kind in ("source-question-brief", "source-question-brief/latest", "source-question-brief/2",
                     "Source-question-brief/1", "source-question-brief/01", None, True, [], {}):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                catalog.require(kind)

    def test_duplicate_version_is_rejected_but_distinct_versions_can_coexist(self):
        with self.assertRaises(ValueError):
            self.module.CapabilityCatalog([self.descriptor, self.descriptor])
        second = replace(self.descriptor, kind="source-question-brief/2")
        catalog = self.module.CapabilityCatalog([self.descriptor, second])
        self.assertEqual(catalog.require("source-question-brief/2"), second)
        self.assertEqual(catalog.require("source-question-brief/1"), self.descriptor)

    def test_disabled_registration_remains_inspectable_but_not_executable(self):
        catalog = self.module.CapabilityCatalog([replace(self.descriptor, enabled=False)])
        self.assertFalse(catalog.describe()["capabilities"][0]["enabled"])
        with self.assertRaises(ValueError):
            catalog.require("source-question-brief/1")

    def test_catalog_copies_inputs_and_returned_metadata(self):
        entries = [self.descriptor]
        catalog = self.module.CapabilityCatalog(entries)
        entries.clear()
        copy = catalog.describe()
        copy["capabilities"][0]["required_actions"].clear()
        copy["capabilities"].clear()
        self.assertEqual(catalog.require("source-question-brief/1").required_actions,
                         ("patient_read", "question_read", "source_read", "source_brief_export"))
        self.assertEqual(len(catalog.describe()["capabilities"]), 1)
        with self.assertRaises(FrozenInstanceError):
            self.descriptor.kind = "replaced/1"

    def test_digest_is_order_independent_and_tracks_capability_changes(self):
        second = replace(self.descriptor, kind="source-question-brief/2")
        first = self.module.CapabilityCatalog([self.descriptor, second]).describe()
        other = self.module.CapabilityCatalog([second, self.descriptor]).describe()
        self.assertEqual(first, other)
        encoded = json.dumps(first["capabilities"], sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.assertEqual(first["catalog_sha256"], hashlib.sha256(encoded).hexdigest())
        disabled = self.module.CapabilityCatalog([replace(self.descriptor, enabled=False), second]).describe()
        self.assertNotEqual(disabled["catalog_sha256"], first["catalog_sha256"])

    def test_bad_descriptors_fail_at_registration(self):
        changes = ({"kind": "missing-version"}, {"kind": "../shell/1"}, {"kind": "thing/0"},
                   {"owner": ""}, {"input_contract": "latest"}, {"output_contract": "unversioned"},
                   {"required_actions": ["patient_read"]}, {"required_actions": ()},
                   {"required_actions": ("patient_read", "patient_read")},
                   {"required_actions": (True,)}, {"enabled": 1})
        for change in changes:
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                self.module.CapabilityCatalog([replace(self.descriptor, **change)])
        with self.assertRaises(TypeError):
            self.module.CapabilityCatalog([{"kind": "source-question-brief/1"}])

    def test_empty_catalog_is_honest_and_does_not_enable_work(self):
        catalog = self.module.CapabilityCatalog([])
        self.assertEqual(catalog.describe()["capabilities"], [])
        with self.assertRaises(ValueError):
            catalog.require("source-question-brief/1")

    def test_builtin_contract_matches_actual_result_schema_and_permission_scope(self):
        from oi_api.composer_runs import ACTIONS, KIND
        from oi_api.source_question_contracts import SourceQuestionBrief
        output = SourceQuestionBrief.model_json_schema()["properties"]["contract"]["const"]
        self.assertEqual(self.descriptor.output_contract, output)
        self.assertEqual(self.descriptor.input_contract, "oi.pg-source-world-model/1")
        self.assertEqual(KIND, "source-question-brief/1")
        self.assertEqual(ACTIONS, ("patient_read", "question_read", "source_read", "source_brief_export"))


class ExecutionCapabilityBoundaryTests(unittest.TestCase):
    def test_disabled_worker_does_not_read_credentials_or_claim_work(self):
        from oi_api.composer_capabilities import SOURCE_BRIEF_CAPABILITY
        from oi_api.config import Settings
        from oi_api.execution_capabilities import CapabilityCatalog
        from oi_api.worker import run_once
        reads = []
        def credential():
            reads.append("attempted")
            raise RuntimeError("No credential is needed for disabled work")
        catalog = CapabilityCatalog([replace(SOURCE_BRIEF_CAPABILITY, enabled=False)])
        with patch("oi_api.worker.COMPOSER_CAPABILITIES", catalog):
            self.assertEqual(run_once(Settings(), credential, "PATIENT-ONE", "CASE-ALPHA"),
                             {"status": "blocked"})
        self.assertEqual(reads, [])

    def test_unknown_claim_kind_stops_before_any_source_or_database_access(self):
        from open_intelligence.patient_registry import PatientRegistryError
        from oi_api.composer_runs import PostgresComposerRuns
        # An intentionally uninitialized owner has no source/DB handles: neither
        # may be needed to reject an unsupported execution envelope.
        owner = object.__new__(PostgresComposerRuns)
        for kind in ("source-question-brief/2", "arbitrary-code/1", None):
            with self.subTest(kind=kind), self.assertRaises(PatientRegistryError):
                owner.complete({"kind": kind, "source_snapshot_contract": "oi.pg-source-world-model/1"},
                               recheck_authority=lambda: None)

    def test_wrong_input_contract_stops_before_source_access(self):
        from open_intelligence.patient_registry import PatientRegistryError
        from oi_api.composer_runs import PostgresComposerRuns
        owner = object.__new__(PostgresComposerRuns)
        with self.assertRaises(PatientRegistryError):
            owner.complete({"kind": "source-question-brief/1", "source_snapshot_contract": "oi.unknown/1"},
                           recheck_authority=lambda: None)


if __name__ == "__main__":
    unittest.main()
