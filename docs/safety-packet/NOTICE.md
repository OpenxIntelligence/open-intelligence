# NOTICE — Open Intelligence demo

## Fictional-data statement

Every patient case, source report, finding, question, assessment, and
bibliographic entry in this demo is independently authored fictional
content created for a software demonstration. No real patient is involved.
No real patient record, clinical document, or identifiable health
information is shipped in this repository, and none may be entered into
the demo. The demo's own documentation states this (`README.md`,
`README_IMPLEMENTATION.md`); the UI labels the demo data as fictional.

## What is not shipped, and what is not claimed

- No third-party clinical content: no article body, guideline text, trial
  record, or real oncology data is retrieved or reused. The only
  third-party material referenced is Crossref bibliographic metadata, which
  is metadata-only (see `DATA_RIGHTS.md`). Publisher abstracts are
  excluded by the adapter.
- No model weights and no model: the demo on `main` makes no model call.
- No unlicensed assets: the demo ships no fonts, images, icons, audio,
  video, or vendored third-party code. The `web/` directory contains only
  HTML, JavaScript, and CSS authored for this repository.
- No clinical approval, validation, or clearance is claimed. Demo
  acknowledgments do not attest professional credentials, and the
  engineering controls in this repository are not evidence of medical
  safety or regulatory status (per `README_IMPLEMENTATION.md`).
- No treatment recommendation, trial matching, staging, grading, variant
  interpretation, or response/progression inference is performed by the
  demo. Labels such as `supports`, `contradicts`, and `applicable` are
  human-entered fictional engineering data, not determinations of evidence
  quality, clinical benefit, trial eligibility, or clinical relevance.

## License status — undecided, explicitly

The project's distribution license has NOT been selected
(per `README.md`: "The project's distribution license has not yet been
selected. This initial foundation includes original project documentation
and references to external sources; it does not vendor their code or
datasets. A project license and any third-party notices will be added
through an explicit licensing decision.").

Public visibility of this repository is not an open-source license grant,
and this NOTICE does not grant one. Do not describe this demo as
open-source licensed until a license is chosen through that explicit
decision.

## Third-party notices

No third-party code is shipped, so no third-party license notices are
owed for shipped code. Two referenced (not shipped) items are recorded
for transparency:

- Crossref bibliographic metadata: bibliographic metadata is factual and
  not subject to copyright; Crossref-generated data is released as CC0;
  abstracts remain under publisher or author copyright and are excluded
  by the adapter. Verified against Crossref's Metadata Retrieval
  documentation on 2026-11-01 and recorded in
  `docs/CROSSREF_METADATA_BOUNDARY.md` (checked 31 October 2026 there).
- GitHub Actions used in CI only (`actions/checkout@v4`,
  `actions/setup-python@v5`): license terms UNVERIFIED in this packet;
  see `SBOM.md` for the re-verification step. They are not shipped.

## Precedence

The current project name is Open Intelligence. The earlier name CEVax
refers only to the historical research archive and is not used for this
demo. Research dossiers, diagrams, and vendor comparisons are
complementary inputs, not a new architecture or a replacement baseline.
