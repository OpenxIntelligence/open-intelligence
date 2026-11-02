# PD-01 — First-party clinical encounter and note domain

**Implementation status:** executable first-party domain service, unmerged review branch. The code is not a presentation mock, a simulated report parser, or a hypothetical architecture proposal. It persists operational state in the existing `CaseStore` SQLite database, and it uses the **same** case identity and event ledger as the other Open Intelligence modules. The tests happen to use fictional patient cases, but the implemented state transitions, constraints and transactions are real.

**Clinical and deployment status:** research/engineering use only. The existing `CaseStore` still requires synthetic cases, has no verified clinician IdP or production PEP, no clinical-compliance or security clearance, and serves unauthenticated loopback demonstration routes. The new module is **not** registered on the HTTP demo routes; real patient data must not be submitted. This is one functional domain slice in the larger first-party platform, **not a release-ready EHR**.

## How this integrates with the canonical architecture

- **PD-01 Clinical EHR/EMR:** owns `clinical_encounters`, `clinical_note_headers` and `clinical_note_versions`. It tracks **scheduled → in_progress → completed**, with cancellation, immutable note revisions, an explicit attestation transition and required correction reasons after attestation. An attestation is a **recorded domain action**, not a legally valid e-signature until a verified IdP, signing method, role and policy exist.
- **PF-01/02 Identity, consent and authority:** requires a trusted host-supplied `(actor, patient, action, purpose) -> bool` policy callback on **every** read and write; no policy or policy exception means deny. The current fictional case ID is not a production patient identifier; later platform migration must preserve one canonical patient identity, not create a duplicate patient registry. The authorizer cannot be supplied by an untrusted API client.
- **PF-03/04 Source and Patient World Model:** authored note versions are preserved with their exact UTF-8 content, SHA-256 digest, author, amendment chain and timestamps; this module does not pretend to parse notes into clinical facts. The record/world-model owner must later expose those versions through a first-party provenance contract before AI can treat them as source assertions.
- **PF-06 Events:** the existing `CaseStore._event` is called in the **same ACID SQLite transaction** as domain state changes and idempotency receipts. Events contain patient-scoped opaque IDs, domain transition and actor references, never the note text. Event delivery/relay still needs the platform transactional outbox; an event row is not itself proof of a delivered notification.
- **PF-10 Security/audit:** write replay requires a stable request key; a repeated exact request returns the recorded result, but a reused key with different actor/purpose/operation/payload is rejected. Optimistic revision expectations catch stale encounter or note writes. SQLite triggers forbid UPDATE and DELETE of note-version and command-receipt history. This is integrity evidence, **not** encryption, signature verification, privileged-access logging, HIPAA compliance or legal-retention clearance.

## Owned domain contracts (implemented)

| Operation | Inputs | Boundary and output |
| --- | --- | --- |
| `schedule` | case ID, unique external encounter key, kind, service date, trusted actor/purpose, command ID | Adds a scheduled encounter, revision 1; does not schedule a hospital or send anything |
| `transition` | case, encounter, target, expected revision and authorization | Checks legal edge and optimistic revision; appends event |
| `write_note` | case, encounter, note key, authored content, expected version, optional correction reason | Creates immutable draft history; amendments to attested content require a reason and a new version |
| `attest_note` | case, encounter, note key, expected version and separate `note.attest` authority | Appends attested version, copying the exact draft content, not a replacement; cannot act on cancelled encounter |
| `list_encounters` / `note_history` | case, actor, purpose; optional encounter and note key | Scope checked, including against cross-case ID enumeration; read state from owning tables |

**Supported encounter kinds:** outpatient, inpatient, telehealth, telephone, procedure, other. There is deliberately no medication administration, result release, clinical recommendation, diagnostic inference, billing, appointment communication or health-record sharing in this bounded domain. Those are owned by other products or require new contracts.

## Technical and reproducible test receipts

```bash
PYTHONPATH=src python -m unittest discover -s tests -p test_clinical_encounters.py -v
PYTHONPATH=src python -m unittest discover -s tests -p 'test_*.py'
python -m compileall -q src
node --check web/app.js
```

The 17 new focused test cases validate default-deny authorization, actor/purpose and patient scope, policy errors, identity/command persistence across a real SQLite restart, idempotency and conflict, legal state transitions and lost-update rejection, cancelled encounter write-denial, append-only attestation/corrections with digest integrity, database-level history triggers, absence of note text from shared events, rollback when the event ledger write fails, and cross-patient event safety. **They do not validate a real clinical workflow or real patient record security.** Full-suite and hosted CI evidence must refer to the exact PR head commit and be updated after any change.

## Remaining gates — part of building the real platform

1. **Resolve OI-16 core ADR and source identity migration:** cases currently have a synthetic-only SQLite schema; build a migration to the accepted production canonical OI patient identity and a first-party, migration-managed transactional database. No parallel patient registry.
2. **Trusted workforce authentication and authorization:** verified clinician identity, active care-team relationship, revocable consent, purpose and role policy, mandatory auditing of denied reads/writes, break-glass with after-the-fact review, and verified note signing semantics. Until then, keep this service private and real patient intake off.
3. **Record/source integration:** publish clinician-authored note versions to PF-03/04 as immutable `SourceVersion`s and typed, span-referenced assertions, without copying or silently promoting note text to verified facts. Backfill, amendments and lineage must be tested.
4. **API and application:** expose versioned OpenAPI/FHIR R4 encounter and document contracts only behind an authenticated clinical service; build the actual clinician encounter composer/worklist and note review UI. Do not bind to the current unauthenticated demo handler.
5. **PF-06 delivery and interoperability:** transactional outbox, consumer idempotency, patient/clinical event semantics, external encounter/HL7/FHIR mappings with loss receipts, and functional end-to-end EHR → laboratory → pathology → research journeys (PR #56 LIS work is separate and stacked on identity PR #51/#53).
6. **Safety, legal and assurance:** security threat model, threat-driven tests, legal/regulatory intended-use review, PHI segregation/encryption and retention, backup/restore, operational monitoring, licensing/SBOM, signed clinical policies, clinical validation, and deployment gates. No synthetic test success substitutes for these.

**Relationship to parallel branches:** this PR adds a new first-party PD-01 module and its tests/docs without editing `store.py`, patient identity/adapters, laboratory operations, the user interface, or shared project governance files. It can be code-reviewed separately and rebased into the accepted integrated baseline. There is no Next.js dependency.
