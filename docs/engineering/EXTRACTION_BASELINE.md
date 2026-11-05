# Executable extraction baseline

4 November 2026. OI-006 / OI-011 / OI-013. Additive implementation of the comparison prerequisite proposed in [#452](https://github.com/OpenxIntelligence/open-intelligence/pull/452).

The offline runner calls the existing document-preview owner. It does not write patient state, accept external documents or invoke a model. Use it to answer two different questions: did intake preserve the source contract, and did linear text preserve the associations visible in a table?

## Intake and table results

| Test | Observed with the pinned pypdf 6.21.4 wheel | Interpretation |
| --- | --- | --- |
| 16 built-in intake challenges (E01–E16) | 8 accepted with exact source checks; 8 refused for the specified reason; no execution errors | All 16 expectations matched. Only the eight accepted cases are extractions. |
| Two PDFs displaying the same two specimen rows (L01–L02) | Both measured; one preserved visual row order, one changed it | Plain-text order alone cannot establish which value belongs to which specimen in this layout. This pair is not a population accuracy estimate. |

E01–E09 retain the original LF/UTF-8/CRLF text, multipage/blank/compressed PDF and encrypted/image-only/malformed/oversize cases. E10 preserves a UTF-8 BOM, decomposed French accent, Arabic, decimal comma and CRLF without normalization. E11 keeps tabs, an empty line and distinct negative, pending and indeterminate states. E12 keeps the physical page and line of opposite rotations. E13 refuses a readable cover followed by an image-only page. E14–E16 refuse an annotated PDF, a bidirectional override in text and a PDF form, respectively. No partial extraction is credited for a refusal.

The table probe uses four nonoverlapping cells at fixed coordinates. L01 emits their drawing commands row by row. L02 emits them column by column. Both show the following fictional content:

| Specimen | Value |
| --- | --- |
| Specimen A | 2.5 mg/L |
| Specimen B | 25 mg/L |

L01 extracted as two lines, `Specimen A 2.5 mg/L` and `Specimen B 25 mg/L`. L02 extracted as four lines: `Specimen A`, `Specimen B`, `2.5 mg/L`, `25 mg/L`. Every word survived. The visual row relationships did not survive as adjacent words in L02. Returning the correct original hash and correct line anchors does not repair that loss. Verify a row against the original before treating it as a specimen/value association. The probe records a limitation; it adds no detector or production review gate.

**Independent render cross-check:** the two authored PDFs produced identical grayscale PGM bytes at 144 DPI (1224 × 1584, 1,938,833 bytes; SHA-256 `d5f9d826e4c6dcea87ea904382267771e9327da1adcfc510c1467e959d8bfac3`), with ink in all four cell regions. This was a local comparison with pdftoppm 26.05.0, not an added runtime or CI dependency. A different rasterizer version may produce different bytes.

## Run and interpret a receipt

From repository root in the existing hash-locked parser environment:

```sh
PYTHONPATH=src python -m tools.extraction_baseline --output extraction-baseline.json
PYTHONPATH=src python -m tools.extraction_baseline --require-layout-order --output layout-qualification.json
PYTHONPATH=src python -m unittest discover -s tests -p test_extraction_baseline.py -v
```

The v2 JSON separates `results` (16 intake cases) from `layout_probe.results` (2 table cases). The default exit 0 means all intake expectations matched and both probes were measurable. It does **not** mean tables qualify. The strict command also requires both visual row orders; on these inputs it writes the receipt and exits 1. A failure to measure yields `all_rows_preserved: null` and fails even the default command. Exit 2 means the specified output could not be created. Output uses exclusive creation; use a new filename on each run. The v1 nine-case receipt remains historical evidence for its original revision.

Accepted results must bind the filename, MIME type, extraction method, annotation method, review status, original byte count/hash, literal text and exact lines. PDF checks additionally bind the pinned descriptor, page text hashes, local anchors and rendition fingerprint. Layout scoring checks the original and reconstructs the one-page rendition before testing word order. Only whitespace is ignored in that comparison. Equal word multisets with different order and changed word content receive separate outcomes. Malformed intake output fails its contract as a mismatch or an error; a missing/wrong worker is an error, never an expected rejection. A missing fixture, wrong fixture digest, or invalid layout rendition makes that probe unmeasurable. Both PDF digests are pinned so that duplicating the easy example cannot qualify the pair.

`metrics` is an allowlisted projection of the intake cases: fixed fixture ID, operation, finite duration or null, and bounded outcome. No text, filenames, hashes or exception messages enter it. The synthetic receipt separately retains original and code/lockfile hashes. No collector/exporter is integrated. Review time is null, and single-attempt timings are not benchmarks. Python adapter/clock injection supports fault tests only.

## Earlier nine-case verification

- Tests-first: seven new tests failed because the runner was absent.
- Initial local implementation: six of seven tests passed. The full-corpus test failed because the local pypdf installation is 6.10.0 instead of the pinned 6.21.4. It reported two text successes, one oversized-text rejection and six PDF execution errors; no skip or false PDF pass is claimed.
- Hosted workflow now explicitly checks out the PR head, executes the unchanged full reference Python/HTTP suite, and retains the real baseline JSON alongside source-under-test and existing browser receipts. Exact-head hosted results and independent review are recorded in the draft PR after execution.
- Independent review found that a recomputed digest could hide a malformed extractor descriptor, and a preceding suite failure would suppress the diagnostic receipt step. A new regression reproduced the descriptor false pass; the runner now checks the complete pinned descriptor independently. The receipt step runs even after failure, without suppressing its exit code. Targeted corruption assertions use a known-valid controlled rendition so an unavailable local PDF worker cannot make those tests falsely pass. Controlled rendition checks are not actual PDF extraction evidence.

## Expanded verification and remaining comparison

The existing wrong-version limitation was resolved locally by installing the exact lockfile wheel in a separate environment with pip --no-index --no-deps --require-hashes; the system interpreter was not changed. Before implementation, sixteen text/PDF attribution subcases falsely passed with a missing or incorrect filename, media type or extraction/annotation method. The expanded regression requires those mutations to fail. Controlled faults distinguish changed word order, changed words and invalid attribution from one another. See the PR for revision-specific hosted evidence.

Docling, OCR, complex layouts/tables, scanned multilingual documents and semantic extraction remain unqualified. This baseline does not measure reading order for arbitrary PDFs, clinical interpretation, reviewer effort, recall on unseen records, patient assignment, amendment persistence or cross-tenant authorization; existing domain tests remain separate. A future adapter must first pin code, artifacts, dependencies and model/data rights, then compare on held-out authored challenges with the same source identity and review boundaries. Do not infer that eight exact synthetic extractions justify clinical deployment or that expected rejections count as successful extraction.
