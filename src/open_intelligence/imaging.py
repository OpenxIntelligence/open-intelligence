"""T1 Imaging comparison: deterministic comparison of imaging studies
(program plan slice D3).

T1 compares a case's imaging studies with each other — consecutive
studies of the same modality, ordered by occurred date — and reports
which reported findings persist, change state, appear, or disappear.
The comparison is a set comparison over the studies' asserted finding
keys and certainties; it is not image analysis, and it never
interprets a measurement: a lesion measurement is a reported finding,
and comparing two measurements' numbers is out of scope here (numeric
series are T2's work, over lab analytes).

A study is a current ``imaging``-kind source version, plus any DICOM
report-only record linked to it (D2). The modality comes from the
linked DICOM record; an imaging source with no linked DICOM record
has modality ``unknown`` and is never paired (it is listed as
``unpaired`` with reason ``modality_unknown``). A DICOM record with no
linked source version is listed as ``unanchored`` and never compared.
Only consecutive studies of the same known modality are paired; a
lone study of a modality is listed as ``unpaired`` with reason
``no_other_study_of_modality``.

Cross-specimen comparisons consult the specimen chain the way D1's
note requires: when a ``validate_chain`` callable is supplied (the D1
``specimen_chain.validate_specimen_chain`` signature), the toolset
consults it for every biological asset anchored to either study's
source version and records any break on the comparison. When no
validator is supplied the comparison records ``chain_not_checked``;
when no asset anchors either study it records ``no_anchored_assets``.
A break never silently blocks the comparison — it is a typed record
on the pair.

This module is report-only by construction: it reads DICOM
report-only records and ledger assertions. No pixel data is read,
stored, or compared anywhere here.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field

from .store import InvalidInput


@dataclass
class ImagingComparison:
    """One case's imaging comparison, read from the ledger.

    ``comparisons`` holds one entry per compared consecutive pair.
    ``unpaired`` lists studies that could not be paired, with a typed
    reason. ``unanchored`` lists DICOM records with no linked source
    version. ``studies`` lists every imaging study considered, ordered
    by occurred date.
    """

    case_id: str
    studies: list[dict] = dc_field(default_factory=list)
    comparisons: list[dict] = dc_field(default_factory=list)
    unpaired: list[dict] = dc_field(default_factory=list)
    unanchored: list[dict] = dc_field(default_factory=list)


def _order_key(study: dict) -> tuple:
    return (study["occurred"], study["documented"], study["received"],
            study["document_id"], study["version"], study["source_version_id"])


def _chain_status(store, case_id, source_a, source_b, validate_chain):
    """Chain status for a comparison between two source versions."""
    if validate_chain is None:
        return {"checked": False, "reason": "no_chain_validator", "breaks": []}
    asset_pks = []
    for source_id in (source_a, source_b):
        rows = store.db.execute(
            "SELECT id FROM biological_assets WHERE anchor_source_version_id=?",
            (source_id,)).fetchall()
        asset_pks.extend(int(row["id"]) for row in rows)
    if not asset_pks:
        return {"checked": False, "reason": "no_anchored_assets", "breaks": []}
    breaks = []
    for asset_pk in sorted(set(asset_pks)):
        validation = validate_chain(store, case_id, asset_pk)
        breaks.extend(dict(b) for b in validation.breaks)
    return {"checked": True, "reason": None, "breaks": breaks}


def compare_imaging(store, case_id: str, *, validate_chain=None) -> ImagingComparison:
    """Compare a case's imaging studies. Reads only; writes nothing."""
    if not isinstance(case_id, str) or not case_id:
        raise InvalidInput("case_id must be a non-empty string")
    if validate_chain is not None and not callable(validate_chain):
        raise InvalidInput("validate_chain must be a callable")
    with store.db:
        store.db.execute("BEGIN")
        case = store.db.execute(
            "SELECT case_id FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if not case:
            raise InvalidInput("Unknown case")
        sources = [dict(row) for row in store.db.execute(
            """SELECT id,document_id,version,event_date,issued_at,received_at,
            specimen_id FROM source_versions
            WHERE case_id=? AND state='current' AND kind='imaging'""",
            (case_id,)).fetchall()]
        assertions = [dict(row) for row in store.db.execute(
            """SELECT a.finding_key,a.certainty,a.quote,a.source_line,
            a.source_version_id FROM assertions a
            JOIN source_versions s ON s.id=a.source_version_id
            WHERE a.case_id=? AND s.state='current' AND s.kind='imaging'""",
            (case_id,)).fetchall()]
        dicom = [dict(row) for row in store.db.execute(
            """SELECT id,study_uid,modality,accession,report_text,
            source_version_id FROM dicom_reports WHERE case_id=?""",
            (case_id,)).fetchall()]
    modality_by_source: dict[int, str] = {}
    unanchored = []
    for record in dicom:
        if record["source_version_id"] is None:
            unanchored.append({
                "dicom_report_id": int(record["id"]),
                "study_uid": record["study_uid"],
                "modality": record["modality"],
                "reason": "unanchored",
            })
        else:
            modality_by_source[int(record["source_version_id"])] = record["modality"]
    findings_by_source: dict[int, dict[str, dict]] = {}
    for item in assertions:
        findings_by_source.setdefault(int(item["source_version_id"]), {})[
            item["finding_key"]] = {
                "certainty": item["certainty"],
                "quote": item["quote"],
                "source_line": int(item["source_line"]),
            }
    studies = []
    for row in sources:
        source_id = int(row["id"])
        studies.append({
            "source_version_id": source_id,
            "document_id": row["document_id"],
            "version": int(row["version"]),
            "occurred": row["event_date"],
            "documented": row["issued_at"],
            "received": row["received_at"],
            "specimen_id": row["specimen_id"],
            "modality": modality_by_source.get(source_id, "unknown"),
            "findings": findings_by_source.get(source_id, {}),
        })
    studies.sort(key=_order_key)
    comparisons = []
    unpaired = []
    by_modality: dict[str, list[dict]] = {}
    for study in studies:
        if study["modality"] == "unknown":
            unpaired.append({**study, "reason": "modality_unknown"})
        else:
            by_modality.setdefault(study["modality"], []).append(study)
    for modality in sorted(by_modality):
        group = by_modality[modality]
        if len(group) == 1:
            unpaired.append({**group[0], "reason": "no_other_study_of_modality"})
            continue
        for earlier, later in zip(group, group[1:]):
            earlier_keys = set(earlier["findings"])
            later_keys = set(later["findings"])
            persisting = []
            changed_state = []
            for key in sorted(earlier_keys & later_keys):
                if earlier["findings"][key]["certainty"] == later["findings"][key]["certainty"]:
                    persisting.append(key)
                else:
                    changed_state.append({
                        "finding_key": key,
                        "from_certainty": earlier["findings"][key]["certainty"],
                        "to_certainty": later["findings"][key]["certainty"],
                    })
            chain = _chain_status(
                store, case_id, earlier["source_version_id"],
                later["source_version_id"], validate_chain)
            comparisons.append({
                "modality": modality,
                "earlier": {k: earlier[k] for k in (
                    "source_version_id", "document_id", "version", "occurred",
                    "specimen_id")},
                "later": {k: later[k] for k in (
                    "source_version_id", "document_id", "version", "occurred",
                    "specimen_id")},
                "persisting": persisting,
                "changed_state": changed_state,
                "added": sorted(later_keys - earlier_keys),
                "removed": sorted(earlier_keys - later_keys),
                "chain": chain,
            })
    comparisons.sort(key=lambda c: (c["modality"], c["earlier"]["occurred"],
                                    c["later"]["occurred"]))
    unpaired.sort(key=lambda s: (s["occurred"], s["document_id"]))
    unanchored.sort(key=lambda r: r["study_uid"])
    return ImagingComparison(case_id=case_id, studies=studies,
                             comparisons=comparisons, unpaired=unpaired,
                             unanchored=unanchored)
