# Open Intelligence

**A patient-centered cancer-care and biomedical intelligence platform.**

Open Intelligence aims to help patients and care teams maintain an evolving understanding of a person's cancer, investigate important questions, and connect new findings to inspectable evidence.

The vision includes longitudinal clinical records, imaging, pathology, molecular and other biological data, specialized AI assistance, patient and clinician workspaces, caregiver collaboration, practical care navigation, and progressively connected first-party clinical operations. The differentiator is their shared patient identity, source-linked understanding, evidence and review history. Clinical decisions remain with qualified professionals.

The repository includes work prepared for the Meta Global AI Developer Hackathon, Indie track. That submission context does not define or limit the product's long-term scope.

## Current status

The repository now contains an **original, local synthetic-only Python/SQLite research prototype**, alongside the product plan and execution backlog. Its bounded case-workspace features include source-preserving report versions, authored findings with source-line references, persistent investigation questions and review drafts, amendment-triggered staleness, an event chronology, fictional evidence/applicability records, and an optional DOI-only bibliographic metadata view. These are demonstration and engineering capabilities, **not a clinically validated application**.

The local prototype has **no real-patient authorization, verified clinician identity, production access control, clinical inference, treatment recommendations, comprehensive EHR interoperability, or licensed full-text literature analysis**. Do not enter actual patient records or treat demo acknowledgments as clinical sign-off. Scientific model and production architecture choices remain under review.

**Audited main baseline (2 November 2026):** commit [`24519839`](https://github.com/OpenxIntelligence/open-intelligence/commit/24519839aa8ac1ea3aff88a956349ba72798a72a), with 236 Python tests independently executed locally. Hosted [synthetic application CI](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41510591184) and [Crossref CI](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41510591705) succeeded; the single-cell workflow had a separate failure, so this is not a claim that all main CI passed. The [execution audit](docs/engineering/EXECUTION_AUDIT_2026-11-02.md) records the candidate integration, research, safety findings, exact source-owner PRs and remaining gaps. Candidate tests do not establish that those changes are merged or deployed.

The accepted bounded H1 target is Python/FastAPI/PostgreSQL 16 and React/Vite/TypeScript. Current main still runs the stdlib/SQLite reference implementation. Next.js is excluded. Preserve the existing identity, source, evidence and authority contracts while moving the connected workflow to that target.

## Start here

| Document | Purpose |
|---|---|
| [First-principles plan](docs/FIRST_PRINCIPLES_PLAN.md) | Product direction, workflow, architecture, evidence, evaluation, and expansion |
| [Execution backlog](docs/EXECUTION_BACKLOG.csv) | Eighteen bounded work packages with dependencies and acceptance evidence |
| [Contributor instructions](AGENTS.md) | How humans and coding agents should work in this repository |
| [Execution audit and MVP sequence](docs/engineering/EXECUTION_AUDIT_2026-11-02.md) | Verified repository state, preserved work, capability map, review handoff and remaining acceptance gates |
| [Biomedical access atlas](docs/research/BIOMEDICAL_ACCESS_ATLAS_2026-11-02.md) | Official access routes, operation-specific rights and unresolved licensing |
| [Technology verification appendix](docs/research/TECHNOLOGY_ATLAS_VERIFICATION_2026-11-02.md) | Exact source/license receipts, shortlist and legal-risk distinctions |
| [Patient journey research](docs/research/PATIENT_JOURNEY_RESEARCH_2026-11-02.md) | Public workflow narratives and generalizable capability hypotheses |

## Investigation workflow under development

The current synthetic-only demonstration exercises a bounded portion of the intended investigation loop. These are requirements for subsequent independent evaluation and controlled expansion, not claims that full clinical workflows have been established:

1. Import source documents and preserve their identity, original bytes, and versions.
2. Persist source-linked assertions, uncertainty, questions, and scoped review decisions.
3. Connect one question to permitted evidence whose content and limits can be inspected.
4. Produce a dated brief with source links and review status.
5. Receive an amended report, identify affected conclusions, preserve history, and prepare a reviewable update.

An incoming amendment marks affected outputs as requiring review. It does not automatically promote a replacement interpretation into a reviewed clinical conclusion.

## Development boundaries

- Use independently authored synthetic patient examples. Keep real patient records, credentials, and restricted clinical content out of this repository and its issues.
- Sid Sijbrandij and other public patient narratives inform workflow discovery only. Do not acquire or use their medical data, or derive synthetic fixtures from it. See [the method-reference boundary](docs/METHOD_REFERENCE_NOT_CASE_DATA.md).
- Document third-party permissions, exact versions, and applicable obligations before integration. A promising repository license does not clear its dependencies, data, models, or services.
- Distinguish proposed capabilities, implemented behavior, test evidence, and clinical validation.
- Evaluate the complete workflow against manual and simpler software approaches. Count total acquisition, preparation, review, and correction effort.
- Keep specialist modalities extensible, and qualify each analysis or research function for its intended use.

## Licensing

The project's distribution license has not yet been selected. This initial foundation includes original project documentation and references to external sources; it does not vendor their code or datasets. A project license and any third-party notices will be added through an explicit licensing decision.

## Run the source-ledger prototype

See [README_IMPLEMENTATION.md](README_IMPLEMENTATION.md) for local setup, supported synthetic report format, tests, and explicit limitations. The first code slice is a local demonstration, not a deployable clinical application.
