# Safety data-boundary reconciliation verification

Date: 2026-11-02. This is local engineering evidence, not a merged or deployed change.

## Source and scope

The worktree starts at exact main `24519839aa8ac1ea3aff88a956349ba72798a72a` on branch `safety/reconcile-data-boundary-20261102`. Only the seven changed files from existing PR #123 head `3a651e6b1c329ff7507863d4cfc3f4e6b646cf98` were overlaid: the three research workflows, their boundary checker and tests, the existing CI-boundary note, and the data-rights safety packet. Acquisition modules were retained from current main, preserving its newer catalog/single-cell denials and tests.

The subsequent bounded extension disables the remaining RNA fetch and four TCIA/GDC patient-cohort entrypoints with immediate `PermissionError`. Synthetic numerical, projection and semantic reducers remain usable. Public trial-registry code and the shared publication/metadata fetch helper are unchanged. The static checker additionally detects ordinary `python -m` invocations for the retired patient-data modules. Diff reconciliation also retains main's dedicated retired-data test path filter and execution step in both RNA and single-cell workflows, alongside the new static checker.

## Fixture provenance correction

Review found concrete violations of the independent-fixture requirement: the HDF5 fixture reused archival case sample labels, dates and selected targets through case-specific analyzer globals; an RNA path test used an archival sample ID; catalog payloads reused real origins; and CSV tests used TCIA-style identifiers. Earlier fictional labels and a passing standard-library suite did not establish independent authorship. Those findings are corrected here without accessing any original data:

- The new HDF5 fixture contains five invented cells, `SYN-SAMPLE-A/B`, dates `2001-02-03` and `2001-03-04`, and four invented `GENE_*` symbols. Its literal matrix is `[[1,0,4,0],[0,3,0,0],[5,6,2,0],[0,0,7,0],[8,0,1,0]]`. Hand-calculated capture sums are `(6,9,6,0)` and `(8,0,8,0)`; positive-cell counts are `(2,2,2,0)` and `(1,0,2,0)`. Tests check means, fractions, denominators and absent-versus-measured-zero behavior.
- `analyze_synthetic_h5ad` requires explicit sample/date, target/control, capture-type and annotation-column configuration, with no archival case defaults. The old case-configured `inspect_and_analyze` now denies before file access. The generic helper retains count-versus-X detection checks, exact/missing symbol handling, annotation caveats, separate captures, bounded numeric validation and HDF5 indirect-storage rejection. It establishes no patient count, malignancy, clinical recommendation or statistical significance.
- RNA path tests temporarily inject synthetic sample names. Catalog parser tests inject reserved `.invalid` origins and an invented bucket/region; their payload dates, identifiers and paths are authored test values. CSV examples were newly authored with nonclinical values and `SYN-PROFILE-*` IDs.
- A text scan of all current research tests and `examples/` checked the known archival sample IDs, dates, target symbols, origins and TCIA-style IDs. The only remaining match is an intentionally blocked endpoint literal in the CI-denial regression, never fetched. This bounded scan does not establish provenance for every historical object or repository fixture.

No patient records, genomic datasets, imaging datasets, Actions logs or historical artifact contents were accessed. No remote branch, issue or external document was changed by this verification.

## Executed checks

Tests ran with `python -S` through an external review harness that registered an audit hook before dependency/repository imports or test discovery. The hook denies URL requests, socket connection/address resolution and subprocess/shell effects, and records attempts even if tests catch the exception. Negative acquisition tests install mocked network constructors before invoking the retired functions.

For the final HDF5-enabled run, the parent provided isolated scratch `h5py==3.15.1` in `/tmp/oi-test-deps` and the existing runtime supplied `numpy==2.3.5`. No application dependency was installed. The initial enabled run was correctly blocked during h5py import because Python 3.12 lazily invokes `uname -p` to populate `platform.uname().processor`: 24 HDF5 setups errored and 24 process attempts were recorded. Inspection traced this to the local standard-library implementation. The harness now supplies that informational cached processor field from `os.uname().machine`, a local kernel call. All network/process denial rules remain unchanged and active before imports. The final run asserts the exact dependency versions and records zero attempts.

| Check | Observed result |
| --- | --- |
| Earlier pinned-main baseline, before fixture correction | 206 discovered; 188 passed; 18 optional HDF5 cases skipped; not HDF5 acceptance evidence |
| Corrected research suite with pinned fixture dependencies | 219 passed; all 24 HDF5 cases executed; zero skips/failures/errors |
| CI-boundary regression suite | 8 passed; zero failures/errors |
| Network/process effect attempts in final guarded runs | Zero; the earlier import failure is disclosed above |
| Workflow syntax | Six YAML files parsed; 28 run blocks passed `bash -n` |
| Python syntax | Research modules and boundary checker/tests parsed |
| Preservation checks | Main `fetch_catalog` and `acquire` function ASTs unchanged; trial registry module byte-identical; shared metadata fetch and profile reducer ASTs unchanged |

The earlier negative-test run reproduced the missing RNA/cohort denials and module-invocation detection before the fixes. One obsolete successful-live-GDC-wrapper test was replaced with a mocked-transport check that public metadata fetch still returns exact bytes and the expected digest.

Commands executed from this review:

```sh
OI_REQUIRE_HDF5=1 \
PYTHONPATH=/tmp/oi-test-deps:/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages \
PYTHONDONTWRITEBYTECODE=1 \
python -S tools/verify_offline_research.py . tools/research 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 python -S tools/verify_offline_research.py . tests test_ci_data_boundaries.py
```

The exact guard harness is now versioned as `tools/verify_offline_research.py` and invoked by all three research workflows before repository test discovery. Detailed local logs remain in `/tmp/oi-safety-review`, with final research output in `independent-fixtures-research-green.log`. Harness SHA-256 is `ca411039a5bc191e5162eb01e7f13e3527b46f6d7691edae1982d2e271465d41`. The harness is test-only defense in depth, not an installed application dependency or an arbitrary-code security sandbox. Its new hosted execution must still be verified on the published commit. Single-cell CI retains pinned fixture dependencies in a YAML block and asserts imports/versions before running tests, preventing silent HDF5 dependency skips. Fresh hosted checks must run after an authorized commit/update. No new commit or hosted result is claimed here.

## Remaining limits

The full application/browser suites were outside this bounded review. The workflow checker remains a static smoke test, not an arbitrary-code network sandbox, DLP system or blanket data-rights clearance. The generic local analyzer does not authenticate the provenance of caller-provided files; only independently authored synthetic input is authorized for this development task.

**Issue #122 remains open.** Neither this code nor successful future CI proves that historical Actions runs, logs, artifacts, caches or retained downloads contain no patient information. No historical artifact inspection, deletion, purge or retention clearance occurred. Historical unreachable acquisition code remains below the explicit denials for traceability.
