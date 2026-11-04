# Scoped authored-evidence comparison drafts

## Patient-workflow outcome
Keep an unfinished human comparison available after ordinary evidence refresh and workspace navigation, without silently applying it to another question, original, permission declaration or source snapshot. Extend OI-007/008/009/010 on PR #300, exact head `818c67fcb742941fe1588c4ee130ce07e15a814d`, tree `39b897a67da9a212e466c9ff7caf6241a219c980`. The baseline artifact checksum and extracted Git tree were recomputed and checked against the downloaded archive.

## Design
Reuse the existing transient RegistrySession/QuestionEvidenceSession. Keep one immutable, in-memory comparison draft with its exact patient, case, question, source snapshot, preflight, evidence original and rights hashes, evidence key/version, statement line and content class. Inputs stay separate from the durable assessment, report and uncertain-write receipt. No browser persistent storage, backend, new API, migration, dependency or source authority.

The existing React evidence panel currently resets local quotation/rationale whenever loading clears its packet. Move comparison editing only into the existing session. File intake, withdrawal reasons and report-selection controls retain their existing lifetime; this change does not claim to protect every form.

A fresh accepted matching packet enables the draft. Navigation and an in-progress evidence refresh hide its quotation and rationale until reauthorized. Another question or an altered original/source/rights context never inherits it. A dirty draft requires explicit discard before selecting a different comparison. Denied/failed fresh reads, withdrawn content, disconnect, credential change and patient/case resets clear the draft; clearing uncertain server intent remains governed by the existing exact-retry owner. A matching confirmed assessment clears its draft; unknown delivery retains exact request identity and blocks editing/discard/new writes.

## Acceptance
Use real RegistrySession and its real validators with independently authored existing fixture responses. Prove unchanged refresh/navigation retention, no network request during local editing, explicit discard, dirty selection guard, same-selection no-op, new-question mismatch, amended/rights-changed context refusal, denial clearing, late response isolation, exact request/retry identity, confirmed success clearing and malformed edits refused. Preserve all 206 inherited client tests. Extend the existing actual PostgreSQL/browser journey as a hosted acceptance requirement; do not claim it passed without execution.

## Boundaries
Synthetic engineering only; this is an unsaved local draft, not a saved assessment, model output, clinical signoff, permission grant, database migration or full PDF/H1 convergence. Current evidence remains selectable for its existing independently authorized withdrawal path even when stale question context blocks new comparisons. No claims of production readiness or clinical validation. Native repository writes are not exposed in this session; publish no success claims for an unpushed patch.
