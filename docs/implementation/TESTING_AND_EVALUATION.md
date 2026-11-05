# Testing and evaluation

Every result belongs to a specific source tree and environment. Use independently authored fictional fixtures, persist failed results, and retain the source commit, dependency receipts and test command. The [implementation status](IMPLEMENTATION_STATUS.md) names the tested versions and distinguishes local limitations from hosted qualification.

| Layer | Run or inspect | Failure modes that matter |
|---|---|---|
| Package inputs | [Wheel gate](../../apps/api/tools/check_dependencies.py), npm rights script, combined verifier below | Changed artifact/hash, undeclared source, missing embedded license evidence, alias substitution, altered notice or optional package presented as inspected. |
| Reference behavior | `PYTHONPATH=src python -m unittest discover -s tests` and `node --test tests/*.js` | Source identity and version, historical evidence, cross-case isolation, pending vs negative, scoped reviews and source-linked hypotheses. This suite is distinct from connected H1. |
| H1 API and migrations | `PYTHONPATH=apps/api/src:src python -m unittest discover -s apps/api/tests`. Use [the workflow](../../.github/workflows/h1-api.yml) and its disposable PostgreSQL settings for full acceptance. | Registration and permission changes, access revocation after preparing a response, clean and populated upgrade, duplicate command with changed intent, stale anchor, forced failure with no partial commit, concurrent writers and actual retry. |
| Admission | [Request policy tests](../../apps/api/tests/test_patient_command_admission.py) and [existing body tests](../../apps/api/tests/test_manual_passage_ingress.py) | New patient routes get the fallback, exact larger uploads retain their transport, unrelated paths and verbs get no allowance, bad length rejected, chunked oversize never reaches parser, real HTTP returns 429 and tells caller when to retry. Reads and health stay accessible. |
| Browser and integration | `npm --prefix apps/web test`, `npm --prefix apps/web run build`, [connected browser and demo](../../.github/workflows/h1-web.yml) | Real API and compiled UI agree on patient, original, question, evidence and follow-through; reopened chart after mutation, amendment and revocation retains correct history. |
| Recovery | Seven Compose probes in H1 API CI, from registry through [evidence recovery](../../apps/api/tools/verify_evidence_compose.py) | Restore a populated database, read original bytes, deny revoked access, retry and make a new write on the restore. Confirm production-style RPO/RTO only in a separately accepted environment. |
| Standards | [Bounded lab parser](../../apps/api/src/oi_api/laboratory_fhir_r4.py), [lab recovery](../../apps/api/tools/verify_fhir_laboratory_compose.py); then test versioned profiles independently | Distinguish an unsupported but valid FHIR resource from a malformed resource or unauthorized subject. Qualify mCODE, SMART, HL7 v2 and DICOMweb individually. |
| Clinical and scientific | [Independent evaluation](../INDEPENDENT_EVALUATION_COLLABORATION.md), [clinical model contract](CLINICAL_DATA_MODEL.md), [AI](AI_PLATFORM_ARCHITECTURE.md), [scientific workflow](BIOINFORMATICS_ARCHITECTURE.md) | Freeze intended use and adjudicated references before evaluating. Report critical omission/harmful assertion or wrong-subject/therapy separately from ordinary software errors; count abstentions, denominator, subgroup and reviewer disagreements. Reproduce scientific outputs with pinned inputs/QC. |

## Verify the combined synthetic build inventory

Run from the repository root after the approved acquisition process has prepared runtime wheels and the web install. Substitute local paths as necessary. For initial setup, use the existing [H1 demo guide](../H1_DEMO.md).

```sh
python apps/api/tools/check_dependencies.py --wheel-dir /tmp/oi-h1-wheels --sbom /tmp/oi-h1-sbom.json
npm --prefix apps/web run rights
python tools/h1_build_inputs.py --output /tmp/oi-h1-build-inputs.json
python tools/h1_build_inputs.py --verify /tmp/oi-h1-build-inputs.json \
  --api-sbom /tmp/oi-h1-sbom.json --web-receipt apps/web/.licenses/inventory.json
```

Keep the original receipts alongside the combined JSON. To reproduce its deterministic bytes, rerun the generator against the same checkout. A successful package check or generated clinical answer is not a validation result. A missing PostgreSQL service, denied Unix socket or skipped dependency is a named test limitation.
