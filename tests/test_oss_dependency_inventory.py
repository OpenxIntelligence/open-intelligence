"""Static inventory tests; no network, package installs or patient information."""
import json
import tempfile
import unittest
from pathlib import Path

from tools.oss_dependency_inventory import inspect


class OssDependencyInventoryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def put(self, path, text):
        dest = self.root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
        return dest

    def test_requirement_lock_and_research_scope_are_visible_not_cleared(self):
        self.put("tools/research/requirements.lock", "# research only\nlanggraph==1.0.3\npydantic==2.14.2\n")
        report = inspect(self.root)
        records = report["dependency_declarations"]
        self.assertEqual([(x["name"], x["specifier"]) for x in records],
                         [("langgraph", "==1.0.3"), ("pydantic", "==2.14.2")])
        self.assertEqual(report["files"][0]["declared_scope"], "isolated_research")
        self.assertFalse(report["rights_verified"])
        self.assertFalse(report["resolved_build_inventory"])
        self.assertFalse(report["external_downloads_performed"])

    def test_inline_pip_install_and_requirement_reference_in_ci(self):
        self.put(".github/workflows/audit.yml", """
jobs:
  test:
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
      - uses: actions/setup-python@v5
      - run: 'python -m pip install --only-binary=:all: numpy==2.3.5 h5py==3.15.1'
      - run: python -m pip install -r tools/research/requirements.lock
""")
        report = inspect(self.root)
        packages = [d["name"] for d in report["dependency_declarations"]]
        self.assertEqual(packages, ["h5py", "numpy"])  # deterministic lexicographic inventory
        self.assertEqual(
            [w["pin_status"] for w in report["workflow_references"] if "action" in w],
            ["full_sha", "tag_or_nonsha"])
        self.assertEqual(
            [w["requirement_ref"] for w in report["workflow_references"] if "requirement_ref" in w],
            ["tools/research/requirements.lock"])

    def test_application_manifest_and_optional_python_scope(self):
        self.put("package.json", json.dumps({
            "dependencies": {"react": "19.0.0"},
            "devDependencies": {"vite": "^7.0.0"},
        }))
        self.put("pyproject.toml", """
[project]
name = "sample"
version = "0.0.1"
dependencies = ["fastapi==0.1.0"]
[project.optional-dependencies]
medical = ["pydicom>=3.0"]
""")
        report = inspect(self.root)
        self.assertEqual(len(report["dependency_declarations"]), 4)
        self.assertTrue(any(d["name"] == "fastapi" and d["pin_status"] == "pinned"
                            for d in report["dependency_declarations"]))
        self.assertTrue(any(d["name"] == "pydicom" and d["pin_status"] == "not_exactly_pinned"
                            for d in report["dependency_declarations"]))
        self.assertTrue(any(d["name"] == "vite" and d["rights"] == "not_reviewed"
                            for d in report["dependency_declarations"]))

    def test_lockfile_exists_but_not_misrepresented_as_sbom(self):
        self.put("uv.lock", "some resolved content not inspected here")
        self.put("tools/research/requirements.lock", "orjson==3.13.0\n")
        result = inspect(self.root)
        self.assertTrue(any("lockfile detected" in line for line in result["warnings"]))
        self.assertFalse(result["resolved_build_inventory"])
        self.assertTrue(all(x["sha256"] for x in result["files"]))

    def test_ignores_fixture_and_venv_requirements(self):
        self.put("tests/fixtures/requirements.txt", "unsafe==0.0.1\n")
        self.put(".venv/requirements.lock", "hidden==9\n")
        self.put("tools/research/requirements.lock", "safe==2.1\n")
        data = inspect(self.root)
        self.assertEqual(len(data["dependency_declarations"]), 1)
        self.assertEqual(data["dependency_declarations"][0]["name"], "safe")

    def test_requirements_remote_or_editable_entries_cannot_pass_silently(self):
        self.put("requirements.txt", "requests>=2.0\n-e git+https://example.com/repo.git\n")
        data = inspect(self.root)
        self.assertTrue(any("manual resolution" in x for x in data["warnings"]))
        self.assertEqual(data["dependency_declarations"][0]["pin_status"], "not_exactly_pinned")

    def test_readonly_scan_is_deterministic_and_does_not_change_files(self):
        file = self.put("requirements.txt", "numpy==2.3.5\n")
        before = file.read_bytes()
        left = inspect(self.root)
        right = inspect(self.root)
        self.assertEqual(left, right)
        self.assertEqual(before, file.read_bytes())
        self.assertEqual(left["schema"], "oi.static-dependency-declarations/1")


if __name__ == "__main__":
    unittest.main()
