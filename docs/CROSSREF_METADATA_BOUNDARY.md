# Crossref bibliographic metadata boundary

This is **not** an oncology evidence interpretation service. It is a narrowly scoped first external-data adapter, independent of the unsettled patient-data PRs.

## Rights and sources (rechecked 3 November 2026)

- Crossref's [Metadata Retrieval](https://www.crossref.org/documentation/retrieve-metadata/) states bibliographic metadata is generally factual and reusable; Crossref-generated material is CC0. **Publisher-supplied abstracts are separately copyrighted.**
- Crossref's [REST API access policy](https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/) allows public access without login, encourages a contact email/identified User-Agent, caching and respecting published rate/concurrency limits.
- This prototype only projects the DOI, title, journal, year, type, public author names and a **constructed** canonical DOI URL with retrieval time and the rights-policy reference. Provider abstracts, article text, clinical claims, unreviewed links, license claims and unknown fields are dropped. No biomedical knowledge is assumed merely from a citation.

## Provenance and parser contract

The supplied retrieval time is an exact, timezone-qualified receipt field. It
must contain a real calendar date, `T`, hour/minute/second, optional 1–6 fractional
digits, and `Z` or an explicit numeric offset. Invalid offsets, naive times,
control characters and the unknown-offset marker `-00:00` are rejected. Valid
explicit values retain their original spelling and precision. Only `None`
(omission) generates the current UTC time; an empty value never becomes a new
receipt. This narrow format excludes leap seconds and higher precision rather
than guessing how to normalize them. Validation does not authenticate an
operator-supplied time or establish that content was fresh at that instant.

Live responses and explicit CLI `--fixture` files share a strict JSON decoder:
duplicate object members at any depth and nonstandard numeric constants are
rejected before projection. Invalid parser input produces a fixed error without
echoing upstream values. Live responses must declare the `application/json`
media type (case-insensitive; parameters permitted), not merely contain that
substring. The fixed repository fixture served by `/api/bibliography/example`
retains its existing fixture-loading path; it is not an arbitrary upload API.

These checks preserve the fixed endpoint, redirect refusal, 256 KiB response
limit, 8-second timeout and DOI-only egress. They do not activate real metadata
inside H1's intentionally fictional PostgreSQL catalog.

## Run (Python 3.11+, standard library only)

Offline fixture (no network):
```bash
python -m tools.crossref_metadata 10.5555/oi-synthetic-001 --fixture examples/synthetic/crossref-metadata-fixture.json
```

Explicit operator-invoked single DOI lookup:
```bash
python -m tools.crossref_metadata 10.1038/s41586-020-2649-2 --live
```

The live mode sends **only the supplied public DOI** to the fixed Crossref HTTPS host. It does not accept free-text search queries, patient identifiers, genomic profiles or attachments. It rejects redirects, bounds response size and timeout, and does not automatically retry. The optional `--contact` parameter identifies an operator to Crossref's polite pool. It is not enabled by default.

Run tests:
```bash
python -m unittest discover -s tests -p 'test_crossref_metadata.py' -v
```

## Explicit limits

- Synthetic fixture DOI is fictional and is not a real article citation.
- No automatic content-rights clearance, article or abstract ingestion, clinical trial matching, evidence-grade estimation, treatment ranking, patient-data access, model training, or PHI egress.
- Bibliographic metadata is useful for discovery and attribution but **cannot support a clinical claim without independently retrieving and evaluating the source under appropriate rights**.
- The repository distribution license is undecided; a successful technical check is not product release approval.

## 3 November 2026 verification and continuation

The original six Crossref tests passed before changes. Added negative tests
reproduced 25 failing subcases across timestamp, duplicate-key, numeric-constant,
media-type and CLI rejection checks. After repair, all 13 Crossref tests and
the complete 244-test unit/HTTP suite passed on Python 3.12.14. The real loopback
HTTP test uses a controlled fictional upstream response, verifies a safe 422
for duplicate DOI fields, then a successful lookup without leaking patient
request fields or excluded content. That test is not a live provider test.

A separate explicit live lookup of `10.1038/s41586-020-2649-2` succeeded at
`2026-11-03T15:29:15+00:00`: *Array programming with NumPy*, bibliography only.
No patient information was sent, no full text was fetched, and no raw response
was retained. This single request is not an availability/performance evaluation
or evidence-appraisal result. Local browser execution was attempted and blocked
by the absence of Chrome/Chromium; hosted results are recorded separately.

See the [bounded mandate audit and next implementation task](research/MASTER_MANDATE_AUDIT_2026-11-03.md).
