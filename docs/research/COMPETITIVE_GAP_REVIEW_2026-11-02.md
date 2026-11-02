# Open Intelligence — competitive capability and integration appendix

**Checked: 2 November 2026.** Additive research for the existing platform plan; no stack or product replacement. All capabilities below are **vendor-documented positioning**, not independently validated performance, clinical benefit, completeness, or availability at a particular institution. This review independently checked public official documentation; it did not operate products, authenticate to APIs, negotiate rights, or access patient data. An API reference not located here is **unknown**, not evidence that an API does not exist. Public interfaces do not license underlying code, models, knowledgebases or third-party content for incorporation.

## 1. Epic oncology / Beacon

**Purpose/users:** Oncology and hematology teams; adult/pediatric care, chemotherapy protocols and administration, radiation tracking, and staging/registry workflows. **Integration:** Public Epic APIs and sandboxes exist; oncology CarePlan/RequestGroup and radiation interfaces are listed. Actual availability depends on release, organization configuration and authorization. The 30-Oct-2026 open.epic MCP announcement concerns developer documentation, not permission to retrieve clinical data. **Boundary:** Commercial EHR and clinical content; public APIs do not grant access to every chart or protocol. **OI inference:** Connect authorized encounter/treatment sources to cross-institution investigations with explicit source coverage and amendment handling.

