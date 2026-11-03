# Connected patient workflow — bounded integration

Continue the founder-approved records → investigation → review → follow-through → amendment/reassessment milestone. Preserve existing patient, source, evidence, task and review owners. Integrate frozen source-owner branches #175, #161, #197 (which includes #174) without merging or overwriting upstream branches or main.

Approach: source-level reconciliation in one isolated candidate, followed by all original owner suites and original browser journeys plus a new cross-domain two-time-point regression. A replacement platform or parallel state store would discard existing work; concatenating branch test totals would not establish integration.

No real records, live model/service, clinical approval, deployment, new dependency or H1 stack decision. This is a reference-prototype integration, not the production migration. Clinical records and external knowledge authority remain separate; a readable case report cannot claim licensed evidence-export authority. Preserve task completion history, original bytes, source revisions, revocation and restart behavior.

Pin source commits #175 1d5cd0502b5789371165539149dcecad8df5e551; #161 3df25cc417f308f7ea1247962656ffa2afc62d5d; #197 ad9713a443d2fe98e74f7d83605db776571e9929. Downloaded CI source archives are temporary merge checkouts; verify tree/blob equivalence before publication.
