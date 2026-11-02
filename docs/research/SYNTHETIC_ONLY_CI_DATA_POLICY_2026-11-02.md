# Patient-story research and CI data boundary — 2026-11-02

**Status: supplemental governance research and historical-scope assessment.** CI implementation owner is [draft PR #123](https://github.com/OpenxIntelligence/open-intelligence/pull/123). This document is not a competing workflow implementation. Applies to Open Intelligence engineering, demonstrations, CI, evaluations and model experiments. Publicly described cancer journeys guide product requirements; individual patients' published medical, genomic, specimen, imaging or case-level datasets are **not required** or implicitly licensed for engineering. This is an amendment to existing governance, not a new architecture.

## Repository baseline reviewed

On `main` at `52ea683fbe3537b17a05066dceff2ba01f758c5d`:

- `.github/workflows/rna-analysis.yml`: manually dispatched `approved_public_case_eval` guard; when manually enabled it executed `tools/research/rna_expression_probe.py`, whose fixed data source refers to the public osteosarcoma case's S3 bucket.
- `.github/workflows/single-cell-analysis.yml`: same manual guard; executed `tools/research/single_cell_probe.py` which retrieved a fixed case-associated catalog/object.
- `.github/workflows/public-research.yml`: PR workflow runs publicly available TCIA/GDC structural probes; optionally a manually enabled `allow_public_case_catalog` input executed `tools/research/public_case_intake.py --live` against the personally linked dataset catalog.
- `.github/workflows/synthetic-tests.yml` and `.github/workflows/ui-glance.yml`: use independently authored fictional clinical inputs; no named public patient source required by their ordinary test steps.

**Important qualification:** Existing RNA/single-cell workflows were manually gated, not automatically fetching person-linked matrices on every PR. The absence of an automatic trigger does **not** meet the new requirement to eliminate that dependency. A published CC0 catalog-level statement does not automatically authorize reuse of every individual's clinical or genomic material, model training, biomedical interpretation, or rights owned by other parties.

## Safety implementation already proposed in PR #123

| Prior workflow | Replacement | Patient-case data downloads |
|---|---|---|
| `rna-analysis.yml` | Run the original fictional parser/math unit tests and source-only receipt | Disabled; no source download/analysis command |
| `single-cell-analysis.yml` | Install isolated test libraries, run original fictional HDF5 fixtures, write dependency/source-only receipt | Disabled; no source HDF5 fetch or cell-level analysis command |
| `public-research.yml` | Run fictional methods/adapter tests and source hashes only | Removed live public catalog, public clinical-case and specimen network probes from CI |
| `test_ci_subject_data_boundary.py` | Enforce that every workflow excludes the known live acquisition entrypoints, former opt-in inputs and named catalog location | Fails on regression |

[PR #123](https://github.com/OpenxIntelligence/open-intelligence/pull/123) owns the actual workflow replacements and executable linter; this research PR provides no conflicting edits to those workflow files. The research source files are retained **for reference only**, including historical parser/scientific methods and separately authored unit tests; they must not be wired back into CI or run with person-linked source files without separate lawful basis, ethically justified purpose, appropriate consent/rights review, governance and current implementation approval. No historical data were downloaded, analyzed, trained on or removed by this change.

## Historical artifact remediation — open, not silently certified

[Issue #122](https://github.com/OpenxIntelligence/open-intelligence/issues/122) is the existing owner for enumerating old GitHub Actions runs, artifacts, logs, caches and any previous exposure. **This branch does not delete runs, mutate historical logs/artifacts, erase published content, or certify that historical data have been expunged.** Record affected run IDs, upload artifact and retention metadata, authorized deletion operations, owner decision and confirmation receipts. Do not assume an aggregate-only result proves that every previous log/cache is free of sensitive data. Preserve audit evidence without retaining unauthorized patient information.

## Invariant

1. Never make named individuals' health data a build-time dependency, a fixture, a benchmark target, or a requirement to run the product.
2. Do not infer legal rights from public discoverability, broad CC0 labels or sharing of a repository link; evaluate per-file provenance and intended use.
3. Use independent synthetic patient/source/specimen/encounter fixtures with fictional identifiers. Identity and specimen collisions, amendments, refusals and negative outcomes belong in the tests.
4. Before any non-synthetic clinical research, require per-person/subject lawful basis and permissions; distinguish clinical care use, research, AI model processing, redistribution and external collaboration. Do not silently treat approval for one purpose as approval for another.
5. The platform's user-controlled patient data must be protected by future validated identity, consent, organizational policy, audit, PHI security and clinical controls before any real patient use.

**Verification gates:** exact-head CI on this PR; existing [#122](https://github.com/OpenxIntelligence/open-intelligence/issues/122) historical artifact review remains open; model/dataset/source licensing and downstream clinical regulatory validation are separate. [PR #123](https://github.com/OpenxIntelligence/open-intelligence/pull/123) is the safety implementation candidate; this complementary research document is a governance cross-reference, not approval or a claim that it has merged.
