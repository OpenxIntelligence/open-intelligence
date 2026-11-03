# Connected evidence chronology and dependency evidence

## Scope and source pins

Continue OI-004/008/009/010 on the existing connected patient workspace, without
changing canonical patient, source, question, evidence or follow-up ownership.
Use independently authored fictional inputs only. This is an unmerged
engineering candidate, not a deployment or clinical validation.

- Base #335: `9d173843f924b40becba3a7dffd71717c12afb5d`, tree
  `57165fc8b1c6305336752eb948710a437eda9cf9`.
- Chronology donor #330: `312ad9379311901f8a69a7c20d4ea09f98027481`.
- Dependency evidence donor #339: `d694db4ca12206e815d6045b73baa9b6f7394290`.

The base already includes #322's strict server citation history and fresh report
download status, plus #328's follow-up attention and #319's mounted import
disclosure. This continues those functional changes from #326 on the newer
connected lineage. It does not transplant #326's legacy browser diagnostics or
their original donor's documentation claims. The separate comparison-draft
(#348) and reviewed PDF/text intake (#349) work remains outside this slice.

## Acceptance

1. Reject impossible calendar dates, clocks, offsets and control characters in
   evidence/citation chronology, including nested questions and report sources.
   Keep the existing distinct precision contracts and valid strings unchanged.
2. Malformed fresh history clears the previous report and prevents download;
   an explicit valid refresh restores access to the unchanged preserved body.
3. Match installed package identity (including npm aliases), version and license
   to the lock. Reject noncanonical paths and linked package ancestors, manifests
   or notices. Keep absent optional packages explicitly uninspected.
4. Run filesystem regression controls before the existing dependency audit and
   build in hosted acceptance. Preserve dependency versions, lockfiles,
   synthetic scope and false commercial/native-linkage clearance flags.
5. Preserve the connected import, reading, evidence/report and follow-up browser
   journey, all permission-denial synchronization, exact retries and restart.

## Execution and evidence

- [x] Inspect live branch heads, instructions, source changes and donor evidence.
- [x] Reconstruct an isolated checkout from #335's verified source artifact.
  Artifact `13248585569` SHA-256:
  `c4c6ab88ab0dadf53f7b9adcf35dec86637ced1cd572bc62fb57600572d1044a`.
  All source bytes reconstruct the exact base tree above.
- [x] Baseline client suite: 300 passed, zero failures/skips.
- [x] Apply donor regressions first and record expected failures. Pinned local
  tests-only commit `89d12cf` produced 9 chronology failures and 301 passing
  client controls (310 total); the original package gate produced 8 expected
  failures and 5 passing filesystem controls. No test was skipped.
- [x] Adopt the bounded donor implementations and CI gate wiring; retain source
  pins and identify any adaptations instead of implying whole-branch reuse.
  All five #330 code/test files and #339's filesystem test retain exact donor
  bytes. The #339 gate, package scripts and workflow only lose an extra blank
  line at EOF. Donor narrative/research documents are not imported.
- [x] Run local client suite, production build, filesystem controls and actual
  installed-tree gate: 310 client tests, 13 filesystem controls, TypeScript/Vite
  build and installed-tree evidence gate pass; 18 installed packages inspected,
  two optional packages explicitly uninspected, zero errors/skips. Dependency
  cache bytes were copied into real local directories so the gate did not need
  a symlink exemption. Diff whitespace checks pass. Backend, migrations,
  lockfiles, patient/source/session owners and browser helpers are unchanged.
- [ ] Obtain a fresh read-only code review and resolve material findings.
- [ ] Publish a draft child of #335 and verify the exact proposed commit using
  the existing hosted PostgreSQL/FastAPI/React/Chromium workflow.
- [ ] Download and verify the combined source, report receipts and gate artifacts.

Hosted results belong to the final draft PR receipt. Separate donor/parent
successes are not combined acceptance. This frontend/tooling slice does not
claim a fresh standalone API suite or database backup/restore run. The local
executor uses the existing dependency cache; hosted acquisition remains pinned
and script-free. No dependency, schema, API, grant or clinical authority change.
The dependency check is static installed-tree evidence, not protection against
concurrent hostile filesystem mutation or tarball-byte reauthentication.
