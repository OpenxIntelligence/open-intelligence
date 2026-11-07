# Original record intake on the scoped H1 application

This is a complementary child of the existing React Records screen (#200) and the canonical PostgreSQL source version API (#187/#193). It does not create another source ledger, loosen permissions or connect all clinical workflows.

Use the existing `apps/api/README.md` and `apps/web/README.md` setup. No dependency or lockfile changed. The backend requires explicit migrations, a disposable fictional PostgreSQL database and an operator-controlled synthetic access file. This is not production sign-in, consent or patient identity proofing.

## Operator prerequisites

The patient must exist in the canonical registry and have an exact patient grant with `patient_read`. A case binding must already be created by the independent authorized operator through the existing case-binding API. No authority is created from a report's Patient header. The session needs `case_binding_read` to view mappings, `source_read` for version metadata, `source_import` for deliberate imports, and separately `source_original_read` for full original-text inspection. Revoked, missing and cross-organization grants remain enforced by the API. The UI does not grant itself actions.

## Browser workflow

1. Open an authorized fictional patient in Overview. Choose Records, check authorized cases and inspect the selected case's source versions.
2. Choose an independently authored fictional `.txt` report in the `OI-SYNTHETIC-REPORT/1` or `OI-SYNTHETIC-REPORT/2` format. Its Patient field must use the selected case reference. Inspect the literal local preview; selection does not upload.
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

## Source-reported cancer episodes in Journey

For the connected H1 application, change the header to `OI-SYNTHETIC-REPORT/2` to supply typed findings. Keep the same patient, document and date headers. Each line gives a unique finding key, the reported role, a case-local episode identifier (or `?` for unassigned), the existing reported state, and the literal source statement.

```text
Oncology-Finding: breast|primary|EP-A|reported|The fictional report describes a breast primary.
Oncology-Finding: colon|primary|EP-B|reported|The fictional report describes a separate colon primary.
Oncology-Finding: nodule|metastasis|?|indeterminate|The fictional report describes a nodule of uncertain origin.
```

Use the same episode identifier across documents only when the author explicitly attributes those findings to the same episode in this case. Ordinary `Finding` lines also work in version 2 and have no episode attribution. Journey groups current typed findings and shows their original status, quote, document version and line. An amendment can change attribution while the previous original remains available in Records. The role is an authored label. This workflow does not extract diagnoses from prose, establish a clinical diagnosis, or reconcile identifiers from external systems.

To exercise the amendment, import [the first fictional report](../../examples/synthetic/oncology-episodes-v1.txt) and then [its amendment](../../examples/synthetic/oncology-episodes-v2.txt) in an authorized binding for `CASE-WEB-EPISODES`. In Journey, the two primaries stay under EP-A and EP-B. The nodule moves from “Episode unassigned” to EP-B and stays indeterminate. Open the nodule’s source-only question context to inspect its attribution. Records can reopen both original versions.

Question review compares findings across sources only when their specimen, date, finding key, episode and role agree. Findings with an unassigned episode are excluded from these comparisons. Source briefs and evidence reports carry the selected line’s role, episode and reported state.

## Limits and evidence

Inputs are strict UTF-8/LF, no BOM/NUL, 1–65536 original bytes; escaped JSON must also fit the unchanged 72000-byte API envelope. Unsupported PDFs/scans require separately qualified integration. A wrong-case original goes to the existing quarantine, not to clinical assertions. Source statements and review remain `not_established`; user acknowledgments are not professional signatures or permission proof. Current data is as checked, not continuous pushed authorization.

`npm test` runs original registry/Records tests plus intake, response validation, ambiguous-write and stale-session tests. The existing hosted Chromium harness now invokes `tools/record_intake_journey.py` against actual FastAPI/PostgreSQL: disk-file selection without auto-upload, exact hashes and originals, duplicates, amendment history, foreign-case quarantine, independent original-read denial and metadata clearing. Unit mocks test client failure handling; the browser/database path is not mocked.

No real patient data, external medical content, AI call, schema/API/dependency addition, commercial rights clearance, main merge or deployment is provided by this increment. Owner review and combined exact-head evidence are required; tests are not independent clinical validation.

### Reviewing two reported origins

In Journey, open a source-linked question from a metastasis statement and save the
question in Investigations. Open Review and refresh the inbox. For that question,
**Compare reported origins** lists passages from other current documents with the
same specimen, event date and finding key and a different reported episode.
Choose a passage, inspect both quotes, and write why the origin remains unresolved.
The return binds both original source lines to the reason and leaves both reports intact.

After an amendment, refresh Journey and choose **Check recorded attribution reviews**.
A changed case snapshot requires reassessment. Open the review history to inspect
the reason and reopen either exact original with fresh source permissions.
This workflow uses fictional credentials and records a verification request.

In the return history, choose **Compare recorded and current passages** to read
the two original quotations alongside the latest version of each document.
The comparison follows the recorded finding key within each document. If an
amendment moves that finding, the view shows its new line. If the key disappears,
the view identifies the missing statement. An explicitly unassigned episode
and a statement without an episode field are displayed separately.

The comparison audit preserves both recorded/current passage pairs, their patient,
case, question and original review receipt, and a deterministic content digest.
Access receipts remain separate so repeated inspection of unchanged content has
the same digest. This snapshot is a prerequisite for a later durable disposition.
Reviewer decisions and completion remain unimplemented in this increment.
