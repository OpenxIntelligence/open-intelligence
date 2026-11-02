# Open Intelligence

**An AI-native, first-party healthcare platform for longitudinal cancer care and biomedical investigation.**

Open Intelligence aims to help patients and care teams maintain an evolving understanding of a person's cancer, investigate important questions, and connect new findings to inspectable evidence.

The accepted full-product mandate includes first-party EHR/EMR, oncology, LIS/laboratory, pathology, imaging/RIS/PACS, genomics, treatment, patient and professional experiences, research, AI/ML intelligence, and enterprise operations. These domains must work together through patient-centered, source-backed records, evidence, controlled intelligence, and appropriate human clinical authority. The current repository is an exploratory software slice, **not** the implementation of those entire products. The full production technology stack remains under evaluation; **Next.js is explicitly excluded** from Open Intelligence by the November 2 founder direction.

Repository context: synthetic demonstration for the Meta Global AI Developer Hackathon. The accepted participant track, team eligibility, and exact submission/video requirements must be confirmed against the official entrant rules; this README is not that confirmation.

## Current status

The repository now contains an **original, local synthetic-only Python/SQLite research prototype**, alongside the product plan and execution backlog. Its bounded case-workspace features include source-preserving report versions, authored findings with source-line references, persistent investigation questions and review drafts, amendment-triggered staleness, an event chronology, fictional evidence/applicability records, and an optional DOI-only bibliographic metadata view. These are demonstration and engineering capabilities, **not a clinically validated application**.

The local prototype has **no real-patient authorization, verified clinician identity, production access control, clinical inference, treatment recommendations, comprehensive EHR interoperability, or licensed full-text literature analysis**. Do not enter actual patient records or treat demo acknowledgments as clinical sign-off. Scientific model and production architecture choices remain under review.

**Engineering verification snapshot — November 2, 2026:** commit [`7626ec8`](https://github.com/OpenxIntelligence/open-intelligence/commit/7626ec8bd91ea7451b042389cb6559339e9f332c) passed [synthetic case-ledger and hosted Chromium CI](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41479806380) and [Crossref contract CI](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41479806510). The recovered CI artifact contained exactly that source SHA and matched the artifact digest published by GitHub; independently reproduced local Python compilation/JS syntax and **48 focused unit/HTTP tests** for timeline, Patient Mission, patient access and rights. The full local suite timed out, and local Chromium did not complete in that container; hosted CI results are separate evidence. Verify the actual newer HEAD and every unmerged PR before integration or release. The [IV-01–03 synthetic evaluation packet (PR #24)](https://github.com/OpenxIntelligence/open-intelligence/pull/24) has since **merged**, but is not an independently completed clinical evaluation.

## Start here

| Document | Purpose |
|---|---|
| [First-principles plan](docs/FIRST_PRINCIPLES_PLAN.md) | Product direction, workflow, architecture, evidence, evaluation, and expansion |
| [Execution backlog](docs/EXECUTION_BACKLOG.csv) | Eighteen bounded work packages with dependencies and acceptance evidence |
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
