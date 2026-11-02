# Repository CI data-boundary decision — November 2, 2026
**Source:** founder's uploaded Open Intelligence Expanded Founding Vision & Master Engineering Directive. **Decision:** do not require Sid Sijbrandij's personal medical or biological data, or other identifiable individual case records, to implement, test, demonstrate or evaluate Open Intelligence. Public narratives are *product discovery inputs*, not patient datasets or clinical evidence of treatment benefit.

## What was actually found
In the inspected main repository:
- `.github/workflows/rna-analysis.yml` exposed a manually gated job that invokes `tools/research/rna_expression_probe.py`, whose fixed HTTPS inputs point to Sid-specific processed RNA assets.
- `.github/workflows/single-cell-analysis.yml` exposed a manually gated job invoking `tools/research/single_cell_probe.py`, whose fixed HTTPS inputs include a processed H5AD file in the named person's public bucket.
- `.github/workflows/public-research.yml` exposed a manual catalog intake job on `osteosarc.com`, plus always-run public TCIA/GDC data probes that perform live queries. They were not a prerequisite to the fictional application, but remained active CI paths.
- Regular `synthetic-tests.yml`, `ui-glance.yml` and `crossref-metadata.yml` do not download these particular patient case assets. This audit does not establish an exhaustive external-egress or privacy guarantee across all tools.

These were opt-in or bounded paths, **not proof that the live jobs were executing when inspected**. This fix removes their executable use from the in-repo workflows, including manual execution, rather than relying on an ethics checkbox.

## Implementation
Three existing workflows are edited in place to run only offline original fictional research-unit/contract tests, without installing an H5AD or fetching public case content. A small source guard (`tools/audit_ci_data_boundaries.py`) and regression tests are added to identify direct reintroduction of known live research scripts, named-person endpoints or sync commands. The archived probes remain available for scientific/code review, but are **not approved development inputs**. If future workflows need truly public, non-identifiable data, add independently verified source rights, ethics, provenance, privacy constraints and separate approvals; never silently re-enable these pipelines.

## Trust and limitations
- Fixtures are represented by the existing documentation as independently authored fictional inputs; the current workflow unit tests use those fixtures. This audit does not independently prove provenance for every historical object.
- The guard is a static pattern-based smoke test. It is **not** a network sandbox, runtime data-loss prevention tool, legal review, SBOM, privacy audit, or guarantee against obfuscated data fetches.
- No real clinical consent, HIPAA authorization, legal rights determination, patient investigation, efficacy claim or external patient-data use is implied.
- Historic GitHub artifacts/runs and any former local caches cannot be deleted by changing a future workflow. Their retention/access need an independently scoped review if appropriate.
- Preserve the canonical architecture, existing full first-party health-system goal and separate professional review gates. Do not replace these with a narrow synthetic demo architecture.

## Evidence/acceptance
- Exact branch/commit and GitHub Actions run must be recorded before declaring CI verified.
- Confirm the three edited workflow files have no person-data execution steps, current no-download smoke test passes, and repository's existing independent synthetic UI and ledger tests continue to pass.
- Do not merge without independent review; repository branch protection is not currently confirmed.
