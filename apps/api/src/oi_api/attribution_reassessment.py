"""Compare recorded passages with current statements from the same document histories."""
from open_intelligence.patient_registry import PatientRegistryError
from open_intelligence.store import parse_report


def compare_versions(anchor: dict, original: dict, latest: dict, findings: list[dict]) -> dict:
    """The caller supplies custody-verified originals and the same locked source index."""
    if ((original["source_id"], original["version"], original["sha256"])
            != (anchor["source_id"], anchor["source_version"], anchor["source_sha256"])
            or original["document_id"] != latest["document_id"] or latest["version"] < original["version"]):
        raise PatientRegistryError("Review passage lineage is inconsistent")

    report = parse_report(original["original_text"].encode("utf-8"), allow_oncology=True)
    finding = next((item for item in report.findings if item.line == anchor["source_line"]), None)
    if not finding or not finding.oncology or finding.oncology.role != "metastasis":
        raise PatientRegistryError("Recorded attribution is unavailable")
    recorded = {"source_id": original["source_id"], "source_line": finding.line, "finding_key": finding.key,
                "reported_state": finding.state, "source_statement": finding.quote,
                "clinical_review_state": "not_established",
                "oncology": {"role": finding.oncology.role, "episode_id": finding.oncology.episode_id}}
    # The canonical parser requires each finding key to occur at most once per original.
    current = next((f for f in findings if f["source_id"] == latest["source_id"]
                    and f["finding_key"] == finding.key), None)
    if latest["version"] == original["version"] and (
            latest["source_id"] != original["source_id"] or latest["sha256"] != original["sha256"] or current != recorded):
        raise PatientRegistryError("Recorded and current views of the same version disagree")

    def version(source, statement):
        return {"source_id": source["source_id"], "document_id": source["document_id"],
                "source_version": source["version"], "source_sha256": source["sha256"], "finding": statement}
    return {"recorded": version(original, recorded), "latest": version(latest, current)}
