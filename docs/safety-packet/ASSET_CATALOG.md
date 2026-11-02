# Asset catalog — every demo asset and its origin

Scope: assets in the current tree on branch `oi/safety-packet`
(current `main` merged in; refreshed 2026-11-02). This supersedes the
earlier `main`-only revision (`46bb1db`), which listed three web files
and seven synthetic files; nothing listed there has been removed, and
the files merged since are added below.

There are no fonts, images, icons, audio, video, or vendored files in the
demo. The complete asset list is: six web files; twenty-one fictional
report, evidence, and discovery text files plus one replay fixture, one
bibliographic fixture, and one readme in `examples/synthetic/`; and
seven fictional report text files plus one expectations file in
`examples/patient-access/`.

## Web assets (authored for this repository)

| Asset | Origin | Purpose |
|---|---|---|
| `web/index.html` | Independently authored for this repository | Demo page structure. Loads only local `/style.css`, `/app.js`, and `/mission.js`. |
| `web/app.js` | Independently authored for this repository | Demo UI logic. No third-party library. All requests go to relative `/api/…` paths. |
| `web/mission.js` | Independently authored for this repository | Patient Mission panel logic. Fetches only the relative `/api/cases/{id}/mission` projection. |
| `web/style.css` | Independently authored for this repository | Demo styling. Imports only the local `./tokens.css` and `./base.css`. No external fonts or imported stylesheets. |
| `web/tokens.css` | Independently authored for this repository | Design tokens (spacing, type, color, system font stacks). No external resources. |
| `web/base.css` | Independently authored for this repository | Base element styles. No external resources. |

## Fictional case and evidence text (independently authored)

| Asset | Origin | Purpose / note |
|---|---|---|
| `examples/synthetic/alpha-pathology-original.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-ALPHA`, case `CASE-ALPHA` | Original pathology source for the Alpha demo case. |
| `examples/synthetic/alpha-pathology-amended.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-ALPHA`, case `CASE-ALPHA` | Amended version of the same document; exercises amendment-stale behavior. |
| `examples/synthetic/alpha-imaging.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `IMG-ALPHA`, case `CASE-ALPHA` | Imaging source for the Alpha demo case. |
| `examples/synthetic/beta-pathology.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-BETA`, case `CASE-BETA` | Pathology source for the Beta demo case. |
| `examples/synthetic/wrong-patient.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-OTHER`, case `CASE-BETA` | Negative test asset: exercises wrong-case linkage rejection. Not a real record. |
| `examples/synthetic/demo-evidence.txt` | Independently authored fictional evidence, format `OI-SYNTHETIC-EVIDENCE/1`, declaration `Rights: original-synthetic` | The original bundled evidence-format example. That declaration is not clearance for arbitrary user-supplied text. |
| `examples/synthetic/discovery-literature-001.txt` | Independently authored fictional discovery record, format `OI-SYNTHETIC-DISCOVERY/1`, key `FICT-LIT-001`, kind `literature`, DOI `10.5555/oi-synthetic-002` | Fictional bibliographic record for demonstration only. The DOI is an identifier only; no lookup is performed. |
| `examples/synthetic/discovery-trial-001.txt` | Independently authored fictional discovery record, format `OI-SYNTHETIC-DISCOVERY/1`, key `FICT-TRIAL-001`, kind `trial`, registry `FICT-NCT-000001`, status `not-verified` | Fictional study listing for demonstration only. Recruitment availability is not verified. |
| `examples/synthetic/oi019-a-t0-pathology.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-OI019-A`, case `CASE-OI019-A` | Case A baseline pathology (T0). |
| `examples/synthetic/oi019-a-t0-imaging.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `IMG-OI019-A`, case `CASE-OI019-A` | Case A baseline imaging (T0). |
| `examples/synthetic/oi019-a-t1-clinical.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `CLIN-OI019-A`, case `CASE-OI019-A` | Case A new-information clinical note (T1). |
| `examples/synthetic/oi019-a-t2-clinical-amended.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `CLIN-OI019-A`, case `CASE-OI019-A`, amends `CLIN-OI019-A@1` | Case A amendment (T2) of the T1 clinical document only. |
| `examples/synthetic/oi019-b-t0-pathology.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-OI019-B`, case `CASE-OI019-B` | Case B baseline pathology (T0). |
| `examples/synthetic/oi019-b-t0-imaging.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `IMG-OI019-B`, case `CASE-OI019-B` | Case B baseline imaging (T0). |
| `examples/synthetic/oi019-b-t1-clinical.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `CLIN-OI019-B`, case `CASE-OI019-B` | Case B new-information clinical note (T1). |
| `examples/synthetic/oi019-b-t2-clinical-amended.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `CLIN-OI019-B`, case `CASE-OI019-B`, amends `CLIN-OI019-B@1` | Case B amendment (T2) of the T1 clinical document only. |
| `examples/synthetic/oi019-evidence-control.txt` | Independently authored fictional evidence, format `OI-SYNTHETIC-EVIDENCE/1`, id `EVID-OI019-CONTROL`, declaration `Rights: original-synthetic` | No-threat control example. That declaration is not clearance for arbitrary user-supplied text. |
| `examples/synthetic/oi019-evidence-discussion.txt` | Independently authored fictional evidence, format `OI-SYNTHETIC-EVIDENCE/1`, id `EVID-OI019-DISCUSSION`, declaration `Rights: original-synthetic` | Preservation-discussion example. That declaration is not clearance for arbitrary user-supplied text. |
| `examples/synthetic/oi019-evidence-hypothetical.txt` | Independently authored fictional evidence, format `OI-SYNTHETIC-EVIDENCE/1`, id `EVID-OI019-HYPOTHETICAL`, declaration `Rights: original-synthetic` | Hypothetical-criterion example. That declaration is not clearance for arbitrary user-supplied text. |
| `examples/synthetic/oi019-evidence-invalid.txt` | Independently authored fictional evidence, format `OI-SYNTHETIC-EVIDENCE/1`, id `EVID-OI019-INVALID`, declaration `Rights: original-synthetic` | Invalid-candidate example. That declaration is not clearance for arbitrary user-supplied text. |
| `examples/synthetic/oi019-wrong-patient.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-OI019-WRONG`, declares `CASE-OI019-B` | Negative test asset: intentionally declares the other synthetic subject. Not a real record. |
| `examples/patient-access/oi017-pathology-specimen-a.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-OI017-A`, case `CASE-OI017` | Institution A pathology on specimen A. |
| `examples/patient-access/oi017-pathology-specimen-a-amended.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-OI017-A`, case `CASE-OI017`, amends `PATH-OI017-A@1` | Amended version of the specimen A document. |
| `examples/patient-access/oi017-pathology-specimen-b.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-OI017-B`, case `CASE-OI017` | Institution B pathology on a different specimen B. |
| `examples/patient-access/oi017-encounter-inst-a.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `ENC-OI017-A`, case `CASE-OI017` | Institution A encounter note. |
| `examples/patient-access/oi017-medications-inst-a.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `MEDS-OI017-A`, case `CASE-OI017` | Institution A medications note. |
| `examples/patient-access/oi017-imaging-report-only.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `IMG-OI017-A`, case `CASE-OI017` | Imaging report-only note. |
| `examples/patient-access/oi017-collision-wrong-binding.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-OI017-COLLISION`, case `CASE-OI017` | Negative test asset: envelope binding conflicts with the recorded binding; must be rejected, not merged. Not a real record. |

