# Open Intelligence

**A patient-centered, clinically governed healthcare intelligence and operations platform, initially focused on oncology.**

Open Intelligence aims to help patients and care teams maintain an evolving understanding of a person's cancer, investigate important questions, and connect new findings to inspectable evidence.

The destination is a complete first-party healthcare ecosystem: EHR, oncology, laboratory, pathology, imaging/PACS, genomics, pharmacy, research, care coordination and institutional operations. Its first connected experience helps patients and authorized professionals organize information, investigate questions, inspect evidence, review interpretations and follow agreed work through to outcomes. Clinical authority remains with qualified professionals.

**Founding clarification — 2 November 2026:** Sid Sijbrandij's public narrative is one source of workflow requirements. His medical data is not a platform input, engineering dependency or evaluation corpus. There is no manual or ethics-note opt-in exception. All current engineering and evaluation uses independently authored synthetic patients; the capability we build must generalize across people, cancers and care circumstances. See [the existing plan](docs/FIRST_PRINCIPLES_PLAN.md) and [the data-boundary work package](docs/engineering/PATIENT_DATA_CI_BOUNDARY_2026-11-02.md).

Repository context: Meta Global AI Developer Hackathon, Indie track.

## Current status

The repository now contains an **original, local synthetic-only Python/SQLite research prototype**, alongside the product plan and execution backlog. Its bounded case-workspace features include source-preserving report versions, authored findings with source-line references, persistent investigation questions and review drafts, amendment-triggered staleness, an event chronology, fictional evidence/applicability records, and an optional DOI-only bibliographic metadata view. These are demonstration and engineering capabilities, **not a clinically validated application**.

The local prototype has **no real-patient authorization, verified clinician identity, production access control, clinical inference, treatment recommendations, comprehensive EHR interoperability, or licensed full-text literature analysis**. Do not enter actual patient records or treat demo acknowledgments as clinical sign-off. Scientific model and production architecture choices remain under review.

**Inspected main baseline (2 November 2026):** commit [`52ea683`](https://github.com/OpenxIntelligence/open-intelligence/commit/52ea683fbe3537b17a05066dceff2ba01f758c5d). The application baseline ran 236 synthetic tests successfully during this audit. Current implementation, proposed changes, unmerged domain work and verification limits are distinguished in [implementation status](docs/IMPLEMENTATION_STATUS.md). Test success is not independent clinical validation.

**Bounded implementation target:** Python/FastAPI/PostgreSQL with React/Vite/TypeScript; Next.js is excluded. This is the selected migration target, not the stack of the existing Python/SQLite prototype.

**H1 patient identity integration candidate:** [apps/api](apps/api/README.md)
connects the existing canonical patient registry to FastAPI/PostgreSQL 16.
Explicit migrations, idempotent synthetic creation, exact-patient/organization
read checks and immutable creation receipts/events are implemented. The default
denies patient access; the opt-in credential file is a synthetic fixture, not
account verification or clinical consent. This unmerged integration preserves
source owners #85/#148 and is stacked on #162/#137. Local verification passed
49 API/migration/gate tests and 245 prototype tests; hosted container/recovery
evidence belongs to the exact draft-PR head. Those counts describe the historical
identity milestone, before the subsequent connected workspace.

**Current unmerged H1 continuation:** [draft #307](https://github.com/OpenxIntelligence/open-intelligence/pull/307)
converges #298's metadata citations and follow-through with #300's case-owned
fictional originals, human-authored comparisons and immutable reports on the same
canonical question. Both rights boundaries and migration histories remain intact.
Its [bounded convergence and verification record](docs/engineering/H1_EVIDENCE_CONTINUITY.md)
distinguishes implementation, exact combined test evidence and remaining work.
Live biomedical retrieval, model execution, professional review, clinical/PDF/
annotation parity and production identity remain separate capabilities. This is
an unmerged engineering candidate, with no clinical approval or deployment claim.

## Start here

| Document | Purpose |
|---|---|
| [First-principles plan](docs/FIRST_PRINCIPLES_PLAN.md) | Product direction, workflow, architecture, evidence, evaluation, and expansion |
| [Execution backlog](docs/EXECUTION_BACKLOG.csv) | Bounded work packages with dependencies and acceptance evidence |
| [Contributor instructions](AGENTS.md) | How humans and coding agents should work in this repository |

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
- Document third-party permissions, exact versions, and applicable obligations before integration. A promising repository license does not clear its dependencies, data, models, or services.
- Distinguish proposed capabilities, implemented behavior, test evidence, and clinical validation.
- Evaluate the complete workflow against manual and simpler software approaches. Count total acquisition, preparation, review, and correction effort.
- Keep specialist modalities extensible, and qualify each analysis or research function for its intended use.

## Licensing

The project's distribution license has not yet been selected. This initial foundation includes original project documentation and references to external sources; it does not vendor their code or datasets. A project license and any third-party notices will be added through an explicit licensing decision.

## Run the source-ledger prototype

See [README_IMPLEMENTATION.md](README_IMPLEMENTATION.md) for local setup, supported synthetic report format, tests, and explicit limitations. The first code slice is a local demonstration, not a deployable clinical application.
