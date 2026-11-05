"""Regression tests for reproducibility, cross-stack identity and scope."""
import base64
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import h1_build_inputs as inputs


class BuildInputsTests(unittest.TestCase):
    def test_reproducible_receipt_and_byte_level_drift(self):
        with TemporaryDirectory() as td:
            a, b = (Path(td) / n for n in ("a.json", "b.json"))
            for path in (a, b):
                self.assertEqual(inputs.main(["--output", str(path)]), 0)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertEqual(inputs.main(["--verify", str(a)]), 0)
            a.write_bytes(a.read_bytes().replace(b'"commercial_distribution_cleared": false',
                                                 b'"commercial_distribution_cleared": true'))
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertNotEqual(inputs.main(["--verify", str(a)]), 0)

    def test_pydicom_upstream_cannot_replace_the_runtime_wheel(self):
        source = inputs.read_json(inputs.ROOT / inputs.API / "dependency-license-inventory.json")
        reviewed = next(p for p in source["packages"] if p["name"] == "pydicom")
        api = inputs.wheel_inputs(inputs.ROOT, source)
        built = next(p for p in api["runtime_wheels"] if p["name"] == "pydicom")
        upstream, = api["preparation_only"]
        self.assertNotEqual(upstream["sha256"], built["sha256"])
        self.assertEqual(upstream["derived_sha256"], built["sha256"])
        reviewed["sha256"] = upstream["sha256"]
        with self.assertRaisesRegex(ValueError, "differs from lock"):
            inputs.wheel_inputs(inputs.ROOT, source)

    def test_nested_alias_has_distinct_install_path_registry_identity_and_digest(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            web = root / inputs.WEB
            web.mkdir(parents=True)
            archive = hashlib.sha512(b"fictional package bytes").digest()
            sri = "sha512-" + base64.b64encode(archive).decode()
            alias = "node_modules/parent/node_modules/build"
            record = {"name": "@tools/wasm", "version": "1.0.0", "license": "MIT", "dev": True,
                      "integrity": sri, "resolved": "https://registry.npmjs.org/@tools/wasm/-/wasm-1.0.0.tgz"}
            parent = {"version": "2.0.0", "license": "MIT", "integrity": sri,
                      "resolved": "https://registry.npmjs.org/parent/-/parent-2.0.0.tgz"}
            deps = {"dependencies": {"parent": "2.0.0"}}
            lock = {"lockfileVersion": 3, "packages": {"": deps, "node_modules/parent": parent, alias: record}}
            (web / "package.json").write_text(json.dumps({**deps, "overrides": {"build": "npm:@tools/wasm@1.0.0"}}))
            path = web / "package-lock.json"
            path.write_text(json.dumps(lock))
            row = next(r for r in inputs.npm_inputs(root) if r["location"] == alias)
            self.assertEqual((row["install_name"], row["name"], row["integrity"]), ("build", "@tools/wasm", sri))
            self.assertEqual(row["dependency_flags"], ["dev"])
            for key, replacement in (("integrity", "sha512-YQ=="), ("name", "build"), ("version", "1.0.1"),
                                     ("resolved", parent["resolved"]), ("optional", "false")):
                with self.subTest(key=key):
                    broken = copy.deepcopy(lock)
                    broken["packages"][alias][key] = replacement
                    path.write_text(json.dumps(broken))
                    with self.assertRaises(ValueError):
                        inputs.npm_inputs(root)

    def test_web_receipt_requires_exact_bindings_and_separate_absences(self):
        inventory = inputs.build(inputs.ROOT)
        digest = inventory["inputs_sha256"][inputs.WEB + "package-lock.json"]
        records = []
        for row in inventory["web_lock_locations"]:
            r = {"location": row["location"], "version": row["version"], "license": row["declared_license"],
                 "integrity": row["integrity"], "installed": row["expected_in_omit_optional_install"]}
            if r["installed"]:
                r.update(name=row["name"], resolved=row["registry_tarball"],
                         notice_files=[{"name": "LICENSE", "text": "sample", "sha256": hashlib.sha256(b"sample").hexdigest()}])
            else:
                r.update(scope="optional-platform-not-inspected")
            records.append(r)
        receipt = {"schema": "oi.frontend-dependency-evidence/1", "scope": "local-fictional-development-only",
                   "commercial_release_cleared": False, "native_object_linkage_reviewed": False,
                   "lock_sha256": digest, "records": records, "errors": []}
        inputs.check_web(receipt, inventory)
        optional = next(i for i, r in enumerate(records) if not r["installed"])
        alias = next(i for i, r in enumerate(records) if r.get("name") == "@rollup/wasm-node")
        for mutation in (
            lambda r: r.update(lock_sha256="0" * 64),
            lambda r: r.update(errors=["an earlier gate failed"]),
            lambda r: r["records"].append(r["records"][0]),
            lambda r: r["records"].pop(),
            lambda r: r["records"][optional].update(installed=True),
            lambda r: r["records"][alias].update(name="rollup"),
            lambda r: r["records"][alias]["notice_files"][0].update(text="substituted"),
        ):
            wrong = copy.deepcopy(receipt)
            mutation(wrong)
            with self.assertRaises(ValueError):
                inputs.check_web(wrong, inventory)

    def test_inventory_binds_image_manifest_bytes_and_declared_platforms(self):
        path = "apps/api/container-image-pins.json"
        with TemporaryDirectory() as td:
            root = Path(td)
            for rel in inputs.INPUTS:
                if rel != path:
                    (root / rel).parent.mkdir(parents=True, exist_ok=True)
                    (root / rel).symlink_to(inputs.ROOT / rel)
            (root / path).write_bytes((inputs.ROOT / path).read_bytes())
            before = inputs.build(root)
            pins = inputs.read_json(root / path)
            self.assertEqual(before["declared_oci_images"], pins)
            pins["postgres"]["config"] = "sha256:" + "1" * 64
            (root / path).write_text(json.dumps(pins))
            after = inputs.build(root)
            self.assertNotEqual(after["inputs_sha256"][path], before["inputs_sha256"][path])
            self.assertEqual(after["declared_oci_images"]["postgres"]["config"], pins["postgres"]["config"])

    def test_web_bom_requires_the_exact_sibling_written_by_the_notice_gate(self):
        with TemporaryDirectory() as td:
            evidence = Path(td) / "licenses"
            evidence.mkdir()
            bom = evidence / "web.cdx.json"
            bom.write_bytes(b'{"bomFormat":"CycloneDX"}\n')
            binding = {"filename": bom.name, "sha256": hashlib.sha256(bom.read_bytes()).hexdigest()}
            inputs.check_web_bom(evidence, binding)
            bom.write_bytes(b'{"bomFormat":"CycloneDX"}')
            with self.assertRaisesRegex(ValueError, "digest"):
                inputs.check_web_bom(evidence, binding)
            bom.rename(Path(td) / bom.name)
            with self.assertRaises(OSError):
                inputs.check_web_bom(evidence, binding)
            with self.assertRaisesRegex(ValueError, "filename"):
                inputs.check_web_bom(evidence, {**binding, "filename": "../web.cdx.json"})
            bom.symlink_to(Path(td) / bom.name)
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                inputs.check_web_bom(evidence, binding)

    def test_api_receipt_cannot_omit_supplier_components_or_replace_wheel_hash(self):
        source = inputs.read_json(inputs.ROOT / inputs.API / "dependency-license-inventory.json")
        sbom = inputs.wheel_gate.cyclonedx({"inventory": source})
        with TemporaryDirectory() as td:
            out = Path(td) / "sbom.json"
            for mutate in (lambda c: c.pop(next(i for i, r in enumerate(c) if r["purl"].startswith("pkg:cargo/"))),
                           lambda c: c[0]["hashes"][0].update(content="0" * 64)):
                broken = copy.deepcopy(sbom)
                mutate(broken["components"])
                out.write_text(json.dumps(broken))
                with self.assertRaisesRegex(ValueError, "API gate SBOM differs"):
                    inputs.check_gates(inputs.ROOT, {}, out, Path(td) / "unused")


if __name__ == "__main__":
    unittest.main()
