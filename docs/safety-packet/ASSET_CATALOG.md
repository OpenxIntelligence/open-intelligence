# Asset catalog — every demo asset and its origin

Scope: assets shipped in the demo on `main` (`46bb1db`). Unmerged work is
excluded; update this catalog when merged work adds an asset.

There are no fonts, images, icons, audio, video, or vendored files in the
demo. The complete asset list is: three web files, six fictional report
and evidence text files, and one fictional bibliographic fixture.

## Web assets (authored for this repository)

| Asset | Origin | Purpose |
|---|---|---|
| `web/index.html` | Independently authored for this repository | Demo page structure. Loads only local `/style.css` and `/app.js`. |
| `web/app.js` | Independently authored for this repository | Demo UI logic. No third-party library. |
| `web/style.css` | Independently authored for this repository | Demo styling. No external fonts or imported stylesheets. |

## Fictional case and evidence text (independently authored)

| Asset | Origin | Purpose / note |
|---|---|---|
| `examples/synthetic/alpha-pathology-original.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-ALPHA`, case `CASE-ALPHA` | Original pathology source for the Alpha demo case. |
| `examples/synthetic/alpha-pathology-amended.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-ALPHA`, case `CASE-ALPHA` | Amended version of the same document; exercises amendment-stale behavior. |
| `examples/synthetic/alpha-imaging.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `IMG-ALPHA`, case `CASE-ALPHA` | Imaging source for the Alpha demo case. |
| `examples/synthetic/beta-pathology.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-BETA`, case `CASE-BETA` | Pathology source for the Beta demo case. |
| `examples/synthetic/wrong-patient.txt` | Independently authored fictional report, format `OI-SYNTHETIC-REPORT/1`, document `PATH-OTHER`, case `CASE-BETA` | Negative test asset: exercises wrong-case linkage rejection. Not a real record. |
| `examples/synthetic/demo-evidence.txt` | Independently authored fictional evidence, format `OI-SYNTHETIC-EVIDENCE/1`, declaration `Rights: original-synthetic` | The only bundled evidence-format example. That declaration is not clearance for arbitrary user-supplied text. |

## Fictional bibliographic fixture (independently authored)

| Asset | Origin | Purpose / note |
|---|---|---|
| `examples/synthetic/crossref-metadata-fixture.json` | Independently authored fictional entry in Crossref JSON shape; DOI `10.5555/oi-synthetic-001`; journal "Fictional Examples Journal" | Offline bibliography demonstration. Not a real article citation. No live lookup is performed for this entry. |

## Explicitly absent

- No real patient records, clinical images, pathology slides, or genomic
  files.
- No copyrighted article, guideline, or trial text.
- No model weights, embeddings, or datasets.
- No stock or licensed media of any kind.

## Verification method

Each file above was listed from the repository and its first lines
inspected on 2026-11-01: every `.txt` file opens with an
`OI-SYNTHETIC-*` marker, and the JSON fixture carries the fictional DOI
and journal title shown above. The guard test
`tests/test_safety_packet.py` re-checks these markers on every test run.
