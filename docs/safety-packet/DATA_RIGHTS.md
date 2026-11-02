# Data-rights note — Open Intelligence demo

For the current tree on branch `oi/safety-packet` (current `main`
merged in; refreshed 2026-11-02).

## All demo data is independently authored fictional content

- Case reports use the structured format `OI-SYNTHETIC-REPORT/1` and are
  authored for this repository. Case identifiers (`CASE-ALPHA`,
  `CASE-BETA`, `CASE-OI019-A`, `CASE-OI019-B`, `CASE-OI017`) are fictional
  labels, not real patients.
- Evidence items use the format `OI-SYNTHETIC-EVIDENCE/1` with the
  declaration `Rights: original-synthetic`. Per `README_IMPLEMENTATION.md`,
  that declaration is not legal clearance for arbitrary user-supplied
  text — it covers only the bundled fictional examples.
- Discovery records use the format `OI-SYNTHETIC-DISCOVERY/1` with the
  declaration `Rights: original-synthetic`, parsed strictly by
  `src/open_intelligence/discovery.py`. Unknown fields — including any
  `Abstract` field — are rejected, so copyrighted article text cannot
  enter through this path. Trial listings carry a fixed
  `Status: not-verified`; a listing never confirms recruitment
  availability. Literature DOIs are identifiers only; no lookup is
  performed by the discovery path.
- The recorded investigation fixture
  (`examples/synthetic/demo-investigation.json`) is human-authored
  demonstration output for offline replay. Its `FIRST_SOURCE` /
  `FIRST_ASSESSMENT` citation placeholders are replaced server-side with
  real current ids from the case and then validated exactly like live
  model output; replay output is labeled `mode=replay`,
  `model=recorded-replay`, never presented as a live run.
