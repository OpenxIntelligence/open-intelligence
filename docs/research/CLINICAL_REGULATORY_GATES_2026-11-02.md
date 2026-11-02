# Clinical, privacy and regulatory launch gates

**Checked: 2 November 2026. Scope:** patient-facing oncology records and evidence investigations. This is a decision brief, not a device determination or legal opinion. Continue independent synthetic development; use no actual patient records for development, tests or evaluation. Passing engineering tests does not establish clinical validity, regulatory authorization or privacy compliance.

## Current US decision boundary

FDA's **29 January 2026** final CDS guidance expressly supersedes its **6 January 2026** version. The statutory non-device CDS exclusion requires all four criteria: no analysis of medical images/IVD signals/acquisition-system patterns; use of medical information; recommendations to a **healthcare professional**; and a basis that the professional can independently review without primarily relying on the recommendation. Patient/caregiver functions do not inherit this HCP exclusion.[1]

Failure to meet that exclusion does **not** alone establish that a function is a regulated device: assess the device definition, other exclusions, applicable guidance and any enforcement-discretion policy separately. FDA also distinguishes time-critical recommendations from merely displaying information in urgent settings.[2] A citation, disclaimer or clinician-review button is not evidence that these conditions are satisfied.

## Functional claims and proposed release dispositions

The risks and evidence below are our product assessment; the dispositions are proposed internal launch gates, not assertions that every listed measure is legally mandated.

| Functional claim | Evidence to establish; material risks | Required professional disposition before patient release |
|---|---|---|
| **Record organizer** | Demonstrate correct patient/document association, chronology, units, provenance and amendments. Missing or misattributed records can mislead. FDA distinguishes sole storage/transfer/display from interpretation.[3] | Product and clinical safety owners approve the exact organizing/display claim and correction workflow; regulatory lead assesses any summarization or interpretation separately. |
| **Evidence retrieval** | Verify retrieval relevance, citation fidelity, source date/version and permitted reuse. Published evidence may be inapplicable to the person's cancer, treatment history or setting. | Evidence owner approves source and update policy; oncology reviewer approves applicability language; regulatory lead distinguishes information search from clinical recommendations.[1][2] |
| **Personalized ranked treatment hypotheses** | Evaluate unsupported rankings, omissions, contraindications, uncertainty and reliance. Calling a recommendation a “hypothesis” does not resolve its intended-use assessment. | Named oncology and regulatory leads approve intended population, user, decisions influenced, clinical evaluation and applicable pathway before enabling personalized recommendations. Synthetic performance alone is insufficient. |
| **Image or variant analysis** | Distinguish displaying a clinician's report from analyzing images or sequence/VCF patterns. FDA expressly addresses the latter outside CDS criterion 1.[1] Validate relevant input quality, analytical performance and clinical interpretation. | Imaging/genomics specialist and regulatory lead determine device/IVD scope, validation and any authorization route; do not equate report ingestion with validated image/variant interpretation. |
| **Symptom triage** | Assess false reassurance, missed urgency, escalation failures and time to human assistance. Time-critical recommendations undermine independent review.[2] | Clinical safety and regulatory leads approve the triage claim, escalation service, human-factors evidence and pathway. Hold individualized urgency decisions pending this disposition. |

## US privacy depends on relationships and data flows

Health information does not automatically make an app HIPAA-covered. HHS says a patient-directed transfer alone does not create a business-associate relationship; handling PHI on behalf of a covered entity can require a BAA.[4] Map direct-to-consumer and provider-contracted services separately, including model, hosting and support vendors.

Outside HIPAA, FTC Act prohibitions on deceptive/unfair practices still matter. The FTC Health Breach Notification Rule can cover personal-health-record vendors and related services; technical capacity to combine identifiable health information from multiple sources matters. A breach can include unauthorized disclosure, not only intrusion.[5] Privacy counsel should document applicability, advertising/analytics disclosures, consent, vendor restrictions, retention/deletion, incident response and applicable state laws before real-data onboarding. Make no “HIPAA compliant” claim from encryption or a vendor BAA alone.

## If an EU jurisdiction is selected

**MDR/IVDR:** assess each function's intended medical purpose and classification using MDCG 2019-11 **rev.1, June 2025**, including MDR Rule 11 where applicable and IVDR for relevant specimen-derived functions. Deployment in a consumer app does not settle classification.[6]

**AI Act:** medical AI can be high-risk under Article 6(1) where it is a regulated product/safety component and requires third-party conformity assessment.[7] The **27 July 2026 consolidated Act** now schedules Annex I product high-risk requirements for **2 August 2028**, and Annex III requirements for **2 December 2027**. Other obligations, including applicable transparency and AI-literacy rules, have earlier dates; the extension is not a general launch exemption.[8][9] Recheck the exact function and law at release.

**GDPR:** establish an Article 6 basis plus an applicable Article 9 condition for health/genetic data; consent is not a universal substitute for purpose-specific analysis.[10] Determine controller/processor roles, minimization, retention, access/correction/deletion, security, transfers and vendor reuse. Assess automated-decision implications and whether a DPIA is required; processing likely to create high risks requires one before processing, with supervisory consultation for unmitigated high risk.[11]

## Decisions and owners to record before launch

1. **Launch owner:** which countries, US states, populations and distribution channels are authorized initially?
2. **Intended-use owner:** patients, caregivers or professionals; which inputs, outputs and clinical decisions; any diagnosis, therapy ranking or urgent triage? Approve matching UI, marketing and documentation.
3. **Accountable reviewers:** name the oncology clinical safety lead, regulatory professional and privacy/security owners; record each function's signed disposition and unresolved evidence.
4. **Release approver:** approve validation thresholds, source/model change control, monitoring, incident escalation and rollback. Any future real-patient evaluation needs its own privacy and clinical/research-governance approval; it is not authorized by this synthetic-development work.

## Primary official sources

1. [FDA CDS guidance, 29 January 2026](https://www.fda.gov/media/109618/download).
2. [FDA CDS FAQs](https://www.fda.gov/medical-devices/software-medical-device-samd/clinical-decision-support-software-frequently-asked-questions-faqs).
3. [FDA Medical Device Data Systems](https://www.fda.gov/medical-devices/general-hospital-devices-and-supplies/medical-device-data-systems).
4. [HHS: patient-selected apps and business-associate agreements](https://www.hhs.gov/hipaa/for-professionals/faq/does-hipaa-require-a-covered-entity-to-enter-into-a-business-associate-agreement.html).
5. [FTC: Health Breach Notification Rule](https://www.ftc.gov/business-guidance/resources/complying-ftcs-health-breach-notification-rule-0).
6. [MDCG 2019-11 rev.1](https://health.ec.europa.eu/document/download/b45335c5-1679-4c71-a91c-fc7a4d37f12b_en?filename=mdcg_2019_11_en.pdf).
7. [MDCG/AIB 2025-6: MDR/IVDR and AI Act interplay](https://health.ec.europa.eu/system/files/2025-06/mdcg_2025-6_en.pdf).
8. [AI Act consolidated 27 July 2026, Article 113](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A02024R1689-20260727).
9. [European Commission: current AI Act timeline](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai).
10. [European Commission: legal grounds and sensitive data](https://commission.europa.eu/law/law-topic/data-protection/information-business-and-organisations/legal-grounds-processing-data_en).
11. [EDPB: data protection impact assessment](https://www.edpb.europa.eu/topics/accountability-and-compliance-tools/data-protection-impact-assessment_en).
