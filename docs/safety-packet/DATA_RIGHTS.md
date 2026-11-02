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

## UNVERIFIED / open items

- The project distribution license is undecided (see `NOTICE.md`). Until
  it is chosen, redistribution terms for the demo itself are UNVERIFIED
  and must not be stated as granted.
- The license terms of the CI-only GitHub Actions (now three, including
  the SHA-pinned `actions/upload-artifact`) are UNVERIFIED (see
  `SBOM.md`). They are not shipped, so this does not affect the demo
  itself.
- The terms of the operator-invoked Meta Model API service (live
  investigation mode only) are UNVERIFIED in this packet.
- No independent legal review of this note has been performed. It is an
  engineering inventory, not legal clearance.
