"""Offline regression: retired case-specific research entrypoints cannot fetch data."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import rna_expression_probe as rna
import single_cell_probe as sc


class RetiredResearchEntrypointTests(unittest.TestCase):
    def test_rna_fetch_is_denied_before_network_open(self):
        with patch.object(rna, "build_opener", side_effect=AssertionError("network call")):
            with self.assertRaises(PermissionError):
                rna.fetch("fictional-test-url", 100)

    def test_rna_run_is_denied_before_acquisition(self):
        with patch.object(rna, "fetch", side_effect=AssertionError("fetch called")):
            with self.assertRaises(PermissionError):
                rna.run()

    def test_single_cell_acquisition_denied_without_file_or_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "source.h5ad"
            with patch.object(sc.urllib.request, "build_opener",
                              side_effect=AssertionError("network call")):
                with self.assertRaises(PermissionError):
                    sc.acquire("fictional-test-url", target, 100)
            self.assertFalse(target.exists())

    def test_single_cell_cli_denied_before_io(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "analysis.json"
            with patch.object(sc.argparse, "ArgumentParser",
                              side_effect=AssertionError("CLI accessed")):
                with self.assertRaises(PermissionError):
                    sc.main()
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
