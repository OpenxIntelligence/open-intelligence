# Data-rights note — Open Intelligence demo

## All demo data is independently authored fictional content

- Case reports use the structured format `OI-SYNTHETIC-REPORT/1` and are
  authored for this repository. Case identifiers (`CASE-ALPHA`,
  `CASE-BETA`) are fictional labels, not real patients.
- Evidence items use the format `OI-SYNTHETIC-EVIDENCE/1` with the
  declaration `Rights: original-synthetic`. Per `README_IMPLEMENTATION.md`,
  that declaration is not legal clearance for arbitrary user-supplied
  text — it covers only the bundled fictional example.
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

## What the demo never does with data

- No training on user data: there is no model in the demo on `main`.
- No egress of case data: the local server binds to `127.0.0.1`; the only
  external request the code can make is the opt-in DOI-only Crossref
  lookup described above.
- No inference about a real person: the demo never stages, grades,
  interprets variants, infers response or progression, determines trial
  eligibility, or recommends treatment. Anything that looks like a
  conclusion in the demo is human-entered fictional engineering data.

## UNVERIFIED / open items

- The project distribution license is undecided (see `NOTICE.md`). Until
  it is chosen, redistribution terms for the demo itself are UNVERIFIED
  and must not be stated as granted.
- The license terms of the CI-only GitHub Actions are UNVERIFIED (see
  `SBOM.md`). They are not shipped, so this does not affect the demo
  itself.
- No independent legal review of this note has been performed. It is an
  engineering inventory, not legal clearance.
