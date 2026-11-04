"""The explicit fictional seed must fail without disclosing operator config."""
import os
import subprocess
import sys
import unittest


class EvidenceCatalogCLITests(unittest.TestCase):
    def test_unconfigured_catalog_fails_without_traceback(self):
        environment = dict(os.environ, OI_API_ENVIRONMENT="synthetic")
        environment.pop("OI_API_DATABASE_URL", None)
        result = subprocess.run([sys.executable, "-m", "oi_api.evidence_catalog"],
                                env=environment, text=True, capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Fictional catalog unavailable", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_invalid_operator_configuration_is_never_echoed(self):
        environment = dict(os.environ, OI_API_ENVIRONMENT="synthetic",
                           OI_API_DATABASE_URL="invalid://private-seed-canary")
        result = subprocess.run([sys.executable, "-m", "oi_api.evidence_catalog"],
                                env=environment, text=True, capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("private-seed-canary", result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
