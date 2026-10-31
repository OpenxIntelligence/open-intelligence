# Open Intelligence

**An AI-native oncology intelligence platform.**

Open Intelligence aims to help patients and care teams maintain an evolving understanding of a person's cancer, investigate important questions, and connect new findings to inspectable evidence.

The vision includes longitudinal clinical records, imaging, pathology, molecular and other biological data, specialized AI assistance, and usable patient and physician experiences. Clinical decisions remain with qualified professionals.

Repository context: Meta Global AI Developer Hackathon, Indie track.

## Current status

This repository starts with the product plan, execution backlog, and contributor instructions. It does not yet contain an implemented or clinically validated application. Architecture choices and clinical workflows remain proposals to evaluate.

## Start here

| Document | Purpose |
|---|---|
| [First-principles plan](docs/FIRST_PRINCIPLES_PLAN.md) | Product direction, workflow, architecture, evidence, evaluation, and expansion |
| [Execution backlog](docs/EXECUTION_BACKLOG.csv) | Eighteen bounded work packages with dependencies and acceptance evidence |
| [Contributor instructions](AGENTS.md) | How humans and coding agents should work in this repository |

## First implementation milestone

Build a complete investigation loop using independently authored synthetic records:

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
