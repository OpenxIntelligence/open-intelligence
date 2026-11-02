# Open Intelligence — Case workspace, source review and change impact

**Status:** implementation candidate (draft PR #29), not a new or approved architecture  
**Updated:** 2026-10-31  
**Scope:** original synthetic-only local UI; no PHI, diagnosis, treatment recommendation, physician authentication or regulated clinical-use claim.

## Authority and scope

The existing [first-principles plan](FIRST_PRINCIPLES_PLAN.md), repository `AGENTS.md`, source ledger, source/assessment/investigation contracts and accepted decisions remain authoritative. The uploaded eight-dossier *Synthesis Index* is supporting research, not a vote to replace the architecture or silently settle any of its D1–D17 open decisions. A UI refactoring does not select React/Next.js/Medplum/FHIR backend, licensure, launch disease, patient trust model, or CDS regulatory classification.

## Why this experience matters

The consequential question is not whether a model produces a compelling paragraph, but whether a user can inspect the original support for a statement and recognize when that support changed. Present one case, one source chronology, durable questions, explicit uncertainty, versioned evidence and a visible review path. The same underlying case may eventually support distinct patient and clinician presentations only after authorization, reviewer identity and consent are established.

The local UI should make the following state transitions inspectable:

1. Case source report is received and retained with SHA-256, provenance and declared event/specimen dates.
2. A source-reported finding links to **exact original source version and source line**. The UI uses `textContent`/DOM text nodes; imported source bytes never execute as HTML.
3. A human-authored investigation selects *explicit* current source and evidence versions and saves a dated draft.
4. An amended source retains earlier report bytes. Only impacted dependent investigation snapshots become stale; historical snapshots remain inspectable. An amendment is not automatically a new biological event.
5. The Source Change Explorer pairs the immutable predecessor and successor source versions and offers a read-only side-by-side original-text comparison. It displays saved investigations citing the older version and currently open linked questions. It does **not** decide which text matters clinically or infer progression.
6. The review-attention panel counts **unresolved reopened questions with stale dependent history**, not all stale historical snapshots. After a newly created draft is acknowledged in demo mode, the active work counter clears without erasing stale history or implying credentialed sign-off.

**Terminology discipline:** “Source says” is an attributed statement, not a diagnosis. “Historical stale” means its known basis changed, not that the original report was deleted or proven false. “No unresolved source-change review flagged” does not mean all records are present, the case is complete, or a clinician has reviewed it. Public DOI bibliography metadata is not case-linked evidence appraisal.

## Interaction contract

| Surface | Action | Inspectable receipt | Boundary |
|---|---|---|---|
| Case overview | Switch fictional case | Source and open-question counts bound to case ID | Unsaved narrative must not silently move to another case |
| Chronology | Inspect report event / all versions | Original source versions grouped under one event | No inferred response or disease evolution |
| Source findings | Open source line | Exact version, line and unmodified source text | Certainty is source-reported, not clinically approved |
| Source Change Explorer | Compare original text | Predecessor/successor text and dependent investigation count | No claim of clinical significance |
| Review attention | Inspect reopened work | Distinct unresolved questions; retained historical snapshots | Demo acknowledgment is **not** clinician sign-off |
| Investigation | Save human-authored observations/hypothesis/gaps | Question, source/evidence version IDs, timestamp and status | Hypothesis optional; no model call in this slice |
| Amendment | Invalidate affected snapshots | Old/updated source, stale status, reopened question | No silent overwriting or old-version promotion |

## Test and accessibility acceptance

- Current finding navigates to its exact source line; missing source or missing line fails visibly.
- A fictional source amendment yields one change card with both immutable versions, correct event identity, and preserved previous text.
- All imported report text renders as inert text; no untrusted HTML or executable script.
- Source version comparison is local/case-scoped and does not send clinical content to a third-party endpoint.
- A stale snapshot causes current review attention *while its question is reopened*; a new demo acknowledgment clears attention but preserves original stale snapshots.
- Unrelated fictional cases remain separate, including async requests, dialogs and unsaved drafts.
- 390 px layout has no horizontal page overflow; compare dialog stacks; keyboard focus and native Escape-to-close are covered by browser journey. **Manual screen-reader, focus order, zoom/reflow, contrast and physical-device review remain required.**
- Status, uncertainty and in-progress work are conveyed by words, not color alone.
- Do not claim WCAG 2.2 AA conformance or clinical validation based solely on passing automated checks.

## Research and rights trace

- W3C [WCAG 2.2 Recommendation](https://www.w3.org/TR/WCAG22/) (12 December 2024): target sizes, focus-not-obscured, status semantics and responsive accessibility. Adopt as a test target, not an automatically proven result.
- U.S. FDA [Clinical Decision Support Software final guidance](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software) (January 2026): the interface must not imply that human review or a citation alone determines Non-Device CDS status. Intended-use and legal review are separate work.
- [Open Intelligence Notion product experience specification](https://app.notion.com/p/40a3866f77ef816881beea1863f14f4f): one source-backed case, timeline, review/status and role-specific explanation.
- [Open Intelligence architecture precedence](https://app.notion.com/p/40a3866f77ef8154bf15c7bb53138c9f): complementary research does not replace accepted architecture.
- GitHub predecessor UI candidates [#26](https://github.com/OpenxIntelligence/open-intelligence/pull/26) and [#27](https://github.com/OpenxIntelligence/open-intelligence/pull/27); consolidated review candidate [#29](https://github.com/OpenxIntelligence/open-intelligence/pull/29).

No third-party software, fonts, icons, clinical terminology or scientific full text has been imported for this change. The project distribution license remains undecided; original source and design changes do not resolve distribution rights for unrelated dependencies.

## Next bounded improvements — research proposals, not implemented here

1. Compare which specific **source lines** differ across revisions, with bounded memory and explicit non-interpretive labelling; do not auto-reconcile clinical meaning.
2. Add a case-specific *missing source/requested/received/unreadable* checklist backed by explicit recorded expectations. Never turn “no known gap” into “nothing missing.”
3. Measure reviewer effort and error detection with an independent fictional-case control: preparation time, source-opening steps, correction detection, false alarms, and reviewer comprehension. Keep genuine blinded validation separate from the public practice packet.
4. Establish consent, identity, reviewer permissions and patient-vs-clinician presentations before any real-data workflow.
5. Evaluate the newly proposed patient question, gap-chasing, meeting and review queues for *net workload*, not merely additional notifications or automation counts. Avoid a second unbudgeted inbox.

**No deployment, real-data use, legal clearance, clinician sign-off, clinical efficacy or new architecture is implied by this document.**
