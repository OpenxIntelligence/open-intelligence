"""A3 Molecular evidence: variant identities linked to pinned evidence
(program plan slice D3).

A3 links a case's genomic findings to the pinned evidence that bears
on them — computed deterministically, never by a model. A *variant
identity* is a finding key asserted on a current ``molecular``-kind
source version; the ledger, not a key-name guess, decides what is a
molecular finding. The gene token is the finding key itself, except
when the key follows the ``variant-<gene>-<change>`` convention, in
which case the gene is the middle token (for example
``variant-egfr-l858r`` names gene ``egfr``). Gene matching is
case-insensitive on the authored token (ledger keys are lowercase;
ledger evidence keys are uppercase) and token-exact: a gene matches
an evidence key only as a whole hyphen-separated token, never as a
substring.

A link is a *pinned* CIViC/ClinVar link only: the evidence record is
a current ``evidence_versions`` row whose key starts with ``CIVIC-``
or ``CLINVAR-``, whose hyphen-separated tokens contain the gene, and
which has at least one ``evidence_assessments`` row for this case —
the assessment is what makes a version a case-linked evidence record
rather than a stray version. The link carries the assessment's
relation and applicability, so a contradicting or limited record is
never presented as support. A current evidence version naming the
gene but with no assessment is listed under ``unassessed`` — named,
never linked. A current evidence version naming the gene under any
other key prefix is listed under ``unrecognized_prefix`` — named,
never linked, because only the two pinned kinds link.

ClinVar note: ClinVar is not an ``evidence_catalog`` source kind
(only ``civic`` is); the link here is prefix matching on synthetic
ledger evidence keys, not a catalog lookup, and no new catalog kind
is declared in this slice. No external evidence is fetched anywhere;
all evidence is independently authored synthetic ledger text.

Genomic delta tables: per variant key, the ordered points (occurred
date, certainty, source) and the certainty changes between
consecutive points — the same change shape as A2's tracks, restricted
to variant keys. A change is a ledger fact, never a variant
interpretation: this module states no pathogenicity, actionability,
or clinical significance for any variant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field

from .store import InvalidInput

_VARIANT_KEY_RE = re.compile(r"variant-([a-z][a-z0-9_-]*)-([a-z][a-z0-9_-]*)\Z")
_PINNED_PREFIXES = ("CIVIC-", "CLINVAR-")


@dataclass
class MolecularEvidence:
    """One case's molecular evidence, read from the ledger.

    ``variants`` lists every variant identity with its links.
    ``unassessed`` lists current evidence versions naming a variant
    gene with no case assessment. ``unrecognized_prefix`` lists
    current evidence versions naming a variant gene under a prefix
    other than the two pinned kinds. ``variant_deltas`` holds the
    per-variant ordered points and certainty changes.
    """

    case_id: str
    variants: list[dict] = dc_field(default_factory=list)
    unassessed: list[dict] = dc_field(default_factory=list)
    unrecognized_prefix: list[dict] = dc_field(default_factory=list)
    variant_deltas: list[dict] = dc_field(default_factory=list)


def gene_for_key(finding_key: str) -> str:
    """Gene token for a variant finding key.

    ``variant-<gene>-<change>`` yields <gene>; any other key is its
    own gene token. The token is returned as authored (lowercase ledger
    keys); matching uppercases it.
    """
    match = _VARIANT_KEY_RE.fullmatch(finding_key)
    return match.group(1) if match else finding_key


def _tokens(evidence_key: str) -> list[str]:
    return evidence_key.split("-")


def molecular_evidence(store, case_id: str) -> MolecularEvidence:
    """Link a case's variant identities to pinned evidence. Reads only."""
    if not isinstance(case_id, str) or not case_id:
        raise InvalidInput("case_id must be a non-empty string")
    with store.db:
        store.db.execute("BEGIN")
        case = store.db.execute(
            "SELECT case_id FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if not case:
            raise InvalidInput("Unknown case")
        rows = [dict(row) for row in store.db.execute(
            """SELECT a.finding_key,a.certainty,a.quote,a.source_line,
            a.source_version_id,s.event_date,s.issued_at,s.received_at,
            s.document_id,s.version,s.specimen_id
            FROM assertions a JOIN source_versions s
              ON s.id=a.source_version_id
            WHERE a.case_id=? AND s.state='current' AND s.kind='molecular'
            ORDER BY s.event_date,s.issued_at,s.received_at,
              s.document_id,s.version,s.id,a.finding_key""",
            (case_id,)).fetchall()]
        evidence = [dict(row) for row in store.db.execute(
            """SELECT id,evidence_key,version,title,statement,state
            FROM evidence_versions WHERE state='current'""").fetchall()]
        assessments = [dict(row) for row in store.db.execute(
            """SELECT evidence_version_id,relation,applicability
            FROM evidence_assessments WHERE case_id=?""", (case_id,)).fetchall()]
    by_gene: dict[str, list[dict]] = {}
    for row in rows:
        by_gene.setdefault(gene_for_key(row["finding_key"]), []).append(row)
    assessment_by_version: dict[int, list[dict]] = {}
    for item in assessments:
        assessment_by_version.setdefault(
            int(item["evidence_version_id"]), []).append(item)
    variants = []
    unassessed = []
    unrecognized_prefix = []
    variant_deltas = []
    for gene in sorted(by_gene):
        points = by_gene[gene]
        identity = {
            "gene": gene,
            "finding_keys": sorted({row["finding_key"] for row in points}),
            "points": [{
                "finding_key": row["finding_key"],
                "occurred": row["event_date"],
                "documented": row["issued_at"],
                "received": row["received_at"],
                "certainty": row["certainty"],
                "source_version_id": int(row["source_version_id"]),
                "document_id": row["document_id"],
                "version": int(row["version"]),
                "specimen_id": row["specimen_id"],
                "quote": row["quote"],
                "source_line": int(row["source_line"]),
            } for row in points],
            "links": [],
        }
        gene_token = gene.upper()
        for record in sorted(evidence, key=lambda r: r["evidence_key"]):
            if gene_token not in [token.upper() for token in _tokens(record["evidence_key"])]:
                continue
            entry = {
                "gene": gene,
                "evidence_key": record["evidence_key"],
                "version": int(record["version"]),
                "title": record["title"],
                "statement": record["statement"],
                "state": record["state"],
            }
            if not record["evidence_key"].startswith(_PINNED_PREFIXES):
                unrecognized_prefix.append(entry)
                continue
            linked = assessment_by_version.get(int(record["id"]), [])
            if not linked:
                unassessed.append(entry)
                continue
            for assessment in sorted(
                    linked, key=lambda a: (a["relation"], a["applicability"])):
                identity["links"].append({
                    **entry,
                    "relation": assessment["relation"],
                    "applicability": assessment["applicability"],
                })
        identity["links"].sort(key=lambda link: (
            link["evidence_key"], link["relation"], link["applicability"]))
        variants.append(identity)
        changes = []
        for earlier, later in zip(identity["points"], identity["points"][1:]):
            # Only cross-date differences are changes: two certainties on
            # the same occurred date are a conflict, not a delta.
            if (earlier["occurred"] != later["occurred"]
                    and earlier["certainty"] != later["certainty"]):
                changes.append({
                    "finding_key": later["finding_key"],
                    "from_certainty": earlier["certainty"],
                    "to_certainty": later["certainty"],
                    "earlier": earlier,
                    "later": later,
                })
        variant_deltas.append({
            "gene": gene,
            "finding_keys": identity["finding_keys"],
            "points": identity["points"],
            "changes": changes,
        })
    variants.sort(key=lambda v: v["gene"])
    variant_deltas.sort(key=lambda d: d["gene"])
    unassessed.sort(key=lambda e: e["evidence_key"])
    unrecognized_prefix.sort(key=lambda e: e["evidence_key"])
    return MolecularEvidence(
        case_id=case_id, variants=variants, unassessed=unassessed,
        unrecognized_prefix=unrecognized_prefix, variant_deltas=variant_deltas)
