# Repository CI data-boundary decision — November 2, 2026

**Historical findings baseline:** the original PR #123 findings below were written against base `52ea683fbe3537b17a05066dceff2ba01f758c5d`. They describe that proposal's context, not current-main verification. The current-main reconciliation is recorded separately below.

**Source:** founder's uploaded Open Intelligence Expanded Founding Vision & Master Engineering Directive. **Decision:** do not require Sid Sijbrandij's personal medical or biological data, or other identifiable individual case records, to implement, test, demonstrate or evaluate Open Intelligence. Public narratives are *product discovery inputs*, not patient datasets or clinical evidence of treatment benefit.

## Original reported findings (historical)

The original review reported:
- `.github/workflows/rna-analysis.yml` exposed a manually gated job that invokes `tools/research/rna_expression_probe.py`, whose fixed HTTPS inputs point to Sid-specific processed RNA assets.
- `.github/workflows/single-cell-analysis.yml` exposed a manually gated job invoking `tools/research/single_cell_probe.py`, whose fixed HTTPS inputs include a processed H5AD file in the named person's public bucket.
- `.github/workflows/public-research.yml` exposed a manual catalog intake job on `osteosarc.com`, plus always-run public TCIA/GDC data probes that perform live queries. They were not a prerequisite to the fictional application, but remained active CI paths.
- Regular `synthetic-tests.yml`, `ui-glance.yml` and `crossref-metadata.yml` do not download these particular patient case assets. This audit does not establish an exhaustive external-egress or privacy guarantee across all tools.

These were opt-in or bounded paths, **not proof that the live jobs were executing when inspected**. This fix removes their executable use from the in-repo workflows, including manual execution, rather than relying on an ethics checkbox.

## Original proposed implementation (historical)

Three existing workflows are edited in place to run only offline original fictional research-unit/contract tests, without installing an H5AD or fetching public case content. A small source guard (`tools/audit_ci_data_boundaries.py`) and regression tests are added to identify direct reintroduction of known live research scripts, named-person endpoints or sync commands. The archived probes remain available for scientific/code review, but are **not approved development inputs**. If future workflows need truly public, non-identifiable data, add independently verified source rights, ethics, provenance, privacy constraints and separate approvals; never silently re-enable these pipelines.

## Current-main reconciliation — 2026-11-02

The isolated safety worktree starts at exact main `24519839aa8ac1ea3aff88a956349ba72798a72a`, with only the seven changed files from PR #123 head `3a651e6b1c329ff7507863d4cfc3f4e6b646cf98` overlaid before the bounded reconciliation. Main's existing immediate catalog and single-cell acquisition denials are preserved. Additional immediate denials retire RNA, TCIA and GDC patient-cohort acquisition. The CI guard also recognizes ordinary `python -m` forms of those retired modules. Publication metadata and trial-registry lookup are outside the patient-dataset retirement scope.

Review found that the previous HDF5 fixture and its analyzer still shared archival case labels, dates and selected targets. The RNA path test used an archival sample ID; catalog fixtures reused real origins; CSV fixtures used TCIA-style identifiers. A synthetic label alone had not established independent authorship. Those specific fixtures are corrected in this reconciliation:

- A new five-cell, four-feature HDF5 matrix uses invented `SYN-SAMPLE-A/B`, `GENE_*` symbols, two arbitrary 2001 dates, and hand-calculated capture summaries. The generic helper requires explicit sample/date, target/control, capture-type and annotation-column configuration. The former case-configured inspection entrypoint is retired before file access.
- RNA path validation is exercised under an injected synthetic sample allowlist. Catalog parser tests inject reserved `.invalid` origins and an invented bucket. CSV profiling uses newly authored nonclinical rows.
- The pinned `numpy==2.3.5` and `h5py==3.15.1` fixture-only CI install is retained using a YAML block, with an import/version prerequisite check so HDF5 coverage cannot silently skip.

The local guarded research run passed **219 tests with zero skips**, including all 24 HDF5 tests; eight CI-boundary tests passed. No network/process attempts were recorded in the final guarded run. These are local checks, not a hosted CI or merge receipt. Exact commands and limits are in `DATA_BOUNDARY_RECONCILIATION_VERIFICATION.md`.

## Trust and limitations

- The identified fixtures were corrected and the current research tests/examples were scanned for known archival identifiers, dates and origins. This bounded review does not prove the provenance of every historical object or every repository fixture. The blocked endpoint literal in the CI-denial regression remains intentionally present; it is never fetched.
- The guard is a static pattern-based smoke test. It is **not** a network sandbox, runtime data-loss prevention tool, legal review, SBOM, privacy audit, or guarantee against obfuscated data fetches.
- No real clinical consent, HIPAA authorization, legal rights determination, patient investigation, efficacy claim or external patient-data use is implied.
- Historic GitHub artifacts/runs and any former local caches cannot be deleted by changing a future workflow. Their retention/access need an independently scoped review if appropriate.
- Preserve the canonical architecture, existing full first-party health-system goal and separate professional review gates. Do not replace these with a narrow synthetic demo architecture.

## Evidence/acceptance
- Exact branch/commit and GitHub Actions run must be recorded before declaring CI verified.
- Confirm the three edited workflow files have no person-data execution steps, current no-download smoke test passes, and repository's existing independent synthetic UI and ledger tests continue to pass.
- Do not merge without independent review; repository branch protection is not currently confirmed.
