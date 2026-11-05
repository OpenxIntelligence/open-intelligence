"""Selected original-line provenance from an already validated source observation."""


def selected_observation_anchor(observation: dict) -> dict:
    """Keep untyped originals byte-compatible; preserve explicit unknown episodes."""
    return {
        "source_id": observation["source_id"], "document_id": observation["document_id"],
        "version": observation["document_version"], "sha256": observation["source_sha256"],
        "line": observation["source_line"], "finding_key": observation["finding_key"],
        "reported_state": observation["reported_state"], "statement": observation["source_statement"],
        "kind": observation["source_kind"], "event_date": observation["event_date"],
        "issued_at": observation["issued_at"], "specimen_id": observation["specimen_id"],
        **({"oncology": dict(observation["oncology"])} if "oncology" in observation else {}),
    }


def oncology_lines(source: dict) -> list[str]:
    if "oncology" not in source:
        return []
    context = source["oncology"]
    return [f'Source oncology role: {context["role"]}. episode: {context["episode_id"] or "unassigned"}']
