# Evidence comparison draft continuity in the connected H1 workspace

## Patient outcome and source owners

An unfinished comparison must survive an unchanged evidence refresh and explicit
workspace navigation, while its original patient/question/source/evidence/rights
context remains binding. Reuse #338's existing in-memory draft implementation in
#335's combined source-reading, intake, report-download and follow-up workspace.
No new patient/session/backend authority, schema, grant or dependency.

- Base #335: `9d173843f924b40becba3a7dffd71717c12afb5d`, tree
  `57165fc8b1c6305336752eb948710a437eda9cf9`.
- Donor #338: `ac6d2be176ff4488aefde870a5f5286313a99210`; tested runtime
  `f844451994713af2c785cef2f1a445ae0cebbe36`. Its final automatic browser run
  `41669224233` also passed. Donor review was self-review; this composition needs
  independent review.
- Preserve #307's common-authority denial clearing, independent metadata/task
  grants, exact uncertain writes, #316 status-bearing downloads and the later
  source-reading/follow-up/intake owners. The donor's old
  `question_evidence_journey.py` now belongs to metadata discovery; transfer only
  the draft checks into `authored_evidence_journey.py` and its separate observer.

## Bounded implementation and acceptance

1. Reuse all 30 donor client regressions unchanged. Add composed-session cases
   proving independent metadata/task denial retains a valid comparison, whereas
   shared patient/binding/source/question denial clears it and blocks late reads.
   Transfer the donor's real-browser refresh/navigation/no-implicit-POST checks.
   Record the expected failures before runtime adoption.
2. Merge only the donor's comparison state/editor/session methods. Keep the
   current component identity, independent route helpers, reset boundaries and
   every existing integration regression. Preserve the donor's spec and plan.
3. Run all compiled client tests, production build and current dependency gate.
   Execute the complete built-React/FastAPI/PostgreSQL Chromium journey at one
   immutable combined commit. Check downloaded report bytes, access receipts,
   restored exact-save behavior, amendment/withdrawal and case-switch clearing.
4. Obtain independent read-only review, inspect the actual hosted artifact and
   desktop/mobile captures, then record evidence in existing documentation and
   backlog. Keep draft/unmerged/undeployed. This is memory-only input retention,
   not durable autosave, clinical appraisal or professional review.
