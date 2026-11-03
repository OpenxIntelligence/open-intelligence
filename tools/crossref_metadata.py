"""Compatibility entry point for the original metadata-only Crossref CLI.

The first-party adapter is shared with H1 through open_intelligence; CLI callers
retain their original import names and explicit offline/live modes.
"""
from pathlib import Path
import sys

# Preserve CLI use from an uninstalled checkout with no PYTHONPATH setting.
_source_root = str(Path(__file__).resolve().parents[1] / "src")
if _source_root not in sys.path:
    sys.path.insert(0, _source_root)

from open_intelligence.crossref_metadata import *  # noqa: F403
from open_intelligence.crossref_metadata import _NoRedirect, main


if __name__ == "__main__":
    main()
