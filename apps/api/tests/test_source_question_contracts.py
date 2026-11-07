"""Shared question contracts remain usable without HTTP composition."""

import subprocess
import sys
import unittest


class SourceQuestionContractTests(unittest.TestCase):
    def test_independent_import_preserves_public_types_and_oncology_validation(self):
        result = subprocess.run([sys.executable, "-c", '''
import sys
from pydantic import ValidationError
from oi_api.source_question_contracts import QuestionSourceState, SelectedComposerSource, SourceQuestionBrief
from oi_api.source_contracts import ReportedOncologyContext, SourceOncologyFields
assert "oi_api.patients" not in sys.modules
from oi_api import patients
assert patients.SourceQuestionBrief is SourceQuestionBrief
assert patients.QuestionSourceState is QuestionSourceState
assert patients.SelectedComposerSource is SelectedComposerSource
assert patients.ReportedOncologyContext is ReportedOncologyContext
assert patients.SourceOncologyFields is SourceOncologyFields
payload = dict(source_id="source", document_id="document", version=1, sha256="digest",
    line=1, finding_key="finding", reported_state="unknown", statement="Fictional source",
    kind="pathology", event_date="2026-11-05", issued_at="2026-11-05", specimen_id=None)
assert "oncology" not in SelectedComposerSource(**payload).model_dump(mode="json")
context = {"role": "primary", "episode_id": "EP-FICTIONAL"}
assert SelectedComposerSource(**payload, oncology=context).model_dump()["oncology"] == context
for invalid in (dict(payload, oncology=None), dict(payload, line=0),
                dict(payload, version=0), dict(payload, oncology={"role": "invented", "episode_id": None})):
    try:
        SelectedComposerSource(**invalid)
    except ValidationError:
        pass
    else:
        raise AssertionError("Invalid source contract accepted")
'''], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