Sources: [Specialties](https://www.epic.com/software/specialties/), [API catalog](https://vendorservices.epic.com/openepicapis), [developer access](https://open.epic.com/EpicSupport), [dated updates](https://open.epic.com/). Status: current pages; no deployment tested.

## 2. Oracle Health

**Purpose/users:** Oncology clinicians and operational teams; documented oncology modules cover staging, treatment planning, chemotherapy ordering and cumulative doses. A **23-Sep-2026 announcement** describes a new Oncology EHR with planned timelines, navigator worklists, multimodal context and AI assistants. These are not all established shipped capabilities. **Integration:** Public Millennium FHIR R4/SMART documentation permits authorized access; do not assume identical API coverage for the announced product. **Boundary:** Licensed EHR, content and customer environments. **OI inference:** Benchmark inspectable longitudinal reasoning and human review against these overlapping ambitions; do not claim incumbents lack them.

Sources: [existing oncology offering](https://www.oracle.com/health/service-lines-departments/), [dated announcement](https://www.oracle.com/news/announcement/oracle-to-advance-cancer-care-with-new-oncology-ehr-2026-09-23/), [FHIR R4 documentation](https://docs.oracle.com/en/industries/health/millennium-platform-apis/mfrap/index.html). Status: documentation versus announcement explicitly separated.

## 3. Flatiron Health

**Purpose/users:** Community oncology practices use OncoEMR and related point-of-care tools; life-sciences teams use oncology real-world evidence services. **Integration:** Certification page publishes a FHIR R4/US Core commitment, API documentation link, EHI-export documentation and possible interface/API fees. The linked FHIR portal returned a rendering error in this review; endpoint-level coverage was not inspected. **Boundary:** Subscription EHR and separately governed evidence/data services; export access does not grant unrestricted research reuse. **OI inference:** Import authorized records into patient-portable, versioned investigations; compare workflow burden and evidence traceability rather than asserting unique oncology functionality.

Sources: [oncology products](https://flatiron.com/oncology), [certification/API/export](https://flatiron.com/certification), [evidence users](https://flatiron.com/real-world-evidence/oncology-insights). Status: current official pages; linked portal only partially retrievable.

## 4. Tempus

**Purpose/users:** Oncologists, care teams and researchers; molecular testing, Hub result/order workspace, AI assistance and trial-related workflows. **Integration:** Official connectivity page documents EHR ordering, result delivery and discrete genomic data, listing Epic, Oracle/Cerner, OncoEMR and others. A general self-service developer API specification was not located. **Boundary:** Commercial testing, models and data services; raw-data and secondary-use entitlements require explicit terms. **OI inference:** Preserve multi-vendor assay context and report revisions in one case, distinguishing measured findings, vendor interpretations and model predictions.

Sources: [oncology portfolio](https://www.tempus.com/oncology/), [integration](https://www.tempus.com/solutions/ehr-integration/), [Hub announcement, 27-May-2026](https://www.tempus.com/news/pr/tempus-upgrades-its-smart-physician-platform-hub-with-next-generation-agentic-ai-architecture-to-streamline-clinical-workflows/). Status: live product/connectivity pages plus vendor announcement; no efficacy claims adopted.

## 5. Foundation Medicine

**Purpose/users:** Licensed providers order genomic profiling and related tests; staff track specimens, orders and reports. **Integration:** Current ordering page documents EHR ordering and PDF/discrete result delivery. Epic integration material explicitly conditions discrete genomic results on a Molecular Data Letter Agreement. No general public API specification was located. **Boundary:** Testing service, interpretation content and contractual data delivery; a report is not automatic access to raw sequencing. **OI inference:** Build an authorized report/discrete-result adapter retaining specimen, assay version, original report and amended interpretation.

Sources: [ordering/integration](https://www.foundationmedicine.com/providers/ordering-and-logistics), [Epic data agreement condition](https://www.foundationmedicine.com/resource/epic-form). Status: current pages; commercial availability not independently exercised.

## 6. Caris Life Sciences

**Purpose/users:** Physicians and clinical staff; molecular profiling, including whole-exome/transcriptome capabilities, with order tracking and results through Caris+Portal. **Integration:** Official pages document EHR orders/results, structured genomic delivery through Epic ORA and OncoEMR connectivity. A public self-service API reference was not located. **Boundary:** Commercial assays, interpretation and platform/data access; partner connectivity is not an incorporation license. **OI inference:** Reconcile Caris results with other assays and tissue/time points without conflating different specimens or overwriting historical interpretation.

Sources: [portal/orders](https://www.carislifesciences.com/order/), [EHR integrations](https://www.carislifesciences.com/partners/ehr-integrations/). Status: current vendor pages; institution-specific coverage unknown.

## 7. Guardant Health

**Purpose/users:** Oncology providers and patients; blood/tissue profiling and recurrence/response-monitoring offerings, including Guardant360 and Reveal. **Integration:** Official institutional page documents EMR test ordering/result delivery and customer-specific integrations. Public general-purpose API/raw-data export specifications were not established. **Boundary:** Commercial assays, algorithms and contracted services; clinical indications and interpretation remain test-specific. **OI inference:** Track longitudinal results with assay, specimen, detection/QC limits and treatment timing, preserving uncertainty rather than treating all serial measurements as directly comparable.

Sources: [portfolio purpose](https://www.guardanthealth.com/precision-oncology/our-approach/), [EMR integration](https://guardanthealth.com/precision-oncology/for-institutional-partners/emr-integration-services/). Status: current pages; numerical marketing benefit claims excluded.

## 8. PathAI

**Purpose/users:** Pathologists, laboratories and research organizations; AISight manages digital pathology cases/images and first/third-party AI applications. **Integration:** AISight Link is explicitly described as an open API supporting LIS and algorithm integration; public endpoint specifications and unrestricted access were not established. **Boundary:** Commercial IMS, algorithm licenses, slide/data rights and intended-use qualifications remain separate. “Open API” does not mean open-source software. **OI inference:** Link authorized slides, annotations and qualified analysis outputs to the existing specimen/source/review model; preserve algorithm/version and reviewer identity.

Sources: [current laboratory platform](https://www.pathai.com/ap-lab-solutions), [integration announcement, 19-Nov-2024](https://www.pathai.com/news/pathai-announces-integrations-with-leading-ai-pathology-companies-deep-bio-domore-diagnostics-paige-and-visiopharm-through-its-aisight-image-management-system). Status: current product page corroborates earlier announcement; no API execution.

## 9. Paige — now within Tempus

**Purpose/users:** Pathologists and laboratories; FullFocus viewing, FullFolio case management and digital pathology AI. **Integration:** Paige published API-based scanner/LIS/application integration capabilities; Tempus's current page supports existing-platform or Paige IMS deployment. **Boundary:** Commercial platforms/models; an individual viewer's intended use does not qualify the whole OI product. Tempus explicitly distinguishes Paige Predict probabilities from actual biomarker status or treatment eligibility. **OI inference:** Support interoperable source-linked review, with model predictions separately typed and confirmed measurements preserved.

Sources: [current Tempus offering](https://www.tempus.com/solutions/digital-pathology/), [API integration announcement](https://www.paige.ai/press-releases/paige-introduces-advanced-integration-capabilities-to-the-paige-platform-a-single-solution-that-integrates-the-entire-digital-pathology-ecosystem-and-streamlines-workflows), [acquisition](https://www.tempus.com/news/pr/tempus-announces-the-acquisition-of-paige/). Status: current owner/product context checked; API access terms unresolved.

## 10. QIAGEN Digital Insights

**Purpose/users:** Clinical molecular laboratories and translational researchers; QCI Interpret supports variant interpretation, review and reporting. **Integration:** Public QCI Datastream API Explorer exists; available endpoints depend on license. Official CLC integration instructions require an active QCI subscription with API privileges. **Boundary:** Licensed software and curated interpretation content; subscription/API entitlement does not automatically permit redistribution or training. **OI inference:** Receive contracted interpretation artifacts with provenance, preserve disagreements between knowledge sources, and distinguish laboratory interpretation from patient-specific clinical review.

Sources: [oncology workflow](https://go.qiagen.com/qci-oncology-workshop), [API Explorer](https://apps.ingenuity.com/qcibridge/apiexplorer/), [API privilege requirement](https://resources.qiagenbioinformatics.com/manuals/biomedicalgenomicsanalysis/2000/index.php?manual=QCI_Interpret_Integration.html). Status: official technical documentation; no authenticated API tested.

## 11. SOPHiA GENETICS

**Purpose/users:** Laboratories and researchers; SOPHiA DDM markets genomic, radiomic and multimodal analysis/interpretation. **Integration:** Official CLI documentation explicitly uses the DDM API to automate raw-sequencing upload. Broader EHR/LIMS integration is documented as product positioning; full report-export coverage and API entitlements were not established. **Boundary:** Cloud SaaS, proprietary algorithms and mode-specific intended use; do not infer self-hosting or model-reuse rights. **OI inference:** Register external analysis runs, input/reference versions, QC and outputs in the same longitudinal biological-asset contracts.

Sources: [platform](https://www.sophiagenetics.com/sophia-ddm/), [public CLI/API documentation](https://api-fr.sophiagenetics.com/uploader/cli/), [radiomics research](https://www.sophiagenetics.com/sophia-ddm-for-radiomics/). Status: official public documentation; some product pages have older crawl dates, so current contracting details remain unverified.

## 12. Thyme Care — patient navigation comparator

**Purpose/users:** Patients, oncology practices and payer/risk partners; human navigation, practical support and coordination supported by digital tools. **Integration:** Thyme Care Signal documents EMR-visible enrollment, navigation activity and requests; partner pages describe bidirectional integration. Public developer API specifications were not located. **Boundary:** Contracted care service, staff workflows and platform; not an open software component. **OI inference:** Turn patient goals, missing records and practical barriers into accountable tasks with visible completion, while keeping clinical service responsibilities explicit.

Sources: [Signal](https://www.thymecare.com/thymecaresignal), [oncology partners](https://www.thymecare.com/partners/oncology-partners). Status: current pages; no operational or outcome validation.

## 13. Elicit — scientific literature comparator

**Purpose/users:** Researchers and evidence-review teams; literature discovery, screening, extraction and synthesis. **Integration:** Official API v2 reference documents paper/trial search, research workflows and library/projects, requiring API-enabled subscriptions. The indexed official reference was retrieved; a direct open timed out. **Boundary:** Commercial research service; access to search/extraction does not grant unrestricted publisher-content reuse or clinical authority. **OI inference:** Use only rights-qualified evidence outputs with reproducible searches, exact citations and applicability review; keep patient data exposure separately authorized.

Sources: [API reference](https://docs.elicit.com/), [systematic-review workflow](https://support.elicit.com/en/articles/14759154-systematic-reviews-in-elicit). Status: indexed official API documentation; workflow article dated 16-Sep-2026; no service call.

## Competitive implication

These sources establish substantial overlap in oncology operations, molecular interpretation, multimodal data, AI assistance and integration. They do **not** establish an unserved market or prove that any vendor lacks a unified patient view. OI's testable opportunity is continuity across institutions and vendors: exact original evidence, specimen/time context, durable questions, contradictory interpretations, scoped review, rights-aware reuse, and visible re-review after amendments. Measure preparation effort, source reconstruction, correction handling and patient comprehension against existing workflows. Build distinctive first-party implementation and evaluate authorized integrations; do not copy proprietary software, content or clinical claims.
