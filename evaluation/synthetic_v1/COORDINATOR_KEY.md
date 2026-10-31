# Coordinator key — development fixture only

Do not include this file with reviewer packet exports. These expected observations describe source/software behavior, not clinically validated conclusions. Reviewers and thresholds have not been established; this is not a blinded or held-out evaluation.

| Source | Expected software/source disposition |
|---|---|
| S01 | Case A marker X not-assessed; classification indeterminate. Original source retained. |
| S02 | Case A discussion/order is not documented administration; source explicitly negates metastasis. |
| S03 | Case B marker pending, not negative. No new urgency is supported by this authored source; missingness does not prove safety. |
| S04 | Original fictional assay context; it does not establish clinical benefit. |
| S05 | Byte-identical redelivery of S01; importer should detect duplicate, not new biology. |
| S06 | S03 bytes incorrectly routed to A; quarantine, do not create A assertions. |
| S09 | Proposed A correction changes specimen identity; reject as amendment, retain originals. |
| S07 | Valid correction of A specimen/report; negative is now source-reported, dependent drafts stale, no auto-approved replacement. |
| S10 | Explicit fictional assay correction with contrary finding; old linked assessment stale, do not silently apply it to the new version. |
| S08 | Earlier event and issue dates but late simulated availability; excluded from R1/R2 and included at R3. No comparison image means no established progression. |

R1 (May 10 cutoff): S01–S04 only. R2 (May 20): add S05, S06, S09, S07, S10 in arrival order. R3 (May 25): additionally S08. Source-line anchors count from line 1 of each exact UTF-8 source. Case B should remain unchanged by Case A correction.

No claim that source statements reflect medical truth. No survival, response, treatment or eligibility probability is supplied.
