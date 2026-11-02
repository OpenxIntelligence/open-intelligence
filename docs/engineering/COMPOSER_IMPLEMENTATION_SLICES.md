# Composer / Copilot implementation slices — planning proposal
**Status:** proposed, 2026-11-02. Build the complete product architecture/requirements program; stage executable, verifiable slices. These slices do not replace the active Notion sprint board or authorize new code. For product contract see [Composer workspace specification](../product/COMPOSER_COPILOT_WORKSPACE_SPEC.md).

| Gate | Deliverable | Dependencies / unchanged boundaries | Acceptance evidence |
| --- | --- | --- | --- |
| C0 | Inventory current source/case/question/investigation/agent/event APIs and active PR overlaps; map Composer intents to existing domain contracts | Reconcile #49, #51, #53, #56 and agent governance PR #55 before code edits to shared files | Proven existing interfaces, source/rights/status checks, no invented stack |
| C1 | Static contextual Composer UX prototype on synthetic case, visible **available** task templates (no free-form medical advice) | Existing case-selection, source-line and Patient Mission UI; no additional patient route | Keyboard/390px usability; selected case, as-of time, original records and tool availability shown; no wrong-case leakage |
| C2 | Read-only typed question/intent API and source-grounded response | Existing source/version/lineage and case isolation; no parallel patient store | Question -> source anchor -> verify; unsupported intent abstains; actor/case scope enforced for currently supported synthetic environment |
| C3 | Plan preview, task and run receipts on existing investigation model | No new generic workflow backend without comparison and ADR | Proposed vs executed statuses cannot be confused; missing data and denied tool return explicit result; repeat is idempotent |
| C4 | One bounded deterministic computation e.g. lab trend with medication overlays | Need valid specimen, timestamps, units and source linkage; live first-party LIS work is separately under #56 | Correct calculation and compatible values; failed QC/unknown or mixed units held; reproducible output |
| C5 | One rights-qualified scientific investigation with explicit evidence and counterevidence | Existing evidence/investigation/rights contracts; external data cannot leak case | No fabricated citations, independent check results, metadata-only clear labels, abstention and stale-input test |
| C6 | Source-change watch and review inbox | Existing source amendment/staleness/event ledger; no autonomous care action | One event -> one affected-review task; no unrelated case updates, no duplicate runs; cancel/revoke/expiry receipt |
| C7 | Governed analysis pipelines and full workbench, role-specific patient/professional views | Required intended-use, permission, security, regulatory, computational model and clinical review decisions | Resume/retry/cancel durable run; bound compute/egress; reference synthetic modality datasets; separate clinician/public evaluation |

### Initial UI experiment
Scope to the **same synthetic case** already used in the local Python/SQLite reference. Add only a task-template "Investigate" / "Compare changes" composer panel and output history. Maintain explicit buttons for independent patient views as future work. Do not invent real EHR/LIS/PACS, patient permissions, disease inference, treatment selection, eligibility or model execution. A composer message that asks for unavailable tools must return unavailable/missing-data, not a fabricated answer.

### Priorities and integrations
- P0 near-term: protect existing Nov 4 demonstration. Do not introduce destabilizing full-platform UI without a reviewed scope decision.
- After freeze: C0/C1 first; then C2/C3, with explicit useful output; C4/C5/C6 as independent safe slices.
- The broader first-party EHR, LIS, PACS, imaging, pathology and omics implementations have their own contracts and cannot be inferred from Composer existence.
- Founder product control and clinical/rights approval gates apply; no agent independently merges, deploys, or claims completed care.

### Verification inventory
Unit and browser tests must cover case switching; missing/offline sources; no cross-case data; immutable source versions; late amendments; contradictory values; unit/date incompatibilities; tool rights and egress; plan/execution status distinction; review authority; patient projection drift; task cancellation and replay; unchanged existing synthetic regression paths. CI and independent clinical evaluation are distinct.
