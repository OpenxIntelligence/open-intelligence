# Image authorization through audit persistence

## Purpose and evidence

Extend the existing source-bound image owner on #370, commit
`cc624fe3b258e39a3b833a0053ed9e9f2ced57be`. Its runtime is identical to #361.
The existing image import, index and original-read paths prepare the complete
response and refresh authority before their audit append. A credential/grant
change during that append can therefore precede a successful commit and image
response. The existing transaction-order fixture reproduces this in all three
operations: the expected `PatientRegistryDenied` is not raised.

## Required behavior

Refresh the existing request authority again after successful image audit
persistence and before leaving the owning transaction. A changed action grant,
patient grant, actor, organization, purpose, expired/revoked credential or failed
credential provider must withhold the prepared response and roll back the image
write/link or disclosure receipt. A later authorized retry must succeed normally.
Identical imports still require current authority even though they append no
new image event. Local originals and archive originals use the same final
boundary. Existing response preparation and before-audit checks remain.

This closes the audit-I/O interval. It does not make an external credential file
transactionally atomic with PostgreSQL commit or guarantee revocation after
commit/HTTP delivery. No production identity or clinical approval is implied.

## Approach and boundaries

Add the check in `PostgresSourceImages` only. Reuse the existing callback and
transactions; preserve shared source ownership, identity mappings, image bytes,
permissions, public API, all migration histories and dependency locks.
Changing the shared source receipt protocol would affect unrelated owners;
introducing a new authorization service would duplicate existing contracts.
Neither is needed for this bounded repair.

Use independently authored synthetic fixtures. Preserve the archive transport's
size/deadline/capacity rules and no-fallback behavior. Reuse #370's separate CI
budget repair; do not publish the superseded local budget patch or modify the
active owner branches. Publish a draft child, with no merge or deployment.

## Acceptance

- Observe a failing ordering regression on the unchanged image owner.
- Verify actual PostgreSQL/HTTP denial and rollback after the real audit append,
  including new import, amendment relink, index and original bytes.
- Demonstrate authorized retry, independent operation grants and sanitized errors.
- Preserve existing response-encoding/commit-failure, archive, question/report,
  browser and all six recovery gates at the exact published head.
- Obtain independent review and record actual local/hosted limitations.
