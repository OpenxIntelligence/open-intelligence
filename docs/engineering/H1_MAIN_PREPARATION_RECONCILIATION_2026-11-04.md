# Current-main reconciliation for the combined patient workspace

## Pinned inputs

- Accepted main: `a5a5482f815ceb3c322cdfb32ab8b18c1c0e8709`, tree
  `a7b17de00d0e0adc5b7644155d690ebacd279815`, including merged #390.
- Combined #445: `641273d98bc9058ac78185f8d674a243f70446e9`, tree
  `07336a03c4b61a7cf6507ed7a229620a4012780f`.
- Main baseline previously incorporated by #405:
  `31509a6b83949f974e25b6913a6e30fc968be939`.
- GitHub compare selected `f200dd107871d89703267ee0d1a14b2d1ca64d36`
  as a common H1 ancestor. Both branches also incorporate the later accepted
  reference-app baseline above. Comparing only against the earlier ancestor
  creates artificial add/add conflicts for the already accepted reference work.

## Disposition of the 18 differing main-side paths

Recursive Git path/blob/mode comparison identified 18 main-changed paths whose
contents differ from #445. No main-side deletions were found. Reference paths
already incorporated through #405 are compared against the explicit 31509a6
accepted baseline; H1 paths use f200dd1. Every path was inspected before deciding
its outcome. This is a bounded content reconciliation, not a blanket choice of
one branch or a replacement source ledger.

| Paths | Disposition |
|---|---|
| `apps/api/tests/test_question_review_returns.py` | Keep main's patient-scoped event count. |
| `apps/api/tests/test_received_record_requests.py` | Add main's stale-original-before-receipt regression; no API implementation change. |
| `web/app.js` | Keep main's same-case selector guard, preserving current authority and unsent drafts. |
| `tests/browser_journey.py`, `tests/patient_mission_browser_journey.py` | Keep main's same-case assertion, bounded duplicate diagnostics, and authoritative workspace-readiness wait. |
| `apps/web/src/registry-client.ts`, `apps/web/tests/followthrough-client.test.mjs`, `apps/web/tools/followthrough_journey.py` | Main's earlier draft protections are already present. Preserve #445's manual draft reset/denial checks and #449's preparation and four-task A/B/A assertions. All three remain byte-identical to #445. |
| `.github/workflows/h1-web.yml` | Only a trailing blank-line difference remains; preserve #445 unchanged. |
| `src/open_intelligence/document_intake.py`, `src/open_intelligence/store.py`, `tests/test_case_switch_guards.py`, `tests/test_investigation.py` | Main is unchanged from the accepted 31509a6 reference baseline. Preserve #445's later PDF, freshness and isolation work unchanged. |
| `docs/EXECUTION_BACKLOG.csv` | Preserve canonical IDs/eight columns and both distinct acceptance histories. Label retained main text as historical. |
| `docs/engineering/H1_EVIDENCE_CONTINUITY.md` and three `docs/project-state` records | Preserve newer combined history and retain main's distinct older checkpoint under an explicit historical label; add this current reconciliation pointer. |

## Acceptance and landing boundary

Publish the reconciliation on the existing combined candidate with both exact
parents, targeting current main. Do not overwrite #405/#413/#449 or main. The
older root candidate's merge conflict is not evidence that this new tree passes.

Required on the new combined tree: independent source review; full client,
rights and production build; full PostgreSQL contracts with no skips; full
reference suite; actual browser journeys; six restart/restore/revocation probes;
and exact source/run/artifact receipts. Keep all migration history, backend
runtime, grants, pinned dependencies and workflow gates unchanged from #445.

The #445 533-test and browser receipt qualifies only the earlier pinned head.
New combined verification is pending at this publication checkpoint. The final
PR receipt must identify its exact head/tree and close each pending gate before
a merge decision. No merge or deployment is performed by this source change.

## Demo handoff

The existing runnable H1 path is `apps/api/compose.yaml` plus the explicit
synthetic-access overlay and the React/Vite application documented in
`apps/web/README.md`. The six recovery drivers are disposable verification
programs, not a persistent interactive demo launcher. A supported seeded demo
launcher remains a subsequent bounded task after this landing candidate passes.
Do not represent the SQLite reference app as the H1 PostgreSQL demo.

Synthetic-only software evidence; no clinical validation, real-patient access,
new model or content integration, production identity or clinical sign-off.
