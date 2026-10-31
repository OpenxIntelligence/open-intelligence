## Running the first implementation locally

This is an **original, dependency-free Python 3.11+** experimental implementation. No clinical backend, model, hosted API, third-party UI library, or professional license is required for the synthetic-only exercise.

```bash
PYTHONPATH=src python -m open_intelligence seed
PYTHONPATH=src python -m open_intelligence serve
# Visit http://127.0.0.1:8765
```

To run the verification suite:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

For the demonstration: create a question in `CASE-ALPHA`, save an investigation draft linked to the pathology document, acknowledge it in demo mode, load the example amendment, and import it. The prior investigation becomes `stale`, the question reopens, and the original source remains accessible. Draft a replacement against the amended document. `CASE-BETA` remains unaffected.

**Scope and warnings:** this is local-only software with no authentication, no access controls suitable for PHI, no clinical inference, no live literature or trials, and no clinical review. Never insert real patient data. The supported structured test format is `OI-SYNTHETIC-REPORT/1`, not a general-purpose clinical document parser. Source statements are author-supplied within report bytes. There is no treatment recommender, trial matching, or AI agent. The demo reviewer acknowledgment cannot attest professional credentials. The engineering controls are not evidence of medical safety or regulatory status.

The project distribution license remains undecided. Public source visibility is not an open-source license grant. All test reports and UI code are independently authored for this repository.
