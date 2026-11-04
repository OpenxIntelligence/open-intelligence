# Open Intelligence — disposable NVIDIA catalog import and export

**Date:** 2026-11-04  
**Status:** actual NVIDIA backend catalog code tested in ephemeral GitHub Actions PostgreSQL; synthetic metadata only; draft, unmerged, undeployed.  
**Scope:** third stacked research PR #451, following #448 and #399. Not connected to Open Intelligence's canonical patient, source, evidence, authorization or clinical review owners.

## Result: vendor catalog interoperability

The Open Intelligence allowlisted synthetic schema (3 metadata tables, 22 fields, 3 semantic terms, 22 semantic column attributes, zero source rows) was imported through NVIDIA Auto Ontology's actual `service.import_model`, with `replace=False` and `embed=False`. Its second import was idempotent. The official `service.export_model` returned the same field and term counts without new SQL, foreign-key joins, sample values or custom analyses.

| Verified vendor operation | Result |
| --- | --- |
| Initial import, vendor catalog database/schema | 1 / 1 created |
| Initial import, vendor catalog tables/columns | 3 / 22 created |
| Initial import, terms/column attributes | 3 / 22 created |
| Second import | 0 new entities across all tested categories |
| Vendor catalog SQL attributes / custom analyses | 0 / 0 |
| Vendor catalog foreign keys / join relations | 0 / 0 |
| Vendor export | 3 tables, 22 fields, 3 terms; no unauthorized joins, SQL or samples |
| Source SQLite data rows | 0 |
| Model inference, embedding generation | Not executed |

## Exact runtime evidence

Source under test: `0662b516457bc9ccd48c4598ddc8c8d0434d77e5`. NVIDIA upstream pinned checkout: `cdaf61e1bd0cf3820d11d72b43bb460816aebbd3`.

[GitHub run 41829256401](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41829256401) completed successfully on the exact OI branch head. The hosted job checked out the pinned NVIDIA repository separately, installed its locked server dependencies in a disposable virtual environment, ran NVIDIA Alembic migrations on a disposable `pgvector/pgvector:pg17` PostgreSQL service, executed NVIDIA's importer and scoped exporter, and asserted the values shown above.

Evidence artifact: [13322805570](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41829256401/artifacts/13322805570). GitHub ZIP digest: `sha256:b569da40afea852d8717076f614d9531394f6d91b24a66cd2f5fbf70905bb9ca`. The artifact was **independently downloaded, SHA-256 checked and ZIP-integrity tested**. Its `import-export.json`, `source-receipt.json`, `fixture-receipt.json` and vendor dependency inventory were inspected. Confirmed the exact upstream and first-party commit identities, first/second import creation counts, export, and zero-row guarantees.

The earlier [NVIDIA Pydantic compatibility run 41827821979](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41827821979) on stacked PR #448 passed 13/13 adversarial tests and discovered that the vendor parser silently ignores unrecognized root keys; first-party strict allowlist pre-validation still runs before the real importer.

## Reproduction boundaries

- `tools/semantic_vendor_catalog_probe.py` requires the explicit `OI_DISPOSABLE_VENDOR_IMPORT=ONLY_SYNTHETIC_AND_EMPTY` guard, localhost, the exact synthetic database and user names, and **no nonempty source/LLM credential variables**. It refuses nonempty vendor catalog tables and checks zero source rows before importing. Import/export are wrapped in first-party source allowlist checks; schema changes are not automatically authorized.
- `.github/workflows/semantic-vendor-import.yml` configures a disposable PostgreSQL 17 container and synthetic-only username/password. It checks out NVIDIA at an immutable SHA in a separate directory; its Python dependency closure is logged, **not adopted into Open Intelligence production**.
- During the importer, HTTP(S) proxy variables target a closed local port and no NVIDIA/model/API keys are supplied. This is a limited defense against ordinary proxy-respecting HTTP clients, **not proof of absolute network isolation**. The source data are empty synthetic schema only.
- The model document uses JSON text parseable as YAML, not a direct clinical connector. The vendor importer populates only NVIDIA's disposable catalog. No Open Intelligence production data or clinical database is exposed, queried, merged or migrated.

## Not covered

NVIDIA FastAPI/Next.js frontend/API-token/SSO deployment, a live dashboard or MCP agent connection, model-based ontology discovery, NL-to-SQL, biological interpretations, clinical action, production identity/revocation, PHI handling, patient-world-model extension, multi-center FHIR ingestion and expert oncologic validation **remain untested**.

Upstream image `pgvector/pgvector:pg17` is pinned by version tag but not immutable image digest, and the installed vendor dependency closure is **not** a commercial license or deployment rights approval. Passing a synthetic API/contract/runtime exercise cannot substitute for security, licensing, privacy, clinical, or regulatory review.

## Next controlled milestone

1. Keep PRs #399 → #448 → #451 draft and dependency-linked; confirm review and merge order. Retain first-party patient/source/evidence/review authority.
2. Resolve image/dependency rights and immutable container image digests, then repeat disposable tests with an explicit isolated network policy and approved harness.
3. Independently adjudicate a held-out case set with ambiguous specimen/date/assay mappings, report amendments, unsupported claims and cross-case access negatives; benchmark a real semantic system against OI's deterministic baseline. Record model endpoint, actual generated terms/edges, latency, error/correction burden and cost.
4. Qualify all separate source-/case-level authorization, patient consent, data provenance and clinical review gates before *any* real record or model-assisted patient feature.

**Decision:** external vendor importer compatibility is verified for the synthetic-only case. Production adoption, clinical utility and broader feature readiness are **not** established.
