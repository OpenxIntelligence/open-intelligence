# Executable extraction baseline

4 November 2026. OI-006 / OI-011 / OI-013. Additive implementation of the comparison prerequisite proposed in [#452](https://github.com/OpenxIntelligence/open-intelligence/pull/452).

The offline runner calls the existing document preview owner with nine independently authored fixtures. Five accepted inputs cover LF text, UTF-8/CRLF, two-page PDF, blank middle page and compressed amendment PDF. Four expected rejections cover encryption, image-only PDF, malformed PDF and oversized text. Literal negation, distinct specimens, units, values and dates must survive unchanged. These are small controlled engineering challenges, not representative clinical documents or measured clinical accuracy.

Run from the repository root with its existing hash-locked pypdf environment:

```sh
PYTHONPATH=src python -m tools.extraction_baseline --output extraction-baseline.json
PYTHONPATH=src python -m unittest discover -s tests -p test_extraction_baseline.py -v
```

The CLI accepts no external document path, model/provider selection or arbitrary adapter. Output is created exclusively; an existing receipt is never replaced. Exit 0 requires every case to match; exit 1 means failed checks; exit 2 means output could not be created. No patient store is opened or mutated. `adapter` and `clock` injection in the Python API support fault tests; those runs do not establish a new extractor's identity or qualification.

Each receipt includes raw case denominators, accepted versus expected-rejected counts, failures, fictional original hashes and code/lockfile fingerprints. Success requires exact original-byte count/hash, literal text, global lines, physical PDF page/local line, page-text hashes and rendition fingerprint. Missing/wrong parser version and unexpected exceptions cannot satisfy expected rejection. Unknown/malformed return data fails without dumping its content. Review time is null because no human review measurement occurred; single-attempt durations are diagnostic, not comparative performance results.

`metrics` is a separate explicit projection: fixed fixture ID, fixed operation, finite duration or null, and bounded outcome. It contains no text, filenames, source hashes, exception messages or patient identity. The full synthetic verification receipt is **not** production telemetry. No collector/exporter or OpenTelemetry SDK is integrated. Production observability still requires its own identity, retention, access, exception-path, automatic-instrumentation and exporter-failure tests.

## Verification ledger

- Tests-first: seven new tests failed because the runner was absent.
- Initial local implementation: six of seven tests passed. The full-corpus test failed because the local pypdf installation is 6.10.0 instead of the pinned 6.21.4. It reported two text successes, one oversized-text rejection and six PDF execution errors; no skip or false PDF pass is claimed.
- Hosted workflow now explicitly checks out the PR head, executes the unchanged full reference Python/HTTP suite, and retains the real baseline JSON alongside source-under-test and existing browser receipts. Exact-head hosted results and independent review are recorded in the draft PR after execution.

## Remaining comparison

Docling, OCR, complex layouts/tables, scanned multilingual documents and semantic extraction remain unqualified. This baseline does not measure reading order for arbitrary PDFs, clinical interpretation, reviewer effort, recall on unseen records, patient assignment, amendment persistence or cross-tenant authorization; existing domain tests remain separate. A future adapter must first pin code, artifacts, dependencies and model/data rights, then compare on held-out authored challenges with the same source identity and review boundaries. Do not infer that five exact synthetic extractions justify clinical deployment or that expected rejections count as successful extraction.
