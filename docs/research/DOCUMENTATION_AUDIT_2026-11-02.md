> **Dated research appendix — 2 November 2026.** This preserves a dated read-only documentation capture. Its source timestamps, document-reported branch claims and old checkpoint conflicts remain historical observations. For inspected GitHub refs use [REPOSITORY_INVENTORY_2026-11-02.json](REPOSITORY_INVENTORY_2026-11-02.json); for the current bounded execution reconciliation use the [execution audit](../engineering/EXECUTION_AUDIT_2026-11-02.md). It does not establish runtime behavior, current CI, approvals or completed work by itself.
>
> The original research text follows unchanged. Original capture `documentation-audit.md` SHA-256: `e28b0a2053bfe4a9003a4703e3faf798c24fa127ef83303b7e23cf1a7dd03e68`. This appendix complements the [first-principles plan](../FIRST_PRINCIPLES_PLAN.md), [execution backlog](../EXECUTION_BACKLOG.csv), and [execution audit](../engineering/EXECUTION_AUDIT_2026-11-02.md).

---

# Open Intelligence documentation audit
Date: 2026-11-02. Read-only audit for the founder's definitive mandate.
Scope: connected Notion project documentation and Google Drive project documents. No external document edits, outbound messages to other people, patient attachments, medical-record downloads, genomic files, imaging files, or actual patient datasets were accessed. Public-narrative research is treated as product discovery only. No software implementation or CI result was independently verified in this audit; those remain the repository audit's responsibility.

## 1. Canonical locations and precedence

- Repository: https://github.com/OpenxIntelligence/open-intelligence
- Existing repository baseline: https://github.com/OpenxIntelligence/open-intelligence/blob/main/docs/FIRST_PRINCIPLES_PLAN.md
- Named-person data exclusion policy: https://github.com/OpenxIntelligence/open-intelligence/blob/main/docs/METHOD_REFERENCE_NOT_CASE_DATA.md
- Notion team root: https://app.notion.com/p/40a3866f77ef81eb91a9c696198ed71b
- Notion research root: https://app.notion.com/p/40a3866f77ef81c7a73af37e4ca73654
- Notion identity and precedence: https://app.notion.com/p/40a3866f77ef8154bf15c7bb53138c9f
- Existing Drive project root: https://drive.google.com/drive/folders/1O037nOW8L15vnsjGEWwETVKejyB71779
- Drive Master Atlas: https://docs.google.com/document/d/1rDcbE4BWOYFws-TAm1oGGQFb9gJVle1WxUHFn_2SnqM/edit
- Drive Engineering Progress: https://docs.google.com/document/d/1Zbn-8Z5fABdGrJa5W0kSh4ojSVFvd1ddXdvW6pHr9gA/edit
- Drive OI-27 Roadmap: https://docs.google.com/document/d/1Wlg7k61mjVbj-_4x6dth8KM1N7N0U4qzZh-ywitwNA4/edit

The Identity page's accepted strategic crosswalk gives this precedence: explicit founder-adopted product/rights decisions; accepted versioned domain/architecture contracts; verified GitHub main and exact-head branch/CI evidence, clearly separated; Notion/Drive studies; proposed alternatives. New summaries are complementary research. They do not replace accepted source, patient, evidence, investigation or authority owners.

The repository defines implemented behavior. Notion owns decisions and detailed research; Drive contains working material and curated summaries. Documents explicitly say these systems are not automatically synchronized. A last-edit timestamp does not prove every embedded claim is current.

## 2. Source index and observed timestamps

All dates below are 2026-11-02, UTC, from connector metadata; they describe document edits, not revalidation of external source facts.

