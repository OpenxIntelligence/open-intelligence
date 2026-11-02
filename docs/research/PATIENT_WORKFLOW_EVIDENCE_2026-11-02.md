# Open Intelligence: additive patient-workflow evidence

Research date: 2026-11-02. Integration target: existing `CANCER_JOURNEY_CAPABILITY_CROSSWALK_2026-11-02.md` in PR #125. The existing CJ-01–CJ-19 registry is retained; this memo adds evidence and sharper acceptance criteria, not a second architecture.

## Audit findings that matter

1. **Correct a synthetic-boundary ambiguity.** The existing next-slice sentence says “one fully fictional patient … one actual specimen.” Replace “one actual specimen” with **“one fictional specimen record.”** The rest of that document explicitly requires independently fictional fixtures.
2. **Add journeys ending in death and caregiver bereavement.** The existing table includes recurrence, complications, and uncertainty, but its named examples predominantly describe survivors. Kathy Oliver and Donna M below add important limits to outcome narratives and continuity beyond active treatment.
3. **Make access confirmation a distinct state.** A trial, expert, resource, or assistance program being discoverable does not mean it is reachable, accepting referrals, funded, appropriate, or available to a particular patient. NCI DTC's operational description provides concrete evidence for referral coordination, preliminary review, visit burden, cost limits, and continued local care. [S10]
4. **Turn broad access categories into concrete tasks.** Childcare, food, loss of work, caregiver capacity, travel, and interpreters should have an owner, next action, and follow-up, rather than only appearing as patient attributes. This extends CJ-16–CJ-19. [S4, S9, S11]
5. **Keep observations distinct from interpretation.** The original “observed problem” column sometimes contains sensible design inferences. Rename it “Source-supported need / design inference,” or label inference per row. The Benetta and Suleika source pages were checked in this pass and support the existing high-level descriptions; the remaining original sources were not all independently re-audited. [A1, A2]

## Scope and limitations

This is public narrative research about methods, organization, resources, expertise, and coordination. No linked Sid clinical-data repository or clinical file was opened. This memo does not reproduce his biological or treatment profile. No named person's records or narrative should be used for training, testing, evaluation, synthetic-case derivation, patient reconstruction, or product fixtures.

Stories below are deliberately varied, not statistically representative. They are retrospective and editorially selected; institutional and fundraising incentives also affect selection. They suggest needs to validate, not prevalence, causality, or proof of software effectiveness. Sid's unusually well-resourced experience is not an operating assumption for ordinary care. The OpenAI article's causal language about AI and survival must not become an Open Intelligence product claim.

## Eight additive workflow observations

| ID | What the public source actually supports | Proposed addition to the existing crosswalk | Source / limitation |
|---|---|---|---|
| W1 | The Sid narrative describes shared context, distributed expertise, summaries of changes, questions for specialists, and repeated expert review. | CJ-03/07/11/17: preserve a reviewed change summary, unanswered questions, named reviewers, and the next action. | S1, 2026-08-06. Vendor-hosted narrative about one exceptional team; no causal attribution or clinical-profile extraction. |
| W2 | Janet Freeman-Daily describes peer-community learning, reaching specialist expertise through a research coordinator, and ongoing local follow-up alongside specialist connections. | CJ-11/17: make referral follow-through and local/specialist responsibilities explicit; reduce reliance on personal networks. | S2, 2025-06-03. Rare-subtype/metastatic adult solid-tumor perspective; peer advice itself is not verified clinical evidence. |
| W3 | Kellie's rural account describes participating in national research through a nearby NCORP hospital. | CJ-08/16: include nearby or shared-care possibilities and actual visit requirements when presenting trial leads. | S3, 2023-09-20. One network example; it does not establish that all trials can be local or remote. |
| W4 | Brian's blood-cancer account describes interrupted work, repeated travel, lodging, bills, childcare, and caregiver strain. | CJ-09/16/17: reassess household and caregiver constraints, with practical assistance tasks and human navigation. | S4, undated; events begin in 2019. Advocacy/fundraising story, not prevalence or current grant eligibility. |
| W5 | Vivian describes difficulty finding peers willing to discuss experiences, while family support and a thorough explanation helped her decision about research participation. | CJ-09/12/18/19: patient-chosen family involvement, plain explanations, question capture, and a human route. | S5, 2024-01-18. Her account must not be generalized to Navajo people or any community. |
| W6 | Emma's pediatric account includes child-life support around procedures and follow-up after treatment. | CJ-09/14/19: developmental and emotional support plus a survivorship handoff; track family questions as well as clinical tasks. | S6, undated. Institution-specific resource model and fundraising selection. |
| W7 | Kathy Oliver describes unfamiliar medical language and difficult navigation as a caregiver; her son died despite years of care. She reports his emphasis on clear explanations and open communication. | CJ-02/12/14/18: support uncertainty, functional goals, and clinician dialogue even when control or cure is not achieved. | S7, 2018-09-07. First-person caregiver account; no inference about which decisions caused the outcome. |
| W8 | Donna M describes counseling for her and her husband during care, continuing counseling after his death, and a bereavement group. | CJ-09/14/19: establish a caregiver-support handoff and patient-approved transitions, including bereavement support where appropriate. | S8, undated. Support-organization testimonial; does not establish treatment efficacy. |

### Authoritative operational support

ACS navigation guidance covers transportation, money, insurance, food, lodging, child/elder care, work/school, interpreters, and supportive-care referrals. It distinguishes clinical and nonclinical navigation. These are useful scope and role boundaries. [S9]

