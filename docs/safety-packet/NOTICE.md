# NOTICE — Open Intelligence demo

For the current tree on branch `oi/safety-packet` (current `main`
merged in; refreshed 2026-11-02).

## Fictional-data statement

Every patient case, source report, finding, question, assessment,
discovery record, option, dependency, investigation output, and
bibliographic entry in this demo is independently authored fictional
content created for a software demonstration. No real patient is involved.
No real patient record, clinical document, or identifiable health
information is shipped in this repository, and none may be entered into
the demo. The demo's own documentation states this (`README.md`,
`README_IMPLEMENTATION.md`); the UI labels the demo data as fictional.

This covers the original Alpha/Beta fixtures and every newer fixture
family: the OI-019 option-evaluation cases, the OI-017 patient-access
fixtures, the discovery literature/trial records, and the recorded
model-investigation replay fixture (see `ASSET_CATALOG.md`). All carry
their fictional markers and are listed there file by file.

The merged-main top-up (2026-11-02) adds two further fictional-only
families, likewise listed file by file in `ASSET_CATALOG.md`: the
IV-01 practice-packet fixtures (`CASE-EVAL-A`/`CASE-EVAL-B` in
`validation/iv01/cases.json`, in the same `OI-SYNTHETIC-REPORT/1` and
`OI-SYNTHETIC-EVIDENCE/1` formats) and the hand-derived `FICTIONAL-*`
/ `SYN-*` fixtures inside the `tools/research/` unit tests and the
`CASE-JSON` parser fixtures. The IV-01 coordinator key
(`validation/iv01/coordinator_key.json`) is a same-author designer
reference, not independent ground truth, and must never be
distributed to participants.

## What is not shipped, and what is not claimed

- No third-party clinical content: no article body, guideline text, trial
  record, or real oncology data is retrieved or reused. The only
  third-party material referenced is Crossref bibliographic metadata, which
  is metadata-only (see `DATA_RIGHTS.md`). Publisher abstracts are
  excluded by the adapter, and the discovery format rejects any
  `Abstract` field.
- No model weights are shipped. The only model use is the bounded,
  operator-keyed Meta investigation path described in `SBOM.md`, whose
  default replay mode runs fully offline; stored model output is always
  a pending hypothesis for review, never a conclusion.
- No unlicensed assets: the demo ships no fonts, images, icons, audio,
  video, or vendored third-party code. The `web/` directory contains only
  HTML, JavaScript, and CSS authored for this repository.
- No clinical approval, validation, or clearance is claimed. Demo
  acknowledgments do not attest professional credentials, and the
  engineering controls in this repository are not evidence of medical
  safety or regulatory status (per `README_IMPLEMENTATION.md`).
- No treatment recommendation, trial matching, staging, grading, variant
  interpretation, response/progression inference, eligibility or efficacy
  determination, or clinical-deadline inference is performed by the
  demo. Labels such as `supports`, `contradicts`, and `applicable` are
  human-entered fictional engineering data, not determinations of evidence
  quality, clinical benefit, trial eligibility, or clinical relevance.
  Discovery titles, summaries, and link rationales pass a fail-closed
  guard that rejects eligibility/efficacy/benefit language; option
  deadlines and threats accept a date only with a `sourced` basis and
  anchor, and `unknown` otherwise. None of these guards is a clinical
  determination.
- No research-probe or evaluation-tooling function is shipped in the
  demo. The `tools/research/` probes run in CI only and hit live
  public endpoints read-only; raw rows stay in memory and only
  aggregate counts, schema, hashes, and receipts leave the probe
  (see `DATA_RIGHTS.md`). They perform no staging, grading, variant
  interpretation, response/progression inference, eligibility or
  efficacy determination, or treatment recommendation, and their
  aggregate outputs are engineering observations, not clinical
  findings. The IV-01/IV-04 validation files are coordinator
  material and blank templates, not an executed evaluation.

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

The legacy standard-library demo does not bundle third-party application code.
The separate H1 API development image installs pinned Python dependencies and
must retain its [artifact notices](../../apps/api/THIRD_PARTY_NOTICES.md) and
[rights inventory](../../apps/api/dependency-license-inventory.json). This packet
does not clear the complete image or select a project distribution license.
Referenced (not shipped by the legacy demo) items are recorded for transparency:

- Crossref bibliographic metadata: bibliographic metadata is factual and
  not subject to copyright; Crossref-generated data is released as CC0;
  abstracts remain under publisher or author copyright and are excluded
  by the adapter. Verified against Crossref's Metadata Retrieval
  documentation on 2026-11-01 and recorded in
  `docs/CROSSREF_METADATA_BOUNDARY.md` (checked 31 October 2026 there).
- Meta Model API (live investigation mode only): no Meta code or weights
  are shipped. Live mode sends a bounded prompt of fictional case text to
  the Meta API host only when the operator supplies a key and selects
  live mode; terms of that operator-invoked service are UNVERIFIED in
  this packet. Replay mode uses only the bundled fictional fixture.
- GitHub Actions used in CI only (`actions/checkout@v4`,
  `actions/setup-python@v5`, and the SHA-pinned
  `actions/upload-artifact`): license terms UNVERIFIED in this packet;
  see `SBOM.md` for the re-verification step. They are not shipped.

## Precedence

The current project name is Open Intelligence. The earlier name CEVax
refers only to the historical research archive and is not used for this
demo. Research dossiers, diagrams, and vendor comparisons are
complementary inputs, not a new architecture or a replacement baseline.
