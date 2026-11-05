"""Check that the synthetic environments consume the same immutable OCI inputs."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]


class ImagePinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pins = json.loads((ROOT / "apps/api/container-image-pins.json").read_text())

    def test_build_uses_reviewed_python_index(self):
        dockerfile = (ROOT / "apps/api/Dockerfile").read_text()
        images = re.findall(r"^FROM (\S+)", dockerfile, re.MULTILINE)
        self.assertEqual(images, [self.pins["python"]["reference"]])

    def test_compose_and_both_ci_services_use_reviewed_postgres_index(self):
        reference = self.pins["postgres"]["reference"]
        for path in ("apps/api/compose.yaml", ".github/workflows/h1-api.yml",
                     ".github/workflows/h1-web.yml"):
            with self.subTest(path=path):
                config = (ROOT / path).read_text()
                images = re.findall(r"^\s*image:\s+(postgres:\S+)\s*$", config, re.MULTILINE)
                self.assertEqual(images, [reference])

    def test_pins_include_index_and_selected_platform_identity(self):
        for name, entry in self.pins.items():
            with self.subTest(image=name):
                self.assertRegex(entry["reference"], rf"^{name}:[\w.-]+@sha256:[0-9a-f]{{64}}$")
                self.assertEqual(entry["platform"], "linux/amd64")
                for key in ("manifest", "config"):
                    self.assertRegex(entry[key], r"^sha256:[0-9a-f]{64}$")
                self.assertIn("/blob/", entry["evidence"])
