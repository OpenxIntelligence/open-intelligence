# Source-event purpose repair: active construction increment

## Goal and ownership

Restore valid synthetic research-source custody on the current shared-foundation
owner without creating an operations delivery obligation or weakening lineage.
Continue OI-006/OI-013 and the existing #565 integration; do not create a second
patient/source/event store. The full PF/PD construction mandate remains open.

Frozen inputs: foundation #565 `acf736082467ef5416f47951e3469090919be045`,
accepted main `16fa42781aa40e3899e36b5b441de8d920fced8e`, and purpose-validation
donor #529 `79960c49f356e7a4259484f5d1523f9bda365887`. The accepted reference
changes merge cleanly; earlier #542 acceptance does not qualify this combined
tree. Episode drafts already exist in #570 and remain their owner's next domain
extension after foundation dependencies are operational.

## Reproduced problem

The #565 API run 42108825811 executed 989 tests and failed in
`test_binding_purpose_must_match_authorized_source_operation`. The research
import did not return a source because the operations-only source outbox tried
to capture a valid research journal event. All seven recovery stages were
therefore skipped. The published #565 0020 migration contains that behavior;
donor #529 corrects it but changes the same historical migration file.

## Implementation steps and contracts

1. Add a populated PostgreSQL regression before implementation. Preserve an
   existing operations outbox/delivery/receipt and its sequence state at 0026;
   demonstrate that a new valid research import fails before the fix. Strengthen
   the existing HTTP test to require the actual import status before its source
   ID, then verify cross-purpose denial.
2. Preserve every published input migration. Add
   `0027_source_event_purpose` after `0026_integrated_core`, with an explicit
   validated source-event binding resolver and replacement capture/guard
   functions adapted from the first-party #529 owner. Research journal lineage
   is validated; only operations events enter the existing outbox. Research
   custody must not disappear merely because it has no operations consumer.
3. Verify malformed research events and forged operations outbox entries still
   fail atomically. Keep existing leases, fencing, actor scopes, acknowledgements,
   revocation and replay rules. Upgrade must preserve all prior rows/receipts;
   downgrade restores previous function semantics without deleting data.
4. Extend existing source recovery with real research-purpose HTTP import,
   original-byte recovery, exact retry, independent operations denial and no
   operations outbox entry. Run all existing seven recovery stages unchanged.
5. Qualify the exact final source against the full API/PostgreSQL, reference,
   web/build/rights/browser and recovery workflows. Preserve failed runs and
   distinguish local environment skips/errors from hosted acceptance.

## Deliberate compatibility boundary

This increment supports fresh databases and databases already at published
0026. An older pre-0020 database containing research journal history cannot
cross the original published 0020 backfill automatically. Keep that upgrade
held with atomic rollback and preserved rows. Do not rewrite/intercept historical
SQL, move/delete journal records or weaken a trigger to conceal this limitation.
A separately reviewed legacy adoption path remains necessary.

No new dependency, clinical interpretation, external model egress, production
deployment or real patient data. The current scope is synthetic engineering.
Final source IDs, commands and outcomes are recorded in the existing integration
PR and implementation status after the tests execute.