- The OI-019 readme (`examples/synthetic/oi019-readme.md`) and the
  patient-access expectations file
  (`examples/patient-access/EXPECTED_RESULTS.json`) are independently
  authored demonstration notes. The latter states its own provenance
  ("Independently authored synthetic fixtures; no real patient data, no
  PHI") and limits itself to synthetic contract evidence.
- No real patient data, no personal health information, no genomic data,
  and no clinical document of any real person appears anywhere in the
  repository, its tests, or its fixtures.
- The runtime SQLite database is created locally when the demo server is
  seeded. It contains only the fictional seed data and user-entered
  fictional content from the local session. It is not shipped.

## Crossref: metadata only, abstracts excluded

- The adapter in `tools/crossref_metadata.py` projects only DOI, title,
  journal, year, type, public author names, and a constructed canonical
  DOI URL, with retrieval time and a rights-policy reference.
- Provider abstracts, article text, clinical claims, unreviewed links,
  license claims, and unknown fields are dropped by the adapter.
- Rights basis (verified against Crossref's Metadata Retrieval
  documentation on 2026-11-01; also recorded in
  `docs/CROSSREF_METADATA_BOUNDARY.md`): bibliographic metadata is
  factual and not subject to copyright; Crossref-generated data is CC0;
  abstracts remain under publisher or author copyright.
- The bundled fixture (`examples/synthetic/crossref-metadata-fixture.json`)
  uses the fictional DOI `10.5555/oi-synthetic-001` and a fictional
  journal title. It is not a real article citation.
- Live lookup is disabled by default, operator-invoked only, DOI-only, and
  sends no patient identifier, genomic profile, free-text query, or
  attachment to any external host.

## Bounded model path: fictional text only, replay by default

- `src/open_intelligence/investigation.py` is the only module that can
  reach a model (see `SBOM.md` and `docs/META_MODEL_API.md`). There is no
  free-text prompt from the browser: the prompt is a fixed template plus
  the fictional case's own assertions and evidence assessments.
- Live mode sends only the fictional case id, the question text, and
  source/assessment statements to the fixed Meta API host, and only when
  the operator supplies `META_API_KEY` and selects live mode. No
  patient-like fields, no real data, and no credentials beyond the
  operator's own key are in the payload. The key itself is used
  server-side only and is never stored, logged, committed, or sent to
  the browser.
- Replay mode sends nothing anywhere: it serves the bundled fictional
  replay fixture through the same validation and language guard.
- Stored model output is always a pending hypothesis (`kind=hypothesis`,
  `review_state=pending`), never a validated conclusion or a
  recommendation. Claims that fail citation validation or the language
  guard are dropped and recorded as dropped, never silently repaired.

## Rights gate for external evidence sources

- `src/open_intelligence/rights.py` is a pure fail-closed gate: a
  permission counts only when explicitly recorded as `allowed` for that
  content item and use on a rights record that is neither revoked nor
  superseded. `unknown` and `denied` both mean no; a missing entry means
  `unknown`, which means no. Content modes (`full`, `metadata_only`,
  `citation_only`) follow from the gate.
- The gate never verifies that a rights record is legally true; it only
  enforces what the record says. Nothing in this slice fetches external
  content (per `docs/RIGHTS_BROKER.md`).

## What the demo never does with data

- No training on user data: no model weights are shipped, and the only
  model path is the bounded investigation call above, which runs in
  offline replay unless the operator explicitly selects live mode.
- No egress of case data by default: the local server binds to `127.0.0.1`;
  the only external requests the code can make are the two opt-in paths
  above (DOI-only Crossref lookup; bounded Meta investigation POST).
- No inference about a real person: the demo never stages, grades,
  interprets variants, infers response or progression, determines trial
  eligibility or efficacy, infers clinical deadlines, or recommends
  treatment. Anything that looks like a conclusion in the demo is
  human-entered fictional engineering data or a pending hypothesis for
  review.

## IV-01 practice fixtures (fictional, coordinator material)

- `validation/iv01/cases.json` holds two fictional cases
  (`CASE-EVAL-A`, `CASE-EVAL-B`), ten sources in the same
  `OI-SYNTHETIC-REPORT/1` / `OI-SYNTHETIC-EVIDENCE/1` formats with
  `Rights: original-synthetic` on the evidence items, eleven receipt
  events, and three cutoffs. It declares `synthetic: true` and
  `status: engineering-practice-only`. Coordinator/development
  material only: participants receive a single cutoff-specific
  `inputs.json`, never the manifest, tests, or key.
- `validation/iv01/coordinator_key.json` is a same-author designer
  reference (`status:
  designer-reference-not-independent-ground-truth`,
  `participant_distribution: DO NOT INCLUDE`), not independent
  ground truth and not a held-out set. A result on this public
  practice set is not blinded or independent clinical validation.
- `validation/iv01/protocol.json` (`status: not_activated`, all
  thresholds null) and `validation/iv01/results_template.csv`
  (header only) record no study, no reviewers, and no outcomes.
- The `tools/research/` unit-test fixtures (`FICTIONAL-*`,
  `SYN-*`) and the `CASE-JSON` parser fixtures in
  `tests/test_evaluation_packet_json_boundary.py` are hand-derived
  fictional cases asserting parser/calculation behavior only. No
  patient records, clinical reference answers, or real-case values
  are embedded or asserted.

## Historical live research probes — archived, not CI inputs after data-boundary change

- **New policy, 2 November 2026:** Named-person clinical, RNA, H5AD or
  public-case catalog data must not be required or fetched by product
  engineering, CI, demo, model training or evaluation. The existing
  catalog, RNA and single-cell modules now retain only generic offline
  helpers and refusal entrypoints in this draft; person-specific retrieval,
  sample constants and cached case analysis have been retired. Their former
  implementations remain in version history, without permission to execute.
  The research workflows run only fictional/offline regression tests.
  Main `24519839` already disabled named-person CI steps and blocked catalog
  and single-cell acquisition. Draft PR #137 reconciles the remaining
  runtime and workflow cleanup from #123/#133 onto that main; it is unmerged.
- Historical runs may have retrieved personal-case or public-cohort
  material, even if they published aggregate receipts instead of raw
  rows. We have not proved previous artifacts/caches absent, erased or
  appropriately reviewed; no past live-data use is implied to be
  authorized by this document. Avoid extrapolating clinical efficacy
  from historical exploratory calculations.
- The following references document *old probe code*, not a current
  right or requirement to ingest these sources:
- Per-source basis, exactly as asserted in the probe headers (terms
  themselves UNVERIFIED in this packet — see below):
  - TCIA attachments (fixed CSV/ZIP URLs): Bakr et al.,
    doi:10.7937/K9/TCIA.2017.7hs46erv (CC BY 3.0),
    doi:10.1038/sdata.2018.202; Clark et al.
    doi:10.1007/s10278-013-9622-7.
  - GDC open/public TCGA case metadata (LUAD, BRCA, LAML): NCI GDC
    data analysis policies
    (`https://gdc.cancer.gov/analyze-data/data-analysis-policies`).
  - Pinned NCI-GDC dictionary terms file (commit `88d66b0`) and
    FHIR R4 MedicationStatement/Administration as a meaning
    reference for the semantic audit.
  - Fixed public osteosarc catalog
    (`osteosarc.com/data/catalog/datasets.json`) and S3 bucket
    listing/processed assets; the in-repo test fixture asserts a
    `CC0-1.0` catalog license.
  - ClinicalTrials.gov/NLM registry records: NLM
    (`https://www.nlm.nih.gov/databases/download.html`) and
    ClinicalTrials.gov
    (`https://clinicaltrials.gov/about-site/terms-conditions`)
    terms; no endorsement implied.
  - One hash-verified pure `parse_criteria` function characterized
    from ncbi-nlp/TrialGPT (commit
    `1b3242cd50c153a9c324661d4a0bd94fc68a4226`, US Government Work
    notice; credit Jin et al., Nature Communications 2024,
    doi:10.1038/s41467-024-53081-z). Only that function is
    executed; no upstream module is imported.
- `tools/research/runtime_probe.py` uses no network and no model
  API: it is a process-boundary experiment on original fictional
  state, with negative controls.
- `tools/evaluation_packet.py` and `tools/evaluation_preflight.py`
  perform no network I/O at all.

## Research-only dependencies (not application dependencies)

- `tools/research/requirements.lock` records exact third-party pins
  observed in research run 41294219202 (langchain/langgraph stack
  and others). It is installed into an isolated `/tmp/oi-research-env`
  venv in historical `public-research` CI runs. The replacement CI in
  draft PR #123 no longer installs this research lock or executes the
  network-dependent research runtime. The file itself is research-only:
  not an application dependency decision or security clearance.
  No package license in that lock has been reviewed in this packet.
- The historical `single-cell-analysis` CI job installed
  `numpy==2.3.5` and `h5py==3.15.1` for exploratory research.
  Draft PR #123 replaces live analysis with fictional unit tests and
  does not install this research environment. These are not
  selected application dependencies. Their licenses remain UNVERIFIED
  in this packet.
- The demo itself remains Python standard library only, as recorded
  in `SBOM.md`; no new dependency is shipped with the demo.

## UNVERIFIED / open items

- The project distribution license is undecided (see `NOTICE.md`). Until
  it is chosen, redistribution terms for the demo itself are UNVERIFIED
  and must not be stated as granted.
- The license terms of historical and current CI-only GitHub Actions
  (including SHA-pinned `actions/upload-artifact`) are UNVERIFIED
  (see `SBOM.md`). They are not shipped with the local demo.
- The terms of the operator-invoked Meta Model API service (live
  investigation mode only) are UNVERIFIED in this packet.
- The public-source terms asserted in the research-probe headers
  (TCIA, GDC, osteosarc catalog/S3 assets, NLM/ClinicalTrials.gov,
  TrialGPT characterization) are recorded as in-repo assertions
  only and are UNVERIFIED in this packet, as are the licenses of
  every package in `tools/research/requirements.lock` and of the
  historical research-only `numpy`/`h5py` install. None of these is
  shipped with the demo; the updated workflows do not execute those
  live-data probes.
- No independent legal review of this note has been performed. It is an
  engineering inventory, not legal clearance.


## Historical 2026-11-02 proposed CI policy enforcement receipt

- Draft PR [#123](https://github.com/OpenxIntelligence/open-intelligence/pull/123)
  removes named-person and other public patient-data fetches from the
  three research workflows, replacing them with independently authored
  fictional tests and an explicit no-download source guard.
- Current feature-branch head before this documentation correction:
  `5839a5b98b15e61c14c42dbe810d711434773e09`. Six hosted workflows
  passed on that exact head (research, RNA, single-cell, synthetic ledger,
  UI glance, Crossref). This historical record predates the newer main
  prohibition and the consolidated runtime-removal draft #137; it must not
  be read as permission to run the retired scripts.
- The scanner matches known direct CI entrypoints; it cannot provide a
  network sandbox, identify all PHI, or prove exact permissions. A release
  still requires security, source rights and professional review.
