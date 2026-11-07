# Semantic contract integration gate — issue #604

Status: **draft contract review**, not an accepted schema or an implemented connected workflow.

## Precedence and existing owners

The connected H1 application uses the existing FastAPI/PostgreSQL patient, source, question, evidence, report, review and task owners (see `apps/api/README.md` and `docs/engineering/H1_ACCEPTED_DEMO_CONVERGENCE.md`). The Python/SQLite application is a separate reference. Never create another canonical source ledger or patient registry.

The **OI-35 Patient World Model and Canonical Data Model** document already proposes a patient-scoped append-only PostgreSQL record envelope, typed extensions, patient edges, epistemic classes and valid/documented/system time. OI-35 remains **proposed** pending its stated spike and decision gate. This PR cannot silently adopt it, rename its concepts or install a second competing model.

[OI-35 source](https://docs.google.com/document/d/1fZM4TA7cF9-gQkwVV3MLT0PmIRz8wwQiEOzHN_gLvOE/edit) · [Notion architecture decision record](https://app.notion.com/p/40a3866f77ef8122b08bcdc16de89876) · [Mathematical/ontology discussion](https://app.notion.com/p/40a3866f77ef81e0a9e9c1a96773f8b9)

## What the prototype does and does not mean

`src/open_intelligence/semantic_contract.py` currently implements **in-memory shape validation only**. Its `Concept`, `Relationship` and `SemanticReference` names are provisional validation vocabulary, not new authoritative persistence entities. The `owner`, `record_id`, `source_version_id` strings are not resolved against PostgreSQL, grants or original hashes. A validated edge does not establish that either record exists, shares patient scope, has compatible event times or is readable by the actor.

The `knowledge_kind` values are **not** the full OI-35 epistemic model: `observed`/`reported`/`inferred`/`calculated`/`hypothesis` cannot substitute for OI-35's separately defined record class, certainty state/basis, model confidence, source grade, review state and lifecycle. Likewise `evidence_status` does not capture every laboratory absence reason, uncertainty or contradiction. Do not map those fields one-to-one without an explicit versioned, lossless mapping decision.

## Required owner crosswalk before a schema/API change

| Question | Existing owner / review |
| --- | --- |
| What identifies patient, case, observation and source version? | Connected H1 patient/source registry and OI-35 proposal; use owner-issued IDs |
| Who controls access to original vs projection, evidence and task? | Existing H1 grants/consent/authority boundaries; check on every read/action |
| What is reported vs clinically verified? | Existing source/review contracts and OI-35 epistemic model; do not infer review from `knowledge_kind` |
| How are valid, documented, received and as-of time represented? | Existing source timestamps; OI-35 three-clock proposal; never infer as-of from event date |
| What owns source amendment and dependent stale state? | OI-006/009 and current source/question/report/task owners; no separate graph truth |
| What owns AI/model writes and evaluation? | Existing `agent_writes.py` and `evaluation.py`; no new parallel run ledger |
| What owns terminology and unit mappings? | Existing modality/source import contracts and reviewed mappings; unsupported values must fail closed |

## Acceptance gates for next implementation

1. Inventory exact tables, routes, grants, migrations and domain services on **current main**, and reconcile with concurrent PRs.
2. Agree a non-lossy mapping from existing record types to the semantic registry; document OI-35 compatibility explicitly.
3. Verify patient/case isolation, original-version provenance, unit and terminology semantics and actor permissions **outside** the pure validator.
4. Build one fictional source -> question -> synthetic calculation -> proposed task, then amend the source and mark **only dependent** results stale.
5. Test historical as-of replay, out-of-order events, duplicates/retries, denial/revocation and backup/restore on exact candidate head.
6. Record test and CI receipts for this PR's head; no promotion from draft based on tests of ancestor commits.

## Parallel research track

The AutoResearch KL objective-verification harness is a separate bounded deliverable: exact enumeration, finite differences, sampling-distribution/importance-weight/stop-gradient checks, and token-versus-sequence estimands. It should reuse existing model-run/evaluation ontology, not invent a training-results authority.

No patient data, clinical model, new database, runtime dependency or permission elevation is authorized by this document.
