# Preparation in the combined patient workspace

Draft #449 composes the existing #408 preparation agenda into #413's current H1 workspace. It is a frontend integration on synthetic fixtures, not a referral or clinical deployment.

## Source ownership

Base #413: `e3259bb2986206e4a7edf8bc3a29546471077beb`, tree `305dbbc98ab90711dbf1553c264c17bc89d22653`. Donor #408: `07cd593430d837dac5e097d15487ce99ac2c4108`; comparison baseline #398: `a85d30f5563d763507c64d91ec3c70100b446fc3`.

All 646 base Git blobs and modes were independently verified against the downloaded source artifact. Its SHA-256 is `640a7b690e29805adfef3b12c2f404276a14869bbddd5a21aa1ec64c0962d703`. That proves source identity, not acceptance of this child.

The three new preparation source files, three new preparation test files, compiler entrypoint and manual-passage browser helper match the donor. The current main view gets only the preparation import/render; styles retain source-image and keyboard-reader additions. Follow-through tests combine donor preparation assertions with the parent's newer A/B/A case-switch sequence. RegistrySession, follow-through runtime, patient-continuity projection, main browser driver, backend, migrations, dependencies, permissions and workflows are unchanged.

## Patient behavior and boundaries

Overview shows up to five exact saved questions and up to two open recorded tasks per question, with explicit total/overflow counts. It preserves source version/line, reassessment state, recorded owner and operational revisit basis. Loading, denied or wrong-case histories remain unavailable, distinct from an authorized empty response. Question and task grants remain independent. Unsent creation details and proposed owners are never presented as saved work.

Primary source status is not a freshness certificate for attached manual passages or preserved reports; the view explicitly directs that check to Investigations. The composed journey visits preparation during an uncertain manual-passage save, verifies the same saved question and empty authorized task history, then recovers the original command. Navigation adds no task writes. Corrections and revocation retain existing historical/report boundaries.

This does not verify record completeness, identity, clinician credentials, referral recipients, eligibility or appointment availability. Session-only draft retention is not durable autosave. Real patient, caregiver and clinician usability testing remains open.

## Verification record

Tests-first source `6db0214f9909c4ec1c157d4a88fdf5bcf22cd4c9`, tree `7242de3000c8576c1ab29e0301a1604c455d15be`, run [41827963055](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41827963055): all 483 existing client tests, 13 dependency-rights controls and production build passed. The actual PostgreSQL/FastAPI/Chromium journey failed at `Timed out waiting for saved preparation question`. This is negative evidence that the combined parent lacks the preparation agenda.

Local focused behavior checks use Node TypeScript transformation; the fresh checkout lacks the pinned TypeScript/React/Vite toolchain. Full local `npm test` reports `tsc: not found`. These checks are not typechecking, build or browser acceptance.

Final combined client/rights/build/browser acceptance and independent review are pending at this source checkpoint. The PR's final exact-head receipt supersedes this pending checkpoint when available. No donor success is substituted. The full standalone API/backup-restore suite is not rerun for this frontend-only change; API/migration bytes are preserved from #413. Sibling integrations #440/#443 and subsequent parent/main movement require their own composition and acceptance.

Backlog mapping: OI-007 question/review continuity, OI-009 explicit reassessment, OI-010 connected patient workflow, OI-013 case/authority isolation. No milestone is promoted to clinically accepted or complete by this slice.
