# Interoperability matrix

| Interface | Evidence on selected main | Next acceptance condition |
|---|---|---|
| FHIR R4 laboratory | `laboratory_fhir_r4.py`, `laboratory_fhir_store.py` and `laboratory_fhir_routes.py` bound preview/import to an authorized case. Original bundle, resource references, values or explicit absence survive. Migrations 0016/0018 cover persistence and saved questions. | Reconcile #536, test identity and specimen mismatches, amendments and restored originals. Preserve value/unit and absence reason without clinical interpretation. |
| Broader FHIR / mCODE STU4 | #427's separate kernel and synthetic acceptance tests are donor material. No profile-conformance receipt was established on the selected main. | Pin package versions and rights, validate each supported resource/profile, quarantine invalid or ambiguous bindings and retain validator diagnostics. Require round-trip semantics and source provenance before any conformance claim. |
| Terminology | The laboratory subset retains declared LOINC/UCUM values. | Track versions and rights separately for LOINC, SNOMED CT, RxNorm, ICD-10-CM, NCI Thesaurus and HGVS references. Preserve local or unmapped codes and provenance. External validation remains opt-in. |
| Imaging | Restricted DICOM custody and authorized original reads in `images.py` and `dicom_integrity.py`. | Qualify DICOMweb, viewer and external archive boundaries separately. Verify image-report linkage and independent display permission. |
| External applications / export | Existing secure source and report reads support specific synthetic workflows. | SMART/OIDC launch, consent-bound export, receiving-system receipts and round-trip amendment behavior require separate integration tests. |

HAPI FHIR is a candidate external validator. It has no accepted role as clinical persistence. No external clinical system, standards content or vendor service was contacted by this change.