| Source | Last edited/modified | Read scope |
| --- | --- | --- |
| Team Dashboard — https://app.notion.com/p/40a3866f77ef81eb91a9c696198ed71b | 18:05:55 metadata; fetch text additionally carried 19:34:41 as-of | Main content; response marked truncated with three unknown alias blocks |
| Research root — https://app.notion.com/p/40a3866f77ef81c7a73af37e4ca73654 | 19:34:41 | Current direction, navigation, precedence |
| Identity — https://app.notion.com/p/40a3866f77ef8154bf15c7bb53138c9f | 19:16:25 | Full project/architecture precedence |
| Decisions 03 — https://app.notion.com/p/40a3866f77ef81e08a12fd4921e19629 | 19:34:40 | Accepted H1 choices, strategic assessment, no-data policy, older contradictory checkpoints |
| Vision 01 — https://app.notion.com/p/40a3866f77ef81199312f0887a7d8f3b | 19:36:38 | Mission, patient loop, current research handoff |
| Clinical data 05 — https://app.notion.com/p/40a3866f77ef81d9a5adca4ee9adb2e0 | 19:42:15 | Architecture and integration headings/receipts; no linked patient source files followed |
| Agents 08 — https://app.notion.com/p/40a3866f77ef81fc929eca89e41a3f4a | 19:19:54 | Patient→evidence priority, source-rights decisions, knowledge context, engine validation |
| Product UX 09 — https://app.notion.com/p/40a3866f77ef816881beea1863f14f4f | 19:19:57 | Task-first experience, source inspector, acceptance, existing UX issue |
| Roadmap 12 — https://app.notion.com/p/40a3866f77ef8197ae65e727c8907eb3 | 19:34:43 | Workstreams, milestones, branch receipts, current dispatch |
| Integration 14 — https://app.notion.com/p/40a3866f77ef8122b08bcdc16de89876 | 19:42:17 | Contract decisions, gate II, newest PR #95 receipt |
| OI-20 audit — https://app.notion.com/p/ee53866f77ef82128797813cfee06927 | 16:34:02 | Existing audit summary, findings, limitations |
| Drive Master Atlas (above) | 19:17:02 | Current product/policy and historical observations |
| Drive Engineering Progress (above) | 19:42:53 on fetch; metadata search earlier reported 19:36:14 | Latest integration and supersession receipts |
| Drive OI-27 (above) | 19:33:09 | H1/H2/H3 roadmap, workstreams, demo, open decisions, issue index |

Notion returned unverified page verification status. The audit covered selected high-value current documents, not the entire corpus, all task rows, attachments, or every source linked from those pages.

## 3. Decisions the documents already record

### Product and MVP

The current Vision page states a single continuous loop: authorized records/context → source-linked Patient World Model → gaps/questions → scientific evidence and possibilities → expert review → accountable follow-through → reassessment on new findings. It says the goal is to make sophisticated organization and research accessible to cancer patients and care teams. Sid's public story is one method/needs input; his clinical files and values are not fixture, training, benchmark, demo or evaluation material.

Agents 08 makes the immediate priority explicit: create a patient, preserve medical/biological history, assemble longitudinal context, investigate against permitted scientific evidence, and present a reviewable patient-specific worksheet. First-party EHR/LIS/PACS/genomics operations enrich the same context; they are not prerequisites to starting this experience. This aligns with the new definitive mandate and resolves the risk of letting operational-domain scaffolding displace the integrated MVP.

The broad first-party destination remains EHR/oncology, LIS/laboratory, pathology, imaging, genomics, therapeutic/pharmacy, care coordination, research and enterprise capabilities. Desktop/laptop and office workstation use is the existing product target. Mobile app work is out of scope in the fetched mission documents.

### H1 technology and scope

Decisions 03, section “H1 build-unblocking decisions,” explicitly records an accepted bounded H1 baseline:

- Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, PostgreSQL 16.
- React, Vite, TypeScript frontend. Next.js excluded.
- Existing stdlib/SQLite synthetic implementation retained as runnable behavior oracle and fallback.
- Existing repo and feat/composer-evidence-slice branch; draft PRs, no automatic merge.
- No vector search in H1: structured/terminology/full-text search with exact source anchors and rights/status controls.
- NCCN metadata/version/links only in H1; content permissions separately required.
- H1 acute clinical alerts excluded; future acute safety work is proposed H2.
- H1 initially reads/reconciles external EHR information; first-party operational EHR/LIS/PACS destination is retained for later domains, with separate write-back/system-of-record decisions.

This is narrower than a production-wide technology ADR. Other sections still call production database, authority, FHIR ownership, model topology and retrieval strategy open. The correct reconciliation is “bounded H1 accepted; production qualification or expanded scope pending,” not “nothing chosen” or “all technology approved.”

### Governance

OI-17 commercial-rights policy remains binding; approved source, dependencies, data, model weights, assets and external content rights are distinct. The docs explicitly reject invented NCCN API/MCP claims as unverified. No clinical-use, real-PHI, model-provider, clinician-signing, trial eligibility or treatment-selection authority follows from the research or a synthetic pass.

## 4. Newest documentation-reported implementation evidence

These are documentation receipts to verify in GitHub now, not independently established current code truth.

Concurrent repository-audit handoff from the lead: main pinned at 24519839aa8ac1ea3aff88a956349ba72798a72a; main remains stdlib Python/SQLite plus vanilla web, and feat/composer-evidence-slice equals main. The six supplied historical clinical PRs remain open drafts; #95 d863bc2dc24dcf0a0b70972594768ebe19cd1d67 is not merged. This is a lead-supplied code receipt, not an additional code verification performed by this documentation audit.

