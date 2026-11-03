# Exact content-class rights gate — independently reviewable prerequisite

This narrow draft extends PR #140's existing pure rights module. It adds an optional, validated `content_item` argument to `excerpt_mode` and `check_link_content`, supporting `full_text`, `abstract` and `api_output`. Store/display permission is required for exactly that selected class. A grant for curated API output does not authorize a linked publication or abstract. Metadata, model-use and redistribution rights remain separate.

Omitting the argument retains the existing full-text behavior. Explicit null, nonstrings and unsupported categories are rejected. The historical availability label `mode=full` means that the selected content is available; it does not grant article rights. No network fetch, database migration, new dependency, patient data, model execution, clinician authority or license clearance is introduced.

## Ownership and the larger integration

This is the shared gate prerequisite, NOT the entire report feature. The accompanying local `Open_Intelligence_Content_Scoped_Reports` development build includes explicit immutable broker-link classification, upgrade tests, typed input receipts/fingerprints, current-rights read/export checks, report UI labels and local HTTP integration. Those caller/schema/report changes are not in this narrow PR and require separate reconciliation with the source owners. PR #158 owns durable review/reassessment; this gate creates no parallel review or patient ledger.

## Verification and limits

The five new gate tests fail on the unchanged upstream implementation because its optional content-class interface is absent. They pass with this extension. They cover every pair of supported classes, legacy behavior, invalid types, independent metadata/model/export permissions, unknown/denied cells and revoked/superseded state. Inputs are invented software fixtures, not actual publisher permission receipts.

Use `PYTHONPATH=src:. python -m unittest discover -s tests -p test_rights_content_types.py -v`. The existing read-only exact-head CI workflow now also targets this child PR's parent branch. Its full application and existing browser suites are preserved; inspect their actual result for the exact head before accepting. No merge, deployment or clinical-readiness claim follows from green engineering tests.
