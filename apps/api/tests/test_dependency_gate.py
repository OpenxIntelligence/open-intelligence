"""Negative controls for the artifact review gate; fixtures are authored here."""

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

TOOL = Path(__file__).resolve().parents[1] / "tools/check_dependencies.py"


class DependencyGateTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("dependency_gate", TOOL)
        self.gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.gate)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.wheels = self.root / "wheels"
        self.wheels.mkdir()
        self.wheel = self.wheels / "fictional_dependency-1.0-py3-none-any.whl"
        notice = b"Fictional test notice, independently authored for this gate test.\n"
        with ZipFile(self.wheel, "w") as archive:
            archive.writestr("fictional_dependency-1.0.dist-info/METADATA", "Name: fictional-dependency\nVersion: 1.0\n")
            archive.writestr("fictional_dependency-1.0.dist-info/licenses/LICENSE", notice)
        digest = hashlib.sha256(self.wheel.read_bytes()).hexdigest()
        (self.root / "THIRD_PARTY_NOTICES.md").write_bytes(notice)
        (self.root / "requirements.lock").write_text(f"fictional-dependency==1.0 --hash=sha256:{digest}\n")
        self.inventory = {
            "schema_version": 1,
            "status": "approved_for_specified_use",
            "approved_scope": "local-synthetic-h1-development",
            "notices": {"path": "THIRD_PARTY_NOTICES.md", "sha256": hashlib.sha256(notice).hexdigest()},
            "license_policy": {"approved_selected_expressions": ["MIT"]},
            "open_items": [],
            "native_components": [],
            "packages": [{
                "name": "fictional-dependency", "version": "1.0", "filename": self.wheel.name,
                "sha256": digest, "rights_state": "approved_for_specified_use",
                "selected_license_expression": "MIT",
                "license_evidence": [{
                    "path_in_wheel": "fictional_dependency-1.0.dist-info/licenses/LICENSE",
                    "sha256": hashlib.sha256(notice).hexdigest(),
                }],
            }],
        }

    def check(self):
        path = self.root / "dependency-license-inventory.json"
        path.write_text(json.dumps(self.inventory))
        return self.gate.verify(self.root, self.wheels)

    def test_reviewed_exact_artifact_passes(self):
        report = self.check()
        self.assertEqual(report["package_count"], 1)
        self.assertEqual(report["scope"], "local-synthetic-h1-development")

    def test_unreviewed_rights_block(self):
        self.inventory["packages"][0]["rights_state"] = "screened"
        with self.assertRaises(self.gate.GateError):
            self.check()

    def test_changed_bytes_and_extra_wheel_block(self):
        with self.wheel.open("ab") as target:
            target.write(b"changed")
        with self.assertRaises(self.gate.GateError):
            self.check()

    def test_unexpected_wheel_blocks(self):
        (self.wheels / "unreviewed-2.0-py3-none-any.whl").write_bytes(b"unreviewed")
        with self.assertRaises(self.gate.GateError):
            self.check()

    def test_lock_version_mismatch_blocks(self):
        path = self.root / "requirements.lock"
        path.write_text(path.read_text().replace("==1.0", "==2.0"))
        with self.assertRaises(self.gate.GateError):
            self.check()

    def test_changed_notices_block(self):
        (self.root / "THIRD_PARTY_NOTICES.md").write_text("Required notices removed")
        with self.assertRaises(self.gate.GateError):
            self.check()

    def test_unknown_expression_blocks_even_with_status_changed(self):
        self.inventory["packages"][0]["selected_license_expression"] = "LicenseRef-Unknown"
        with self.assertRaises(self.gate.GateError):
            self.check()

    def test_copyleft_cannot_be_added_as_a_policy_shortcut(self):
        self.inventory["packages"][0]["selected_license_expression"] = "AGPL-3.0-only"
        self.inventory["license_policy"]["approved_selected_expressions"].append("AGPL-3.0-only")
        with self.assertRaises(self.gate.GateError):
            self.check()

    def test_embedded_runtime_cannot_bypass_review(self):
        self.inventory["embedded_runtime_components"] = [{
            "name": "fictional-runtime", "version": "1", "rights_state": "screened",
            "selected_license_expression": "MIT", "license_evidence": [{"source": "fixture"}],
        }]
        with self.assertRaises(self.gate.GateError):
            self.check()

    def test_blocking_item_and_scope_expansion_block(self):
        self.inventory["open_items"] = [{"issue": "Unresolved grant"}]
        with self.assertRaises(self.gate.GateError):
            self.check()
        self.inventory["open_items"] = []
        self.inventory["approved_scope"] = "all-commercial-distribution"
        with self.assertRaises(self.gate.GateError):
            self.check()


if __name__ == "__main__":
    unittest.main()
