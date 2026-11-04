"""Code-only wheel boundaries, using independently authored non-DICOM fixtures."""

import base64
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import warnings
from zipfile import ZIP_STORED, ZipFile, ZipInfo


TOOL = Path(__file__).resolve().parents[1] / "tools/pydicom_runtime.py"
DIST = "pydicom-3.0.2.dist-info"
OUTPUT = "pydicom-3.0.2-1oi1-py3-none-any.whl"


class DependencyPackagingTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(TOOL.is_file(), "The code-only packaging implementation is required")
        spec = importlib.util.spec_from_file_location("pydicom_runtime_test", TOOL)
        self.runtime = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.runtime)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "pydicom-3.0.2-py3-none-any.whl"
        self.output = self.root / OUTPUT
        self.entries = {
            "pydicom/__init__.py": b'__version__ = "3.0.2"\nimport pydicom.examples\n',
            "pydicom/filereader.py": b"# Authored parser stand-in; never clinical data.\n",
            "pydicom/_private_dict.py": b"private_dictionaries = {}\n",
            "pydicom/_dicom_dict.py": b"DicomDictionary = {}\n",
            "pydicom/data/__init__.py": b"# Runtime helper code is retained.\n",
            "pydicom/py.typed": b"",
            "pydicom/examples.py": b"# Example helpers are outside the runtime scope.\n",
            "pydicom/examples/__init__.py": b'raise AssertionError("Example dataset lookup must never execute")\n',
            "pydicom/data/test_files/fixture.dcm": b"NOT_DICOM_EXCLUDED_SENTINEL_7e2f",
            "pydicom/data/test_files/generator.py": b"# Sample-only generator is excluded.\n",
            "pydicom/data/charset_files/fixture.dcm": b"Fictional charset asset; not DICOM.",
            "pydicom/data/palettes/extensionless": b"Fictional palette asset; not DICOM.",
            "pydicom/data/urls.json": b'{"no-download": "https://example.invalid"}',
            "pydicom/data/hashes.json": b"{}",
            f"{DIST}/METADATA": b'Metadata-Version: 2.4\nName: pydicom\nVersion: 3.0.2\nRequires-Python: >=3.10\nRequires-Dist: numpy ; extra == "basic"\n',
            f"{DIST}/WHEEL": b"Wheel-Version: 1.0\nGenerator: authored-test-fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
            f"{DIST}/licenses/LICENSE": b"Independently authored license-text placeholder for packaging tests.\n",
            f"{DIST}/entry_points.txt": b"[console_scripts]\nfictional = pydicom:main\n",
            f"{DIST}/RECORD": b"Source RECORD is replaced, not copied.\n",
        }
        self.write_source()

    def write_source(self):
        with ZipFile(self.source, "w", compression=ZIP_STORED) as archive:
            # Deliberately reverse source order; the output must canonicalize it.
            for name, content in reversed(list(self.entries.items())):
                archive.writestr(name, content)
        self.source_hash = hashlib.sha256(self.source.read_bytes()).hexdigest()

    def build(self):
        return self.runtime.build_code_only(self.source, self.output, self.source_hash)

    def rewrite_output(self, replacements):
        with ZipFile(self.output) as archive:
            entries = {item.filename: (item, archive.read(item.filename)) for item in archive.infolist()}
        for name, content in replacements.items():
            info = entries[name][0] if name in entries else ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = ZIP_STORED
            entries[name] = (info, content)
        with ZipFile(self.output, "w", compression=ZIP_STORED) as archive:
            for name in sorted(entries):
                info, content = entries[name]
                archive.writestr(info, content)

    def test_repeated_build_is_identical_with_fixed_zip_metadata(self):
        self.build()
        first = self.output.read_bytes()
        self.output.unlink()
        self.build()
        self.assertEqual(first, self.output.read_bytes())
        with ZipFile(self.output) as archive:
            self.assertEqual(archive.namelist(), sorted(archive.namelist()))
            self.assertTrue(all(x.date_time == (1980, 1, 1, 0, 0, 0) for x in archive.infolist()))
            self.assertTrue(all(x.compress_type == ZIP_STORED for x in archive.infolist()))

    def test_source_tampering_fails_before_output_exists(self):
        with self.source.open("ab") as stream:
            stream.write(b"tampered")
        with self.assertRaises(self.runtime.PackagingError):
            self.build()
        self.assertFalse(self.output.exists())

    def test_excluded_asset_payload_is_never_read(self):
        # Corrupt only the excluded entry's payload, leaving its ZIP CRC stale.
        # Reading/decompressing it would raise BadZipFile. No actual DICOM is used.
        content = self.source.read_bytes().replace(
            b"NOT_DICOM_EXCLUDED_SENTINEL_7e2f", b"NOT_DICOM_EXCLUDED_SENTINEL_7e2g")
        self.source.write_bytes(content)
        self.source_hash = hashlib.sha256(content).hexdigest()
        self.build()
        with ZipFile(self.output) as archive:
            self.assertNotIn("pydicom/data/test_files/fixture.dcm", archive.namelist())

    def test_only_runtime_code_and_notices_survive_with_valid_metadata_and_record(self):
        self.build()
        expected = {
            "pydicom/__init__.py", "pydicom/filereader.py", "pydicom/_private_dict.py",
            "pydicom/_dicom_dict.py", "pydicom/data/__init__.py", "pydicom/py.typed",
            f"{DIST}/METADATA", f"{DIST}/WHEEL", f"{DIST}/licenses/LICENSE",
            f"{DIST}/entry_points.txt", f"{DIST}/RECORD",
        }
        with ZipFile(self.output) as archive:
            self.assertEqual(set(archive.namelist()), expected)
            for name in expected - {f"{DIST}/WHEEL", f"{DIST}/RECORD", "pydicom/__init__.py"}:
                self.assertEqual(archive.read(name), self.entries[name])
            self.assertEqual(archive.read("pydicom/__init__.py"), b'__version__ = "3.0.2"\n')
            wheel = archive.read(f"{DIST}/WHEEL").decode()
            self.assertIn("Build: 1oi1\n", wheel)
            self.assertIn("Tag: py3-none-any\n", wheel)
            rows = list(csv.reader(io.StringIO(archive.read(f"{DIST}/RECORD").decode())))
            self.assertEqual({r[0] for r in rows}, expected)
            self.assertEqual(len(rows), len(expected))
            for name, digest, size in rows:
                if name.endswith("/RECORD"):
                    self.assertEqual((digest, size), ("", ""))
                else:
                    content = archive.read(name)
                    want = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode()
                    self.assertEqual((digest, size), ("sha256=" + want, str(len(content))))
        self.runtime.verify_code_only(self.output)

    def test_core_import_never_invokes_example_lookup(self):
        self.build()
        result = subprocess.run(
            [sys.executable, "-I", "-c", "import sys; sys.path.insert(0, sys.argv[1]); import pydicom; assert pydicom.__version__ == '3.0.2'", str(self.output)],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_eager_import_patch_target_is_rejected(self):
        self.entries["pydicom/__init__.py"] = b'__version__ = "3.0.2"\n'
        self.write_source()
        with self.assertRaises(self.runtime.PackagingError):
            self.build()

    def test_wrong_package_identity_is_rejected(self):
        self.entries[f"{DIST}/METADATA"] = b"Name: pydicom\nVersion: 99.0\n"
        self.write_source()
        with self.assertRaises(self.runtime.PackagingError):
            self.build()

    def test_mandatory_runtime_dependency_is_rejected(self):
        self.entries[f"{DIST}/METADATA"] += b"Requires-Dist: forbidden-runtime\n"
        self.write_source()
        with self.assertRaises(self.runtime.PackagingError):
            self.build()

    def test_traversal_archive_member_is_rejected(self):
        self.entries["pydicom/../escape.py"] = b"# must never be retained\n"
        self.write_source()
        with self.assertRaises(self.runtime.PackagingError):
            self.build()

    def test_duplicate_archive_member_is_rejected(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with ZipFile(self.source, "a") as archive:
                archive.writestr("pydicom/__init__.py", b"# duplicate")
        self.source_hash = hashlib.sha256(self.source.read_bytes()).hexdigest()
        with self.assertRaises(self.runtime.PackagingError):
            self.build()

    def test_final_verifier_rejects_retained_data_asset(self):
        self.build()
        self.rewrite_output({"pydicom/data/test_files/retained.dcm": b"Authored non-DICOM sentinel"})
        with self.assertRaises(self.runtime.PackagingError):
            self.runtime.verify_code_only(self.output)

    def test_final_verifier_rejects_record_mismatch(self):
        self.build()
        self.rewrite_output({"pydicom/filereader.py": b"# Changed code without matching RECORD\n"})
        with self.assertRaises(self.runtime.PackagingError):
            self.runtime.verify_code_only(self.output)

    def pipeline_fixture(self, *, derived_hash=None):
        self.build()
        self.api = self.root / "api"
        (self.api / "tools").mkdir(parents=True)
        self.baseline = self.root / "baseline"
        self.baseline.mkdir()
        baseline_file = self.baseline / "fictional_dependency-1.0-py3-none-any.whl"
        notice = b"Authored packaging-test notice.\n"
        with ZipFile(baseline_file, "w") as archive:
            archive.writestr("fictional_dependency-1.0.dist-info/METADATA", "Name: fictional-dependency\nVersion: 1.0\n")
            archive.writestr("fictional_dependency-1.0.dist-info/LICENSE", notice)
        derived_hash = derived_hash or hashlib.sha256(self.output.read_bytes()).hexdigest()
        self.manifest = {
            "schema_version": 1, "name": "pydicom", "version": "3.0.2",
            "approved_scope": "local-synthetic-h1-development",
            "transformation": "oi-pydicom-code-only-v1", "build": "1oi1",
            "source": {"filename": self.source.name, "sha256": self.source_hash},
            "derived": {"filename": OUTPUT, "sha256": derived_hash},
            "patch": {"path": "pydicom/__init__.py", "operation": "remove-one-examples-import",
                      "source_sha256": hashlib.sha256(self.entries["pydicom/__init__.py"]).hexdigest(),
                      "derived_sha256": hashlib.sha256(b'__version__ = "3.0.2"\n').hexdigest()},
        }
        manifest_bytes = (json.dumps(self.manifest) + "\n").encode()
        (self.api / "tools/pydicom-runtime.json").write_bytes(manifest_bytes)
        (self.api / "tools/pydicom-upstream.lock").write_text(f"pydicom==3.0.2 --hash=sha256:{self.source_hash}\n")
        (self.api / "THIRD_PARTY_NOTICES.md").write_bytes(notice)
        baseline_hash = hashlib.sha256(baseline_file.read_bytes()).hexdigest()
        self.inventory = {
            "schema_version": 1, "status": "approved_for_specified_use", "open_items": [],
            "approved_scope": "local-synthetic-h1-development",
            "notices": {"path": "THIRD_PARTY_NOTICES.md", "sha256": hashlib.sha256(notice).hexdigest()},
            "license_policy": {"approved_selected_expressions": ["MIT", "MIT AND BSD-3-Clause"]},
            "packages": [
                {"name": "fictional-dependency", "version": "1.0", "filename": baseline_file.name,
                 "sha256": baseline_hash, "rights_state": "approved_for_specified_use",
                 "selected_license_expression": "MIT", "license_evidence": [
                     {"path_in_wheel": "fictional_dependency-1.0.dist-info/LICENSE", "sha256": hashlib.sha256(notice).hexdigest()}]},
                {"name": "pydicom", "version": "3.0.2", "filename": OUTPUT,
                 "sha256": derived_hash, "rights_state": "approved_for_specified_use",
                 "selected_license_expression": "MIT AND BSD-3-Clause", "license_evidence": [
                     {"path_in_wheel": f"{DIST}/licenses/LICENSE", "sha256": hashlib.sha256(self.entries[f"{DIST}/licenses/LICENSE"]).hexdigest()}],
                 "derivation": {"manifest": "tools/pydicom-runtime.json", "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                                "source_filename": self.source.name, "source_sha256": self.source_hash,
                                "transformation": "oi-pydicom-code-only-v1"}},
            ],
        }
        (self.api / "dependency-license-inventory.json").write_text(json.dumps(self.inventory))
        (self.api / "requirements.lock").write_text(
            f"fictional-dependency==1.0 --hash=sha256:{baseline_hash}\npydicom==3.0.2 --hash=sha256:{derived_hash}\n")
        self.destination = self.root / "verified-wheels"

    def prepare_process(self):
        prepare = TOOL.with_name("prepare_dependencies.py")
        self.assertTrue(prepare.is_file(), "Verified preparation CLI is required")
        return subprocess.run(
            [sys.executable, str(prepare), "--api-root", str(self.api), "--wheel-dir", str(self.destination),
             "--existing-wheel-dir", str(self.baseline), "--upstream-wheel", str(self.source)],
            capture_output=True, text=True, timeout=30,
        )

    def test_offline_preparation_publishes_only_the_verified_final_set(self):
        self.pipeline_fixture()
        result = self.prepare_process()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({p.name for p in self.destination.iterdir()},
                         {"fictional_dependency-1.0-py3-none-any.whl", OUTPUT})
        self.assertEqual(json.loads(result.stdout)["package_count"], 2)
        self.assertFalse((self.destination / self.source.name).exists())

    def test_preparation_rejects_changed_derived_pin_without_publishing(self):
        self.pipeline_fixture(derived_hash="0" * 64)
        result = self.prepare_process()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.destination.exists())

    def test_preparation_rejects_tampered_source_without_publishing(self):
        self.pipeline_fixture()
        with self.source.open("ab") as stream:
            stream.write(b"changed upstream")
        result = self.prepare_process()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.destination.exists())

    def test_preparation_keeps_baseline_artifact_checks(self):
        self.pipeline_fixture()
        with next(self.baseline.iterdir()).open("ab") as stream:
            stream.write(b"changed existing dependency")
        result = self.prepare_process()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.destination.exists())

    def test_preparation_rejects_source_pin_disagreement(self):
        self.pipeline_fixture()
        (self.api / "tools/pydicom-upstream.lock").write_text("pydicom==3.0.2 --hash=sha256:" + "0" * 64 + "\n")
        result = self.prepare_process()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.destination.exists())

    def test_preparation_rejects_false_patch_provenance(self):
        self.pipeline_fixture()
        self.manifest["patch"]["source_sha256"] = "0" * 64
        contents = (json.dumps(self.manifest) + "\n").encode()
        (self.api / "tools/pydicom-runtime.json").write_bytes(contents)
        self.inventory["packages"][1]["derivation"]["manifest_sha256"] = hashlib.sha256(contents).hexdigest()
        (self.api / "dependency-license-inventory.json").write_text(json.dumps(self.inventory))
        result = self.prepare_process()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.destination.exists())

    def test_existing_gate_refuses_upstream_pydicom_even_if_inventory_is_relabelled(self):
        self.pipeline_fixture()
        self.destination.mkdir()
        for wheel in self.baseline.iterdir():
            (self.destination / wheel.name).write_bytes(wheel.read_bytes())
        (self.destination / self.source.name).write_bytes(self.source.read_bytes())
        package = self.inventory["packages"][1]
        package.update(filename=self.source.name, sha256=self.source_hash)
        package.pop("derivation")
        (self.api / "dependency-license-inventory.json").write_text(json.dumps(self.inventory))
        lock = self.api / "requirements.lock"
        lock.write_text(lock.read_text().replace(self.manifest["derived"]["sha256"], self.source_hash))
        spec = importlib.util.spec_from_file_location("code_only_dependency_gate_test", TOOL.with_name("check_dependencies.py"))
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        with self.assertRaises(ValueError):
            gate.verify(self.api, self.destination)


if __name__ == "__main__":
    unittest.main()
