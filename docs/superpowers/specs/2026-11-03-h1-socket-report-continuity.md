# H1 bounded socket/report continuity

## Intent and ownership
Connect #351's verified transport/capacity to #358's existing image/question/task/
citation/authored-report owner. A requested original must traverse the bounded
socket client without losing the existing final-authority or immutable-history
checks. Independently authored fictional inputs only; no clinical release.

Base: #358 `ee43e8c5c358162a3f3b330665b60f9cb1cc83e9`.
Selective transport donor: #351 `f864dbaf7055025b73a7bc86f4c7f620a29f45a7`.

## Approaches and decision
Use the exact donor runtime and five supporting test/fixture modules, preserving
all newer base owners. Do not merge the older transport branch wholesale: that
would risk replacing later report/source boundaries. A new production gateway
is a different security/deployment decision, not necessary for this composition.
This is a reversible engineering choice under the existing continuation mandate.

## Behavior and acceptance
Keep the optional `create_app(..., image_archive=...)` injection and default local
custody unchanged. Preserve the 2 MiB transport object limit, total deadline,
peer-UID check, non-waiting capacity (default four, exact integers 1..16), and no
local fallback. No credential forwarding or public archive configuration.

Exercise real Unix-socket reads with a populated question, return, task, citation
and human-authored report. Prove exact original/report identities through source
amendment/relink, evidence withdrawal, overload and revocation. Failed transport
must create neither a successful-read receipt nor changed business history.

Extend the existing image recovery acceptance's archive phase through a test-only
Unix socket responder backed by its existing bounded file fixture. Keep its
manifest, read-only originals, synthetic invocation trace, restored HTTP checks,
full-owner/sequence/catalog comparisons and all six recovery gates. The fixture
must close its listener on application shutdown and start cleanly after restart.
It is absent from the application image and has no environment activation.

## Non-goals and limits
No new patient/source/evidence ledger, schema, permission, dependency or UI. No
live PACS, independent service-UID deployment, private-network isolation, raw-PACS
bypass denial, external-archive backup or general DICOMweb qualification. The
acceptance responder is same-process/same-UID test infrastructure, not a gateway.
Production identity/consent, broader stack integration and independent review
remain separate gates. Actual execution must distinguish local, hosted and pending.
