"""Behavioral checks on disposable source trees; never import the application."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


TOOL = Path(__file__).with_name("check_engine_boundaries.py")
checker = None
if TOOL.is_file():
    spec = importlib.util.spec_from_file_location("engine_boundary_checker", TOOL)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)


class EngineBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(checker, "Architecture checker has not been implemented")
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.package = self.root / "apps/api/src/oi_api"
        self.package.mkdir(parents=True)
        self.write("__init__.py", '__version__ = "synthetic"\n')
        self.write("contracts.py", "class Result:\n    pass\n")
        self.write("records.py", "def _write():\n    pass\n")
        self.write("analysis.py", "from .contracts import Result\n")
        self.manifest = {
            "schema_version": "oi.engine-boundaries/1",
            "baseline_commit": "a" * 40,
            "scope": {"package": "oi_api", "path": "apps/api/src/oi_api"},
            "owners": [
                {"id": "platform", "responsibility": "Shared platform contract",
                 "modules": ["oi_api"], "exports": {"oi_api": ["__version__"]},
                 "depends_on": []},
                {"id": "records", "responsibility": "Canonical records",
                 "modules": ["oi_api.contracts", "oi_api.records"],
                 "exports": {"oi_api.contracts": ["Result"]},
                 "depends_on": ["platform"]},
                {"id": "research", "responsibility": "Research consumer",
                 "modules": ["oi_api.analysis"], "exports": {},
                 "depends_on": ["platform", "records"]},
            ],
            "reference_bridges": [],
            "legacy_imports": [],
        }

    def write(self, name, content):
        path = self.package / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def report(self):
        return checker.check_repository(self.root, self.manifest)

    def rejects(self, code):
        report = self.report()
        self.assertFalse(report["ok"], report)
        self.assertIn(code, [item["code"] for item in report["violations"]], report)
        return report

    def legacy(self, symbols=None):
        self.manifest["legacy_imports"].append({
            "consumer": "oi_api.analysis", "provider": "oi_api.records",
            "symbols": symbols or ["_write"],
            "reason": "Retained synthetic baseline coupling pending port extraction",
            "backlog": "OI-005",
        })

    def test_public_contract_is_allowed_and_report_is_deterministic(self):
        first = self.report()
        self.assertTrue(first["ok"], first)
        self.assertEqual(first["module_count"], 4)
        self.assertEqual(first["legacy_import_count"], 0)
        self.assertEqual(first, self.report())

    def test_new_nested_module_requires_explicit_ownership(self):
        self.write("hidden/worker.py", "value = 1\n")
        report = self.rejects("unowned_module")
        self.assertIn("oi_api.hidden.worker", json.dumps(report))

    def test_registered_module_cannot_silently_disappear(self):
        (self.package / "records.py").unlink()
        self.rejects("missing_module")

    def test_two_owners_cannot_claim_the_same_module(self):
        self.manifest["owners"][2]["modules"].append("oi_api.records")
        self.rejects("invalid_manifest")

    def test_duplicate_owner_identifier_is_rejected(self):
        self.manifest["owners"][2]["id"] = "records"
        self.rejects("invalid_manifest")

    def test_unknown_dependency_and_dependency_cycle_are_rejected(self):
        self.manifest["owners"][2]["depends_on"].append("absent")
        self.rejects("invalid_manifest")
        self.manifest["owners"][2]["depends_on"].remove("absent")
        self.manifest["owners"][1]["depends_on"].append("research")
        self.rejects("invalid_manifest")

    def test_export_cannot_reassign_another_owners_module(self):
        self.manifest["owners"][2]["exports"] = {"oi_api.records": ["_write"]}
        self.rejects("invalid_manifest")

    def test_private_import_is_rejected_even_with_declared_dependency(self):
        self.write("analysis.py", "from .records import _write\n")
        self.rejects("private_import")

    def test_public_export_still_requires_declared_dependency(self):
        self.manifest["owners"][2]["depends_on"] = ["platform"]
        self.rejects("undeclared_dependency")

    def test_absolute_and_aliased_imports_receive_the_same_check(self):
        for statement in ("from oi_api.records import _write as safe_name\n",
                          "import oi_api.records as store\n",
                          "from oi_api import records as store\n",
                          "from . import records as store\n"):
            with self.subTest(statement=statement):
                self.write("analysis.py", statement)
                self.rejects("private_import")

    def test_relative_import_from_nested_package_resolves_to_owner(self):
        (self.package / "analysis.py").unlink()
        self.write("research/__init__.py", "")
        self.write("research/analysis.py", "from ..records import _write\n")
        self.manifest["owners"][2]["modules"] = [
            "oi_api.research", "oi_api.research.analysis"]
        self.rejects("private_import")
        self.write("research/analysis.py", "from ..contracts import Result\n")
        self.assertTrue(self.report()["ok"], self.report())

    def test_function_local_import_does_not_escape_enforcement(self):
        self.write("analysis.py", "def run():\n    from .records import _write\n")
        self.rejects("private_import")

    def test_package_attribute_cannot_hide_behind_a_same_named_child_module(self):
        (self.package / "records.py").unlink()
        self.write("records/Result.py", "value = 1\n")
        self.manifest["owners"][2]["modules"].append("oi_api.records.Result")
        self.write("analysis.py", "from .records import Result\n")
        for content in ("class Result:\n    pass\n", "if True:\n    Result = object()\n",
                        "def __getattr__(name):\n    return object()\n",
                        "match 1:\n    case Result:\n        pass\n",
                        "match [1]:\n    case [*Result]:\n        pass\n",
                        "match {'a': 1}:\n    case {**Result}:\n        pass\n"):
            with self.subTest(content=content):
                self.write("records/__init__.py", content)
                self.rejects("ambiguous_import")

    def test_unambiguous_same_owner_package_import_still_works(self):
        self.write("helper.py", "value = 1\n")
        self.manifest["owners"][2]["modules"].append("oi_api.helper")
        self.write("analysis.py", "from . import helper as helper_module\n")
        self.assertTrue(self.report()["ok"], self.report())

    def test_regular_module_cannot_be_mistaken_for_a_package_parent(self):
        self.write("records/Result.py", "value = 1\n")
        self.manifest["owners"][2]["modules"].append("oi_api.records.Result")
        self.write("analysis.py", "from .records import Result\n")
        self.rejects("invalid_source")

    def test_unknown_internal_module_does_not_become_external(self):
        self.write("analysis.py", "from .unknown import Thing\n")
        self.rejects("unknown_internal_import")

    def test_exact_existing_exception_allows_only_its_named_symbols(self):
        self.write("analysis.py", "from .records import _write\n")
        self.legacy()
        report = self.report()
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["legacy_import_count"], 1)
        self.write("analysis.py", "from .records import _write, erase_everything\n")
        self.rejects("private_import")

    def test_exception_does_not_authorize_another_consumer(self):
        self.write("analysis.py", "from .records import _write\n")
        self.legacy()
        self.write("other.py", "from .records import _write\n")
        self.manifest["owners"][2]["modules"].append("oi_api.other")
        self.rejects("private_import")

    def test_removed_legacy_import_requires_debt_entry_removal(self):
        self.legacy()
        self.rejects("stale_legacy_import")

    def test_duplicate_and_blanket_exceptions_are_rejected(self):
        self.legacy()
        self.manifest["legacy_imports"].append(deepcopy(self.manifest["legacy_imports"][0]))
        self.rejects("invalid_manifest")
        self.manifest["legacy_imports"].pop()
        self.manifest["legacy_imports"][0]["symbols"] = ["*"]
        self.rejects("invalid_manifest")

    def test_exception_becoming_public_must_be_removed(self):
        self.manifest["legacy_imports"].append({
            "consumer": "oi_api.analysis", "provider": "oi_api.contracts",
            "symbols": ["Result"], "reason": "Old coupling", "backlog": "OI-005"})
        self.rejects("redundant_legacy_import")

    def test_shared_reference_bridge_is_explicit_and_symbol_bounded(self):
        reference = self.root / "src/open_intelligence/rights.py"
        reference.parent.mkdir(parents=True)
        reference.write_text("def permitted():\n    return False\n", encoding="utf-8")
        self.manifest["reference_bridges"].append({
            "module": "open_intelligence.rights", "path": "src/open_intelligence/rights.py",
            "symbols": ["permitted"], "reason": "Retain canonical rights owner"})
        self.write("analysis.py", "from open_intelligence.rights import permitted\n")
        self.assertTrue(self.report()["ok"], self.report())
        self.write("analysis.py", "from open_intelligence.rights import allow_all\n")
        self.rejects("undeclared_reference_import")
        self.write("analysis.py", "from open_intelligence.unregistered import Thing\n")
        self.rejects("undeclared_reference_import")

    def test_reference_bridge_cannot_point_outside_repository(self):
        self.manifest["reference_bridges"].append({
            "module": "open_intelligence.rights", "path": "../rights.py",
            "symbols": ["permitted"], "reason": "Invalid path"})
        self.rejects("invalid_manifest")

    def test_wildcard_and_dynamic_imports_require_refactoring(self):
        statements = [
            ("from .contracts import *\n", "wildcard_import"),
            ("import importlib as loader\nloader.import_module('oi_api.records')\n", "dynamic_import"),
            ("from importlib import import_module as load\n", "dynamic_import"),
            ("loader = __import__\nloader('oi_api.records')\n", "dynamic_import"),
            ("exec('from oi_api.records import _write')\n", "dynamic_import"),
        ]
        for statement, code in statements:
            with self.subTest(statement=statement):
                self.write("analysis.py", statement)
                self.rejects(code)

    def test_syntax_error_fails_instead_of_skipping_a_module(self):
        self.write("analysis.py", "def broken(\n")
        self.rejects("invalid_source")

    def test_scanner_never_executes_top_level_source(self):
        marker = self.root / "executed.txt"
        self.write("analysis.py", "from pathlib import Path\n"
                   f"Path({str(marker)!r}).write_text('executed')\n"
                   "from .contracts import Result\n")
        self.assertTrue(self.report()["ok"], self.report())
        self.assertFalse(marker.exists())

    def test_source_file_and_directory_symlinks_fail(self):
        external = self.root / "outside.py"
        external.write_text("value = 1\n", encoding="utf-8")
        (self.package / "analysis.py").unlink()
        (self.package / "analysis.py").symlink_to(external)
        self.rejects("source_symlink")
        (self.package / "analysis.py").unlink()
        self.write("analysis.py", "from .contracts import Result\n")
        (self.package / "hidden").symlink_to(self.root, target_is_directory=True)
        self.rejects("source_symlink")

    def test_manifest_unknown_fields_and_scope_narrowing_fail(self):
        self.manifest["ignore"] = ["analysis.py"]
        self.rejects("invalid_manifest")
        del self.manifest["ignore"]
        self.manifest["scope"]["path"] = "empty"
        self.rejects("invalid_manifest")

    def test_duplicate_json_keys_and_nonfinite_numbers_are_rejected(self):
        path = self.root / "manifest.json"
        for content in ('{"owners":[],"owners":[]}', '{"value":NaN}', '{"value":Infinity}'):
            with self.subTest(content=content):
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    checker.load_manifest(path)

    def test_cli_fails_on_violation_and_reports_machine_readable_result(self):
        path = self.root / "manifest.json"
        path.write_text(json.dumps(self.manifest), encoding="utf-8")
        command = [sys.executable, str(TOOL), "--root", str(self.root),
                   "--manifest", str(path), "--json"]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(json.loads(result.stdout)["ok"])
        self.write("analysis.py", "from .records import _write\n")
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertFalse(json.loads(result.stdout)["ok"])

    def test_cli_malformed_manifest_fails_without_traceback(self):
        path = self.root / "manifest.json"
        path.write_text("{bad json", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(TOOL), "--root", str(self.root), "--manifest", str(path), "--json"],
            capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)["ok"])
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
