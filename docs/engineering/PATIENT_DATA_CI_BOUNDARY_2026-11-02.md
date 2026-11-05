# Repository CI data-boundary decision — November 2, 2026
**Source:** founder's November 2 clarification and Open Intelligence master directive. **Decision:** do not use Sid Sijbrandij's personal medical or biological data, or other identifiable individual case records, to implement, test, demonstrate or evaluate Open Intelligence. Public narratives are *product discovery inputs*, not patient datasets or clinical evidence of treatment benefit.

## What was actually found
At the initial inspected main commit `52ea683fbe3537b17a05066dceff2ba01f758c5d`:
- `.github/workflows/rna-analysis.yml` exposed a manually gated job that invokes `tools/research/rna_expression_probe.py`, whose fixed HTTPS inputs point to Sid-specific processed RNA assets.
- `.github/workflows/single-cell-analysis.yml` exposed a manually gated job invoking `tools/research/single_cell_probe.py`, whose fixed HTTPS inputs include a processed H5AD file in the named person's public bucket.
- `.github/workflows/public-research.yml` exposed a manual catalog intake job on `osteosarc.com`, plus always-run public TCIA/GDC data probes that perform live queries. They were not a prerequisite to the fictional application, but remained active CI paths.
- Regular `synthetic-tests.yml`, `ui-glance.yml` and `crossref-metadata.yml` do not download these particular patient case assets. This audit does not establish an exhaustive external-egress or privacy guarantee across all tools.

These were opt-in or bounded paths, **not proof that the live jobs were executing when inspected**. This fix removes their executable use from the in-repo workflows, including manual execution, rather than relying on an ethics checkbox.

## Implementation
Three existing workflows are edited in place to run only offline original fictional research-unit/contract tests, without installing an H5AD or fetching public case content. A small source guard (`tools/audit_ci_data_boundaries.py`) and regression tests identify common direct reintroductions of known live research scripts, named-person endpoints or sync commands. The workflows also run for stacked PRs, so a non-main review base does not omit the policy checks.

### Runtime retirement supplement

The founder's explicit clarification supersedes D-08/D-09 and OI-09.15: studying a public narrative does not authorize using the person's medical data. There is no manual opt-in, ethics-note exception, or training/evaluation exception. All current engineering and evaluation patient inputs must be independently authored synthetic cases; de-identifying or relabeling a real case is not equivalent.

PR #123 proposed replacement CI checks; PR #133 added runtime refusals. Concurrent main commit `24519839aa8ac1ea3aff88a956349ba72798a72a` independently disabled the named-person workflow steps and blocked catalog/single-cell acquisition. Its RNA fetch and cached case-analysis paths remained. Because the older stacked PRs overlap and #123 conflicts with this newer main, this integration is based on that current main, preserves its policy and regression tests, and incorporates the useful existing draft work without merging either branch. It closes the remaining local paths in the same research modules:

- `public_case_intake.py`: remove live catalog acquisition; retain offline provenance/uncertainty/input-planning helpers with fictional catalog metadata.
- `rna_expression_probe.py`: remove remote keys, fixed patient sample identifiers, download orchestration and case-specific target selection; retain generic GCT parsing and numerical summaries.
- `single_cell_probe.py`: remove endpoints, file fingerprints, collection dates and case-specific analysis; retain generic matrix decoding and numerical aggregation helpers.
- `data_policy.py`: old public functions and CLI invocations fail before network access, cached-file analysis, directory creation or output writing. Legacy `--live` or output arguments cannot override the policy.
- Synthetic tests no longer reuse the person's bucket labels, sample identifiers or collection dates. Retired case-specific integration tests are removed with the retired function; generic matrix tests remain.

The original case-specific implementations exist only in version history. They must not be restored or executed as development/evaluation inputs. Lawful biomedical publications and non-patient knowledge metadata remain governed by the separate evidence/rights contracts; that is different from individual patient datasets.

### Bounded execution plan and review decisions

1. Inspect main and existing policy PR; preserve useful code and avoid a second CI design.
2. Add failure tests that intercept all outbound transport before exercising legacy entrypoints; demonstrate old flag behavior violates the new boundary.
3. Remove acquisition and person-specific orchestration, preserving only generic offline helpers; verify direct calls, CLI arguments and module imports.
4. Review the CI guard and receipts. Recognize common `python -m`, interpreter-option and multiple-command forms. Record the actual audit outcome; do not write unconditional no-download claims when the audit fails.
5. Reconcile existing requirements, project instructions and roadmap; publish isolated changes for review. No merge, clinical release, history purge or artifact deletion is implied.

Rulings: preserve generic numerical helpers because they are useful with independently authored fixtures; retire the case-specific orchestration because it is not a platform requirement. Preserve historical evidence as history, not execution authority. A static source scan is not a runtime network or data-origin guarantee.

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

Local verification for the supplement: the personal-data-boundary tests failed before the implementation and passed after. The research suite includes two additional current-main refusal tests; final counts and isolated application-regression results are recorded in the PR. Optional local HDF5 checks are skipped where `h5py` is absent; the single-cell workflow retains current main's pinned fixture dependencies to exercise those generic helpers in CI. A skipped test does not qualify a helper. **Nine** CI guard/receipt tests passed, including both independent-review findings. Exact final branch and hosted check results belong in the PR record. Previously generated artifacts/caches are not claimed to have been deleted.
