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


## Fictional evidence and case applicability slice

The evidence form supports only the explicit \`OI-SYNTHETIC-EVIDENCE/1\` format with \`Rights: original-synthetic\`. Use the bundled \`examples/synthetic/demo-evidence.txt\` text. That declaration is not legal clearance for arbitrary user-supplied text. No third-party paper, article body, guideline, or real oncology data is retrieved or reused.

The UI can register an original fictional evidence item, attach a manually-authored relationship and applicability assessment to a case-specific question, include selected assessments when drafting an investigation, inspect the exact source text/line/hash, and withdraw a fictional item. An explicit \`Amends: EVIDENCE-ID@LATEST-VERSION\` replacement or withdrawal flags every dependent investigation in every affected synthetic case as stale, while retaining older source versions for audit. Assessments for superseded/withdrawn evidence cannot be included in new drafts.

The labels \`supports\`, \`contradicts\`, and \`applicable\` are human-entered **fictional engineering data**, not determinations of evidence quality, clinical benefit, trial eligibility, or clinical relevance. The prototype has no clinician identity verification or legal rights-verification service. Never use real patient records or copyrighted publication text. Run the unit/HTTP tests before reviewing the UI; browser execution requires a separate interactive verification.


## Bibliographic metadata panel

The public bibliography panel is **not linked to the selected synthetic patient**. It displays an authored Crossref-format test record using an offline local JSON fixture. The local demo server denies live lookups by default. To explicitly enable an operator-requested DOI-only Crossref lookup:

```bash
PYTHONPATH=src python -m open_intelligence serve --enable-crossref-live
```

Optional: `--crossref-contact operator@example.org` adds the operator-supplied contact email to the DOI-only metadata request, not a patient address. Crossref's current [access policy](https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/) describes rate limits and polite contact requirements. The prototype enforces one concurrent DOI lookup and a conservative one-second gap.

Only the public DOI is transmitted to a fixed Crossref API endpoint, and only bibliographic metadata fields are rendered. Abstracts, article text, full-text links, evidence grades and patient identifiers are never included in the output. The UI does not attach metadata to a clinical assertion or claim patient relevance. Live service behavior and medical usefulness require separate evaluation. No patient data should ever be used in this demo.