## Fictional bibliographic and replay fixtures (independently authored)

| Asset | Origin | Purpose / note |
|---|---|---|
| `examples/synthetic/crossref-metadata-fixture.json` | Independently authored fictional entry in Crossref JSON shape; DOI `10.5555/oi-synthetic-001`; journal "Fictional Examples Journal" | Offline bibliography demonstration. Not a real article citation. No live lookup is performed for this entry. |
| `examples/synthetic/demo-investigation.json` | Independently authored recorded demonstration output with `FIRST_SOURCE` / `FIRST_ASSESSMENT` citation placeholders | Offline replay for model investigation. Placeholders are replaced server-side with real current case ids and validated like live output; labeled `mode=replay`, never a live run. |
| `examples/synthetic/oi019-readme.md` | Independently authored demonstration note | Describes the OI-019 two-case staging (T0/T1/T2 by file import) and the four evaluation elements. Not advice or a recommendation. |
| `examples/patient-access/EXPECTED_RESULTS.json` | Independently authored expectations record for `CASE-OI017` | Per-fixture hashes and sizes plus a synthetic-provenance statement. Synthetic contract evidence only. |

## Explicitly absent

- No real patient records, clinical images, pathology slides, or genomic
  files.
- No copyrighted article, guideline, or trial text.
- No model weights, embeddings, or datasets.
- No stock or licensed media of any kind.

## Verification method

Each file above was listed from the repository and its first lines
inspected on 2026-11-02: every `.txt` file opens with an
`OI-SYNTHETIC-*` marker, the JSON fixtures carry the fictional
identifiers shown above, and the two readme/expectations files carry
their own fictional-provenance statements. The guard test
`tests/test_safety_packet.py` re-checks these markers in both example
directories on every test run.
