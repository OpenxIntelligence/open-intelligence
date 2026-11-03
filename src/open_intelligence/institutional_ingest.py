"""Three-institution ingest receipt contract, issue 115 (WS-03).

This is a pure, tested wrapper over the existing CaseStore on main:
it ingests one synthetic report per fictional institution and returns
an immutable-style receipt per institution, with the store's own
source version, fingerprint, duplicate, and quarantine outcomes.

It is NOT a FHIR ingester. FP-01..04 FHIR bundles are not in main,
and this slice does not invent them: it proves the same acceptance
that issue 115 asks for, >=3 fictional institutions, stable source
fingerprints, duplicate idempotency, and mismatched-subject
quarantine, over the existing OI-SYNTHETIC-REPORT/1 format that the
store already validates. A FHIR bundle ingester is a separate step,
not a claim made here.

Rules, fail closed:
- At least three distinct institution labels are required. Fewer
  is denied before any ingest.
- Duplicate institution labels are denied.
- Each delivery must be nonempty bytes; the store validates the
  report format, patient, document, type, dates, and findings.
- A delivery whose patient does not match the case is quarantined
  by the store, never asserted as fact, and the receipt says so.
- A repeated delivery of identical bytes returns the store's
  duplicate result, with the original source id and version, and
  creates no new source version.
- Receipts carry only institution label, result, source id,
  version, fingerprint (SHA-256 of the raw bytes), and quarantine
  id when quarantined. No patient content beyond the case id,
  no treatment, diagnosis, or prognosis content.
"""

from __future__ import annotations

import hashlib


def ingest_institutions(store, case_id, deliveries):
    """Ingest one report per institution and return receipts.

    deliveries is a list of (institution_label, raw_bytes) tuples.
    Returns a dict with case_id, institutions (list of receipts),
    and counts. Raises ValueError on fewer than three institutions
    or duplicate institution labels.
    """
    if not isinstance(deliveries, list) or len(deliveries) < 3:
        raise ValueError("At least three institutions are required")
    labels = [label for label, _ in deliveries]
    if len(set(labels)) != len(labels):
        raise ValueError("Duplicate institution label")
    receipts = []
    for label, raw in deliveries:
        if not isinstance(raw, (bytes, bytearray)) or not raw:
            raise ValueError(f"Empty delivery for {label}")
        outcome = store.import_report(case_id, bytes(raw))
        receipts.append(
            {
                "institution": label,
                "result": outcome.get("result", "ingested"),
                "source_id": outcome.get("source_id"),
                "version": outcome.get("version"),
                "fingerprint": hashlib.sha256(bytes(raw)).hexdigest(),
                "quarantine_id": outcome.get("quarantine_id"),
                "duplicate": outcome.get("duplicate", False) or outcome.get("result") == "duplicate",
            }
        )
    return {
        "case_id": case_id,
        "institutions": receipts,
        "counts": {
            "total": len(receipts),
            "ingested": sum(1 for r in receipts if r["result"] not in ("duplicate", "quarantined")),
            "duplicate": sum(1 for r in receipts if r["result"] == "duplicate"),
            "quarantined": sum(1 for r in receipts if r["result"] == "quarantined"),
            "distinct_fingerprints": len({r["fingerprint"] for r in receipts}),
        },
    }
