# Existing World Model and investigation workflow integration

Date: 2 November 2026. Scope: independently authored fictional records in the existing local application. This is software integration, not clinical validation or production authority.

## Preserved source owners

This increment starts from product draft [#158](https://github.com/OpenxIntelligence/open-intelligence/pull/158), commit `1bb4ff06a5ab222d3561145e757226f671dbf3ea`, including safety [#123](https://github.com/OpenxIntelligence/open-intelligence/pull/123). It reuses:

| Owner | Inspected immutable source | Reused responsibility |
|---|---|---|
| [#147](https://github.com/OpenxIntelligence/open-intelligence/pull/147) | `97f197c3472df785b68cfab8794c388e20c4b798`, `feat/synthetic-world-model-source-projection-20261102` | Read-only `oi.synthetic-world-model/1`, eight projection/HTTP tests and source-owner specification |
| [#157](https://github.com/OpenxIntelligence/open-intelligence/pull/157) | `0bad696797af2ff036710eaed8dbff0427c48a59`, `feat/pwm-source-inspector-ui-20261102` | Patient Mission source inspector, literal rendering and bounded asynchronous refresh |

The projection module and its original Python tests retain their source-owner bytes. The source-owner specification keeps its wording, with trailing-space Markdown breaks normalized to paragraphs. The inspector is extended only to settle the existing canonical case-picker veto before reading the selected case and to label old stale IDs as historical reports. Shared server, HTML and CI wiring preserves #158's handoff, literature and Composer paths. No clinical #152/#154 implementation is incorporated by this increment.

## Connected behavior

`GET /api/cases/{CASE-ID}/world-model` projects the existing transactionally consistent `CaseStore.state()`; it creates no database, patient identity, source ledger or review store. Source observations retain version/hash/line, specimen and distinct event/issued/received dates. Report generation uses the existing investigation and snapshot contracts.

| Event | Existing projection behavior |
|---|---|
| Prepare investigation report | Report ID appears in draft IDs; its question remains open. |
| Explicit demo acknowledgment | Draft and open-question references clear. The canonical report records `reviewed_in_demo`; source observations remain `not_established` with no clinical meaning. |
| Source amendment | The old report becomes stale, the question reopens and the superseded source remains inspectable. Old report text, reviewer and review time are preserved. |
| Reassess and prepare | A distinct draft report appears alongside the old stale history. |
| Acknowledge the replacement | Current draft/open-question references clear; the historical stale report remains visible. Its presence alone does not establish an open clinical task. |

The inspector remains expanded through these changes and refreshes from the existing event-list render. It clears immediately on case changes, rejects older A-to-B-to-A responses, respects a draft-vetoed selection and invalidates work when collapsed. Text is rendered through text nodes.

## Integration defects reproduced and corrected

1. The source inspector referenced `/world-model.js` but the application uses an explicit static-file allowlist. The reused drafts supplied no static route. Two new real HTTP regressions first failed with 404 on the API/asset paths; the integration adds both routes, checks exact JavaScript bytes/MIME and exercises the real report lifecycle.
2. The inspector could run its case-change listener before `app.js` restored a draft-vetoed selection, then remain loading without the original case. The new DOM regression failed on an unwanted CASE-B request. Immediate invalidation plus a microtask-deferred selection read now honors the canonical guard; the six inspector tests pass.

The browser journey additionally expands the real inspector, attempts the actual unfinished-draft case switch, and checks prepare, acknowledgment, amendment, case isolation, reassessment and replacement acknowledgment. Its final Mission assertion includes the separately reviewed Mission active-versus-historical-staleness repair. The integration owner composed that repair after independent review. Only an addressed question with its own current reviewed-in-demo report clears active stale work; missing question/review context stays actionable. The existing total stale count and additive review history retain every old report. The World Model never suppresses historical stale IDs to make an active workflow look resolved.

## Verification and limits

- Source-owner blob hashes were checked before adaptations; eight original Python tests and three original Node tests are preserved.
- Ten World Model Python/HTTP tests passed after route integration. The two new HTTP tests cover the delivered asset and connected source/report/review/amendment lifecycle.
- Six named inspector Node tests passed, including added A-to-B-to-A, ledger-refresh and draft-veto cases.
- The isolated World Model composition passed all **335 application Python tests** in 53.723 seconds, with no failures, errors or skips. This includes the original application tests and ten World Model Python/HTTP checks. Python compilation, JavaScript syntax and final staged whitespace checks passed. The separate Mission repair and final hosted-browser receipts belong to the exact final composition recorded by the integration owner; a static browser-script review is not a browser pass.

The helper consumes an unchanged canonical synthetic store snapshot; it is not an authorization validator for externally assembled dictionaries. The current host permits only the existing fictional local workflow. This work supplies no verified identity, consent, clinician authority, real-patient access, semantic medical interpretation, PDF extraction, model training, external evidence rights or clinical action. New production modules use the standard library and existing first-party browser runtime; no package, dataset or model weight is added. The integration owner regenerates the scoped source SBOM for the final composition.

Continue under existing World Model [#116](https://github.com/OpenxIntelligence/open-intelligence/issues/116), cross-domain [#81](https://github.com/OpenxIntelligence/open-intelligence/issues/81), review [#120](https://github.com/OpenxIntelligence/open-intelligence/issues/120) and combined acceptance [#121](https://github.com/OpenxIntelligence/open-intelligence/issues/121). Source branches, main, merge decisions and deployment remain unchanged by this isolated increment.

### Final local composition receipt

Root combined both independently reviewed patches with the existing product candidate. The complete application suite passed **341 tests in 46.741 seconds**, with zero failures/errors/skips. All **63 named JavaScript tests**, **219 guarded research tests** (including 24 HDF5 cases), eleven script syntax checks, six workflow YAML files and 31 shell blocks passed. The final source SBOM was regenerated and passed official CycloneDX schema validation. Final hosted Chromium is a separate exact-commit publication gate recorded in PR #158 and the canonical roadmap; no local browser execution is claimed.
