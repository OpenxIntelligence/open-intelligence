# Crossref bibliographic metadata boundary

This is **not** an oncology evidence interpretation service. It is a narrowly scoped first external-data adapter, independent of the unsettled patient-data PRs.

## Rights and sources (checked 31 October 2026)

- Crossref's [Metadata Retrieval](https://www.crossref.org/documentation/retrieve-metadata/) states bibliographic metadata is generally factual and reusable; Crossref-generated material is CC0. **Publisher-supplied abstracts are separately copyrighted.**
- Crossref's [REST API access policy](https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/) allows public access without login, encourages a contact email/identified User-Agent, caching and respecting published rate/concurrency limits.
- This prototype only projects the DOI, title, journal, year, type, public author names and a **constructed** canonical DOI URL with retrieval time and the rights-policy reference. Provider abstracts, article text, clinical claims, unreviewed links, license claims and unknown fields are dropped. No biomedical knowledge is assumed merely from a citation.

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
