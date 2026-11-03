# Connected reading and patient Overview: verification

## Result and scope

[Draft PR #308](https://github.com/OpenxIntelligence/open-intelligence/pull/308) connects the existing patient Overview and interrupted verification-return recovery to the connected source-reading workspace in [#305](https://github.com/OpenxIntelligence/open-intelligence/pull/305). It also fixes prepared source quotations and briefs surviving contextual navigation. The combined frontend passed the existing hosted PostgreSQL/FastAPI/built-React browser gate using independently authored fictional records.

Overview can resume the same unfinished question, distinguish current questions from source reassessment, open original records, and find an uncertain verification return after a same-case source refresh. Unchecked or unavailable question history remains unknown; only an authorized empty response produces zero counts. The recovery shortcut performs navigation only. An explicit retry in the existing Review panel retains the original intent and request key.

The common navigation function now clears both prepared source views before its same-section early return. Sidebar and contextual links therefore invalidate completed previews and late deliveries consistently. Authored question text, saved questions, the World Model and unrelated follow-through drafts retain their existing ownership.

## Immutable evidence

| Item | Identity |
| --- | --- |
| Parent #305 head | `aea88341e260a4829d5b1647d5395b78ca17bfa6` |
| Parent tree | `7ef9eb08115f12c027b18513808ceb6255369f67` |
| Failing test-only head | `b5e406071697529e170f4ba5f51adf82d09f6ca6` |
| Runtime candidate head | `f18876efe3609bd701857ef341ba0a5dfe005342` |
| Runtime candidate tree | `e8cc3c86cb3624114fc71da9dbc727a3033b0326` |
| Passing runtime run | [41657360248](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41657360248) |
| Passing runtime job | `125991124497` |
| Evidence artifact | `13240901200` — `h1-web-verification-41657360248-1` |
| Artifact SHA-256 | `a7add36f1f0f9f040d6a0e26e23ffdb08866d2fa0bc1e36764bae3f1d9966a72` |

The downloaded ZIP matched GitHub's artifact digest. Its `commit.txt` and source archive identify the runtime head. Every one of its 346 source file blobs and executable modes matches the committed runtime tree. The local checkout began as a snapshot of the exact parent tree; its local commit IDs are not presented as upstream commits.

This report pins implementation evidence to the runtime head above. The later documentation-only closeout and its final automatic check are recorded in PR #308. The artifact has finite retention; the [compact receipt](2026-11-03-reading-overview-verification.json) preserves the run identity, scope comparison and selected acceptance observations.

## Defects reproduced and repaired

**Contextual navigation retained prepared source views.** The test-only [run 41655414937](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41655414937) passed all 216 inherited client tests and the build, then failed `Contextual navigation must invalidate the prepared source packet` after a Review-to-Questions round trip. The assertion was retained in the passing combined journey. Additional probes hold actual authorized 200 quotation and brief responses across both a contextual round trip and same-section navigation. Delivery occurs before the client timeout, with Questions mounted and the request signal still active. Neither prepared reader returns.

**Overview could advertise recovery for a different effective Review case.** Independent review found that old source metadata for one case can survive a failed World Model refresh for another case while preserving the latter's uncertain return. The unchanged Review panel has a defined case-precedence order. The projection now uses that same order before offering recovery. A regression using the actual RegistrySession transitions failed with the imported projection, then passed with the guard. Same-case metadata refresh still restores recovery. RegistrySession and ReviewPanel implementation files remain identical to the parent.

Reassessment copy says that a question's source context needs reassessment. It does not assert that source bytes necessarily changed, because older snapshot contracts can also require reassessment.

## Verification results

| Check | Observed result |
| --- | --- |
| Client suite | 228 passed; zero failed, cancelled or skipped, locally and in the passing hosted run |
| Production build | TypeScript checks and Vite build passed |
| Combined browser journey | Passed against actual PostgreSQL 16, FastAPI, built React and Chromium |
| Overview continuity | Literal fourth-question draft resumed; four saved questions retained; 3 current and 1 requiring reassessment |
| Unknown versus empty history | Unchecked and denied history stay unknown; real authorized empty history shows zero counts |
| Late response suppression | Two navigation scenarios; actual 200 quotation and brief responses in each; Questions mounted after delivery; neither reader restored |
| Interrupted verification return | Original POST committed 201, response delivery interrupted once; explicit retry returned 200 with `duplicate: true` and the same receipt |
| Exact retry | Paths and complete bodies identical, including reason, request key and queue fingerprint; one matching durable history receipt |
| Neutral recovery navigation | Zero observed API requests from the Overview recovery shortcut |
| Original and actual download | Same question, source/version/line and snapshot throughout; all four downloaded briefs match their recorded byte lengths and SHA-256 hashes |
| Independent review | Whole-delta review: no remaining Critical, Important or Minor findings; separate receipt inspection: no blocking gap |

The fourth question's downloaded UTF-8 brief is 3,278 bytes with SHA-256 `94c9b95f22191f1dd2d1634bd8c506ea6b21cea587f7a2f53c6ea8cc5674df57`. Its exact original anchor is DOC-ONE v2, line 9. The four downloads preserve one historical v1/line-8 anchor and three v2/line-9 anchors, consistent with the Overview counts. The recovery probe concerns an earlier question among those four; it does not conflate that return with the fourth question's separate return.

The inherited reading, source amendment, exact original, fresh download authorization, independent grant denial, follow-through lifecycle, case switch and session clearing journeys also passed. Their reading and follow-through helper files were not changed.

## Visual and source review

The combined gate checks reading layouts at 320, 390, 768 and 1280 pixels, plus doubled text and short-height scenarios. New Overview checks cover 320, 390 and 1440 pixels. Manual screenshot inspection covered all three Overview widths, patient reading at 320, clinical reading at 390, follow-through attention at 390 and the connected-question desktop view. The reviewed recovery control and its focus ring remain visible below the context header and within the narrow viewport; text and controls remain contained.

At the runtime checkpoint, 333 of the parent's 340 files are byte- and mode-identical. Seven existing files change, all in frontend source, frontend test/config or browser acceptance. Six files are added, including the specification and plan. Backend, database, schemas, APIs, permissions, business logic, RegistrySession, ReviewPanel, dependencies and workflows retain parent bytes and modes. The closeout adds documentation and an OI-010 evidence reference only.

## Remaining boundaries

This establishes the tested synthetic, same-session software workflow. Browser receipt counts and request observations are backed by the archived harness and passing log; they are not a separate database audit. The positive same-case recovery path ran in the browser; contrary effective Review scope is covered by the new client regression.

The reading-layout selector does not implement authenticated patient or clinician accounts. This work does not merge the separate authored-evidence and governed-metadata integrations in #300 and #298, add biomedical appraisal or professional review, or complete OI-010's full investigation acceptance. It does not establish broad accessibility certification, production readiness or clinical validity. PR #308 is a draft, unmerged and undeployed.
