# H1 laboratory workspace and manual-task convergence

Status: synthetic-only integration candidate. No merge, deployment, production authorization or clinical qualification. Tracks existing #428 / #425 and #442; no new canonical data owner.

## Patient-facing purpose

Put the existing explicit FHIR laboratory import, typed Journey results, current/historical original inspection and keyboard reading on the same source tree as the existing laboratory/manual-task migration convergence. Laboratory input remains source-reported and unreviewed. Reading a preview does not import a file. Importing a laboratory report does not create a question, task or clinical conclusion.

## Frozen source and ownership

| Input | Exact commit | Role |
| --- | --- | --- |
| #469 | 8ff6e9e5a0389a1142ca479a6705c599cbda88e7 | Common laboratory source baseline |
| #471 | 95bf73d23172c15bcf326183494030e6597ed449 | Primary parent; canonical backend, manual-task dependencies and migration convergence |
| #473 | 9ea4560fc03be567e8383f9b145fc8eaef0cd140 | Second parent; laboratory UI and keyboard reading, includes #472 |
| #472 | 2ccdfad6aeba3cb3378c4648f4dba3df604cc554 | Laboratory workspace inherited through #473 |

Three-way inspection against #469 found 23 paths changed by #471 and 20 by #473. Only `docs/EXECUTION_BACKLOG.csv` overlaps. Its changes reconcile by row/field without conflicting field edits; both existing notes are retained. Nineteen nonoverlapping donor paths are copied byte-for-byte from #473; their Git blob identities are in `H1_LAB_WORKSPACE_SOURCE_REUSE.json`.

All application backend, published migrations and shared Python source retain #471 bytes. The existing RegistrySession remains the only client session owner. Both published 0016 migrations and the no-DDL `0017_lab_manual_convergence` join remain unchanged. The only workflow change adds `apps/web/tests/laboratory-manual-convergence.test.mjs` to the API workflow's path filter: no job, permission, old trigger, assertion or recovery stage is removed or weakened.

The new commit is intended to record both source parents without merging either PR or changing their branches. Main is not a target of this draft.

## Artifact/source checks

Downloaded source artifacts:

| Artifact | SHA-256 |
| --- | --- |
| #469 / 13349748428 | a3356bdd8f19f904928de90e220a691e9c650fddfc84b0f40c87a215033ef026 |
| #471 / 13361755324 | 93bfbc26f2e24d7d5d2c20a189f9b172ead9583b2155e3c3eea784c717b062be |
| #473 / 13368518149 | d6fa1e0f161738c93955d886033fab0bccf2ea0cf4094265627a93a844d30af8 |

Each downloaded digest and commit marker matches its recorded source. Reconstructing all 656 #471 and 661 #473 source paths as ordinary Git files yields the exact published trees `5d68ccd807ee0d919aaa3d926bef00854f59a49c` and `91a9a7df714cc9e6a28e12bcc88ea5cb3fb9e293`. This checks path, blob and mode identities; the ZIP itself does not encode executable modes or Git ancestry. No complete source audit is implied.

## New regression contract

`apps/web/tests/laboratory-manual-convergence.test.mjs` exercises the actual RegistrySession with only HTTP transport substituted by independently fictional responses:

1. Exact laboratory JSON/receipt and a fresh existing manual-dependent task coexist. No implicit task is created, and its source binding is not silently reassigned to the new laboratory report.
2. After a laboratory import, a fresh task projection marked for manual-context reassessment cannot be completed; no transition POST is emitted.
3. Independent task-read denial clears the prior task projection without an unsolicited compensating write.
4. Disconnect clears protected laboratory/task context; a late task response cannot restore it.

These are client contract tests, not real PostgreSQL/HTTP or clinical evaluation. They do not implement a laboratory-observation-to-question association.

## Tests-first and local evidence

| Check | Observed result |
| --- | --- |
| #471 client baseline | 76 existing follow-through/attention tests passed |
| Four new tests on #471 | 4 failed at the absent laboratory-import method |
| Four new tests on #473 | 3 failed because its task decoder could not consume the manual-dependency projection; late-disconnect control passed |
| Combined focused client set | 103 passed, 0 failed/skipped; includes the four new tests |
| Full `npm test` attempt | 496 entries: 491 passed, 5 failed, 0 skipped; all five failed modules could not load React in this environment |
| Full API discovery attempt | 247 executions: 66 missing-pydicom import errors, 27 database skips; not API acceptance |
| Complete reference suite rerun | 765 tests executed; 9 failures and 8 errors, all in PDF intake tests reporting that the exact pinned pypdf 6.21.4 is required |
| Laboratory parser | 8 passed |
| Dependency-gate controls | 13 passed; this is not installed-package license clearance |
| Static Alembic graph | One 0017 head and both published 0016 parents verified; no database migration execution |
| Syntax and synthetic-source scanner | Passed within their existing bounded scope |
| API workflow trigger | Missing path reproduced; added path passes; all jobs/permissions/prior trigger definitions remain identical |
| Whitespace | CRLF-aware Git diff check passed, retaining the existing CSV line endings |

The five unavailable frontend modules are `evidence-continuity-panel`, `laboratory-world-panel`, `patient-continuity-panel`, `question-evidence-panel`, and `source-images-panel`. No React-rendered result, production Vite build or local browser pass is claimed. Local Python is 3.13.5 and global TypeScript is 5.8.3, not the locked hosted toolchain. PostgreSQL, Docker, pg8000, pydicom and the required local React/Vite installation are unavailable. No dependency or rights gate was relaxed to hide those limitations.

The initial reference-suite attempt was interrupted by the command timeout and retained separately. The complete rerun exited 1 after 765 tests: nine failing subtests and eight errors in `test_pdf_intake`, all reporting the required exact pypdf 6.21.4 installation (local version 5.9.0). Existing SQLite ResourceWarnings also remain. The failed test names are recorded in `H1_LAB_WORKSPACE_LOCAL_RESULTS.json`; no assertions or dependency pins were changed. Suite counts overlap and are not additive unique-test totals.

## Required exact combined acceptance

The new source head must independently pass the existing H1 API/PostgreSQL suite, all seven restart/backup/restore/revocation stages, React/client and installed dependency-rights gates, production TypeScript/Vite build and the actual PostgreSQL/FastAPI/Chromium journey including laboratory import/history/denial and keyboard reading. Source artifact identity must match the exact composed commit. Separate parent results are not acceptance of this tree. Independent review and explicit human merge/release decisions remain outstanding; this composition is self-reviewed only.

## Remaining work and limits

- #475's direct Journey-to-Records navigation is a separate continuation, not imported here.
- Exact laboratory observation/source-locator binding to the canonical question/evidence/report lifecycle remains separate implementation work under #428/#425.
- #471's dedicated restored populated optional manual-dependency scenario remains an open acceptance extension; this UI composition does not close it.
- No general FHIR validation, XML, terminology expansion, external provider connection, new model inference, automatic task creation, medication/diagnostic decision or real-patient authority is added.
- The broader Levels 1-5 resource register remains a target plan, not an implementation-completeness claim.

Read this together with the existing source-owner contracts, the source-reuse manifest, and the exact-head PR verification receipt. Later receipts may close hosted/publication tasks without changing this tested tree; failed attempts must remain visible.
