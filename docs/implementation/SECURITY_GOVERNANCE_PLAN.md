# Security and governance checkpoints

| Boundary | Existing mechanism | Next verification or dependency |
|---|---|---|
| Synthetic identity, organization and patient scope | `apps/api/src/oi_api/access.py`, patient registry and case bindings. The request is scoped to actor, purpose, patient and case. | Negative cross-organization and cross-patient tests. Keep workforce identity, professional credentials, caregiver delegation and purpose-bound real consent blocked pending identity and policy integration. |
| Sensitive read / write | Existing owners recheck grants before sensitive disclosures and commits and record source access, events and command receipts. | For each new episode command, test actor substitution and revocation between preparation and commit. Require rollback of the command, clinical version and event together. Test revocation while preparing a response and after restore. |
| Source integrity and history | `sources.py` and `source_integrity.py` verify immutable version, bytes, scoped identity and line evidence. | Verify amendment staleness, historical reads with current authority, stale retries, and no stale rendering after refresh denial. |
| Research / model egress | The current change reads the authorized fictional source projection only. | Enforce explicit input and destination policy, minimum permitted data, quotas and audit. Keep research models and experimental output outside clinical commands. |
| Operations and production data | Synthetic Compose and restore tooling exercise engineering recovery. | Operational owners must verify encryption and key recovery, secrets rotation, monitoring, tenant isolation, retention/legal hold/correction/deletion, incident response, break-glass review, restore testing and real consent revocation. Evidence and authorization for real patient use are separate release gates. |

Use `test_source_read_authority.py`, `test_projection_authority.py`, `test_original_response_authority.py` and `test_intake_write_authority.py` for existing patterns. No new grants, authentication provider, external data transfer or deployment is part of this increment.
