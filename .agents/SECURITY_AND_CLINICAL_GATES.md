# Security, clinical, provenance and rights gates

These are engineering controls and stop conditions. They are not a claim of HIPAA compliance, regulatory clearance, clinical validation or capability to process PHI.

## Hard stops — do not proceed
- Any real patient record, PHI, case identifier, clinician private correspondence, secret, or restricted record in public commits, PRs, issues, synthetic fixtures or model/tool inputs. Quarantine and escalate without copying exposure into logs.
- A model answer presented as a clinician-reviewed fact, treatment recommendation, real consent, delegated authority, clinical order, trial eligibility, achieved outcome or authorized safety action.
- An independently chosen patient identity merge, automatic cross-subject binding, undisclosed third-party patient egress, hidden model training or permissions expansion.
- An unreviewed license/terms/asset/weight/terminology dependency or commercial use based solely on a repo license label.
- A destructive clinical schema migration, production integration, deployment, external outreach, or real-world experiment without separately authorized human process.

## Patient/clinical integrity checks
Source/version/lineage, specimen/lesion/assay and dates; case/subject isolation; permissions/consent provenance; revoked and outdated claims; known-at cutoffs; idempotent duplicate receipt; amendment invalidation; explicit abstention; separation between observation, hypothesis, reviewed interpretation, authorization, action and outcome. For patient safety, critical alerts or medication interaction functions require deterministic qualification and clinical review, not agent discretion.

## Privacy and credentials
Least-privilege token per agent; separate synthetic test DB and environment; no privileged production secrets; no generic writable shared workstation; no uncontrolled uploads or telemetry. Local demo localhost binding is not patient-grade authentication. Set log redaction and allowlisted egress before future real-data evaluation; obtain legal, privacy, security and clinical review first.

## Rights and procurement
Founder-approved commercially independent first-party policy governs core selections. Track exact version, code/dependencies, data/weights/terminology, patent/trademark/notice, outbound network and distribution context separately. Unknown/incompatible rights = HOLD. Existing docs/safety-packet and adoption registers are supporting evidence, not blanket license clearance.

## Verification
Synthetic engineering tests can demonstrate software invariants only. Scientific/clinical claims require independent methodology and adjudication; full-patient system claims require actual measured domain coverage. Record what was checked, what was not checked and explicit release status.
