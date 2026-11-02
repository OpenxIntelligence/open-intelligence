# Open Intelligence — master-directive data boundary repair

Date: 2 November 2026. Base main: `24519839aa8ac1ea3aff88a956349ba72798a72a`.

This is a focused Phase 0 correction under the founder's definitive master directive, not a new product architecture. Preserve the complete first-party platform and the existing patient/source/evidence/authority contracts. The MVP priority remains the connected patient-information and permitted-evidence investigation loop in issue #92; operational integration remains issue #87.

## Binding restriction

Public narratives may inform research into methods and unmet needs. Sid Sijbrandij's personal medical data, dataset catalogs, records, imaging, pathology, molecular data and case-derived fixtures must not be fetched, analyzed, tested, evaluated, benchmarked, trained on or reconstructed. Public availability is not permission under this project mandate. There is no manual opt-in. The same no-unauthorized-data rule applies to other people. Development fixtures must be independently authored.

## Confirmed gap and correction

The existing method-only policy and two anti-acquisition tests were insufficient: `rna_expression_probe.fetch()` had its own live downloader and `run()` invoked it directly. `single_cell_probe.inspect_and_analyze()` also still processed local case data with hard-coded case context. Reproduced using mocked network construction and an invented nonexistent path; no patient asset was fetched or read.

This patch retires all three historical CLI runners and acquisition/case-analysis entrypoints before network or file access, removes dead acquisition recipes, replaces fixed personal-case selectors with reserved fictional namespaces, and removes case-derived labels/dates from the affected fixtures. Generic numerical parser/reducer tests are preserved. A fixture-only inspector requires explicit invented context and an original-fixture marker; those declarations do NOT prove provenance, consent or de-identification.

The ordinary test suite now invokes the no-data boundary. The automatic public-research workflow temporarily runs only offline original-fixture tests; live cohort/trial/runtime experiments require a separately reviewed source/rights contract. Existing permitted DOI metadata functionality is unchanged. The single-cell workflow's unquoted `--only-binary=:all:` command failed YAML parsing; block-scalar syntax fixes it without changing the existing dependency versions.

## Verification at publication

- Test-first boundary: three assertion failures and two unexpected exceptions against the old implementation, four passing controls. After repair nine boundary tests pass.
- Full local offline research suite: **215 tests passed**, including 39 catalog, 23 RNA, 32 single-cell and nine retirement checks. Those focused counts are included in 215.
- Ordinary-suite boundary/CLI wrappers: **2 passed**, reusing some checks. No manual `--live` override writes a file.
- Workflow YAML parsed locally; research compilation passed.
- Full local application attempts exceeded execution time limits. No full-suite or browser pass is claimed here; inspect hosted CI at the final head.
- No new runtime dependency, data access, model call, patient entity, schema, final UI decision, licensing approval or deployment.

## What this does NOT close

This initial audit read the pinned main source archive (162 tracked files), the relevant research scripts/tests/workflows and live metadata for PRs #70/#74/#56/#85/#89/#93. All six referenced PRs were open drafts and unmerged; their descriptions are not independent code or clinical verification. #89 explicitly stops before LIS; #93 is a context/right-check component, not the complete intelligence engine.

All branches, historical artifacts/caches/results, old data-derived reports, credential stores and fixture origin histories have NOT been comprehensively audited. Do not claim that prohibited historical materials or secrets were absent or purged. Do not download patient data to complete that review; inventory metadata and provenance first, and obtain scoped owner/security decisions for quarantine, deletion or credential rotation. No history was rewritten or old evidence deleted by this patch.

The user mandate takes precedence over any earlier conditional personal-case evaluation language. This correction needs ordinary independent review and exact-head CI. It does not authorize clinical use or reduce the broader healthcare product ambition.
