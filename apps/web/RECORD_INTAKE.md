# Original record intake on the scoped H1 application

This is a complementary child of the existing React Records screen (#200) and the canonical PostgreSQL source version API (#187/#193). It does not create another source ledger, loosen permissions or connect all clinical workflows.

Use the existing `apps/api/README.md` and `apps/web/README.md` setup. No dependency or lockfile changed. The backend requires explicit migrations, a disposable fictional PostgreSQL database and an operator-controlled synthetic access file. This is not production sign-in, consent or patient identity proofing.

## Operator prerequisites

The patient must exist in the canonical registry and have an exact patient grant with `patient_read`. A case binding must already be created by the independent authorized operator through the existing case-binding API. No authority is created from a report's Patient header. The session needs `case_binding_read` to view mappings, `source_read` for version metadata, `source_import` for deliberate imports, and separately `source_original_read` for full original-text inspection. Revoked, missing and cross-organization grants remain enforced by the API. The UI does not grant itself actions.

## Browser workflow

1. Open an authorized fictional patient in Overview. Choose Records, check authorized cases and inspect the selected case's source versions.
2. Choose an independently authored fictional `.txt` report in the existing `OI-SYNTHETIC-REPORT/1` format. Its Patient field must use the selected case reference. Inspect the literal local preview; selection does not upload.
3. Confirm fictional input and explicitly import. The original bytes are preserved: no newline normalization, source identity rewriting or medical extraction. The interface separately reports imported, duplicate or quarantined. A lost response, server error or malformed receipt is **unknown**, not a proof of rollback. Nothing is automatically retried.
4. Choose Inspect original on a current or historical version. The API checks original-read authority separately; the client verifies source/case/document/version/state and SHA-256 before showing inert text. A rejected recheck removes the previously opened original.
5. Import a correctly authored amendment with `Amends: DOCUMENT-ID@previous-version`. The source owner preserves the old version. This H1 screen does not yet invalidate scientific investigations or establish clinical review.

Example (replace the case reference with your independently authorized fictional binding; keep LF line endings):

```text
OI-SYNTHETIC-REPORT/1
Patient: CASE-WEB-INTAKE
Document: FICTION-PATH
Type: pathology
Event-Date: 2026-01-02
Issued-At: 2026-01-03
Specimen: FICTION-TISSUE
Finding: marker|not-reported|This authored fictional marker was not tested.
```

## Limits and evidence

Inputs are strict UTF-8/LF, no BOM/NUL, 1–65536 original bytes; escaped JSON must also fit the unchanged 72000-byte API envelope. Unsupported PDFs/scans require separately qualified integration. A wrong-case original goes to the existing quarantine, not to clinical assertions. Source statements and review remain `not_established`; user acknowledgments are not professional signatures or permission proof. Current data is as checked, not continuous pushed authorization.

`npm test` runs original registry/Records tests plus intake, response validation, ambiguous-write and stale-session tests. The existing hosted Chromium harness now invokes `tools/record_intake_journey.py` against actual FastAPI/PostgreSQL: disk-file selection without auto-upload, exact hashes and originals, duplicates, amendment history, foreign-case quarantine, independent original-read denial and metadata clearing. Unit mocks test client failure handling; the browser/database path is not mocked.

No real patient data, external medical content, AI call, schema/API/dependency addition, commercial rights clearance, main merge or deployment is provided by this increment. Owner review and combined exact-head evidence are required; tests are not independent clinical validation.