NCI DTC describes provider review for preliminary eligibility, coordinators obtaining necessary information, protocol-specific visits, some possible local procedures, continued local oncology, and limits on travel/cost coverage. These are DTC-specific practices, not universal trial rules. A listing is only a lead; eligibility, a slot, benefit, and access must remain unconfirmed until appropriately reviewed. [S10]

NCI's financial-toxicity summary describes cost, work disruption, and caregiver burden even for insured patients, while acknowledging limits in its underlying evidence. The product response is optional barrier assessment and access to human help, not automated financial or insurance advice. [S11]

## Ten MVP requirements mapped to existing IDs

These are proposed acceptance criteria, not claims of implementation or clinical validation.

| Priority | Existing capabilities | Minimum reviewable behavior |
|---|---|---|
| 1 | CJ-01/02/09 | Record the patient's goals, communication preferences, chosen participants, and each participant's authority; separate caregiver needs from patient preferences. |
| 2 | CJ-03/06/15 | Maintain source-linked events and questions with dates, missingness, contradiction, reviewer, and amendment state; do not convert a request into a result. |
| 3 | CJ-07/12/18 | Produce an editable, plain-language appointment brief with source-backed research questions, evidence limits, changes since review, and unanswered questions. |
| 4 | CJ-17/19 | Give each information request, referral, and support task an owner, next step, review date, and completion evidence; retain a human contact route. |
| 5 | CJ-11/17 | Track a specialist referral from question and information request through acknowledgment and handoff; explicitly record local and specialist responsibilities. |
| 6 | CJ-08/12/16 | Show trial source freshness, location, visit burden, outstanding eligibility questions, and contact status; separate potential lead from site-confirmed screening. |
| 7 | CJ-16/17/19 | Screen optionally for transport, lodging, food, childcare, work, affordability, and language barriers; track resource verification and assistance follow-through. |
| 8 | CJ-18/19 | Provide low-bandwidth, printable, accessible explanations and a navigator route; choose communication support by stated need rather than demographic assumptions. |
| 9 | CJ-09/14 | Support patient-controlled caregiver collaboration and a separately reviewed pediatric/guardian workflow, with emotional/developmental support tasks. |
| 10 | CJ-02/14/19 | Preserve unresolved needs through recurrence, survivorship, supportive care, and caregiver/bereavement transitions. Define the human-care route; do not imply continuous symptom monitoring. |

The original next vertical slice can exercise priorities 2–5 with an independently invented patient, institutions, and specimen record. Add a separate generic access scenario whose information is complete but referral or travel support remains unresolved. This distinguishes technical completeness from successful access without deriving a case from any real patient.

## Later capabilities and evaluation

Later work can add governed authorized-record integration, expert-reviewed literature monitoring, deeper trial prescreening with site confirmation, navigator partnerships, multilingual support, and clinically governed symptom workflows. The last category needs defined staffing, escalation, response expectations, and prospective evaluation. Research participation requires its own consent and governance; public availability is not data-use authorization.

Suggested initial measures are source traceability, question closure, referral acknowledgment, unresolved access barriers, coordination burden, and patient comprehension. These are operational hypotheses, not survival surrogates. Evaluate independently authored generic cases across rural/low-resource, hematology, rare/pediatric, recurrent/metastatic, caregiver, and communication-access workflows; no narratives or named-patient facts become evaluation labels or fixtures.

## Sources

All accessed 2026-11-02. Dates are displayed publication/revision dates; undated does not mean current.

| ID | Source | Date | URL |
|---|---|---|---|
| S1 | OpenAI Academy: public Sid workflow narrative | 2026-08-06 | https://academy.openai.com/public/blogs/sid-sijbrandij-chatgpt-cancer-research |
| S2 | CU Anschutz Cancer Center: From New Patient to Patient Advocate | 2025-06-03 | https://news.cuanschutz.edu/cancer-center/patient-janet-freeman-daily |
| S3 | NCI: Enrolling in a Clinical Trial in Rural America | 2023-09-20 | https://www.cancer.gov/research/participate/stories/clinical-trial-rural-america |
| S4 | Blood Cancer United / formerly LLS: Brian | Undated | https://bloodcancerunited.org/about-us/stories/brian-1 |
| S5 | NCI: Finding a Voice and Surviving Breast Cancer | 2024-01-18 | https://www.cancer.gov/research/participate/stories/finding-her-voice-surviving-breast-cancer |
| S6 | St. Jude: Meet Emma | Undated | https://www.stjude.org/about-st-jude/stories/meet-our-patients/meet-emma.html |
| S7 | NCI: Caregiver Journey Leads to an International Brain Tumor Patient Organization | 2018-09-07 | https://www.cancer.gov/rare-brain-spine-tumor/blog/2018/caregiver-journey |
| S8 | CancerCare: Donna M | Undated | https://www.cancercare.org/voice-of-cancercare/stories/donna-m |
| S9 | ACS: Patient Navigation in Cancer Care | Revised 2025-09-15 | https://www.cancer.org/cancer/patient-navigation.html |
| S10 | NCI DTC: FAQs about Clinical Trials | Updated 2025-06-18 | https://dctd.cancer.gov/programs/dtc/about/about-dtc-clinical-trials |
| S11 | NCI: Financial Toxicity PDQ, patient version | Updated 2024-06-06 | https://www.cancer.gov/about-cancer/managing-care/track-care-costs/financial-toxicity-pdq |
| A1 | CancerCare: Benetta (existing-crosswalk verification) | Undated | https://www.cancercare.org/benetta2026 |
| A2 | Suleika Jaouad: author biography (existing-crosswalk verification) | Undated | https://www.suleikajaouad.com/about |