| Area | Latest relevant receipt | Material limitation |
| --- | --- | --- |
| Cross-domain continuity | PR #95, branch integration/patient-ehr-lis-event-spine-20261102; Drive Engineering Progress latest head d863bc2dc24dcf0a0b70972594768ebe19cd1d67; 355/355 local tests, compilation/JS syntax clean | Hosted CI for this new head not yet claimed; draft/unmerged |
| Reused domain code | #95 incorporates original #94 clinical_lab_bridge.py and #124 clinical_source_provenance.py; one CanonicalEHRHost, new ClinicalContinuityView | Preserve upstream ownership; no duplicate host, patient master, clinical belief store or signed assessment |
| Continuity integrity | Source-bound note/lab pointers; checks outbox hashes, event receipts, case/specimen/assay, source version, QC, permission and binding on read; checks permission again after read | Separate SQLite connections, no globally atomic snapshot; no production authority proof |
| Identity conflict | New guard rejects disagreement between identity_case_bindings and adapter_identity_bindings using the qualified source org/system/subject tuple | Permanent identity ownership/migration contract remains open |
| Knowledge context | PR #93 uses CaseStore.state and rights.py, original IDs/hashes/lines/dates, distinct metadata/full-text/model-use permissions; Drive records head aa6d3f21b8d36d9949b66ed13ed34f76dabbd875 with successful historical runs | Does not download external content, invoke AI, license guidelines or provide complete evidence investigation |
| Composer | #68/#72/#83/#90/#91 describe source-bound questions, deterministic calculations, persistent local work, stale state and browser tests | Separate branches; durable runtime/actor policy, combined integration and clinical review remain incomplete |
| UI | PR #64 groups 14 anchors; #48 records source/review state and timeline fixes; UX issue #58 owns navigation/evidence-inspector work | Navigation success is not usability/clinical validation; no verified complete MVP in the docs |
| CI data exclusion | Decisions/roadmap record main commits 51718d1c… (RNA), 24a36d2… (single-cell), 52ea683f… (catalog); #123 additional fixture-only work | Direct legacy path and historical artifacts remain audit item #122; do not inspect/download those artifacts |
| Research branch reconciliation | Drive Engineering Progress says #125 is now stacked on #123 at 95f258de8d75f576787d34738fff133ae0a914e9, adds five research/rights files, no workflow diff | Earlier Notion sections still call #123/#125 competing workflow changes; verify current diff |

