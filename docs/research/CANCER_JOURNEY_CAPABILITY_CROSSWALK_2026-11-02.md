# Patient-journey research → capability crosswalk (Wave 1, 2026-11-02)

**Status: research-to-requirements proposal, not clinical evidence, dataset ingestion, or a new Open Intelligence architecture.** This adds to the existing patient/clinician context, first-party healthcare modules, Patient World Model, evidence/Composer, and care navigation. The individuals and programs below are publicly described examples. No medical/genomic record, image, transcript, timeline, sample or other person-specific dataset is acquired or stored.

## Research method and limitations

Use first-person, treating-center, government, clinical research organization and patient-support primary sources for **workflow observations**, distinguishing observed activity from proposed software responses. A survivor's outcome is not proof that any trial, research method, or software caused that outcome. Selection is deliberately heterogeneous but **not** statistically representative; these are self-selected public narratives, including positive outcomes, recurrences, uncertainty and access barriers. Do not use any source story for model training, patient matching, actual diagnosis, simulated clinical outcomes or automated treatment recommendations.

| Case or source (source link) | Documented workflow / situation | Observed problem (source-grounded) | Proposed Open Intelligence capability — not a claim of implemented software |
|---|---|---|---|
| Kathy Giusti — [MMRF founder biography](https://themmrf.org/about/board-of-directors/kathy-giusti/), [NCI CoMMpass overview](https://gdc.cancer.gov/about-gdc/contributed-genomic-data-cancer-research/foundation-medicine/multiple-myeloma-research-foundation-mmrf) | Multiple myeloma survivor organizing research partnerships, data/registry programs, precision-medicine and clinical-trial collaborations | Research, molecular data and specialists are fragmented; an individual cannot normally build an MMRF-like program | `CJ-05` molecular context; `CJ-07` evidence and trial research; `CJ-10` voluntary research partnership and consent |
| Emily Whitehead and family — [CHOP account](https://www.chop.edu/stories/relapsed-leukemia-emilys-story), [family foundation](https://www.emilywhiteheadfoundation.org/our-cause/) | Pediatric relapsed acute lymphoblastic leukemia; family consulted specialist clinicians about an experimental CAR-T trial; serious treatment complication | Caregiver authority, trial eligibility questions, risk discussions and specialist communication are essential | `CJ-08` trial *screening preparation*, `CJ-09` caregiver/proxy role, `CJ-12` time-bound risk/uncertainty, `CJ-13` complication tracking |
| T.J. Sharpe — [Cancer Research Institute story](https://www.cancerresearch.org/stories/patients/t-j-sharpe) | Metastatic melanoma; patient explored immunotherapy options and participated in two clinical trials | Trial navigation and patient questions require considerable effort and coordination | `CJ-07` evidence review, `CJ-08` trial workflow, `CJ-11` referral/second-opinion coordination. No inference that enrollment was broadly appropriate |
| Jen (public self-written rare-brain-tumor account) — [NCI](https://www.cancer.gov/rare-brain-spine-tumor/blog/2023/finding-a-good-medical-team) | Recurrent ependymoma, repeated surgery and eventual specialized NCI-CONNECT consultation | Rare-disease expertise and a long-term care history are hard to navigate | `CJ-03` episodic disease timeline, `CJ-11` referral/specialist packet, `CJ-14` recurrence and survivorship longitudinality |
| Darien (public rare-tumor account) — [NCI](https://www.cancer.gov/rare-brain-spine-tumor/blog/2019/pxa-survivor) | Brain tumor initially considered more aggressive; later corrected rare-tumor classification altered his understanding | Diagnostic revisions can fundamentally change the interpretation of historical records | `CJ-04` amendable diagnosis/staging and uncertainty, `CJ-06` contradictory source resolution, `CJ-15` invalidation of derived conclusions |
| Suleika Jaouad — [her published biography](https://www.suleikajaouad.com/about) | Leukemia, survivorship and recurrence; communication, creativity, social participation and health-system engagement | The lived experience, repeated transitions and emotional burdens are not fully represented by diagnostic codes | `CJ-02` goals, symptoms and lived experience; `CJ-09` family/caregiver dialogue; `CJ-14` long-term survivorship and recurrence context |
| Benetta — [CancerCare case account](https://www.cancercare.org/benetta2026) | Stage IV metastatic breast cancer with loss of employment and financial stress; support and financial assistance grant | Ability to continue planned care depends on practical financial assistance as well as medical facts | `CJ-16` affordability/benefit-navigation, `CJ-17` referrals and practical follow-through. Do not assume this story describes every low-income patient's experience |
| Patient-partnered collective — [Count Me In](https://joincountmein.org/about-us) | Patients with multiple cancers contribute experiences to research partnerships, including the Metastatic Breast Cancer and Angiosarcoma projects | Patient contributions and research access need governance and clear participation boundaries | `CJ-10` opt-in research pathway, consent scopes, audit and withdrawal; **a program, not one individual's case** |
| Underserved and rural navigation needs — [President's Cancer Panel report](https://prescancerpanel.cancer.gov/reports-meetings/enhancing-patient-navigation-2024/executive-summary), [NCI rare/rural navigation trial](https://www.cancer.gov/research/participate/clinical-trials-search/v?id=NCI-2025-08365) | Published evidence and navigation studies identify geographic, language, transport, financial, health-literacy and technology-access barriers | Technology can add barriers unless workflows support human navigation, alternative channels and reasonable cost | `CJ-16` practical support, `CJ-18` inclusive low-bandwidth/multilingual accessible interface, `CJ-19` human navigator handoff; **group evidence, not a patient narrative** |

## Capability registry — proposed requirements, not implemented-status claims

| ID | First-party capability | Operational contract / acceptance |
|---|---|---|
| CJ-01 | Governed canonical patient identity, consent and relationships | Purpose-scoped access; distinguish verified patient/person matching from synthetic IDs; no implicit match |
| CJ-02 | Patient goals, preferences, symptoms, functional status | Patient-authored vs clinician-authored facts separated; uncertainty and timestamps retained |
| CJ-03 | Disease episodes and temporal history | Encounter, episode, specimen, source and occurrence/recorded dates remain distinct |
| CJ-04 | Diagnosis/classification/staging with revision history | Amendments do not silently rewrite original status; require review on contradictions |
| CJ-05 | Pathology, imaging, molecular, genomics context | Normalize with raw source/version references, assay methodology and reference build |
| CJ-06 | Contradictions and missing-information worklist | Support/contradiction/missingness separated; requests do not turn into results |
| CJ-07 | Rights-qualified biomedical evidence and guideline links | License/model-processing rights checked per source; versioned citations and opposing evidence |
| CJ-08 | Clinical trial discovery and inquiry preparation | Trial metadata/freshness/criterion uncertainty shown; no invented eligibility |
| CJ-09 | Caregiver/proxy and multidisciplinary collaboration | Delegated scope with reviewable revocation; minors and caregiver authority explicitly modeled |
| CJ-10 | Research participation and specimen/data opt-in | Distinct research consent, ethics authority and purpose; no open-publication license assumed to authorize PHI |
| CJ-11 | Second-opinion and specialist handoff | Durable source-backed packet, questions, referral status and responsible owner |
| CJ-12 | Clinical risk/uncertainty communication | Clinical safety escalation through authorized professionals; no unsupported recommendations |
| CJ-13 | Therapy and side-effect follow-up | Record prescribed/planned vs administered vs observed outcomes distinctly |
| CJ-14 | Survivorship, recurrence, transition and supportive care | Longitudinal reassessment and transitions, not one-off diagnosis search |
| CJ-15 | Amendment-triggered derivative invalidation | If a source changes after a prior world-model projection, mark dependents stale and reopen review |
| CJ-16 | Financial, travel, access and affordability navigation | Resource and assistance information with verified currency, geography and eligibility caveats |
| CJ-17 | Action coordination and accountability | Owner, authority, required input, last verified status, review date and next step |
| CJ-18 | Inclusive UI and low-noise reading | Accessibility, plain-language explanation, multilingual and low-bandwidth options |
| CJ-19 | Human navigator escalation | Preserve human contact options; technology use never prerequisite for care |

## Journey coverage map

| Stage | Must answer from the same governed patient context | Initial proof target |
|---|---|---|
| Initial concern / diagnosis | What tests exist? What is provisional? What is missing? | Source import → diagnosis and pathology timeline with uncertainty |
| Characterization | What do pathology, imaging, molecular tests actually show? | Specimen-qualified source/assay mapping and provenance |
| Investigation | What questions remain? Which sources support or contradict? | Rights-qualified literature/trial evidence with source receipts |
| Specialist consultation | What to ask, what changed, who decides? | Export source-backed case packet and pending professional review |
| Treatment coordination | What is planned vs authorized vs administered? | Authorization and real workflow-state separation |
| Follow-up / progression | Which measured changes and source amendments matter? | Revision-aware Patient World Model + stale dependency propagation |
| Survivorship / supportive care | What functional, psychosocial, access or family issues remain? | Goals, navigator handoff and task ownership |

## Engineering reconciliation (2 Nov 2026)

**Already implemented or in reviewed candidates:** Synthetic source ledger and rights constructs on `main`; canonical patient + EHR + outbox [#89](https://github.com/OpenxIntelligence/open-intelligence/pull/89); laboratory release → pending-review integration [#94](https://github.com/OpenxIntelligence/open-intelligence/pull/94), alongside overlapping [#95](https://github.com/OpenxIntelligence/open-intelligence/pull/95); version-bound Composer proposals and staleness in [#68](https://github.com/OpenxIntelligence/open-intelligence/pull/68) and [#91](https://github.com/OpenxIntelligence/open-intelligence/pull/91). These open PRs are **not merged production capabilities**.

**Not established:** verified identity and consent, real medical records/PHI, trained or validated AI oncology inference, patient-goal assessment, caregiver authorization, multidisciplinary clinical review, travel/financial navigation, production authentication, full PACS/genomics service, validated real-world clinical outcome improvement.

**Next vertical slice (proposed):** one fully fictional patient with two institutional sources and one actual specimen → one conflicting/corrected report → one rights-permitted evidence query → one review-pending investigation and named review owner → amended source invalidates dependent investigation. Link to [#92](https://github.com/OpenxIntelligence/open-intelligence/issues/92), [#87](https://github.com/OpenxIntelligence/open-intelligence/issues/87) and program [#96–#111](https://github.com/OpenxIntelligence/open-intelligence/issues/96) rather than duplicating architecture.

## Permanent privacy boundary

These public stories are for **product discovery only**. No public person's individual clinical report, laboratory/genomic dataset, research object, consent record, imaging, personal narrative transcript or digital identity enters Open Intelligence development fixtures or training by default. All executable fixtures are independently authored and fictional; patients' own words are not copied into prompts or benchmarks. Source links here are research citations, **not** patient-data licenses. Study negative, inaccessible and inconclusive journeys alongside public success narratives.
