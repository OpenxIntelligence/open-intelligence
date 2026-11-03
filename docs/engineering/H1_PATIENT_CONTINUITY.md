# Patient Overview on the connected question workflow

This is the bounded continuation in draft [#288](https://github.com/OpenxIntelligence/open-intelligence/pull/288).
It brings the existing Overview projection onto the shared authored-question,
source-inspection, verification-return and brief workflow. It creates no patient,
question, task, review or source store.

## Source ownership

The final base is [#287](https://github.com/OpenxIntelligence/open-intelligence/pull/287)
at `f7b0f683ab64ba2de7363744b65b8e26528f3138`, tree
`a72d810aaf32a76f9c736aa1df4232e3bcd9ced0`. The available local commit
`bd9b563cfca3cfaca51a58adb75c9e79209a1b02` has exactly that tree. All API code
and tests, migrations, source/domain code, inherited reference tests, workflows,
dependency locks, and the shared owner's project-state assessment are retained
unchanged. The shared session differs only by the Overview projection re-export.

Overview comes from [#286](https://github.com/OpenxIntelligence/open-intelligence/pull/286)
at `eb3cff81a4edeaf433d25cc069c9894c3bc52d0b`. Its projection, component and
seven projection tests are byte-for-byte reused. Its actual-session uncertain-save
test and browser assertions are retained with the existing owner fixtures.
The [source manifest](H1_PATIENT_CONTINUITY_SOURCE_REUSE.json) records these identities and the protected parent trees.

#287 appeared after the first ownership audit. This continuation adopts its
published implementation and extends its existing combined browser helper.
The earlier overlapping tests-first work is retained in Git history as diagnostic
evidence, rather than maintained as another API implementation or acceptance lane.

## Patient behavior

Overview offers the existing question editor, Records and Investigations. It
distinguishes an unfinished question, an in-flight save, an uncertain result and
a server-confirmed save. Drafts remain in this tab's memory and retain the existing
source fingerprint and exact retry identity. Reload and disconnect clear them.

Current/unreviewed and source-reassessment counts come only from a successful
history read for the loaded active patient/case mapping. Unknown, loading, failed
or mixed-scope histories are withheld; they are not reported as zero. A zero
count does not establish an absence of care needs. A verification return remains
an operational request, and does not turn a source question into clinical review.

All section navigation now uses the same packet/brief clearing behavior. This
includes the rail, Overview and contextual buttons between source questions and
Review. Clearing invalidates pending deliveries as well as prepared views. It
preserves the existing authored draft and uncertain-return intent. Disconnect
continues to use the existing complete session reset.

## Observed defect and acceptance

The tests-first candidate `61a4734138c6961e221a9a14b833a325c0c516c0`
(tree `42ae4c2b53a8a9c8d2d3eacd9118e1ea5f609714`) passed 143 client checks and
the locked build in [browser run 41627928286](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41627928286).
The actual PostgreSQL/FastAPI/React/Chromium journey then failed:
`Contextual navigation must invalidate the prepared source packet`.
Prepared context reappeared after navigating back from Review through its own
button. The assertion is retained unchanged and checks the remounted source panel.

The same checkpoint's [API run 41627928161](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41627928161)
ran 298 methods with 47 failing assertions/subtests in eight new disclosure
methods, zero test errors and zero skips. It demonstrated the inherited encoding
and commit-order gap. Final runtime repair and tests are owned by #287 and are
adopted unchanged here; the discarded overlapping test variant is historical.

The final browser journey extends #287's existing fourth authored question:

1. Leave its unfinished draft for Records, open Overview, and resume the exact text.
2. Save against the existing source preflight, inspect the exact original quotation,
   and show the scoped counts: three current/unreviewed questions and one historical
   question requiring source reassessment.
3. Record an explicit independent-verification reason and retain its return ID.
4. Revisit Overview and the same question, inspect the unchanged source identity,
   prepare a fresh brief and perform the actual freshly authorized download.
5. Verify the return history remains attached and clinical/model/evidence flags
   remain false. Keep the inherited amendment, original download, permission,
   delayed-response and uncertain-retry assertions.

The artifact `patient-continuity-workflow.json` connects the actual question,
source anchor, return, fresh brief receipts and downloaded bytes. Its linked
`source-brief-<question-id>.json` records the independent download request.
Desktop and 390 px Overview screenshots remain in the existing browser artifact.
Final exact-head test counts, run links, archive checksum/source comparison and
image inspection belong in the draft PR verification receipt. Local discovery
without PostgreSQL is not database acceptance.

## Limits

This uses independently authored fictional records and operator fixture grants.
It does not provide production identity, consent, clinical review, biomedical
evidence qualification, model execution, patient authorization or deployment.
The source-only brief is not the full reference application's PDF/governed-report
parity. Review returns are not external notifications or completed review.

The projection describes the last successful reads in this tab. Server operations
recheck their own permissions; external revocation, database commit and HTTP
delivery are not one atomic operation. Receipts are not delivery proof and
downloaded files cannot be recalled. Repository-wide historical data cleanup
remains a separate administration/integration issue. Keep this PR draft and unmerged.