The older Gate II receipt uses main 52ea683fbe3537b17a05066dceff2ba01f758c5d and separate branch test counts (#95 326, #94 286, #124 271). Those cannot be added or presented as a single combined pass, and #95's 355-test update supersedes that branch snapshot. Historical supplied PRs #70/#74/#56/#85/#89/#93 remain reference points, not current truth.

Current integration contract URL:
https://github.com/OpenxIntelligence/open-intelligence/blob/integration/patient-ehr-lis-event-spine-20261102/docs/CLINICAL_CONTINUITY_RECONCILIATION_2026-11-02.md

## 5. Concrete conflicts and small in-place fixes

| Priority | Existing target | Observed conflict | Small useful edit |
| --- | --- | --- | --- |
| P0 | Decisions 03 + Identity 00 + Master Atlas | H1 Python/React choice is accepted, but other text says backend/frontend unspecified without distinguishing scope | Add one short current decision table: H1 accepted, production ADR pending, old Next.js proposals superseded |
| P0 | Decisions 03 + Roadmap 12 | Data exclusion policy and main CI removals coexist with later-looking text saying current main still permits manual acquisition and #123 is pending | Mark each checkpoint with inspected SHA/effective status; point current readers to verified main result and #122 without retrieving patient artifacts |
| P0 | Integration 14 + Roadmap 12 + Engineering Drive | Separate Gate II snapshots and older competing #123/#125 claim coexist with newer reconciliation receipts | Put a small current-head status block above history, retaining historical receipts underneath; refresh only after repository verification |
| P0 | Drive OI-27 issue index | Workstream URLs are malformed: /issues/960…969 and /issues/9610…9615 | Replace with verified actual #96–#111 links already present in Notion Roadmap 12 |
| P1 | Drive OI-27 open decisions | Still asks H to confirm Python backend and 10:00 ET fallback after Decisions 03 records both accepted | Mark those as accepted within H1; leave repo restructure/license/other unresolved choices explicitly pending |
| P1 | Team Dashboard Overview/Goals and Research root | Hero copy still says hackathon-built demo, while founder correction says full platform and immediate patient→evidence loop | Rewrite short overview and goals for full mission + current bounded integrated MVP; retain hackathon deadline under separate delivery checkpoint |
| P1 | Vision 01 accepted strategy section | Calls Sid's case “one test input,” conflicting with top-level no-data policy | Replace with “one public workflow-discovery input”; preserve independently authored challenge cases |
| P1 | Research root architecture differences paragraph | Still lists Next.js among live unresolved alternatives | Mark Next.js historical/excluded; link accepted H1 and remaining production ADR scopes |
| P1 | UX 09 | Multiple proposed menus and old 14-anchor baseline references accumulate | Keep one existing candidate task map and one tested MVP journey; attach exact current code/head and measured outcomes once implemented |
| P2 | OI-20 audit | 76 findings include claims such as 56 legacy docs in trash and pending stack choices | Reconcile existing findings rather than create another audit database; confirm retention from metadata before any restoration and avoid patient artifacts |

Do not replace complete documents, erase history, duplicate the roadmap, create new architecture editions, or adopt every proposal merely to clear “open” labels.

## 6. Existing execution roadmap

Notion Roadmap 12 has WS-00 through WS-15 issues #96–#111 and immediate H1 tickets #112–#122. Those were created but documented as unassigned/unimplemented. OI-27 additionally lists WS-16 research; this enumeration mismatch should be explained before claiming a complete dispatch.

Key existing owners:
- #81 integration/Composer contracts.
- #87 cross-domain patient/EHR/LIS integration.
- #92 full patient-data plus lawful evidence intelligence.
- #58 task-first workspace/evidence inspector.
- #59 component integration and commercial-rights comparison.
- #122 historical data acquisition/artifact audit and direct-path retirement.
- #128 public-narrative method-to-capability research.

The accepted planning order is reconciliation → one identity/source contract → source-linked PWM → permitted knowledge → evidence-first investigations → task-first workspace/review → expanded modalities/clinical operations. Research can advance in parallel. Operational milestones are S0 originals/corrections, S1 permitted question/support/counterevidence, S2 targeted stale state, S3 source-bound clinical/LIS pending review, S4 blind specialty/usability evaluation.

A Nov 4 10:00 ET go/no-go and noon freeze appear as H1 hackathon delivery checkpoints, not deadlines for complete clinical software. Verify competition details separately if used; this audit did not research event rules.

## 7. Recommended MVP surfaces and one connected acceptance story

Use the existing UX 09 candidate destinations: Overview, Journey, Record, Investigations, Care & work. They are views over common domain contracts, not five separate apps. Keep patient identity, selected context, source cutoff and actual review state persistent.

1. Patient creation and records intake: canonical opaque patient, explicit patient↔case/source binding, original fictional upload bytes with hash/version, issuer and relevant dates. Conflicting identity or wrong-patient material is quarantined. A fixture seed is not a substitute for a functioning upload path.
2. Patient overview and journey: source-backed current situation, goals/function when actually recorded, material changes, pending/conflicting/unknown data, timeline and specimen/assay context. Preserve source assertion, AI interpretation and clinician decision as separate states.
3. Original-source inspector: one direct action from every material fact to original version/line, correction lineage, event/issued/recorded times and source context. Side-by-side old/new source comparison keeps patient and scroll/focus context.
4. Evidence investigation: start from a selected finding or question; show included/excluded input, source cutoff, permitted evidence versions, supporting and opposing evidence, applicability, gaps and limits. Store the actual run and typed report; no fabricated citations or fake background progress.
5. Human review and report: inspect claim-to-source support, record accept/reject/request-more-information with synthetic authorized actor and rationale, retain report/version/review receipts. No AI promotion into signed clinical facts.
6. Changes and reassessment: add an original fictional amendment, mark only dependent report claims/investigations stale, retain earlier reviewed version, show exactly what changed and the review work now required.

Core acceptance story: create Alpha → upload three independently authored original records → confirm identity/source links and source-backed timeline/PWM → investigate one question with permitted evidence and counterevidence → save sourced report → record human review → upload correction → observe targeted stale/reassessment → switch to Beta and prove isolation.

Useful negative cases: two fictional patients share a local external ID under different issuers; source amendment while a report is being reviewed; wrong specimen/assay; missing versus explicitly negative data; permission revoked before tool/model output; evidence withdrawn or license blocked; retrieval failure; no supported citation; stale report mistaken for current; keyboard/focus and 200% zoom. These test the integrated user's job and consequential failures, not just individual helper functions.

## 8. Genuine unresolved approvals

Existing docs require explicit owner approval before merge and distinguish code review from source-rights and clinical release. Still unresolved at this documentation checkpoint: production canonical patient/source authority and revocation; production storage/tenancy/migrations; cross-store consistency and event-driven invalidation; real identity/consent and clinician authorization; signed review semantics; live source/provider contracts and content rights; model-use and retention terms; clinical intended-use/regulatory/security qualification; independent user/clinical validation.

None of those prevents building the already-authorized independent-fictional-data integrated MVP. No permission should be re-requested merely because an old document still labels the accepted H1 choice or research sequence “proposed.”
